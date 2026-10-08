"""Offline tests for backtest/rsi_confluence.py. No network.

  outcome_equals_trade   the vectorised exits equal rsi_factors.trade() (already tested) on random paths, all 3 exits,
                         both sides
  htf_causal             the higher-timeframe RSI at a bar never moves when later bars change (60 cuts)
  confirmations_causal   no confirmation at bar i moves when later bars change

    python tests/test_rsi_confluence.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import rsi_confluence as rc  # noqa: E402
from backtest import rsi_factors as rf  # noqa: E402

MAP = {"tp2": ("tp2", "none"), "tp2_nw": ("tp2", "not_working"), "rsi50": ("rsi50", "none")}


def frame(n, seed):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(0.006 * rng.standard_normal(n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame(dict(time=pd.date_range("2023-01-01", periods=n, freq="15min").astype("datetime64[ns]"),
                             o=o, h=np.maximum(o, c) * (1 + 0.003 * np.abs(rng.standard_normal(n))),
                             l=np.minimum(o, c) * (1 - 0.003 * np.abs(rng.standard_normal(n))), c=c,
                             v=np.exp(rng.standard_normal(n))))


def test_outcome_equals_trade():
    checked = 0
    for seed in range(3):
        d = frame(3000, seed)
        P = rf.prep(d, d.c.to_numpy() * 2)
        fc = np.cumsum(np.random.default_rng(seed + 9).normal(0, 0.01, len(d)))
        for i in range(260, 2900, 23):
            for side in (1, -1):
                for ex, (prof, fac) in MAP.items():
                    a = rc.outcome(i, side, ex, P, fc, 200)
                    b = rf.trade(i, side, prof, fac, P, fc, 200)
                    assert a[0] == b[0] and abs(a[1] - b[1]) < 1e-12 and abs(a[2] - b[2]) < 1e-12, (seed, i, side, ex, a, b)
                    checked += 1
    assert checked > 1000


def test_htf_causal():
    d0 = frame(4000, 5)
    h0 = rc.htf_rsi(d0, 4, 1)
    for j, cut in enumerate(range(1000, 3900, 49)):
        d1 = d0.copy()
        d1.loc[cut + 1:, ["o", "h", "l", "c"]] *= 1.03 if j % 2 else 0.97
        h1 = rc.htf_rsi(d1, 4, 1)
        assert np.array_equal(h0[:cut + 1], h1[:cut + 1], equal_nan=True), cut


def test_confirmations_causal():
    d0 = frame(1500, 7)
    P0 = rf.prep(d0, d0.c.to_numpy() * 2)
    e0 = pd.Series(P0["btc"]).ewm(span=200, adjust=False).mean().to_numpy()
    h0 = rc.htf_rsi(d0, 4, 1)
    for i in range(300, 1400, 37):
        d1 = d0.copy()
        d1.loc[i + 1:, ["o", "h", "l", "c", "v"]] *= 1.5
        P1 = rf.prep(d1, d1.c.to_numpy() * 2)
        e1 = pd.Series(P1["btc"]).ewm(span=200, adjust=False).mean().to_numpy()
        h1 = rc.htf_rsi(d1, 4, 1)
        for side in (1, -1):
            assert rc.confirmations(i, side, P0, h0, e0) == rc.confirmations(i, side, P1, h1, e1), (i, side)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
