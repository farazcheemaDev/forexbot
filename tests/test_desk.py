"""desk.py offline: no network, a temp folder. Run as a script: python tests/test_desk.py"""
import argparse
import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import desk  # noqa: E402

MIN = 60_000
T0 = 1_800_000_000_000 // MIN * MIN


def bar(i, o, h, l, c):
    return (T0 + i * MIN, o, h, l, c)


def call(side="long", mode="limit", entry=100.0, stop=98.0, target=104.0, expires_min=600):
    return dict(side=side, mode=mode, entry=entry, stop=stop, target=target, expires_ms=T0 + expires_min * MIN, status="open")


def test_plan_numbers_long_and_short_mirror():
    for side, e, s, t in (("long", 100.0, 98.0, 104.0), ("short", 100.0, 102.0, 96.0)):
        p = desk.plan_numbers(side, e, s, t, 221.0, 1.0)
        assert abs(p["stop_pct"] - 0.02) < 1e-12 and abs(p["target_pct"] - 0.04) < 1e-12 and abs(p["rr"] - 2.0) < 1e-12
        assert abs(p["fee_r"] - 0.06) < 1e-9, p                                  # 12bp / 2%
        assert abs(p["win_r"] - 1.94) < 1e-9 and abs(p["loss_r"] - 1.06) < 1e-9
        assert abs(p["be_p"] - 1.06 / 3.0) < 1e-9, p                              # break-even win rate after fees
        assert abs(p["risk_usd"] - 2.21) < 1e-9 and abs(p["notional"] - 110.5) < 1e-9 and abs(p["lev"] - 0.5) < 1e-9


def test_geometry_is_refused_the_wrong_way_round():
    assert desk.geometry_ok("long", 100, 98, 104) is None and desk.geometry_ok("short", 100, 102, 96) is None
    assert desk.geometry_ok("long", 100, 102, 104) and desk.geometry_ok("long", 100, 98, 99)
    assert desk.geometry_ok("short", 100, 98, 96) and desk.geometry_ok("short", 100, 102, 101)


def test_baseline_counts_target_first_and_a_double_touch_as_the_stop():
    up = [bar(i, 100 * 1.01 ** i, 100 * 1.01 ** i * 1.002, 100 * 1.01 ** i * 0.998, 100 * 1.01 ** i) for i in range(40)]
    b = desk.baseline(up, "long", 0.02, 0.03, 6)
    assert b["p_tp"] == 1.0 and b["p_sl"] == 0.0, b                               # a steady climb always meets +3% before -2%
    assert desk.baseline(up, "short", 0.02, 0.03, 6)["p_sl"] == 1.0
    flat = [bar(i, 100, 100, 100, 100) for i in range(40)]
    assert desk.baseline(flat, "long", 0.02, 0.03, 6)["p_to"] == 1.0
    wide = [bar(i, 100, 106, 94, 100) for i in range(40)]                         # every bar reaches both +3% and -2%
    assert desk.baseline(wide, "long", 0.02, 0.03, 6)["p_sl"] == 1.0              # the pessimistic tie


def test_resolve_win_loss_and_the_fee_in_r():
    b = [bar(0, 101, 102, 99.5, 101), bar(1, 101, 104.5, 100.5, 104)]
    w = desk.resolve(call(), b, T0 + 700 * MIN)
    assert w["status"] == "WIN" and abs(w["exit_price"] - 104) < 1e-9 and abs(w["r_net"] - 1.94) < 1e-9, w
    b = [bar(0, 101, 102, 99.5, 101), bar(1, 101, 101.5, 97.9, 98.5)]
    l = desk.resolve(call(), b, T0 + 700 * MIN)
    assert l["status"] == "LOSS" and abs(l["exit_price"] - 98) < 1e-9 and abs(l["r_net"] + 1.06) < 1e-9, l


def test_a_bar_touching_both_is_a_loss_and_a_gap_exits_at_the_open():
    b = [bar(0, 101, 102, 99.5, 101), bar(1, 101, 105, 97.5, 101)]
    assert desk.resolve(call(), b, T0 + 700 * MIN)["status"] == "LOSS"
    b = [bar(0, 101, 102, 99.5, 101), bar(1, 97.0, 97.5, 96.0, 96.5)]            # opens through the stop
    g = desk.resolve(call(), b, T0 + 700 * MIN)
    assert g["status"] == "LOSS" and abs(g["exit_price"] - 97.0) < 1e-9 and abs(g["r_net"] - (-0.03 - 0.0012) / 0.02) < 1e-9, g
    b = [bar(0, 100.5, 101, 97.8, 100)]                                           # the FILL bar itself reaches the stop
    assert desk.resolve(call(), b, T0 + 700 * MIN)["status"] == "LOSS"


def test_short_mirrors_the_long():
    c = call("short", entry=100.0, stop=102.0, target=96.0)
    b = [bar(0, 99, 100.5, 98.5, 99), bar(1, 99, 99.5, 95.5, 96)]
    w = desk.resolve(c, b, T0 + 700 * MIN)
    assert w["status"] == "WIN" and abs(w["r_net"] - 1.94) < 1e-9, w
    b = [bar(0, 99, 100.5, 98.5, 99), bar(1, 99, 102.2, 98.5, 101)]
    l = desk.resolve(c, b, T0 + 700 * MIN)
    assert l["status"] == "LOSS" and abs(l["r_net"] + 1.06) < 1e-9, l


def test_nofill_open_expired_market_and_bars_after_expiry_are_ignored():
    b = [bar(i, 105, 106, 104, 105) for i in range(5)]                            # never reaches the 100 limit
    assert desk.resolve(call(expires_min=3), b, T0 + 10 * MIN)["status"] == "NOFILL"
    assert desk.resolve(call(expires_min=600), b, T0 + 10 * MIN)["status"] == "open"           # still live
    b = [bar(0, 101, 101.5, 99.8, 101), bar(1, 101, 102, 100.2, 101.5), bar(2, 101.5, 102, 101, 101.8)]
    e = desk.resolve(call(expires_min=2), b, T0 + 10 * MIN)
    assert e["status"] == "EXPIRED" and abs(e["exit_price"] - 101.8) < 1e-9 and e["r_net"] > 0, e
    late = [bar(0, 101, 102, 99.5, 101), bar(1, 101, 103, 100.5, 102), bar(5, 102, 105, 101, 104)]   # the target is touched AFTER expiry
    assert desk.resolve(call(expires_min=2), late, T0 + 10 * MIN)["status"] == "EXPIRED"
    m = desk.resolve(call(mode="market", entry=100.0), [bar(0, 103, 103.5, 102, 103), bar(1, 103, 104.5, 102.5, 104)], T0 + 10 * MIN)
    assert m["status"] == "WIN"                                                    # a market call fills at the first bar whatever its range


def test_a_limit_touched_only_after_expiry_is_not_a_fill():
    b = [bar(0, 105, 106, 104, 105), bar(1, 105, 106, 104, 105), bar(5, 103, 104, 99.0, 100)]   # the touch is at minute 5; the call expired at minute 2
    r = desk.resolve(call(expires_min=2), b, T0 + 10 * MIN)
    assert r["status"] == "NOFILL" and not r.get("filled_ms"), r


def test_price_action_before_the_call_cannot_fill_it():
    patched_dir()
    now = desk.now_ms()
    made = now - 3 * 3_600_000
    desk.save_calls([dict(id=1, made_utc="x", made_ms=made, symbol="ETHUSDT", side="long", mode="limit", entry=100.0, stop=98.0, target=104.0,
                          expires_ms=made + 3_600_000, method="other", note="", equity=221, risk_pct=1, risk_usd=2.21, qty=1, notional=110,
                          lev=0.5, stop_pct=0.02, target_pct=0.04, rr=2, be_p=0.353, base_p=0.4, status="open")])
    touch_at = made // MIN * MIN - 30 * MIN                                       # price dipped to 99.0 half an hour BEFORE the call

    def fetch(sym, interval, start=None, end=None, limit=1500):
        t, out = start, []
        while t <= end and len(out) < limit:
            out.append((t, 105, 106, 99.0 if t == touch_at else 104, 105))
            t += MIN
        return out
    with contextlib.redirect_stdout(io.StringIO()):
        desk.cmd_score(fetch)
    assert desk.load_calls()[0]["status"] == "NOFILL", desk.load_calls()[0]


def patched_dir():
    d = Path(tempfile.mkdtemp())
    desk.D, desk.CALLS = d, d / "calls.csv"
    return d


def fake_fetch(hours_up=True):
    def fetch(sym, interval, start=None, end=None, limit=500):
        if interval == "1h":
            return [bar(i, 100, 100.2, 99.8, 100.0) for i in range(500)]
        n = int((end - start) // MIN) + 1 if (start is not None and end is not None) else 100
        return [(start + i * MIN, 100, 100.2, 99.8, 100.0) for i in range(min(n, limit))]
    return fetch


def test_plan_logs_before_the_outcome_and_refuses_a_bad_geometry():
    patched_dir()
    ns = argparse.Namespace(symbol="sol", side="long", entry="mkt", stop="98", target="104", hours=24, equity=221.0, risk_pct=1.0,
                            method="sr", note="test", no_log=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert desk.cmd_plan(ns, fake_fetch()) == 0
    out = buf.getvalue()
    assert "PLAN SOLUSDT LONG" in out and "BASELINE" in out and "logged as PAPER call #1" in out, out
    rows = desk.load_calls()
    assert len(rows) == 1 and rows[0]["symbol"] == "SOLUSDT" and rows[0]["status"] == "open" and rows[0]["method"] == "sr"
    assert float(rows[0]["entry"]) == 100.0 and abs(float(rows[0]["be_p"]) - 1.06 / 3.0) < 1e-3
    bad = argparse.Namespace(**{**vars(ns), "stop": "101", "note": "x"})
    with contextlib.redirect_stdout(io.StringIO()) as b2:
        assert desk.cmd_plan(bad, fake_fetch()) == 2
    assert len(desk.load_calls()) == 1                                           # nothing logged for a refused plan


def test_stats_says_not_enough_calls_below_30_and_gives_a_verdict_at_30():
    patched_dir()

    def rows(n_win, n_loss):
        out = []
        for i in range(n_win + n_loss):
            win = i < n_win
            out.append(dict(id=i + 1, made_utc="x", made_ms=0, symbol="BTCUSDT", side="long", mode="limit", entry=100, stop=98, target=104,
                            expires_ms=0, method="sr", note="", equity=221, risk_pct=1, risk_usd=2.21, qty=1, notional=110, lev=0.5,
                            stop_pct=0.02, target_pct=0.04, rr=2, be_p=0.353, base_p=0.40, status="WIN" if win else "LOSS",
                            filled_ms=0, exit_ms=0, exit_price=104 if win else 98, r_net=1.94 if win else -1.06))
        return out
    desk.save_calls(rows(5, 5))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        desk.cmd_stats()
    assert "NOT ENOUGH CALLS (10 of 30)" in buf.getvalue() and "EDGE" not in buf.getvalue().replace("NO EDGE", "")
    desk.save_calls(rows(24, 6))                                                  # 80% against a 40% baseline, positive R
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        desk.cmd_stats()
    assert "EDGE (positive average R and p < 0.05)" in buf.getvalue() and "NO EDGE" not in buf.getvalue(), buf.getvalue()
    desk.save_calls(rows(11, 19))                                                 # 37% hit rate, negative R
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        desk.cmd_stats()
    assert "NO EDGE PROVEN" in buf.getvalue(), buf.getvalue()


def test_score_resolves_open_calls_through_the_fetcher():
    patched_dir()
    made = desk.now_ms() - 3 * 3_600_000
    desk.save_calls([dict(id=1, made_utc="x", made_ms=made, symbol="ETHUSDT", side="long", mode="market", entry=100.0, stop=98.0, target=104.0,
                          expires_ms=made + 2 * 3_600_000, method="other", note="", equity=221, risk_pct=1, risk_usd=2.21, qty=1, notional=110,
                          lev=0.5, stop_pct=0.02, target_pct=0.04, rr=2, be_p=0.353, base_p=0.4, status="open")])

    def fetch(sym, interval, start=None, end=None, limit=1500):
        n = min(int((end - start) // MIN) + 1, limit)
        return [(start + i * MIN, 100, 100.3 if i != 50 else 104.5, 99.8, 100.0) for i in range(n)]    # the 51st minute spikes to the target
    with contextlib.redirect_stdout(io.StringIO()):
        desk.cmd_score(fetch)
    r = desk.load_calls()[0]
    assert r["status"] == "WIN" and abs(float(r["r_net"]) - 1.94) < 1e-6, r


def test_the_minute_baseline_reads_the_scoring_grid_and_falls_back_to_hours_for_a_new_listing():
    calls = []

    def fetch(sym, interval, start=None, end=None, limit=1500):
        calls.append(interval)
        n = max(0, min(int((end - start) // 60_000) + 1, limit))
        px = lambda t: 100.0 * 1.0001 ** ((t - now) / 60_000)                          # noqa: E731
        return [(start + i * 60_000, px(start + i * 60_000), px(start + i * 60_000) * 1.00002, px(start + i * 60_000) * 0.99999, px(start + i * 60_000))
                for i in range(n)]
    now = 1_800_000_000_000
    hours = [bar(i, 100, 100, 100, 100) for i in range(60)]                       # hourly bars that would say "nothing happens"
    cache: dict = {}
    b = desk.minute_baseline("XUSDT", "long", 0.05, 0.01, 6, now, fetch, hours, cache)
    assert b["grid"] == "1m" and b["p_tp"] == 1.0 and 1000 < b["n"] < 2000, b            # 1% up beats a 5% stop in a 0.01%-a-minute climb, on minutes
    n_calls = len(calls)
    desk.minute_baseline("XUSDT", "short", 0.05, 0.01, 6, now, fetch, hours, cache)
    assert len(calls) == n_calls                                                  # the same symbol's minutes are reused inside a cycle
    thin = desk.minute_baseline("NEWUSDT", "long", 0.05, 0.01, 6, now, lambda *a, **k: [], hours)
    assert thin["grid"] == "1h" and thin["p_to"] == 1.0                            # a listing with no minutes falls back to the hourly bars
    a = desk.baseline([bar(i, 100 * 1.01 ** i, 100 * 1.01 ** i, 100 * 1.01 ** i, 100 * 1.01 ** i) for i in range(40)], "long", 0.02, 0.03, 6, 4)
    assert a["n"] == len(range(0, 40 - 6 - 1, 4)) and a["p_tp"] == 1.0              # step thins the random starts


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
