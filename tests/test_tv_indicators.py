"""Offline tests for backtest/tv_indicators.py: wma matches the textbook, and no indicator's entry / exit at bar i moves
when later bars change (looped indicators - SuperTrend, PSAR, Heikin-Ashi - included). No network.

    python tests/test_tv_indicators.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import rsi_factors as rf  # noqa: E402
from backtest import tv_indicators as tv  # noqa: E402


def frame(n, seed):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    c = 100 * np.exp(0.03 * np.sin(2 * np.pi * t / 60) + np.cumsum(0.008 * rng.standard_normal(n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame(dict(time=pd.date_range("2023-01-01", periods=n, freq="4h").astype("datetime64[ns]"), o=o,
                             h=np.maximum(o, c) * (1 + 0.004 * np.abs(rng.standard_normal(n))),
                             l=np.minimum(o, c) * (1 - 0.004 * np.abs(rng.standard_normal(n))), c=c,
                             v=np.exp(rng.standard_normal(n))))


def test_wma():
    x = np.arange(1, 11, dtype=float)
    w = tv.wma(x, 3)
    assert np.isnan(w[1]) and abs(w[2] - (1 * 1 + 2 * 2 + 3 * 3) / 6) < 1e-12 and abs(w[9] - (8 + 18 + 30) / 6) < 1e-12


def test_causal():
    d0 = frame(900, 4)
    i0 = tv.indicators(rf.prep(d0, d0.c.to_numpy()))
    fired = {k: int(np.nan_to_num(a).astype(bool).sum()) for k, (a, _) in i0.items()}
    assert min(fired.values()) >= 3, fired
    for j, cut in enumerate(range(300, 880, 11)):
        d1 = d0.copy()
        d1.loc[cut + 1:, ["o", "h", "l", "c"]] *= 1.04 if j % 2 else 0.96
        d1.loc[cut + 1:, "v"] *= 3
        i1 = tv.indicators(rf.prep(d1, d1.c.to_numpy()))
        for k in i0:
            for a, b in zip(i0[k], i1[k]):
                a = np.nan_to_num(np.asarray(a, float))
                b = np.nan_to_num(np.asarray(b, float))
                assert np.array_equal(a[:cut + 1], b[:cut + 1]), (k, cut)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
