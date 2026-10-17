"""THE DASHBOARD'S FEED: one compact snapshot of every paper book, pushed to Upstash every minute (2026-10-17, docs/24)

Runs on the VM (systemd timer, deploy/forexbot-dash.*). READ-ONLY towards the bots: it reads their state, trade and log
files, asks Binance for public prices (one request) and systemd for service health, builds one JSON snapshot and writes
it to an Upstash Redis key the Vercel page reads (dashboard/). Standard library only - the VM has ~200 MB to spare.
    final       THE FINAL MACHINE (combo_bot --final, dry): equity, peak, fall, P&L by book, open positions by book
                (trend / daily / capit2 / news / ndx), the netted ledger valued at live prices, gross leverage vs the cap,
                the news book's recent headlines, daily marks, the last orders, closed trades and log lines
    others      combo paper (machine v2), crash-bid ledgers (Bitget / Binance), pair paper (cash and positions)
    health      each service's state and restart count, memory, disk, the final bot's last log time
KEYS        forexbot:snapshot (the JSON), forexbot:eq (a list of "unix,equity" for the last 2 days, one a minute)
SECRETS     UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN from the environment only (the service's EnvironmentFile,
            readable by root) - never in the repo, a log or an argument.

    python dashboard_push.py --print     build the snapshot and print it (no network push)
    python dashboard_push.py             build and push
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
FINAL = LOGS / "combo_bot_dry_final"
SERVICES = ["combo-bot-final", "combo-paper", "blend-paper", "wick-paper", "combo-bot-demo", "pair-paper"]
START_EQUITY = 300.0
GROSS_CAP = 14.5
KEY, EQ_KEY, EQ_KEEP = "forexbot:snapshot", "forexbot:eq", 2880


def jload(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def tail_csv(p: Path, n: int) -> list:
    try:
        with p.open(newline="") as f:
            rows = list(csv.DictReader(f))
        return rows[-n:]
    except Exception:
        return []


def tail_lines(p: Path, n: int) -> list:
    try:
        with p.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 40_000))
            return f.read().decode("utf-8", "replace").splitlines()[-n:]
    except Exception:
        return []


def binance_prices() -> dict:
    try:
        with urllib.request.urlopen("https://fapi.binance.com/fapi/v1/ticker/price", timeout=20) as r:
            return {x["symbol"]: float(x["price"]) for x in json.loads(r.read().decode())}
    except Exception:
        return {}


def bsym(venue_sym: str) -> str:
    """'AKE/USDT:USDT' -> 'AKEUSDT' (the price feed's key)."""
    return venue_sym.split("/")[0] + "USDT"


def final_section(prices: dict) -> dict:
    st = jload(FINAL / "combo_state.json", {}) or {}
    eq = float(st.get("equity", START_EQUITY))
    peak = float(st.get("peak", eq))
    fin = st.get("fin", {}) or {}
    led = (st.get("exec", {}) or {}).get("virtual_pos", {}) or {}
    pos, gross = [], 0.0
    for s, q in led.items():
        px = prices.get(bsym(s)) or prices.get(bsym(s).replace("1000", ""), 0.0)
        val = q * px
        gross += abs(val)
        pos.append(dict(symbol=s.split("/")[0], qty=q, price=px, value=round(val, 2)))
    pos.sort(key=lambda r: -abs(r["value"]))
    trend = [dict(key=k, side=v.get("side"), entry=v.get("entry"), stop=v.get("stop"), units=v.get("units"),
                  notional=round(v.get("notional", 0.0) * v.get("units", 1), 2), since=v.get("entry_bar"))
             for k, v in (st.get("trend", {}) or {}).get("open", {}).items()]
    books = {}
    for b in ("daily", "capit2"):
        books[b] = [dict(symbol=s, entry=p.get("entry"), qty=p.get("qty"), since_ms=p.get("t_ms"),
                         now=prices.get(s), ret=(prices.get(s) / p["entry"] - 1) if prices.get(s) and p.get("entry") else None)
                    for s, p in (fin.get(b, {}) or {}).get("open", {}).items()]
    news = fin.get("news", {}) or {}
    books["news"] = [dict(symbol=p["coin"], etype=p.get("etype"), entry=p.get("e_coin"), since_ms=p.get("t_ms"),
                          now=prices.get(p["coin"]), coin_move=(prices.get(p["coin"]) / p["e_coin"] - 1)
                          if prices.get(p["coin"]) else None) for p in (news.get("open", {}) or {}).values()]
    nd = (fin.get("ndx", {}) or {}).get("open")
    books["ndx"] = [dict(symbol="QQQUSDT", entry=nd.get("entry"), days=nd.get("days"), now=prices.get("QQQUSDT"),
                         ret=(prices.get("QQQUSDT") / nd["entry"] - 1) if prices.get("QQQUSDT") else None)] if nd else []
    closed = tail_csv(FINAL / "combo_final_trades.csv", 40) + \
        [dict(ts=r.get("t1") or r.get("ts", ""), book="trend", symbol=r.get("key", r.get("coin", "")), ret=r.get("R", ""),
              pnl=r.get("pnl", ""), why=r.get("why", "")) for r in tail_csv(FINAL / "trades_combo_trend.csv", 40)]
    closed.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return dict(
        equity=round(eq, 2), start=START_EQUITY, peak=round(peak, 2), fall=round(1 - eq / peak, 4) if peak else 0.0,
        max_dd=st.get("max_dd"), started=st.get("started"), cum={k: round(v, 2) for k, v in (st.get("cum") or {}).items()},
        gross=round(gross, 2), leverage=round(gross / eq, 2) if eq else None, cap=GROSS_CAP,
        positions=pos[:60], trend_open=trend, books=books,
        pending=dict(capit2=len((fin.get("capit2", {}) or {}).get("pending", {})), news=len(news.get("pending", {}) or {})),
        news_recent=list(reversed((news.get("recent") or [])[-30:])),
        news_stats=dict(taken=news.get("taken", 0), dropped=news.get("dropped", 0), seen=news.get("seen", 0),
                        watching_from=news.get("last_id")),
        marks=tail_csv(FINAL / "combo_marks.csv", 120), orders=list(reversed(tail_csv(FINAL / "combo_exec.csv", 40))),
        closed=closed[:40], log=tail_lines(FINAL / "combo_paper.log", 40))


def others_section() -> dict:
    out = {}
    c = jload(LOGS / "combo_state.json")
    if c:
        out["combo_paper"] = dict(name="Combo paper (machine v2)", equity=round(c.get("equity", 0.0), 2), start=221.0,
                                  started=c.get("started"), max_dd=c.get("max_dd"))
    w = jload(LOGS / "wickp_state.json")
    if w:
        for venue, l in (w.get("led") or {}).items():
            out[f"wick_{venue}"] = dict(name=f"Crash bids ({venue})", equity=round(l.get("equity", 0.0), 2), start=300.0,
                                        fills=l.get("fills"), started=w.get("started"))
    p = jload(LOGS / "pair_paper_state.json")
    if p:
        out["pair"] = dict(name="Pair paper (PKR book, cash in $)", cash={k: round(v, 2) for k, v in (p.get("cash") or {}).items()},
                           open={k: len(v) for k, v in (p.get("open") or {}).items()}, started=p.get("started"))
    return out


def health_section() -> dict:
    svc = {}
    for s in SERVICES:
        try:
            a = subprocess.run(["systemctl", "is-active", s], capture_output=True, text=True, timeout=10).stdout.strip()
            n = subprocess.run(["systemctl", "show", s, "-p", "NRestarts", "--value"], capture_output=True, text=True,
                               timeout=10).stdout.strip()
            svc[s] = dict(active=a, restarts=int(n) if n.isdigit() else None)
        except Exception:
            svc[s] = dict(active="unknown", restarts=None)
    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            if k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
                mem[k] = int(v.split()[0]) // 1024
    except Exception:
        pass
    du = shutil.disk_usage(str(ROOT))
    last = tail_lines(FINAL / "combo_paper.log", 1)
    return dict(services=svc, memory_mb=mem, disk_used_pct=round(du.used / du.total * 100, 1),
                final_last_log=last[0][:19] if last else None)


def build() -> dict:
    prices = binance_prices()
    return dict(generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), final=final_section(prices),
                others=others_section(), health=health_section(), btc=prices.get("BTCUSDT"))


def push(snap: dict):
    url, tok = os.environ.get("UPSTASH_REDIS_REST_URL"), os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not tok:
        sys.exit("UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN are not set in this environment")
    eq_point = f"{int(time.time())},{snap['final']['equity']}"
    body = json.dumps([["SET", KEY, json.dumps(snap, separators=(",", ":"))],
                       ["LPUSH", EQ_KEY, eq_point], ["LTRIM", EQ_KEY, "0", str(EQ_KEEP - 1)]]).encode()
    req = urllib.request.Request(url.rstrip("/") + "/pipeline", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        res = json.loads(r.read().decode())
    bad = [x for x in res if isinstance(x, dict) and x.get("error")]
    if bad:
        sys.exit(f"Upstash refused: {bad[0]['error'][:120]}")


def main():
    snap = build()
    if "--print" in sys.argv:
        print(json.dumps(snap, indent=1))
        return
    push(snap)


if __name__ == "__main__":
    main()
