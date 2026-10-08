"""Offline tests for backtest/rsi_only.py's trade(). No network.

    python tests/test_rsi_only.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import rsi_only as ro  # noqa: E402


def arrs(rows, rsi):
    o, h, l, c = (np.array(x, float) for x in zip(*rows))
    return o, h, l, c, np.array(rsi, float), np.zeros(len(rows))


def test_tp_no_stop_and_worst():
    o, h, l, c, r, fc = arrs([(100, 100, 100, 100), (100, 100.5, 95, 99), (99, 102.5, 98, 102), (102,) * 4, (102,) * 4],
                             [25, 25, 40, 50, 50])
    j, net, worst = ro.trade(0, 1, "tp2", o, h, l, c, r, fc, 10, 30)
    assert j == 2 and abs(net - (0.02 - ro.FEE)) < 1e-12 and abs(worst - 0.05) < 1e-12


def test_stop_first_when_both_and_gap():
    o, h, l, c, r, fc = arrs([(100, 100, 100, 100), (100, 103, 95, 99), (99,) * 4, (99,) * 4], [25, 25, 25, 25])
    j, net, _ = ro.trade(0, 1, "tp2_sl4", o, h, l, c, r, fc, 10, 30)
    assert j == 1 and abs(net - (-0.04 - ro.FEE)) < 1e-12
    o, h, l, c, r, fc = arrs([(100, 100, 100, 100), (100, 100.5, 99, 100), (90, 91, 89, 90), (90,) * 4, (90,) * 4],
                             [25] * 5)
    j, net, _ = ro.trade(0, 1, "tp2_sl4", o, h, l, c, r, fc, 10, 30)
    assert j == 2 and abs(net - (-0.10 - ro.FEE)) < 1e-12                  # gapped through the stop: the open


def test_rsi_exit_and_cap():
    o, h, l, c, r, fc = arrs([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (100, 101, 99.5, 101), (101.5, 102, 101, 101.5),
                              (101.5,) * 4], [25, 30, 55, 60, 60])
    j, net, _ = ro.trade(0, 1, "rsi50", o, h, l, c, r, fc, 10, 30)
    assert j == 3 and abs(net - (101.5 / 100 - 1 - ro.FEE)) < 1e-12         # RSI 55 at bar 2's close -> bar 3's open
    o, h, l, c, r, fc = arrs([(100, 100, 100, 100)] + [(100, 100.5, 99.5, 100)] * 6, [25] * 7)
    j, net, _ = ro.trade(0, 1, "tp2", o, h, l, c, r, fc, 3, 30)
    assert j == 4 and abs(net - (0 - ro.FEE)) < 1e-12                       # capped: out at the close


def test_short_mirror():
    o, h, l, c, r, fc = arrs([(100, 100, 100, 100), (100, 101, 97.9, 98), (98,) * 4, (98,) * 4], [75, 75, 60, 60])
    j, net, _ = ro.trade(0, -1, "tp2", o, h, l, c, r, fc, 10, 30)
    assert j == 1 and abs(net - (0.02 - ro.FEE)) < 1e-12


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
