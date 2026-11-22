"""THE ORDER-FLOW RECORDER - Bitget public websocket `books` + `trade`, raw frames to gzip (Module 5, 2026-10-30).

PUBLIC DATA ONLY. No API keys, no account, no orders: it can only listen. Nothing in this package can trade.

WHAT IT DOES
    one websocket connection subscribes `books` (the diff-stream order book) and `trade` (every print, with the taker side) for the ten registered pairs;
    every frame is stored RAW with the local receive time (orderflow/store.py); a Book per pair (orderflow/book.py) follows the `pseq` chain only to DETECT a missed
    message; a gap is logged and that pair's `books` subscription is renewed (unsubscribe, subscribe) so a fresh snapshot arrives; a ping every 20 s keeps the link alive;
    30 s of silence makes it reconnect with exponential backoff; every `--audit-every` seconds a SECOND, short-lived connection fetches a fresh `books` snapshot of each
    pair and stores it under audit/. `seq` is global across connections, so orderflow/verify.py compares that snapshot with the main stream's rebuilt book AT THE SAME seq:
    an exact, level-for-level audit.

    python -m orderflow.recorder --out strategy_analysis/data/orderflow_trial --minutes 10        a trial
    python -m orderflow.recorder --out strategy_analysis/data/orderflow                           the official record (runs until stopped; Ctrl+C)

REGISTERED BEFORE THE FIRST TRIAL (2026-10-30; the 50-second probe had already shown: fields asks / bids / ts / seq / pseq, no checksum, 200 levels a side (BTC 500),
updates about every 100 ms, pseq chain unbroken over 911 updates)
    R1  Over a 10-minute trial of all ten pairs the pseq chain breaks at most twice in total (probe: 0 of 911).
    R2  BTC's compressed recording is the largest of the ten, more than 40% of the total; the ten pairs together compress to between 0.3 and 1.5 GB per day.
    R3  Local receive time minus the server timestamp has a median between 100 and 250 ms on every pair and a 90th percentile under 400 ms.
    R4  At least 90% of the REST audits match the rebuilt book's top 5 levels within +-250 ms of server time.
        RESULT (first trial, 40 audits): WRONG - 12 of 40 (30%). Diagnosis: the REST book is not tied to the stream's state (hot pairs never matched at ANY offset in +-4 s;
        quiet pairs matched), not a flaw in the rebuild: a probe with a second websocket connection found that its fresh snapshot's `seq` exists in the main stream in 9 of 9
        cases (SOL, XRP, BTC) and the rebuilt book at that seq was identical level for level. The REST audit was therefore replaced by the seq-aligned snapshot audit above.
    R5  The deliberate renewal of one pair's `books` subscription yields a new snapshot within 2 s and the chain then continues unbroken.
    R6  The rebuilt book's level count stays within +-30% of the snapshot depth (the server removes levels that leave the recorded window).
    R7  The three least liquid pairs (SHIB, DOT, WLD) show uneven update gaps (90th percentile at least 1.5x the median), BTC and XRP a steady ~100 ms.

RESULTS OF THE TRIALS (2026-10-30, 13:57-14:47 UTC; logs/orderflow_trial*_verify.txt):
    R1 right: 0 chain breaks in 63,617 updates (10 minutes, ten pairs), and 0 in every later trial.   R2 right: BTC 48% of the bytes; 1.33-1.38 GB a day (busy hours).
    R3 right: receive lag median 118-154 ms, 90th percentile 141-235 ms.   R4 WRONG (30%), see above - replaced by the seq-aligned snapshot audit: 69 of 69 exact.
    R5 right: 600 ms to the new snapshot, no gap afterwards.   R6 right: exactly 400 levels (BTC 1,000) always.   R7 right: DOT / SHIB 2.2x, WLD 1.7x; BTC, XRP 99-101 ms.
    Found on the way: a malformed update with a valid chain position half-applied (fixed: parse first, mutate after; test_bad_frames_never_stop_the_recording).

THE OFFICIAL RECORD starts only when the user says so: the registry (backtest/order_flow_registry.py) counts its first 10 days as TUNE days, so trial data goes to a
separate folder and is never counted.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

import orjson
import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderflow.book import Book  # noqa: E402
from orderflow.store import EventLog, RawWriter  # noqa: E402

WS_URL = "wss://ws.bitget.com/v2/ws/public"
INST = "USDT-FUTURES"
PAIRS = ["XRPUSDT", "SUIUSDT", "LINKUSDT", "WLDUSDT", "DOGEUSDT", "SHIBUSDT", "ADAUSDT", "DOTUSDT", "BTCUSDT", "SOLUSDT"]
SILENCE_S, PING_S, STATS_S = 30.0, 20.0, 60.0


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}  {msg}", flush=True)


def rss_mb() -> float:
    """This process's resident memory in MB (NaN if the platform will not say). For monitoring an unattended run: a recorder that leaks shows it here, minute by minute."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            k32, ps = ctypes.windll.kernel32, ctypes.windll.psapi
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(pmc)
            ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            return pmc.WorkingSetSize / 1e6
        import os
        with open("/proc/self/statm", encoding="ascii") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6
    except Exception:
        return float("nan")


async def fetch_snapshots(pairs, url: str = None, timeout: float = 8.0) -> list:
    """Fresh `books` snapshots, one pair at a time, over a SECOND short-lived connection. Returns [(pair, recv_ns, raw or None)]. A timeout gives raw = None."""
    out = []
    async with websockets.connect(url or WS_URL, max_size=None, ping_interval=None, open_timeout=15, close_timeout=3) as ws:
        for p in pairs:
            arg = [{"instType": INST, "channel": "books", "instId": p}]
            await ws.send(json.dumps({"op": "subscribe", "args": arg}))
            got = None
            try:
                while got is None:
                    raw = await asyncio.wait_for(ws.recv(), timeout)
                    recv_ns = time.time_ns()
                    if raw == "pong" or '"event"' in raw[:30]:
                        continue
                    m = orjson.loads(raw)
                    if m.get("action") == "snapshot" and m["arg"]["instId"] == p:                  # later updates of an earlier pair are skipped
                        got = (p, recv_ns, raw)
            except asyncio.TimeoutError:
                got = (p, time.time_ns(), None)
            out.append(got)
            await ws.send(json.dumps({"op": "unsubscribe", "args": arg}))
    return out


class Recorder:
    def __init__(self, pairs, out, audit_every_s: float = 600.0, flush_every_s: float = 5.0, resub_test_after_s: float = 0.0):
        self.pairs, self.out = list(pairs), Path(out)
        self.books = {p: Book() for p in self.pairs}
        self.writers = {p: RawWriter(self.out / "raw", p, flush_every_s=flush_every_s, on_rotate=self._checkpointer(p)) for p in self.pairs}
        self.events = EventLog(self.out / "events.jsonl")
        self.stats = {p: dict(books=0, trades=0, gaps=0, snapshots=0, bytes=0) for p in self.pairs}
        self.audit_every_s, self.resub_test_after_s = audit_every_s, resub_test_after_s
        self.audit_writers = {p: RawWriter(self.out / "audit", p, flush_every_s=flush_every_s) for p in self.pairs}
        self.ws_url = WS_URL
        self.last_rx = time.monotonic()
        self.pongs = 0
        self.resubs = 0

    def _checkpointer(self, pair: str):
        """Called when a pair's hourly file is opened: the book as it stands (if it is ready) becomes the file's first line, so the hour can be read on its own."""
        def cb(recv_ns: int):
            b = self.books[pair]
            return b.checkpoint_message(pair) if b.ready else None
        return cb

    # ------------------------------------------------------------------ one frame in, a list of actions out (pure enough to test offline)
    def handle(self, raw, recv_ns: int) -> list:
        self.last_rx = time.monotonic()
        if raw == "pong":
            self.pongs += 1
            return []
        try:
            m = orjson.loads(raw)
        except ValueError:
            self.events.write("bad_json", head=str(raw)[:80])
            return []
        ev = m.get("event")
        if ev:
            if ev == "error":
                self.events.write("ws_error", message=m)
            return []
        arg = m.get("arg") or {}
        pair, ch = arg.get("instId"), arg.get("channel")
        if pair not in self.books:
            return []
        self.writers[pair].write(recv_ns, raw)                                       # RAW FIRST: whatever happens next, the frame is on disk
        st = self.stats[pair]
        st["bytes"] += len(raw)
        actions: list = []
        try:
            if ch == "books":
                d = m["data"][0]
                last_seq = self.books[pair].seq
                res = self.books[pair].apply(m["action"], d)
                st["books"] += 1
                if res == "snapshot":
                    st["snapshots"] += 1
                    self.events.write("snapshot", pair=pair, seq=d.get("seq"), depth=list(self.books[pair].snapshot_depth))
                elif res == "gap":
                    st["gaps"] += 1
                    self.events.write("gap", pair=pair, last_seq=last_seq, pseq=d.get("pseq"), seq=d.get("seq"))
                    actions.append(("resub", pair))
            elif ch == "trade":
                st["trades"] += len(m["data"])
        except Exception as e:                                                       # a malformed message must not stop the recording
            self.events.write("handler_error", pair=pair, error=f"{type(e).__name__}: {str(e)[:100]}")
            if ch == "books" and self.books[pair].ready:
                self.books[pair].ready = False                                       # a book that skipped a message cannot be trusted: ask for a new snapshot
                actions.append(("resub", pair))
        return actions

    def sub_args(self, channels=("books", "trade"), pairs=None) -> list:
        return [{"instType": INST, "channel": c, "instId": p} for p in (pairs or self.pairs) for c in channels]

    # ------------------------------------------------------------------ the connection
    async def _ping(self, ws):
        while True:
            await asyncio.sleep(PING_S)
            await ws.send("ping")

    async def _resub(self, ws, pair: str):
        self.resubs += 1
        self.events.write("resub", pair=pair)
        arg = self.sub_args(("books",), [pair])
        await ws.send(json.dumps({"op": "unsubscribe", "args": arg}))
        await asyncio.sleep(0.3)
        self.books[pair].ready = False
        await ws.send(json.dumps({"op": "subscribe", "args": arg}))

    async def _selftest(self, ws):
        await asyncio.sleep(self.resub_test_after_s)
        self.events.write("selftest_resub", pair=self.pairs[-1])
        await self._resub(ws, self.pairs[-1])

    async def _stats_loop(self):
        prev = {p: dict(s) for p, s in self.stats.items()}
        cpu0, wall0 = time.process_time(), time.monotonic()
        while True:
            await asyncio.sleep(STATS_S)
            row = {}
            for p, s in self.stats.items():
                row[p] = {k: s[k] - prev[p][k] for k in s}
            prev = {p: dict(s) for p, s in self.stats.items()}
            disk = sum(w.disk_bytes() for w in self.writers.values())
            cpu1, wall1 = time.process_time(), time.monotonic()
            cpu_pct, cpu0, wall0 = 100 * (cpu1 - cpu0) / max(wall1 - wall0, 1e-9), cpu1, wall1
            mem = rss_mb()
            self.events.write("stats", per_minute=row, disk_bytes=disk, cpu_pct=round(cpu_pct, 1), rss_mb=round(mem, 1))
            log(f"{sum(r['books'] for r in row.values())} book msgs, {sum(r['trades'] for r in row.values())} trades, "
                f"{sum(r['gaps'] for r in row.values())} gaps this minute; disk {disk / 1e6:.1f} MB; cpu {cpu_pct:.1f}% of one core; memory {mem:.0f} MB; pongs {self.pongs}; resubs {self.resubs}")

    async def audit_round(self):
        """One audit round: a fresh snapshot of every pair from a second connection, stored under audit/. Never raises (an audit must not take the recorder down)."""
        try:
            for pair, recv_ns, raw in await fetch_snapshots(self.pairs, self.ws_url):
                if raw is None:
                    self.events.write("audit_timeout", pair=pair)
                else:
                    self.audit_writers[pair].write(recv_ns, raw)
            self.events.write("audit_round")
        except Exception as e:
            self.events.write("audit_error", error=f"{type(e).__name__}: {str(e)[:100]}")

    async def _audit_loop(self):
        while True:
            await asyncio.sleep(self.audit_every_s)
            await self.audit_round()

    async def session(self, deadline) -> str:
        for b in self.books.values():
            b.ready = False                                                          # every connection starts from a fresh snapshot
        async with websockets.connect(WS_URL, max_size=None, ping_interval=None, open_timeout=15, close_timeout=5) as ws:
            self.events.write("connect")
            log("connected")
            await ws.send(json.dumps({"op": "subscribe", "args": self.sub_args()}))
            self.last_rx = time.monotonic()
            aux = [asyncio.create_task(self._ping(ws)), asyncio.create_task(self._stats_loop()), asyncio.create_task(self._audit_loop())]
            if self.resub_test_after_s:
                aux.append(asyncio.create_task(self._selftest(ws)))
            try:
                while True:
                    if deadline is not None and time.monotonic() >= deadline:
                        return "done"
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        if time.monotonic() - self.last_rx > SILENCE_S:
                            raise ConnectionError(f"no frame for {SILENCE_S:.0f} s")
                        continue
                    for act in self.handle(raw, time.time_ns()):
                        if act[0] == "resub":
                            await self._resub(ws, act[1])
            finally:
                for t in aux:
                    t.cancel()
                await asyncio.gather(*aux, return_exceptions=True)

    async def run(self, minutes: float = None):
        deadline = time.monotonic() + minutes * 60 if minutes else None
        backoff = 1.0
        try:
            while True:
                t0 = time.monotonic()
                try:
                    if await self.session(deadline) == "done":
                        break
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.events.write("disconnect", error=f"{type(e).__name__}: {str(e)[:120]}")
                    log(f"disconnected: {type(e).__name__}: {str(e)[:100]} - retrying in {backoff:.0f} s")
                if deadline is not None and time.monotonic() >= deadline:
                    break
                backoff = 1.0 if time.monotonic() - t0 > 60 else min(backoff * 2, 30.0)
                await asyncio.sleep(backoff)
        finally:
            for w in list(self.writers.values()) + list(self.audit_writers.values()):
                w.close()
            self.events.write("stop")
            log("stopped; files closed")


def single_instance(out: Path) -> socket.socket:
    """One recorder per output folder: hold a local TCP port derived from the folder's name. The OS frees it when the process dies, however it dies."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port = 47000 + zlib.crc32(str(Path(out).resolve()).encode()) % 1000
    try:
        s.bind(("127.0.0.1", port))
    except OSError:
        raise SystemExit(f"another recorder already writes to {out} (port {port} is held)")
    return s


def main():
    ap = argparse.ArgumentParser(description="Record Bitget public order-book and trade frames (no keys, no orders).")
    ap.add_argument("--out", required=True, help="output folder (a trial folder, or the official one)")
    ap.add_argument("--pairs", default=",".join(PAIRS))
    ap.add_argument("--minutes", type=float, default=None, help="stop after this many minutes (default: run until Ctrl+C)")
    ap.add_argument("--audit-every", type=float, default=600.0)
    ap.add_argument("--selftest-resub-after", type=float, default=0.0, help="seconds after connecting to renew one pair's books subscription on purpose")
    a = ap.parse_args()
    lock = single_instance(Path(a.out))
    rec = Recorder([p.strip() for p in a.pairs.split(",") if p.strip()], a.out, a.audit_every, resub_test_after_s=a.selftest_resub_after)
    try:
        asyncio.run(rec.run(a.minutes))
    except KeyboardInterrupt:
        pass
    finally:
        lock.close()


if __name__ == "__main__":
    main()
