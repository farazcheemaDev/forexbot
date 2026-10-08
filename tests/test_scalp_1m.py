"""Offline tests for backtest/scalp_1m.py. No network.

  rules_causal     no signal at bar i moves when bars after i change (BTC-lead included)
  leverage_path    1 + lev x net% per trade; a loss reaching 1/lev - maintenance wipes the margin
  valid_mask       no window crosses a missing minute

    python tests/test_scalp_1m.py
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


def frame(n, seed, gap_at=None):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(0.001 * rng.standard_normal(n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + 0.0003 * np.abs(rng.standard_normal(n)))
    l = np.minimum(o, c) * (1 - 0.0003 * np.abs(rng.standard_normal(n)))
    t = pd.date_range("2024-01-01", periods=n, freq="min")
    if gap_at is not None:
        t = t.where(np.arange(n) < gap_at, t + pd.Timedelta(minutes=30))
    return pd.DataFrame(dict(time=t.astype("datetime64[ns]"), o=o, h=h, l=l, c=c))


def test_rules_causal():
    """Many cut points, future moved up AND down: a rule that reads bar i+1 must flip somewhere.
    (One cut point did not catch a planted shift(-1) - signals are too sparse.)"""
    d0 = frame(3000, 1)
    btc0 = frame(3000, 2).c.to_numpy()
    r0 = sc.rules(d0, on.features(d0.o, d0.h, d0.l, d0.c), btc0)
    assert "btc_lead" in r0
    for j, cut in enumerate(range(1600, 2950, 9)):
        m = 1.02 if j % 2 else 0.98
        d1, btc1 = d0.copy(), btc0.copy()
        d1.loc[cut + 1:, ["o", "h", "l", "c"]] *= m
        btc1[cut + 1:] *= 2 - m
        r1 = sc.rules(d1, on.features(d1.o, d1.h, d1.l, d1.c), btc1)
        for k in r0:
            for a, b in zip(r0[k], r1[k]):
                assert np.array_equal(a[:cut + 1], b[:cut + 1]), (k, cut)


def test_leverage_path():
    fin, _, ruin = sc.leverage_path(np.array([0.1, 0.1]), 40)
    assert abs(fin - sc.START_PKR * 1.04 ** 2) < 1e-6 and ruin is None
    fin, low, ruin = sc.leverage_path(np.array([0.1, -2.0, 0.1]), 40)     # 2.5% - 0.5% maintenance
    assert fin == 0.0 and low == 0.0 and ruin == 2
    fin, _, _ = sc.leverage_path(np.array([-1.9]), 40)                    # survives, -76%
    assert abs(fin - sc.START_PKR * (1 - 0.76)) < 1e-6


def test_valid_mask_rejects_windows_across_a_gap():
    d = frame(1000, 3, gap_at=500)
    ok = sc.valid_mask(d)
    i = np.arange(1000)
    assert ok[i < 500 - sc.HOLD - 1].any() and ok[i > 500 + on.WARMUP].any()
    assert not ok[(i >= 500 - sc.HOLD - 1) & (i < 500 + on.WARMUP - 1)].any()


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
