"""Tests for backtest/small_profit_scalp.py: the trend and pullback features, and the cell statistics.

Run as a script (no pytest on this PC):  python tests/test_small_profit_scalp.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.small_profit_scalp as sp  # noqa: E402


def ticks():
    ts = np.arange(0, 200.0)
    mid = np.full(200, 100.0)
    mid[100:] = 120.0                                  # the day rose 20 points from the open
    mid[140] = 121.0                                   # 30 s before t = 170 the price was 121 ...
    mid[170:] = 120.0                                  # ... and it is 120 now: a one-point pullback
    return ts, mid


def test_a_long_with_the_trend_after_a_pullback_reads_trend_20_pull_1():
    ts, mid = ticks()
    tr, pu = sp.features(ts, mid, 170.0, 1)
    assert abs(tr - 20.0) < 1e-9 and abs(pu - 1.0) < 1e-9


def test_a_short_against_the_trend_reads_negative_trend_and_negative_pullback():
    ts, mid = ticks()
    tr, pu = sp.features(ts, mid, 170.0, -1)
    assert abs(tr + 20.0) < 1e-9 and abs(pu + 1.0) < 1e-9


def test_features_need_thirty_seconds_of_history():
    ts, mid = ticks()
    assert sp.features(ts, mid, 10.0, 1) is None and sp.features(ts, mid, 40.0, 1) is not None


def rows(spec):
    """spec: list of (day, trend, pull, outcome-path) -> rows with first-touch data for a +T no-stop trade."""
    out = []
    for day, trend, pull, path in spec:
        up, dn, end = sp.first_hits(np.array(path, float))
        out.append(dict(day=day, trend=trend, pull=pull, up=up, dn=dn, end=end))
    return out


def test_cell_statistics_win_loser_ev_and_the_break_even_win_rate():
    # 9 winners (+7 reached) and 1 loser that ends at -50 with no stop: EV = (9*7 - 50)/10 = +1.3, break-even = 50/57
    spec = [(i, 10.0, 2.0, [8.0]) for i in range(9)] + [(9, 10.0, 2.0, [-20.0, -50.0])]
    c = sp.cell(rows(spec * 4), np.array([r["day"] < 5 for r in rows(spec * 4)]), 0.0, 0.0, 7)
    assert c["n"] == 40 and abs(c["win"] - 90.0) < 1e-9 and abs(c["loser"] + 50.0) < 1e-9 and abs(c["ev"] - 1.3) < 1e-9 and abs(c["pstar"] - 50 / 57 * 100) < 1e-9
    assert c["worst"] == -50.0


def test_tune_and_holdout_halves_are_reported_in_the_right_columns():
    spec = [(i, 10.0, 2.0, [8.0]) for i in range(20)] + [(i, 10.0, 2.0, [-20.0, -50.0]) for i in range(20, 40)]
    r = rows(spec)
    c = sp.cell(r, np.array([x["day"] < 20 for x in r]), 0.0, 0.0, 7)
    assert abs(c["tune"] - 7.0) < 1e-9 and abs(c["hold"] + 50.0) < 1e-9


def test_the_filters_select_by_trend_and_pullback_and_tiny_cells_are_dropped():
    spec = [(i, 40.0 if i % 2 else 5.0, 2.0 if i % 4 < 2 else 0.5, [8.0]) for i in range(160)]
    r = rows(spec)
    tune = np.array([x["day"] < 80 for x in r])
    assert sp.cell(r, tune, 30.0, 0.0, 7)["n"] == 80
    assert sp.cell(r, tune, 30.0, 1.5, 7)["n"] == 40                     # odd i (trend 40) and i % 4 == 1 (pullback 2.0)
    assert sp.cell(r[:40], tune[:40], 30.0, 1.5, 7) is None              # 10 qualifying entries: too few to report


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
