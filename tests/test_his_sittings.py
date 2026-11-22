"""Tests for backtest/his_sittings.py: sitting boundaries and ticket order.

Run as a script (no pytest on this PC):  python tests/test_his_sittings.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest.his_sittings import sittings  # noqa: E402


def frame(minutes):
    base = pd.Timestamp("2026-05-04 14:00:00")
    return pd.DataFrame({"o": [base + pd.Timedelta(minutes=m) for m in minutes], "pts": 1.0, "mae": -1.0, "hold": 10.0})


def test_a_gap_over_thirty_minutes_starts_a_new_sitting():
    d = sittings(frame([0, 10, 100]))
    assert list(d.sit) == [0, 0, 1] and list(d.k) == [0, 1, 0]


def test_exactly_thirty_minutes_stays_in_the_same_sitting():
    d = sittings(frame([0, 30]))
    assert list(d.sit) == [0, 0] and list(d.k) == [0, 1]
    d = sittings(frame([0, 30.01]))
    assert list(d.sit) == [0, 1]


def test_input_order_does_not_matter_and_k_counts_in_time_order():
    d = sittings(frame([20, 0, 10]))
    assert list(d.k) == [0, 1, 2] and d.o.is_monotonic_increasing


def test_a_single_trade_is_its_own_first_ticket():
    d = sittings(frame([0]))
    assert list(d.sit) == [0] and list(d.k) == [0]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
