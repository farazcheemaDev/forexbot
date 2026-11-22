"""Tests for backtest/his_exit_shape.py: the quote convention, first-touch logic, entry hour and the clustered t.

Run as a script (no pytest on this PC):  python tests/test_his_exit_shape.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.his_exit_shape as es  # noqa: E402


def ticks():
    ts = np.arange(0, 100, 1.0)
    mid = np.full(100, 100.0)
    spr = np.full(100, 2.0)
    return ts, mid, spr


def test_an_instant_round_trip_costs_exactly_the_spread_for_both_sides():
    ts, mid, spr = ticks()
    for s in (1, -1):
        p = es.path_points(ts, mid, spr, 10.0, s)
        assert np.allclose(p, -2.0)


def test_a_long_enters_at_the_ask_and_exits_at_the_bid_a_short_the_reverse():
    ts, mid, spr = ticks()
    mid = mid.copy()
    mid[20:] = 110.0                                            # +10 in the mid
    assert abs(es.path_points(ts, mid, spr, 10.0, 1)[-1] - (110 - 1 - (100 + 1))) < 1e-9     # bid 109 - ask 101 = +8
    assert abs(es.path_points(ts, mid, spr, 10.0, -1)[-1] - (-(110 + 1 - (100 - 1)))) < 1e-9  # a short loses 12 (buys back at the ask 111 after selling at 99)


def test_the_first_touch_decides_and_a_tie_goes_to_the_stop():
    p = np.array([1.0, 2.0, 8.0, -5.0])
    up, dn, end = es.first_hits(p)
    assert es.outcome(up, dn, end, 7, None) == 7 and es.outcome(up, dn, end, 7, 10) == 7
    p = np.array([-4.0, 8.0])
    up, dn, end = es.first_hits(p)
    assert es.outcome(up, dn, end, 7, 10) == 7.0                # -4 never reaches the 10-point stop: the target is touched
    p = np.array([-12.0, 9.0, -8.0])
    up, dn, end = es.first_hits(p)
    assert es.outcome(up, dn, end, 7, 10) == -10.0
    p = np.array([1.0, 2.0, 3.0])
    up, dn, end = es.first_hits(p)
    assert es.outcome(up, dn, end, 7, None) == 3.0 and es.outcome(up, dn, end, 7, 10) == 3.0     # neither touched: the last tick
    p = np.array([8.0, -11.0])
    up, dn, end = es.first_hits(p)
    assert es.outcome(up, dn, end, 7, 10) == 7 and es.outcome(up, dn, end, 7, None) == 7      # the target came first
    p = np.array([-11.0, 8.0])
    up, dn, end = es.first_hits(p)
    assert es.outcome(up, dn, end, 7, 10) == -10.0 and es.outcome(up, dn, end, 7, None) == 7  # no stop: it recovers and takes the 7


def test_a_price_exactly_on_the_target_or_the_stop_counts_as_touching_it():
    up, dn, end = es.first_hits(np.array([7.0, -3.0]))
    assert es.outcome(up, dn, end, 7, None) == 7.0                                  # the target is reached at exactly +7, then it falls back
    up, dn, end = es.first_hits(np.array([-10.0, 4.0]))
    assert es.outcome(up, dn, end, 7, 10) == -10.0                                  # the stop is reached at exactly -10, then it recovers


def test_entry_hour_is_new_york_time_from_the_0930_open():
    assert es.hour_of(0) == 9 and es.hour_of(1799) == 9 and es.hour_of(1800) == 10 and es.hour_of(5399) == 10 and es.hour_of(5400) == 11 and es.hour_of(23000) == 15


def test_day_clustered_t_is_smaller_than_the_naive_t_when_days_move_together():
    x = np.array([5.0, 5.0, 5.0, 5.0, -5.0, -5.0, -5.0, -5.0, 1.0, 1.0])
    day = np.array([1, 1, 1, 1, 2, 2, 2, 2, 3, 3])
    m, t = es.clustered_t(x, day)
    naive = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    assert abs(m - x.mean()) < 1e-12 and abs(t) < abs(naive)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
