"""Offline tests for the rules added to the Bitget demo bot on 2026-09-24: the time stop, 7
pyramid units, and the 10x gross guard. They drive longtrend_bot.cycle() itself - no exchange
(ex=None), dry-run, synthetic 1h klines, and scratch state/trade/log files - so what is tested
is the code the bot runs, not a re-implementation of it.

Each rule is checked where it must fire AND where it must not.

    python tests/test_longtrend_rules.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = [sys.argv[0]]
import longtrend_bot as L  # noqa: E402

TMP = Path(tempfile.mkdtemp())
L.STATE, L.TRADES, L.LOGF = TMP / "state.json", TMP / "trades.csv", TMP / "log.txt"
L.BOOK = {"TESTUSDT": "STEST/SUSDT:SUSDT"}
RAW = "STESTSUSDT"
L.btc_below_ma = lambda ex=None: False
L.btc_break_now = lambda: False
_BAR = {}


def fake_klines(sym, limit=300):
    """60 quiet bars around 100, then the bar under test, then a forming bar."""
    n = 60
    t = pd.date_range(pd.Timestamp("2026-01-01") + pd.Timedelta(hours=_BAR.get("shift", 0)),
                      periods=n + 2, freq="h")
    c = np.full(n + 2, 100.0)
    h, lo = c + 1.0, c - 1.0
    h[n], lo[n], c[n] = _BAR["h"], _BAR["l"], _BAR["c"]
    return pd.DataFrame({"time": t, "open": c, "high": h, "low": lo, "close": c})


L.klines = fake_klines


def long_rec(**kw):
    r = dict(entry=100.0, size=1.0, size_unit=1.0, risk=2.0, stop=96.0, side="long",
             entry_bar="1999-01-01", high_water=100.0, bars=0, units=1, next_add=1,
             tight=False, barmed=True)
    r.update(kw)
    return r


def run(rec, h, l, c, others=None):
    _BAR.update(h=h, l=l, c=c, shift=0)
    st = {"open": {RAW: rec}, "last_bar": {}}
    st["open"].update(others or {})
    if L.TRADES.exists():
        L.TRADES.unlink()
    L.cycle(None, st, True)
    trades = pd.read_csv(L.TRADES) if L.TRADES.exists() else pd.DataFrame()
    return st, trades


def test_time_stop_fires_on_bar_100_under_2R():
    st, tr = run(long_rec(bars=99), h=102, l=99, c=101)        # +0.5R at bar 100
    assert RAW not in st["open"], "position should be closed"
    assert list(tr.reason) == ["TIME_STOP"] and abs(tr.exit.iloc[0] - 101.0) < 1e-9


def test_no_time_stop_at_or_above_2R():
    st, tr = run(long_rec(bars=99), h=106, l=103, c=105)        # +2.5R
    assert RAW in st["open"] and tr.empty


def test_no_time_stop_before_100_bars():
    st, tr = run(long_rec(bars=50), h=102, l=99, c=101)
    assert RAW in st["open"] and tr.empty


def test_stop_beats_time_stop_on_the_same_bar():
    st, tr = run(long_rec(bars=99), h=101, l=95, c=100)         # low 95 < stop 96
    assert list(tr.reason) == ["TRAIL"] and abs(tr.exit.iloc[0] - 96.0) < 1e-9


def test_time_stop_never_applies_to_shorts():
    rec = long_rec(side="short", bars=150, stop=104.0, high_water=100.0)
    st, tr = run(rec, h=101, l=99.5, c=100)
    assert RAW in st["open"] and tr.empty


def test_pyramid_adds_the_7th_unit_and_stops_there():
    rec = long_rec(units=6, next_add=6, stop=110.0, high_water=120.0, bars=10)
    st, _ = run(rec, h=125, l=121, c=124)                      # +12.5R >= 6 x 2R
    assert st["open"][RAW]["units"] == 7 and st["open"][RAW]["next_add"] == 7
    # the NEXT bar (the bot manages once per closed bar, so the same bar would be skipped
    # and this check would pass without testing anything): +20R clears the 8th unit's
    # +14R trigger, so only the unit cap can stop it
    _BAR.update(h=140, l=130, c=138, shift=1)
    L.cycle(None, st, True)
    assert st["open"][RAW]["bars"] == 12, "the second bar was not managed"
    assert st["open"][RAW]["units"] == 7


def test_10x_guard_blocks_an_add_that_would_breach():
    rec = long_rec(units=6, next_add=6, stop=110.0, high_water=120.0, bars=10)
    # another open position already at ~2,100 of notional: 10 x $221 = $2,210 is the line
    big = {"OTHER": long_rec(size_unit=20.0, size=20.0, entry=105.0, units=1)}
    st, _ = run(rec, h=125, l=121, c=124, others=big)
    assert st["open"][RAW]["units"] == 6 and st["open"][RAW].get("lev_warned")


def test_guard_counts_every_unit_already_open():
    recs = {"A": long_rec(units=7), "B": long_rec(size_unit=2.0, units=3)}
    assert abs(L.gross_notional(recs) - (1.0 * 100 * 7 + 2.0 * 100 * 3)) < 1e-9


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
