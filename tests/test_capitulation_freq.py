"""Offline test for backtest/capitulation_freq.py's 3-slot account. No network.

    python tests/test_capitulation_freq.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import capitulation_freq as cf  # noqa: E402


def T(rows):
    return pd.DataFrame(rows, columns=["t_in", "t_out", "net", "worst"]).assign(
        t_in=lambda d: pd.to_datetime(d.t_in), t_out=lambda d: pd.to_datetime(d.t_out))


def test_slots_skip_and_release():
    rows = [("2024-01-01 00:00", "2024-01-02", 0.02, 0.01)] * 4 + [("2024-01-03 00:00", "2024-01-04", 0.02, 0.01)]
    end, taken, skipped = cf.account(T(rows), 1)
    assert taken == 4 and skipped == 1                               # the 4th same-time signal finds 3 slots full
    third = cf.STAKE / 3
    assert abs(end - (cf.STAKE + 3 * third * 0.02 + (cf.STAKE + 3 * third * 0.02) / 3 * 0.02)) < 1e-6


def test_liquidation_takes_the_slot():
    end, taken, _ = cf.account(T([("2024-01-01", "2024-01-02", 0.01, 0.40)]), 3)    # a 40% dip at 3x
    assert taken == 1 and abs(end - cf.STAKE * 2 / 3) < 1e-6


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
