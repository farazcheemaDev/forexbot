"""orderflow/book.py, store.py and the recorder's frame handler, offline, on hand-built messages.
Run as a script: python tests/test_orderflow_core.py"""
import asyncio
import gzip
import json
import math
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import order_flow_registry as reg  # noqa: E402
from orderflow import recorder as rc  # noqa: E402
from orderflow import store  # noqa: E402
from orderflow import verify  # noqa: E402
from orderflow.book import Book  # noqa: E402


def snap(seq, ts, bids, asks):
    return dict(bids=[[str(p), str(s)] for p, s in bids], asks=[[str(p), str(s)] for p, s in asks], ts=str(ts), seq=seq, pseq=0)


def upd(seq, pseq, ts, bids=(), asks=()):
    return dict(bids=[[str(p), str(s)] for p, s in bids], asks=[[str(p), str(s)] for p, s in asks], ts=str(ts), seq=seq, pseq=pseq)


def frame(action, pair, channel, data):
    return json.dumps({"action": action, "arg": {"instType": "USDT-FUTURES", "channel": channel, "instId": pair}, "data": data, "ts": 1})


def base_book():
    b = Book()
    b.apply("snapshot", snap(10, 1000, [(100.00, 600), (99.99, 900)], [(100.01, 500), (100.02, 800)]))
    return b


# ------------------------------------------------------------------ the book

def test_updates_replace_and_delete_levels_and_follow_the_pseq_chain():
    b = base_book()
    assert b.ready and b.snapshot_depth == (2, 2) and b.seq == 10
    assert b.apply("update", upd(11, 10, 1100, bids=[(100.00, 650)], asks=[(100.01, 0), (100.03, 300)])) == "ok"
    assert b.bids[100.00] == 650 and 100.01 not in b.asks and b.asks[100.03] == 300 and b.seq == 11 and b.ts == 1100
    assert b.apply("update", upd(12, 11, 1200, bids=[(99.99, 0)])) == "ok" and 99.99 not in b.bids


def test_a_broken_chain_makes_the_book_unready_until_a_new_snapshot():
    b = base_book()
    assert b.apply("update", upd(13, 12, 1100, bids=[(100.00, 1)])) == "gap"                    # pseq 12 is not the last seq (10): a message was missed
    assert not b.ready and b.best() is None and b.levels("bid", 2) == [] and math.isnan(b.mid())
    assert b.bids[100.00] == 600                                                                 # the broken update was NOT applied
    assert b.apply("update", upd(14, 13, 1200)) == "unsynced"
    assert b.apply("snapshot", snap(20, 2000, [(50, 1)], [(51, 1)])) == "snapshot" and b.ready and b.seq == 20 and b.bids == {50.0: 1.0}
    assert b.apply("update", upd(21, 20, 2100, bids=[(50, 2)])) == "ok"
    assert Book().apply("update", upd(1, 0, 1)) == "unsynced" and b.apply("ping", {}) == "ignored"


def test_touch_spread_and_crossing():
    b = base_book()
    assert b.best() == (100.00, 100.01) and abs(b.mid() - 100.005) < 1e-12
    assert abs(b.spread_bp() - 0.01 / 100.005 * 1e4) < 1e-9
    assert not b.crossed()
    b.apply("update", upd(11, 10, 1100, bids=[(100.02, 5)]))
    assert b.crossed()
    assert [p for p, _ in b.levels("bid", 2)] == [100.02, 100.00] and [p for p, _ in b.levels("ask", 2)] == [100.01, 100.02]


def test_imbalance_in_dollars_bands_in_basis_points_and_the_microprice():
    b = base_book()
    B1, A1 = 100.00 * 600, 100.01 * 500
    assert abs(b.imbalance_levels(1) - (B1 - A1) / (B1 + A1)) < 1e-12
    B2, A2 = B1 + 99.99 * 900, A1 + 100.02 * 800
    assert abs(b.imbalance_levels(2) - (B2 - A2) / (B2 + A2)) < 1e-12
    assert math.isnan(b.usd_within("bid", 2.0)) and math.isnan(b.usd_within("ask", 2.0))       # the book only reaches 1.5bp: a 2bp band would be silently truncated, so NaN
    b.apply("update", upd(11, 10, 1100, bids=[(99.97, 1)], asks=[(100.04, 1)]))                # levels 3.5bp out: now a 2bp band is fully covered
    assert abs(b.usd_within("bid", 0.5) - B1) < 1e-9                                           # 100.00 is 0.50bp from the mid, 99.99 is 1.5bp
    assert abs(b.usd_within("bid", 2.0) - B2) < 1e-9 and abs(b.usd_within("ask", 2.0) - A2) < 1e-9     # the far levels are outside the band
    assert math.isnan(b.usd_within("bid", 10.0)) and math.isnan(b.usd_within("ask", 10.0))     # but 10bp is still beyond the recorded depth
    assert abs(b.imbalance_band(2.0) - (B2 - A2) / (B2 + A2)) < 1e-12
    micro = (100.00 * 500 + 100.01 * 600) / 1100
    assert abs(b.microprice_offset_bp() - (micro - 100.005) / 100.005 * 1e4) < 1e-9 and b.microprice_offset_bp() > 0     # the bigger bid pulls it up
    cb, ca = b.coverage_bp()
    assert abs(cb - (100.005 - 99.97) / 100.005 * 1e4) < 0.01 and abs(ca - (100.04 - 100.005) / 100.005 * 1e4) < 0.01


# ------------------------------------------------------------------ storage

def ns(y, mo, d, h, mi, s):
    return int(datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc).timestamp() * 1e9)


def test_the_writer_rotates_each_utc_hour_and_the_reader_returns_everything_in_order():
    with tempfile.TemporaryDirectory() as td:
        w = store.RawWriter(Path(td), "XRPUSDT")
        t1, t2, t3 = ns(2026, 11, 1, 10, 59, 59), ns(2026, 11, 1, 11, 0, 1), ns(2026, 11, 1, 11, 0, 2)
        for t, r in ((t1, "a"), (t2, "b"), (t3, "c\nd")):
            w.write(t, r)
        w.close()
        files = sorted(p.name for p in (Path(td) / "XRPUSDT").glob("*.log.gz"))
        assert files == ["2026-11-01_10.log.gz", "2026-11-01_11.log.gz"]
        assert list(store.iter_raw(Path(td), "XRPUSDT")) == [(t1, "a"), (t2, "b"), (t3, "c d")]            # an embedded newline is flattened, never splits a record
        assert w.frames == 3 and w.disk_bytes() > 0


def test_a_crash_after_a_flush_loses_nothing_that_was_flushed():
    with tempfile.TemporaryDirectory() as td:
        w = store.RawWriter(Path(td), "BTCUSDT", flush_every_s=3600)
        t = ns(2026, 11, 1, 10, 0, 0)
        for i in range(50):
            w.write(t + i, f"frame{i}")
        w.flush()                                                                                  # ... and then the process dies: close() is never called
        got = list(store.iter_raw(Path(td), "BTCUSDT"))
        assert [r for _, r in got] == [f"frame{i}" for i in range(50)], len(got)
        w.close()                                                                                  # (only so Windows can delete the folder afterwards)


def test_a_restart_inside_the_same_hour_appends_a_second_gzip_member():
    with tempfile.TemporaryDirectory() as td:
        t = ns(2026, 11, 1, 10, 0, 0)
        w = store.RawWriter(Path(td), "SOLUSDT")
        w.write(t, "first")
        w.close()
        w2 = store.RawWriter(Path(td), "SOLUSDT")
        w2.write(t + 1, "second")
        w2.close()
        assert [r for _, r in store.iter_raw(Path(td), "SOLUSDT")] == ["first", "second"]


def test_the_event_log_survives_a_torn_last_line():
    with tempfile.TemporaryDirectory() as td:
        e = store.EventLog(Path(td) / "events.jsonl")
        e.write("connect")
        e.write("gap", pair="X", seq=5)
        with open(e.path, "a", encoding="utf-8") as f:
            f.write('{"t_ns":1,"type":"half')
        got = e.read()
        assert [r["type"] for r in got] == ["connect", "gap"] and got[1]["seq"] == 5


# ------------------------------------------------------------------ the recorder's frame handler

def make_recorder(td, pairs=("XRPUSDT", "BTCUSDT")):
    return rc.Recorder(list(pairs), Path(td), audit_every_s=1e9, flush_every_s=3600)


def test_handler_stores_raw_follows_the_book_counts_and_ignores_acks_pongs_and_strangers():
    with tempfile.TemporaryDirectory() as td:
        r = make_recorder(td)
        t = ns(2026, 11, 1, 10, 0, 0)
        assert r.handle(json.dumps({"event": "subscribe", "arg": {"channel": "books", "instId": "XRPUSDT"}}), t) == []
        assert r.handle("pong", t) == [] and r.pongs == 1
        assert r.handle(frame("snapshot", "XRPUSDT", "books", [snap(10, 1000, [(1.0, 5)], [(1.1, 5)])]), t) == []
        assert r.handle(frame("update", "XRPUSDT", "books", [upd(11, 10, 1100, bids=[(1.0, 6)])]), t + 1) == []
        assert r.handle(frame("update", "XRPUSDT", "trade", [dict(ts="1100", price="1.0", size="3", side="buy", tradeId="1"),
                                                         dict(ts="1101", price="1.0", size="2", side="sell", tradeId="2")]), t + 2) == []
        assert r.handle(frame("update", "NOTMINEUSDT", "books", [upd(1, 0, 1)]), t + 3) == []
        st = r.stats["XRPUSDT"]
        assert st["books"] == 2 and st["snapshots"] == 1 and st["trades"] == 2 and st["gaps"] == 0 and r.books["XRPUSDT"].bids[1.0] == 6.0
        assert r.stats["BTCUSDT"]["books"] == 0 and "NOTMINEUSDT" not in r.writers
        r.writers["XRPUSDT"].close()
        assert len(list(store.iter_raw(Path(td) / "raw", "XRPUSDT"))) == 3                          # snapshot, update, trade - not the ack, not the pong


def test_a_gap_is_logged_stops_the_book_and_asks_for_a_new_snapshot_of_that_pair_only():
    with tempfile.TemporaryDirectory() as td:
        r = make_recorder(td)
        t = ns(2026, 11, 1, 10, 0, 0)
        r.handle(frame("snapshot", "BTCUSDT", "books", [snap(10, 1000, [(100, 1)], [(101, 1)])]), t)
        acts = r.handle(frame("update", "BTCUSDT", "books", [upd(15, 14, 1100, bids=[(100, 2)])]), t + 1)
        assert acts == [("resub", "BTCUSDT")] and not r.books["BTCUSDT"].ready and r.stats["BTCUSDT"]["gaps"] == 1
        assert r.handle(frame("update", "BTCUSDT", "books", [upd(16, 15, 1200)]), t + 2) == []           # still waiting for the snapshot: no second request
        ev = [e for e in r.events.read() if e["type"] == "gap"]
        assert len(ev) == 1 and ev[0]["pair"] == "BTCUSDT" and ev[0]["last_seq"] == 10 and ev[0]["pseq"] == 14
        r.handle(frame("snapshot", "BTCUSDT", "books", [snap(30, 2000, [(100, 1)], [(101, 1)])]), t + 3)
        assert r.books["BTCUSDT"].ready and r.stats["BTCUSDT"]["snapshots"] == 2
        for w in r.writers.values():
            w.close()


def test_bad_frames_never_stop_the_recording():
    with tempfile.TemporaryDirectory() as td:
        r = make_recorder(td)
        t = ns(2026, 11, 1, 10, 0, 0)
        assert r.handle("{not json", t) == []
        r.handle(frame("snapshot", "XRPUSDT", "books", [snap(10, 1000, [(1.0, 5)], [(1.1, 5)])]), t + 1)
        bad = json.dumps({"action": "update", "arg": {"channel": "books", "instId": "XRPUSDT"},
                          "data": [{"bids": [["1.0", "9"]], "ts": "1100", "seq": 11, "pseq": 10}]})            # a valid chain position, but the `asks` field is missing
        assert r.handle(bad, t + 2) == [("resub", "XRPUSDT")]                                        # logged, not raised, and a fresh snapshot is requested
        assert r.books["XRPUSDT"].bids[1.0] == 5.0 and not r.books["XRPUSDT"].ready                # the bids were NOT applied: nothing is half-applied
        assert r.handle(bad, t + 3) == []                                                          # a second bad frame while waiting does not storm the server
        kinds = [e["type"] for e in r.events.read()]
        assert "bad_json" in kinds and kinds.count("handler_error") == 1                              # one error logged; the second bad frame was ignored while unsynced
        r.writers["XRPUSDT"].close()
        assert len(list(store.iter_raw(Path(td) / "raw", "XRPUSDT"))) == 3                          # snapshot + both malformed frames are on disk for later inspection


def test_subscriptions_cover_every_pair_and_channel_and_match_the_registry():
    r = rc.Recorder(rc.PAIRS, Path(tempfile.mkdtemp()))
    args = r.sub_args()
    assert len(args) == 20 and {a["channel"] for a in args} == {"books", "trade"} and all(a["instType"] == "USDT-FUTURES" for a in args)
    assert r.sub_args(("books",), ["DOGEUSDT"]) == [{"instType": "USDT-FUTURES", "channel": "books", "instId": "DOGEUSDT"}]
    assert set(rc.PAIRS) == set(reg.TUNE_PAIRS) | set(reg.TEST_PAIRS) | set(reg.CONTROL_PAIRS) and len(rc.PAIRS) == 10


def fake_exchange(silent=()):
    """A tiny local websocket server speaking just enough of Bitget's protocol: on subscribe it sends one stray update and then the snapshot (unless the pair is silent)."""
    async def handler(ws):
        async for raw in ws:
            m = json.loads(raw)
            if m.get("op") != "subscribe":
                continue
            for a in m["args"]:
                pair = a["instId"]
                await ws.send(json.dumps({"event": "subscribe", "arg": a}))
                if pair in silent:
                    continue
                await ws.send(json.dumps({"action": "update", "arg": a, "data": [upd(7, 6, 1)]}))
                await ws.send(json.dumps({"action": "snapshot", "arg": a, "data": [snap(1000 + len(pair), 5000, [(1.0, 5)], [(1.1, 5)])]}))
    return handler


def test_the_audit_connection_collects_one_fresh_snapshot_per_pair_and_survives_a_silent_one():
    async def go():
        async with websockets.serve(fake_exchange(silent=("DEADUSDT",)), "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            return await rc.fetch_snapshots(["XRPUSDT", "DEADUSDT", "BTCUSDT"], url=f"ws://127.0.0.1:{port}", timeout=0.6)
    got = asyncio.run(go())
    assert [g[0] for g in got] == ["XRPUSDT", "DEADUSDT", "BTCUSDT"]
    assert got[1][2] is None                                                                        # a pair that never answers is reported, not waited on forever
    assert json.loads(got[0][2])["data"][0]["seq"] == 1000 + len("XRPUSDT") and json.loads(got[2][2])["action"] == "snapshot"     # the stray update was skipped


def test_an_audit_round_stores_the_snapshots_under_audit_and_logs_timeouts():
    td = tempfile.mkdtemp()
    try:
        r = rc.Recorder(["XRPUSDT", "DEADUSDT"], Path(td), audit_every_s=1e9, flush_every_s=3600)

        async def go():
            async with websockets.serve(fake_exchange(silent=("DEADUSDT",)), "127.0.0.1", 0) as server:
                r.ws_url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
                import orderflow.recorder as mod
                real = mod.fetch_snapshots
                mod.fetch_snapshots = lambda pairs, url=None, timeout=8.0: real(pairs, url, 0.6)
                try:
                    await r.audit_round()
                finally:
                    mod.fetch_snapshots = real
        asyncio.run(go())
        for w in list(r.writers.values()) + list(r.audit_writers.values()):
            w.close()
        stored = list(store.iter_raw(Path(td) / "audit", "XRPUSDT"))
        assert len(stored) == 1 and json.loads(stored[0][1])["action"] == "snapshot"
        assert list(store.iter_raw(Path(td) / "audit", "DEADUSDT")) == []
        kinds = [e["type"] for e in r.events.read()]
        assert "audit_timeout" in kinds and "audit_round" in kinds
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_an_audit_round_that_cannot_connect_logs_and_does_not_raise():
    td = tempfile.mkdtemp()
    try:
        r = rc.Recorder(["XRPUSDT"], Path(td), audit_every_s=1e9)
        r.ws_url = "ws://127.0.0.1:1"                                                              # nothing listens there
        asyncio.run(r.audit_round())
        assert "audit_error" in [e["type"] for e in r.events.read()]
        for w in list(r.writers.values()) + list(r.audit_writers.values()):
            w.close()
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_the_stats_line_reports_the_recorders_own_memory_and_cpu():
    m = rc.rss_mb()
    assert math.isnan(m) or 5 < m < 20000                                                          # a plausible resident size, or NaN where the platform will not say
    td = tempfile.mkdtemp()
    try:
        r = make_recorder(td)
        old = rc.STATS_S
        rc.STATS_S = 0.05
        try:
            async def go():
                task = asyncio.create_task(r._stats_loop())
                await asyncio.sleep(0.2)
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            asyncio.run(go())
        finally:
            rc.STATS_S = old
        ev = [e for e in r.events.read() if e["type"] == "stats"]
        assert ev and "cpu_pct" in ev[0] and "rss_mb" in ev[0] and ev[0]["cpu_pct"] >= 0 and "per_minute" in ev[0] and "disk_bytes" in ev[0]
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_a_checkpoint_replaces_the_book_exactly_and_keeps_the_chain():
    b = base_book()
    b.apply("update", upd(11, 10, 1100, bids=[(100.00, 650.5)], asks=[(100.01, 0), (100.03, 0.0001)]))
    msg = json.loads(b.checkpoint_message("XRPUSDT"))
    assert msg["action"] == "checkpoint" and msg["arg"]["instId"] == "XRPUSDT" and msg["data"][0]["seq"] == 11 and msg["data"][0]["pseq"] == 11
    c = Book()
    assert c.apply(msg["action"], msg["data"][0]) == "checkpoint" and c.ready
    assert c.bids == b.bids and c.asks == b.asks and c.seq == 11 and c.ts == 1100             # identical, down to the last digit of every price and size
    assert c.apply("update", upd(12, 11, 1200, bids=[(100.00, 1)])) == "ok"                    # the chain continues from the checkpoint
    d = Book()
    d.apply("checkpoint", msg["data"][0])
    assert d.apply("update", upd(13, 12, 1300)) == "gap"                                       # and a wrong pseq is still a gap


def test_a_writer_asks_for_a_first_frame_once_per_file_and_writes_nothing_when_told_none():
    with tempfile.TemporaryDirectory() as td:
        calls = []

        def cb(recv_ns):
            calls.append(recv_ns)
            return "CHECKPOINT" if len(calls) == 2 else None
        w = store.RawWriter(Path(td), "XRPUSDT", on_rotate=cb)
        t1, t2, t3 = ns(2026, 11, 1, 10, 59, 59), ns(2026, 11, 1, 11, 0, 1), ns(2026, 11, 1, 11, 0, 2)
        for t, r in ((t1, "a"), (t2, "b"), (t3, "c")):
            w.write(t, r)
        w.close()
        assert calls == [t1, t2]                                                               # once per file, not per frame
        assert [r for _, r in store.iter_raw(Path(td), "XRPUSDT")] == ["a", "CHECKPOINT", "b", "c"]
        assert [r for _, r in store.iter_raw(Path(td), "XRPUSDT", since="2026-11-01_11")] == ["CHECKPOINT", "b", "c"]


def test_every_hourly_file_after_the_first_opens_with_a_checkpoint_and_can_be_verified_alone():
    td = tempfile.mkdtemp()
    try:
        r = make_recorder(td, ("XRPUSDT",))
        t0 = ns(2026, 11, 1, 10, 59, 58)
        seq, ts = 10, 1000
        r.handle(frame("snapshot", "XRPUSDT", "books", [snap(seq, ts, [(1.0, 5), (0.9, 7)], [(1.1, 5), (1.2, 9)])]), t0)
        for i in range(1, 6):                                                                  # two updates before 11:00:00, three after
            sizes = dict(bids=[(1.0, 5 + i)], asks=[(1.1, 5 + 2 * i)])
            r.handle(frame("update", "XRPUSDT", "books", [upd(seq + i, seq + i - 1, ts + i * 100, **sizes)]), t0 + int(i * 0.6e9))
        r.writers["XRPUSDT"].close()                                                          # (close first: unflushed frames are not yet on disk)
        full = Book()
        for _, raw in store.iter_raw(Path(td) / "raw", "XRPUSDT"):
            m = json.loads(raw)
            full.apply(m["action"], m["data"][0])
        files = sorted(p.name for p in (Path(td) / "raw" / "XRPUSDT").glob("*.log.gz"))
        assert files == ["2026-11-01_10.log.gz", "2026-11-01_11.log.gz"]
        first_of = {f: next(iter(store.iter_raw(Path(td) / "raw", "XRPUSDT", since=f.split(".")[0])))[1] for f in files}
        assert json.loads(first_of[files[0]])["action"] == "snapshot" and json.loads(first_of[files[1]])["action"] == "checkpoint"
        alone = verify.verify_pair(Path(td) / "raw", "XRPUSDT", since="2026-11-01_11")
        assert alone["snapshots"] == 0 and alone["checkpoints"] == 1 and alone["gaps"] == 0 and alone["unsynced"] == 0 and alone["updates"] >= 2
        replay = Book()
        for _, raw in store.iter_raw(Path(td) / "raw", "XRPUSDT", since="2026-11-01_11"):
            m = json.loads(raw)
            replay.apply(m["action"], m["data"][0])
        assert replay.bids == full.bids and replay.asks == full.asks and replay.seq == full.seq    # the hour read alone ends in exactly the book the whole recording ends in
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_no_checkpoint_is_written_while_the_book_is_not_ready():
    td = tempfile.mkdtemp()
    try:
        r = make_recorder(td, ("XRPUSDT",))
        cb = r._checkpointer("XRPUSDT")
        assert cb(0) is None                                                                   # before any snapshot there is no book to checkpoint
        r.handle(frame("snapshot", "XRPUSDT", "books", [snap(10, 1000, [(1.0, 5)], [(1.1, 5)])]), ns(2026, 11, 1, 10, 0, 0))
        assert json.loads(cb(0))["action"] == "checkpoint"
        r.handle(frame("update", "XRPUSDT", "books", [upd(99, 50, 1100)]), ns(2026, 11, 1, 10, 0, 1))      # a gap: the book is unusable
        assert cb(0) is None
        for w in r.writers.values():
            w.close()
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_only_one_recorder_may_write_to_a_folder():
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as td2:
        s = rc.single_instance(Path(td))
        try:
            rc.single_instance(Path(td))
            assert False, "a second recorder on the same folder must be refused"
        except SystemExit:
            pass
        s2 = rc.single_instance(Path(td2))                                                          # a different folder is fine
        s.close()
        s3 = rc.single_instance(Path(td))                                                           # and the port frees when the first one ends
        s2.close()
        s3.close()


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
