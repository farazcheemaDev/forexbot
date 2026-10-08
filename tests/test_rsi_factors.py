"""Offline tests for backtest/rsi_factors.py's trade(): each protective factor fires when it should, reads only what
was known, and the disaster stop beats the target inside one bar. No network.

    python tests/test_rsi_factors.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import rsi_factors as rf  # noqa: E402


def P(rows, rsi, btc=None, vol=None, lo50=95.0, hi50=105.0, atr=1.0):
    o, h, l, c = (np.array(x, float) for x in zip(*rows))
    n = len(o)
    return dict(o=o, h=h, l=l, c=c, r=np.array(rsi, float), v=np.array(vol if vol else [1.0] * n, float),
                vavg=np.ones(n), atr=np.full(n, atr), ema200=np.full(n, 100.0),
                lo50=np.array(lo50, float) if np.ndim(lo50) else np.full(n, lo50),
                hi50=np.full(n, hi50), btc=np.array(btc if btc else [100.0] * n, float))


FLAT = (100, 100.5, 99.5, 100)


def test_level_break_uses_the_pre_entry_low():
    # the rolling 50-bar low drops to 94 once bar 2 prints it: a leak would read 94 and never fire on a 94.5 close
    p = P([FLAT, FLAT, (99, 99.5, 94, 94.5)] + [FLAT] * 7, [25, 26] + [20] * 8, lo50=[95, 95] + [94] * 8)
    j, net, _ = rf.trade(0, 1, "tp2", "level_break", p, np.zeros(10), 20)
    assert j == 3 and abs(net - (100 / 100 - 1 - rf.FEE)) < 1e-12          # close 94.5 < 95 -> out at bar 3's open


def test_btc_against_and_not_working():
    p = P([FLAT] * 6, [25] * 6, btc=[100, 100, 98, 96.5, 96, 96])
    j, _, _ = rf.trade(0, 1, "tp2", "btc_against", p, np.zeros(6), 10)
    assert j == 4                                                           # BTC -3.5% at bar 3's close
    p = P([FLAT] * 30, [25] * 30)
    j, _, _ = rf.trade(0, 1, "tp2", "not_working", p, np.zeros(30), 40)
    assert j == 25                                                          # 24 bars, not in profit -> out next open


def test_atr6_beats_the_target_in_one_bar_and_none_holds():
    p = P([FLAT, (100, 103, 93, 99), FLAT, FLAT], [25] * 4)
    j, net, worst = rf.trade(0, 1, "tp2", "atr6", p, np.zeros(4), 10)
    assert j == 1 and abs(net - (-0.06 - rf.FEE)) < 1e-12
    j, net, _ = rf.trade(0, 1, "tp2", "none", p, np.zeros(4), 10)
    assert j == 1 and abs(net - (0.02 - rf.FEE)) < 1e-12                    # without protection: the target


def test_vol_against_needs_a_losing_red_spike():
    p = P([FLAT, (100, 100.2, 98, 98.5), FLAT, FLAT], [25] * 4, vol=[1, 5, 1, 1])
    j, _, _ = rf.trade(0, 1, "tp2", "vol_against", p, np.zeros(4), 10)
    assert j == 2
    p = P([FLAT, (100, 101.5, 99.8, 101)] + [FLAT] * 6, [25] * 8, vol=[1, 5] + [1] * 6)
    j, _, _ = rf.trade(0, 1, "tp2", "vol_against", p, np.zeros(8), 10)
    assert j == 6                                                           # a green spike in profit: held to the data end


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
