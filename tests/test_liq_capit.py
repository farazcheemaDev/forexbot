"""Offline tests for backtest/liq_capit.py - the three factors at a capit2 signal (24-hour map flush, 24-hour real open-interest
fall, leverage left under the limit), the reset, and the tune-only cuts with 'left' flagged LOW. Synthetic data only.

    python tests/test_liq_capit.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import liq_capit as lc  # noqa: E402
from backtest import liq_map as lm  # noqa: E402

H = lm.H


def _coin(n=60):
    t = np.arange(n, dtype=np.int64) * H + 5_000 * H
    return t, np.full(n, 100.05), np.full(n, 99.95), np.full(n, 100.0)


def test_left_is_the_leverage_between_the_limit_and_five_percent_under_it():
    t, h, l, c = _coin()  # noqa: E741
    oi = np.full(60, 100.0)
    oi[10:] = 200.0                                                                           # +100 booked at hour 10, P = 100
    out = lc.features(t, h, l, c, oi, [40])[0]
    v = 100 * 100.0 / 4                                                                       # a quarter per leverage
    # limit 98: band [93.1, 98] holds the 50x (98) and 20x (95) bins; 99 (100x) is above the limit, 90 (10x) under the band
    assert abs(out[2] - 2 * v / (200 * 100.0)) < 1e-9
    assert out[3] == 40


def test_mapflush_sums_the_last_24_hours_and_oiflush_reads_real_open_interest():
    t, h, l, c = _coin()  # noqa: E741
    oi = np.full(60, 100.0)
    oi[10:] = 200.0
    oi[45:] = 150.0
    l[30] = 94.0                                                                              # 30 is 20 hours before 50: inside
    l[20] = 89.0                                                                              # would clear all, but 20 is 30 hours before
    out = lc.features(t, h, l, c, oi, [50])[0]
    v = 100 * 100.0 / 4
    # hour 20 cleared everything: nothing left for hour 30 -> the window sums 0
    assert out[0] == 0.0
    t2, h2, l2, c2 = _coin()
    l2[30] = 94.0                                                                              # clears 99, 98, 95 (3 bins) at hour 30
    o2 = lc.features(t2, h2, l2, c2, oi, [50, 60 - 1])
    assert abs(o2[0][0] - 3 * v / (200 * 100.0)) < 1e-9 and o2[1][0] == 0.0                # hour 59's window (36..59) misses hour 30
    o3 = lc.features(t2, h2, l2, c2, oi, [53, 54])
    assert abs(o3[0][0] - 3 * v / (200 * 100.0)) < 1e-9 and o3[1][0] == 0.0                # 30..53 is 24 hours; 31..54 misses it
    assert abs(out[1] - (-(150 / 200 - 1))) < 1e-12


def test_oiflush_needs_24_consecutive_hours():
    t, h, l, c = _coin()  # noqa: E741
    t[30:] += 5 * H                                                                           # a 5-hour hole (no reset)
    oi = np.full(60, 100.0)
    out = lc.features(t, h, l, c, oi, [40, 59])
    assert np.isnan(out[0][1]) and out[1][1] == 0.0


def test_a_gap_resets_the_map():
    t, h, l, c = _coin()  # noqa: E741
    t[30:] += 60 * H
    oi = np.full(60, 100.0)
    oi[10:30] = 200.0
    out = lc.features(t, h, l, c, oi, [55])[0]
    assert out[2] == 0.0 and out[3] == 25


def test_flags_use_the_tune_cut_and_left_is_flagged_low():
    T = pd.DataFrame(dict(mapflush=np.r_[np.arange(9.0), [100.0] * 3], oiflush=np.r_[np.arange(9.0), [100.0] * 3],
                          left=np.r_[np.arange(9.0), [-1.0] * 3]))
    tune = pd.Series([True] * 9 + [False] * 3)
    cuts, F = lc.flags(T, tune)
    assert abs(cuts["mapflush"] - np.quantile(np.arange(9.0), 2 / 3)) < 1e-12 and abs(cuts["left"] - np.quantile(np.arange(9.0), 1 / 3)) < 1e-12
    assert F.mapflush[:9].sum() == 3 and F.left[:9].sum() == 3 and F.left[:3].all() and F.left[9:].all()


def test_spread_is_flagged_minus_unflagged():
    T = pd.DataFrame(dict(net=[0.03, 0.01, 0.0, 0.0, -0.01, 0.01], day=list("abcdef")))
    s = lc.spread(T, pd.Series([True, True, True, False, False, False]), np.ones(6, bool))
    assert abs(s["b"] - (0.04 / 3 - 0.0)) < 1e-12 and s["n"] == 3


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
