"""Offline tests for backtest/btc_doge.py. No network, no data files.

  features_causal   no feature at minute i moves when anything after i changes - 150 cut points, both
                    directions, both coins (a single cut point missed a planted leak in scalp_1m)
  target_alignment  the target is DOGE's next open -> close h minutes later, nothing earlier
  take              one trade at a time, the next one after the exit

    python tests/test_btc_doge.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import btc_doge as bd  # noqa: E402


def aligned(n, seed):
    rng = np.random.default_rng(seed)
    cols = {"time": pd.date_range("2024-01-01", periods=n, freq="min").astype("datetime64[ns]")}
    for s, p0 in (("d", 0.1), ("b", 50000.0)):
        c = p0 * np.exp(np.cumsum(0.001 * rng.standard_normal(n)))
        o = np.r_[c[0], c[:-1]]
        cols |= {f"o_{s}": o, f"c_{s}": c,
                 f"h_{s}": np.maximum(o, c) * (1 + 0.0003 * np.abs(rng.standard_normal(n))),
                 f"l_{s}": np.minimum(o, c) * (1 - 0.0003 * np.abs(rng.standard_normal(n)))}
    return pd.DataFrame(cols)


def test_features_causal():
    m0 = aligned(2600, 1)
    X0 = bd.make(m0)[1]
    for j, cut in enumerate(range(1800, 2550, 5)):
        m1 = m0.copy()
        k = 1.01 if j % 2 else 0.99
        coin = "d" if j % 4 < 2 else "b"
        for col in "ohlc":
            m1.loc[cut + 1:, f"{col}_{coin}"] *= k
        X1 = bd.make(m1)[1]
        assert np.array_equal(X0[:cut + 1], X1[:cut + 1], equal_nan=True), cut


def test_target_alignment():
    m = aligned(2600, 2)
    _, _, _, Y, ok, _, (od, hd, ld) = bd.make(m)
    cd = m.c_d.to_numpy()
    for h in bd.HS:
        i = 2000
        assert abs(Y[h][i] - (cd[i + h] / od[i + 1] - 1)) < 1e-12
        assert np.isnan(Y[h][-1])


def test_take():
    assert bd.take(np.array([0, 2, 5, 6, 11]), 5).tolist() == [0, 5, 11]


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
