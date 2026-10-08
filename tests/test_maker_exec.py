"""Offline tests for backtest/maker_exec.py - the limit-order fill rules. No network.

    python tests/test_maker_exec.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import maker_exec as mx  # noqa: E402


def arr(rows):
    return tuple(np.array(x, float) for x in zip(*rows))     # o, h, l, c


def test_touch_is_not_a_fill():
    o, h, l, c = arr([(100, 100, 100, 100), (100, 100.5, 100.0, 100.2), (100.2, 100.6, 99.99, 100.1)])
    assert mx.limit_fill(0, 1, 100.0, h, l) == 2               # minute 1 only touched 100; minute 2 went through
    assert mx.limit_fill(0, -1, 100.5, h, l) == 2             # sell at 100.5: minute 1 touched, minute 2 through
    assert mx.limit_fill(0, 1, 99.0, h, l) == -1


def test_model_trade_maker_exit_and_market_fallback():
    rows = [(100, 100, 100, 100), (100, 100.1, 99.9, 100.05)] + [(100.05, 100.3, 100.0, 100.2)] * 6
    o, h, l, c = arr(rows)
    g, mk, tk, ex = mx.model_trade(0, 1, 2, o, h, l, c)       # fill at minute 1; exit limit at c[3], sells through at 4
    assert abs(g - (100.2 / 100 - 1)) < 1e-12 and mk == 2 and tk == 0 and ex == 4
    rows2 = [(100, 100, 100, 100), (100, 100.1, 99.9, 100.05)] + [(100.2, 100.2, 100.1, 100.2)] * 7
    o, h, l, c = arr(rows2)
    g, mk, tk, ex = mx.model_trade(0, 1, 2, o, h, l, c)       # exit limit at 100.2 never traded through
    assert mk == 1 and tk == 1 and ex == 3 + mx.W


def test_rule_trade_short_stop_first_gap_and_target():
    atr = 0.5                                                 # R = 1.0
    base = [(100, 100, 100, 100), (100, 100.2, 99.9, 100.1)]  # sell limit at 100 fills in minute 1
    o, h, l, c = arr(base + [(100.1, 101.5, 97.5, 99)] + [(99, 99, 99, 99)] * 70)
    g, mk, tk, _ = mx.rule_trade(0, -1, atr, o, h, l, c)      # minute 2 touches stop 101 and target 98: stop
    assert abs(g - (-0.01)) < 1e-12 and tk == 1
    o, h, l, c = arr(base + [(102, 102.5, 101.8, 102.2)] + [(99, 99, 99, 99)] * 70)
    g, _, _, _ = mx.rule_trade(0, -1, atr, o, h, l, c)        # gaps above the stop: filled at the open
    assert abs(g - (-0.02)) < 1e-12
    o, h, l, c = arr(base + [(100, 100.3, 98.0, 98.5), (98.5, 98.9, 97.9, 98.2)] + [(98, 98, 98, 98)] * 70)
    g, mk, tk, _ = mx.rule_trade(0, -1, atr, o, h, l, c)      # minute 2 only touches 98; minute 3 goes through
    assert abs(g - 0.02) < 1e-12 and mk == 2 and tk == 0


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
