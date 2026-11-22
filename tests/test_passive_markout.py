"""Tests for backtest/passive_markout.py: the sign convention, the touch-only fill definition, the timestamp rule and the clustered standard error.

Run as a script (no pytest on this PC):  python tests/test_passive_markout.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest.passive_markout import block_mean_se, markouts  # noqa: E402


def states():
    # times in ms: 1000 bid 100 / ask 102 (mid 101); 6000 bid 99 / ask 101 (mid 100); 31000 bid 101 / ask 103 (mid 102)
    ts = np.array([1000, 6000, 31000, 40000], "int64")                                 # the last state lets a 30 s horizon from t=2000 stay inside the recording
    bid = np.array([100.0, 99.0, 101.0, 101.0])
    ask = np.array([102.0, 101.0, 103.0, 103.0])
    imb = np.array([0.5, -0.5, 0.0, 0.0])
    return ts, bid, ask, imb


def test_sell_at_bid_has_markout_vs_fill_price():
    ts, bid, ask, imb = states()
    rows = markouts(ts, bid, ask, imb, {"a": (2000, 100.0, 1.0, "sell")}, set())
    assert len(rows) == 1 and rows[0]["side"] == 1
    # fill at the bid 100, mid 5 s later (state at 6000 is the last at or before 7000) = 100: markout 0; 30 s later (32000 -> state 31000, mid 102): +2/101
    assert abs(rows[0]["m5"] - (100.0 - 100.0) / 101.0 * 1e4) < 1e-9
    assert abs(rows[0]["m30"] - (102.0 - 100.0) / 101.0 * 1e4) < 1e-9


def test_buy_at_ask_has_opposite_sign():
    ts, bid, ask, imb = states()
    rows = markouts(ts, bid, ask, imb, {"a": (2000, 102.0, 1.0, "buy")}, set())
    assert len(rows) == 1 and rows[0]["side"] == -1
    assert abs(rows[0]["m5"] - (102.0 - 100.0) / 101.0 * 1e4) < 1e-9                  # sold at 102, mid fell to 100: a gain for the maker
    assert abs(rows[0]["m30"]) < 1e-9                                                  # mid back at 102 by 31 s: sold at 102 and flat = 0


def test_a_sweep_counts_once_at_the_touch_and_every_print_in_the_old_definition():
    ts, bid, ask, imb = states()
    sweep = {"a": (2000, 100.0, 1.0, "sell"), "b": (2000, 99.5, 1.0, "sell"), "c": (2000, 99.0, 1.0, "sell")}
    assert len(markouts(ts, bid, ask, imb, sweep, set(), touch_only=True)) == 1
    assert len(markouts(ts, bid, ask, imb, sweep, set(), touch_only=False)) == 3


def test_two_prints_at_the_touch_in_one_millisecond_are_one_fill():
    ts, bid, ask, imb = states()
    two = {"a": (2000, 100.0, 1.0, "sell"), "b": (2000, 100.0, 2.0, "sell")}
    assert len(markouts(ts, bid, ask, imb, two, set())) == 1
    other_ms = {"a": (2000, 100.0, 1.0, "sell"), "b": (2001, 100.0, 2.0, "sell")}
    assert len(markouts(ts, bid, ask, imb, other_ms, set())) == 2                       # different milliseconds are different fills


def test_a_horizon_past_the_end_of_the_recording_is_nan_not_a_guess():
    ts, bid, ask, imb = states()
    rows = markouts(ts, bid, ask, imb, {"a": (20000, 100.0, 1.0, "sell")}, set())       # state at 6000 is 14 s old: skipped
    assert rows == []
    ts2 = np.array([1000, 6000, 31000], "int64")                                        # recording ends at 31 s
    rows = markouts(ts2, bid[:3], ask[:3], imb[:3], {"a": (31500, 101.0, 1.0, "sell")}, set())   # the state at 31 s is fresh and its bid is 101
    assert len(rows) == 1 and np.isnan(rows[0]["m5"]) and np.isnan(rows[0]["m30"])      # 36.5 s and 61.5 s are beyond the last message


def test_a_horizon_ending_after_the_last_message_is_nan_even_if_that_message_is_fresh():
    ts3 = np.array([1000, 6000, 31000, 36000], "int64")
    bid3, ask3, imb3 = np.array([100.0, 99.0, 101.0, 101.0]), np.array([102.0, 101.0, 103.0, 103.0]), np.zeros(4)
    rows = markouts(ts3, bid3, ask3, imb3, {"a": (31500, 101.0, 1.0, "sell")}, set())   # 5 s horizon ends at 36.5 s, 0.5 s after the last message
    assert len(rows) == 1 and np.isnan(rows[0]["m5"])


def test_only_prints_at_the_touch_are_fills():
    ts, bid, ask, imb = states()
    assert markouts(ts, bid, ask, imb, {"a": (2000, 101.0, 1.0, "sell")}, set()) == []   # a sell INSIDE the spread is not a fill of a bid at 100
    assert markouts(ts, bid, ask, imb, {"a": (2000, 99.0, 1.0, "sell")}, set()) == []    # nor is one BELOW it (a deeper level of a sweep)


def test_state_stamped_at_the_print_is_not_used_for_the_print():
    ts, bid, ask, imb = states()
    # the print at 6000 sells at 99 = the NEW bid, but the state stamped 6000 may not be used: the bid before the print was 100
    assert markouts(ts, bid, ask, imb, {"a": (6000, 99.0, 1.0, "sell")}, set()) == []


def test_stale_state_is_skipped():
    ts, bid, ask, imb = states()
    assert markouts(ts, bid, ask, imb, {"a": (20000, 99.0, 1.0, "sell")}, set()) == []   # last state is 14 s old


def test_trades_seen_in_an_earlier_recording_are_not_counted_twice():
    ts, bid, ask, imb = states()
    assert markouts(ts, bid, ask, imb, {"a": (2000, 100.0, 1.0, "sell")}, {"a"}) == []


def test_block_mean_se_matches_hand_computation():
    m, se, n = block_mean_se(np.array([1.0, 1.0, 3.0, 3.0]), np.array([0, 0, 1, 1]))
    assert m == 2.0 and n == 4 and abs(se - 1.0) < 1e-12                               # sqrt(2/(2-1) * 8) / 4 = 1


def test_block_mean_se_is_larger_than_the_naive_one_when_a_block_moves_together():
    x = np.array([5.0, 5.0, 5.0, 5.0, -5.0, -5.0, -5.0, -5.0])
    blocks = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    _, se_block, _ = block_mean_se(x, blocks)
    se_naive = x.std(ddof=1) / np.sqrt(len(x))
    assert se_block > 1.5 * se_naive


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(len(tests), "tests passed")
