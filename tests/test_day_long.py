"""Offline tests for backtest/day_long.py. No network.

  outcome    a hand-built 3-day hourly path: entry at day 2's 00:00 open, exit at day 3's 00:00 open, fees, funding
             only for settlements after the entry, the worst drop from the hourly lows
  causal     no condition on day i moves when later days change - 120 cuts, both directions
  play       fixed and all-in arithmetic, and a liquidation

    python tests/test_day_long.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import day_long as dl  # noqa: E402


def hours(n_days, price_fn):
    t = pd.date_range("2024-01-01", periods=24 * n_days, freq="h").astype("datetime64[ns]")
    p = np.array([price_fn(k) for k in range(len(t))], float)
    return pd.DataFrame({"open": p, "high": p * 1.001, "low": p * 0.999, "close": p, "qvol": 1.0}, index=t)


def test_outcome():
    h = hours(3, lambda k: 100.0 if k < 24 else (100.0 + (k - 24) * 0.1 if k < 48 else 110.0))
    h.loc[pd.Timestamp("2024-01-02 13:00"), "low"] = 95.0                  # a dip inside the held day
    d = dl.daily_bars(h)
    fund = pd.Series([0.001, 0.0005, 0.0002], index=pd.DatetimeIndex(
        ["2024-01-02 00:00", "2024-01-02 08:00", "2024-01-03 00:00"]).astype("datetime64[ns]"))
    net, worst = dl.outcomes(pd.concat([d, d.iloc[[-1]].set_axis([d.index[-1] + pd.Timedelta(days=1)])]),
                             pd.concat([h, hours(1, lambda k: 110.0).set_axis(
                                 pd.date_range("2024-01-04", periods=24, freq="h").astype("datetime64[ns]"))]), fund)
    e, x = 100.0, 110.0                                                    # day 2 00:00 open, day 3 00:00 open
    assert abs(net[0] - (x / e - 1 - dl.FEE - (0.0005 + 0.0002))) < 1e-12  # the 00:00 entry settlement is NOT paid
    assert abs(worst[0] - (1 - 95.0 / e)) < 1e-12


def test_causal():
    rng = np.random.default_rng(1)
    n = 24 * 400
    p = 100 * np.exp(np.cumsum(0.004 * rng.standard_normal(n)))
    h = pd.DataFrame({"open": np.r_[p[0], p[:-1]], "high": p * 1.002, "low": p * 0.998, "close": p,
                      "qvol": np.exp(rng.standard_normal(n))},
                     index=pd.date_range("2022-01-01", periods=n, freq="h").astype("datetime64[ns]"))
    d0 = dl.daily_bars(h)
    btc0 = d0.c * 1.5
    f0 = pd.Series(rng.standard_normal(len(d0)) * 1e-4, index=d0.index)
    c0, _ = dl.conditions(d0, btc0, f0)
    fired = {k: int(v.sum()) for k, v in c0.items()}
    assert min(fired.values()) >= 3, fired                     # a condition that never fires tests nothing
    for j, cut in enumerate(range(220, 399, 3)):
        d1, btc1, f1 = d0.copy(), btc0.copy(), f0.copy()
        k = 1.05 if j % 2 else 0.95
        d1.iloc[cut + 1:, :4] *= k
        d1.iloc[cut + 1:, 4] *= 3
        btc1.iloc[cut + 1:] *= 2 - k
        f1.iloc[cut + 1:] *= -1
        c1, _ = dl.conditions(d1, btc1, f1)
        for name in c0:
            assert np.array_equal(c0[name][:cut + 1], c1[name][:cut + 1]), (name, cut)


def test_play():
    net, worst = np.array([0.01, -0.005]), np.array([0.002, 0.01])
    f = dl.play(net, worst, 10, "fixed")
    assert abs(f["total"] - dl.STAKE * (0.10 - 0.05)) < 1e-9 and f["liqs"] == 0
    f = dl.play(net, np.array([0.002, 0.05]), 20, "fixed")                 # 5% drop at 20x: liquidated
    assert f["liqs"] == 1 and abs(f["worst"] + dl.STAKE) < 1e-9
    a = dl.play(net, worst, 10, "allin")
    assert abs(a["end"] - dl.STAKE * 1.10 * 0.95) < 1e-9


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
