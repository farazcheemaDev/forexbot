"""Tests for backtest/nasdaq_regimes.py: previous-close alignment of the regime flags, the on / off summary and the closing-hour rule.

Run as a script (no pytest on this PC):  python tests/test_nasdaq_regimes.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.nasdaq_regimes as nr  # noqa: E402


def toy_vol():
    idx = pd.bdate_range("2020-01-01", periods=400)
    vix = pd.Series(15.0, index=idx)
    v3 = pd.Series(18.0, index=idx)
    vix.iloc[300] = 25.0                                                    # one inverted day (VIX 25 > VIX3M 18)
    vxn = pd.Series(20.0, index=idx)
    vxn.iloc[300:] = 30.0                                                   # VXN steps up at day 300
    return idx, vix, v3, vxn


def toy_session(n, idx):
    L = 390
    rng = np.random.default_rng(2)
    base = 100 + np.cumsum(rng.normal(0, 0.01, (n, L)), axis=1)
    O = base.copy()
    C = base.copy()
    return dict(o=O, h=np.maximum(O, C) + 0.01, l=np.minimum(O, C) - 0.01, c=C)


def test_a_regime_flag_uses_the_previous_close_not_the_same_day():
    idx, vix, v3, vxn = toy_vol()
    A = toy_session(len(idx), idx)
    R = nr.regimes(idx, A, vix, v3, vxn)
    p1 = R["P1 VIX > VIX3M"]
    assert not bool(p1.iloc[300]) and bool(p1.iloc[301])                    # VIX inverted AT day 300's close: day 300 is still 'off', day 301 is 'on'
    p2 = R["P2 VXN > 1y median"]
    assert not bool(p2.iloc[300]) and bool(p2.iloc[301])


def test_the_flags_are_undefined_until_their_history_exists():
    idx, vix, v3, vxn = toy_vol()
    R = nr.regimes(idx, toy_session(len(idx), idx), vix, v3, vxn)
    assert R["P2 VXN > 1y median"].iloc[:250].isna().all() and R["P3 range > 60d median"].iloc[:60].isna().all()


def test_summary_splits_on_and_off_days_and_the_halves():
    net = np.array([0.001] * 50 + [-0.0002] * 50)
    flag = np.array([True] * 50 + [False] * 50, dtype=float)
    s = nr.summarize(net, flag, 25)
    assert abs(s["on"] - 10.0) < 1e-9 and abs(s["off"] + 2.0) < 1e-9 and abs(s["share"] - 0.5) < 1e-12
    nan_flag = flag.copy()
    nan_flag[:10] = np.nan
    assert abs(nr.summarize(net, nan_flag, 25)["share"] - 40 / 90) < 1e-12


def test_the_closing_hour_goes_with_a_big_day_and_stays_out_otherwise():
    n, L = 30, 390
    C = np.full((n, L), 100.0)
    O = C.copy()
    C[:, :] += np.linspace(0, 0.1, L)                                       # a small drift every day: mean |day return| ~ 10 bp
    C[-1, :CLOSE_MIN] = 100.0 * (1 + 0.003)                                 # the last day is up 30 bp through 15:30 ...
    C[-1, CLOSE_MIN:] = 100.0 * (1 + 0.004)                                 # ... and keeps going
    O[-1, CLOSE_MIN] = C[-1, CLOSE_MIN - 1]
    A = dict(o=O, h=np.maximum(O, C), l=np.minimum(O, C), c=C)
    net, tr = nr.close_flow(A, None, 1.0, cost=0.0)
    assert tr[-1] == 1 and abs(net[-1] - (C[-1, -1] / O[-1, CLOSE_MIN] - 1)) < 1e-12
    assert tr[:14].sum() == 0                                               # no trailing window yet: no trade


CLOSE_MIN = nr.CLOSE_MIN


def test_the_closing_hour_decides_on_what_is_known_at_1530_not_on_the_bar_that_follows():
    n, L = 30, 390
    C = np.full((n, L), 100.0)
    O = C.copy()
    C[:, :] += np.linspace(0, 0.1, L)
    C[-1, :CLOSE_MIN] = 100.0                                                # a flat day through 15:29 ...
    C[-1, CLOSE_MIN] = 100.0 * 1.01                                          # ... and the 15:30 bar jumps 100 bp: not known at the decision
    A = dict(o=O, h=np.maximum(O, C), l=np.minimum(O, C), c=C)
    net, tr = nr.close_flow(A, None, 0.5, cost=0.0001)
    assert tr[-1] == 0 and net[-1] == 0.0 and np.all(net[:14] == 0.0)        # no trade, and no cost charged on days without one


def test_a_big_down_day_is_shorted_and_costs_are_charged_per_trade():
    n, L = 30, 390
    C = np.full((n, L), 100.0)
    O = C.copy()
    C[:, :] += np.linspace(0, 0.1, L)
    C[-1, :CLOSE_MIN] = 100.0 * (1 - 0.003)
    C[-1, CLOSE_MIN:] = 100.0 * (1 - 0.004)
    O[-1, CLOSE_MIN] = C[-1, CLOSE_MIN - 1]
    A = dict(o=O, h=np.maximum(O, C), l=np.minimum(O, C), c=C)
    net, tr = nr.close_flow(A, None, 1.0, cost=0.0001)
    assert tr[-1] == 1 and abs(net[-1] - (-(C[-1, -1] / O[-1, CLOSE_MIN] - 1) - 0.0001)) < 1e-12


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
