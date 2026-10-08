"""Offline tests for backtest/scalp_15m.py: the 15-minute gap mask and the 10,000 PKR path. No network.

    python tests/test_scalp_15m.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import odds_now as on  # noqa: E402
from backtest import scalp_1m as sc  # noqa: E402
from backtest import scalp_15m as s15  # noqa: E402


def test_valid_mask_15m_step_and_gap():
    n = 1000
    t = pd.date_range("2024-01-01", periods=n, freq="15min")
    t = t.where(np.arange(n) < 500, t + pd.Timedelta(minutes=45))          # one 45-minute hole
    c = 100 * np.exp(np.cumsum(0.001 * np.random.default_rng(0).standard_normal(n)))
    d = pd.DataFrame(dict(time=t.astype("datetime64[ns]"), o=np.r_[c[0], c[:-1]], h=c * 1.001, l=c * 0.999, c=c))
    ok = s15.valid_mask(d)
    i = np.arange(n)
    assert ok[(i > on.WARMUP) & (i < 500 - sc.HOLD - 1)].all()             # a regular 15m grid is valid
    assert not ok[(i >= 500 - sc.HOLD - 1) & (i < 500 + on.WARMUP - 1)].any()


def test_path():
    end, under = s15.path(np.array([1.0, 1.0]), 10)                       # +1% of position at 10x = +10% a trade
    assert abs(end - s15.STAKE * 1.1 ** 2) < 1e-6 and under is None
    end, under = s15.path(np.array([1.0, -9.6]), 10)                       # 9.6% against at 10x: liquidated
    assert end == 0.0 and under == 2


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
