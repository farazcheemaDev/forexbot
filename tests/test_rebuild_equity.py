"""Offline tests for rebuild_equity.py. The main fixture is REAL: the triple paper book's 19
closes from 2026-09-28 06:00 to 2026-09-29 15:00 UTC, pasted from the VM's
logs/trades_blend_triple.csv. Eight of them are legacy positions (opened before the entry-sized
fix, sized at close); the rest are entry-sized, and three were opened MID-POLL between closes.
The replay has to reproduce every recorded equity value, which it can only do with the bot's
in-poll order.

    python tests/test_rebuild_equity.py
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = [sys.argv[0]]
import rebuild_equity as rb  # noqa: E402

HEAD = "ts,symbol,sleeve,side,entry,exit,units,R,bars,risk_pct,equity,tightened\n"
TRIPLE_0928 = HEAD + """\
2026-09-28 06:00:34,ADAUSDT,1h,long,0.20480000,0.24779286,7,+22.2014,245,0.300,223.65,1
2026-09-28 06:00:34,LINKUSDT,1h,long,11.23200000,13.70178571,7,+32.1080,261,0.300,245.19,1
2026-09-28 06:00:34,AVAXUSDT,1h,long,7.53000000,10.96257143,7,+104.2035,268,0.300,321.84,1
2026-09-28 06:00:34,LTCUSDT,1h,long,65.81000000,71.67142857,2,+1.8307,99,0.300,322.99,1
2026-09-28 06:00:34,WLDUSDT,1h,long,0.37340000,0.52029286,7,+32.1564,268,0.300,354.15,1
2026-09-28 06:00:34,ARBUSDT,1h,long,0.16820000,0.22992857,4,+8.0877,270,0.300,362.74,1
2026-09-28 10:00:11,SUIUSDT,1h,long,0.71140000,1.16187857,7,+127.6847,277,0.300,501.70,1
2026-09-28 10:00:11,ENAUSDT,1h,long,0.14650000,0.26292143,7,+71.4164,278,0.300,609.18,1
2026-09-28 10:00:11,NEARUSDT,1h,long,2.45700000,5.00514286,7,+150.1137,282,0.300,883.52,1
2026-09-28 11:00:12,LTCUSDT,1h,short,70.11000000,71.88285714,1,-1.0475,1,0.300,881.95,0
2026-09-28 13:02:04,XRPUSDT,1h,short,1.47980000,1.51570000,1,-1.0495,6,0.300,880.80,0
2026-09-28 13:02:04,ADAUSDT,1h,short,0.24510000,0.25300000,1,-1.0372,6,0.300,879.68,0
2026-09-28 13:02:04,LINKUSDT,1h,short,13.79800000,14.15028571,1,-1.0470,6,0.300,878.54,0
2026-09-28 14:01:55,ENAUSDT,1h,short,0.26010000,0.27182857,1,-1.0266,3,0.300,875.82,0
2026-09-29 01:02:12,AVAXUSDT,1h,short,10.54300000,10.89842857,1,-1.0356,18,0.300,874.69,0
2026-09-29 08:01:20,ADAUSDT,1h,short,0.24100000,0.25095714,1,-1.0290,17,0.300,871.99,0
2026-09-29 12:00:46,ARBUSDT,1h,short,0.20560000,0.21164286,1,-0.5545,26,0.300,870.52,0
2026-09-29 13:00:36,SHIBUSDT,1h,short,0.00000570,0.00000586,1,-1.0420,31,0.300,869.51,0
2026-09-29 15:00:14,WLDUSDT,1h,short,0.50580000,0.51883571,1,-0.5359,29,0.300,868.53,0
"""
START = 209.686        # the book just before ADA's close: 223.65 / (1 + 0.003 * 22.2014)
FIX = pd.Timestamp("2026-09-23 12:00")   # the legacy longs opened 09-17/18, LTC's long 09-24
TMP = Path(tempfile.mkdtemp())


def fixture() -> pd.DataFrame:
    p = TMP / "triple.csv"
    p.write_text(TRIPLE_0928)
    return rb.load(p)


def test_real_log_reproduced_row_by_row():
    c = rb.replay(fixture(), START, FIX)
    ok, dmax, first = rb.check(c)
    assert ok, (dmax, first)
    assert dmax < 0.02, dmax                               # to the cent, every row
    assert int(c.legacy.sum()) == 8                        # the 8 old runners, not LTC's long


def test_the_in_poll_order_is_what_makes_it_match():
    """Mutation: drop the BOOK order (every coin index equal) so an open no longer sits between
    the closes around it. SHIB, WLD, ARB and the LTC short are then sized on the wrong equity."""
    d = fixture()
    d["kidx"] = 0
    ok, dmax, _ = rb.check(rb.replay(d, START, FIX))
    assert not ok and dmax > 1.0, dmax


def test_without_the_fix_time_it_cannot_match():
    """Mutation: treat every position as legacy (the old script's only model). LTC's long was
    entry-sized, so the column diverges at its close."""
    ok, _, first = rb.check(rb.replay(fixture(), START, None))
    assert not ok and first == pd.Timestamp("2026-09-28 06:00:34"), first


def test_corrected_is_the_hand_calculation():
    c = rb.replay(fixture(), START, FIX)
    near = c[(c.symbol == "NEARUSDT")].equity_corrected.iloc[0]
    want = START * (1 + 0.003 * (547.9718 + 1.8307))      # 8 legacy longs + LTC, all at START
    assert abs(near - want) < 0.01, (near, want)
    assert abs(near - 555.54) < 0.05
    rec = c[(c.symbol == "NEARUSDT")].equity_recorded.iloc[0]
    assert rec - near > 320                                # the legacy path overstated $328


def test_growth_since_excludes_positions_opened_before():
    p = TMP / "triple.csv"
    p.write_text(TRIPLE_0928)
    m, n = rb.growth_since(p, "2026-09-28 06:30:00")
    assert n == 9, n                                       # SHIB (06:00) and the longs are out
    assert 0.974 < m < 0.976, m                            # nine small shorts, -8.36R at 0.30%
    m0, n0 = rb.growth_since(p, "2026-10-01")
    assert (m0, n0) == (1.0, 0)


def test_forked_book_starts_from_main_at_the_fork():
    d = TMP / "fork"
    d.mkdir(exist_ok=True)
    (d / "trades_blend.csv").write_text(HEAD + """\
2026-09-20 10:00:05,XRPUSDT,1h,long,1,1,1,+10.0000,5,0.300,227.63,0
2026-09-21 10:00:05,ADAUSDT,1h,long,1,1,1,-1.0000,3,0.300,226.95,0
2026-09-26 10:00:05,SUIUSDT,1h,long,1,1,1,+2.0000,4,0.300,228.31,0
""")
    (d / "trades_blend_triple.csv").write_text(HEAD + """\
2026-09-25 10:00:05,LINKUSDT,1h,long,1,1,1,+5.0000,10,0.300,230.35,1
""")
    (d / "blend_state_triple.json").write_text(json.dumps({"forked": "2026-09-24T12:00:00+00:00"}))
    f, note = rb.book_frame("triple", d)
    assert note is None
    assert list(f.symbol) == ["XRPUSDT", "ADAUSDT", "LINKUSDT"]   # main's post-fork SUI is out
    assert list(f.own) == [False, False, True]
    c = rb.replay(f, 221.0, pd.Timestamp("2026-09-01"))
    ok, dmax, _ = rb.check(c)
    assert ok, dmax                                        # 226.95 + 5R x 0.3% of 226.95
    (d / "blend_state_triple.json").unlink()
    _, note = rb.book_frame("triple", d)
    assert note and "NOT its true start" in note


def test_fix_time_read_from_the_marker_line():
    lf = TMP / "blend_paper.log"
    lf.write_text("2026-09-23 10:00:00 | alive\n2026-09-23T14:05:09Z ENTRY-SIZED FIX APPLIED.\n"
                  "Equity before this line used equity-at-close\n")
    assert rb.fix_time(lf) == pd.Timestamp("2026-09-23 14:05:09")
    assert rb.fix_time(TMP / "nope.log") is None


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
