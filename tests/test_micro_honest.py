"""Offline test: backtest/micro_honest.py's vectorised exit path equals micro_bot.manage() run bar by bar.

    python tests/test_micro_honest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import micro_bot as mb  # noqa: E402
from backtest import micro_honest as mh  # noqa: E402
from longtrend_bot import atr  # noqa: E402


def fake_coin(n, seed):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(0.004 * rng.standard_normal(n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + 0.002 * np.abs(rng.standard_normal(n)))
    l = np.minimum(o, c) * (1 - 0.002 * np.abs(rng.standard_normal(n)))
    cn = object.__new__(mh.Coin)
    cn.o, cn.h, cn.l, cn.c = o, h, l, c
    cn.a = atr(pd.DataFrame(dict(high=h, low=l, close=c)), mb.ATR_PERIOD).to_numpy(float)
    cn._paths = {}
    return cn


def by_manage(cn, i, d):
    rec = dict(side="long" if d > 0 else "short", entry=cn.c[i], risk=mb.SL_MULT * cn.a[i],
               stop=cn.c[i] - d * mb.SL_MULT * cn.a[i], water=cn.h[i] if d > 0 else cn.l[i], bars=0, entry_bar=i)
    for t in range(i + 1, len(cn.c) - 1):
        if mb.manage(rec, t, cn.h[t], cn.l[t], cn.a[t]) is not None:
            return t
    return len(cn.c) - 2


def test_path_equals_manage():
    checked = 0
    for seed in range(4):
        cn = fake_coin(6000, seed)
        for i in range(50, 5000, 37):
            for d in (1, -1):
                assert cn.path(i, d) == by_manage(cn, i, d), (seed, i, d)
                checked += 1
    assert checked > 500


if __name__ == "__main__":
    test_path_equals_manage()
    print("PASS test_path_equals_manage\n\n1 passed")
