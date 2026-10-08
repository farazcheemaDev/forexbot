"""Offline tests for backtest/doge_focus.py's exits. No network.

    python tests/test_doge_focus.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import doge_focus as df_  # noqa: E402
from backtest import rsi_confluence as rc  # noqa: E402
from backtest import rsi_factors as rf  # noqa: E402


def frame(n, seed):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(0.006 * rng.standard_normal(n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame(dict(time=pd.date_range("2023-01-01", periods=n, freq="h").astype("datetime64[ns]"), o=o,
                             h=np.maximum(o, c) * (1 + 0.003 * np.abs(rng.standard_normal(n))),
                             l=np.minimum(o, c) * (1 - 0.003 * np.abs(rng.standard_normal(n))), c=c,
                             v=np.exp(rng.standard_normal(n))))


def test_exit_target_equals_tested_outcome():
    d = frame(3000, 1)
    P = rf.prep(d, d.c.to_numpy())
    fc = np.cumsum(np.random.default_rng(3).normal(0, 0.01, len(d)))
    for i in range(260, 2900, 31):
        for side in (1, -1):
            for ex, args in (("tp2", (0.02, None, None)), ("tp2_nw", (0.02, None, 24)), ("rsi50", (None, 50.0, None))):
                a = rc.outcome(i, side, ex, P, fc, 200)
                b = df_.exit_target(i, side, *args, P, fc, 200)
                assert a[0] == b[0] and abs(a[1] - b[1]) < 1e-12 and abs(a[2] - b[2]) < 1e-12, (i, side, ex)


def P_of(rows, atr=1.0):
    o, h, l, c = (np.array(x, float) for x in zip(*rows))
    return dict(o=o, h=h, l=l, c=c, atr=np.full(len(o), atr))


def test_exit_trail_paths():
    fc = np.zeros(20)
    # long, entry 100 (o[1]), stop 98 (2 x ATR): bar 2 low 97.5 -> stopped at 98
    P = P_of([(100, 100, 100, 100), (100, 101, 99, 100.5), (100.5, 101, 97.5, 98)] + [(98,) * 4] * 5)
    j, net, worst, _ = df_.exit_trail(0, 1, 3.0, P, fc, s0=2.0)
    assert j == 2 and abs(net - (-0.02 - df_.FEE)) < 1e-12
    # gap through the stop: bar 2 opens at 95 -> filled at 95
    P = P_of([(100, 100, 100, 100), (100, 101, 99, 100.5), (95, 96, 94, 95)] + [(95,) * 4] * 5)
    j, net, _, _ = df_.exit_trail(0, 1, 3.0, P, fc, s0=2.0)
    assert j == 2 and abs(net - (-0.05 - df_.FEE)) < 1e-12
    # the trail ratchets: high 110 at bar 2 -> stop 107 (3 x ATR); bar 3 low 106.9 -> out at 107
    P = P_of([(100, 100, 100, 100), (100, 101, 99.5, 100.5), (100.5, 110, 100.5, 109), (109, 109.5, 106.9, 107)]
             + [(107,) * 4] * 5)
    j, net, _, _ = df_.exit_trail(0, 1, 3.0, P, fc, s0=2.0)
    assert j == 3 and abs(net - (0.07 - df_.FEE)) < 1e-12
    # breakeven: 1R = 2; best 106.5 (>= 3R) with a wide trail -> the stop is lifted to the entry
    P = P_of([(100, 100, 100, 100), (100, 101, 99.5, 100.5), (100.5, 106.5, 100.5, 106), (106, 106, 99.9, 100)]
             + [(100,) * 4] * 5)
    j, net, _, _ = df_.exit_trail(0, 1, 20.0, P, fc, s0=2.0, be=3.0)
    assert j == 3 and abs(net - (0.0 - df_.FEE)) < 1e-12


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
