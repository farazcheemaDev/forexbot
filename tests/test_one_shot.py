"""Offline tests for backtest/one_shot.py. No network.

  shot_*          a hand-built path: double, liquidation, a minute touching both (= liquidation), the time cap
  setups_causal   no setup at minute i moves when anything after i changes - 745 cuts, both directions, on data where every setup fires often

    python tests/test_one_shot.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import one_shot as os_  # noqa: E402

LV = os_.levels()                       # 40x: liquidation 1.94% away, double needs +2.62%


def path(rows):
    o = np.array([100.0] + [r[0] for r in rows])
    h = np.array([100.0] + [r[1] for r in rows])
    l = np.array([100.0] + [r[2] for r in rows])
    c = np.array([100.0] + [r[3] for r in rows])
    return o, h, l, c


def at40(rows, side=1):
    return os_.shot(0, side, *path(rows), LV)[(40, 1)]


def test_shot_double():
    assert at40([(100, 101, 99.5, 100.5), (100.5, 102.7, 100, 102.6)]) == 2.0


def test_shot_liquidation():
    assert at40([(100, 100.5, 98.0, 98.5), (98.5, 110, 98, 109)]) == 0.0


def test_shot_same_minute_is_liquidation():
    assert at40([(100, 103, 97.9, 101)]) == 0.0


def test_shot_cap_closes_at_market():
    got = at40([(100, 100.6, 99.5, 100.2), (100.2, 100.7, 99.8, 100.5)])
    assert abs(got - (1 + 40 * 0.005 - 40 * os_.FEE)) < 1e-9


def test_shot_short_mirror():
    assert at40([(100, 100.5, 97.3, 97.4)], side=-1) == 2.0
    assert at40([(100, 102.0, 99.9, 101.9)], side=-1) == 0.0


def frame(n, seed):
    """Swinging prices and frequent volume spikes, so every setup fires often: a one-bar leak has to show."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    c = 100 * np.exp(0.02 * np.sin(2 * np.pi * t / 90) + np.cumsum(0.001 * rng.standard_normal(n)))
    o = np.r_[c[0], c[:-1]]
    v = 1.0 + 9.0 * ((t % 150 < 20) | (rng.random(n) < 0.1))        # volume bursts and lone spikes
    buy = np.clip(0.5 + 200 * (c - o) / o + 0.05 * rng.standard_normal(n), 0.05, 0.95)
    return pd.DataFrame(dict(o=o, h=np.maximum(o, c) * 1.0003, l=np.minimum(o, c) * 0.9997, c=c, v=v,
                             tbv=v * buy))


def test_setups_causal():
    d0, btc0 = frame(3000, 1), frame(3000, 2).c.to_numpy()
    s0 = os_.setups(d0, btc0)
    fired = {(nm, side): int(x.sum()) for nm, pair in s0.items() for side, x in zip(("long", "short"), pair)}
    assert min(fired.values()) > 20, fired          # every side of every setup must be exercised
    for j, cut in enumerate(range(1500, 2990, 2)):
        d1, btc1 = d0.copy(), btc0.copy()
        k = 1.02 if j % 2 else 0.98
        d1.loc[cut + 1:, ["o", "h", "l", "c"]] *= k
        d1.loc[cut + 1:, ["v", "tbv"]] *= 3 if j % 3 else 0.3
        btc1[cut + 1:] *= 2 - k
        s1 = os_.setups(d1, btc1)
        for nm in s0:
            for a, b in zip(s0[nm], s1[nm]):
                assert np.array_equal(a[:cut + 1], b[:cut + 1]), (nm, cut)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
