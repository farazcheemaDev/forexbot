"""order_flow_lab.py offline: the wall tracker's executed / cancelled accounting on hand-built event streams.
Run as a script: python tests/test_order_flow_lab.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import order_flow_lab as lab  # noqa: E402

MID = 10.0
ASK = (False, 10.01)          # a sell wall at 10.01
BID = (True, 9.99)


def wall(W, key=ASK, qty=10_000.0, ts=0):
    usd = qty * key[1]
    assert W.start(key, usd, ts, abs(key[1] - MID) / MID * 1e4)
    return qty


def test_executed_and_cancelled_are_separated_by_the_tape():
    W = lab.WallTracker()
    q = wall(W)                                           # 10,000 coins at 10.01 = $100,100
    W.on_trade("buy", 10.01, 3_000.0, MID)                # taker buys lift 3,000 of it
    W.on_update(ASK, q, 7_000.0, 1_000, MID)              # the level shows 7,000: that decrease WAS the execution
    W.on_update(ASK, 7_000.0, 1_000.0, 2_000, MID)        # then 6,000 more leave with no print: a cancel
    (e,) = W.done
    assert e["why"] == "faded" and abs(e["life_s"] - 2.0) < 1e-12
    assert abs(e["removed"] - 9_000 * 10.01) < 1e-6 and abs(e["executed"] - 3_000 * 10.01) < 1e-6
    assert abs(e["cancelled"] - 6_000 * 10.01) < 1e-6 and abs(e["cancel_share"] - 6 / 9) < 1e-12


def test_a_print_on_the_wrong_side_or_price_is_not_an_execution():
    W = lab.WallTracker()
    q = wall(W)
    W.on_trade("sell", 10.01, 5_000.0, MID)               # a taker SELL hits bids, not asks
    W.on_trade("buy", 10.02, 5_000.0, MID)                # another price
    W.on_update(ASK, q, 2_000.0, 500, MID)
    (e,) = W.done
    assert e["executed"] == 0.0 and abs(e["cancelled"] - 8_000 * 10.01) < 1e-6 and e["cancel_share"] == 1.0
    W2 = lab.WallTracker()
    wall(W2, BID)
    W2.on_trade("sell", 9.99, 4_000.0, MID)               # a taker sell at a bid wall IS an execution
    assert abs(W2.live[BID]["executed"] - 4_000 * 9.99) < 1e-6


def test_cancelled_never_goes_negative_when_prints_exceed_the_visible_decrease():
    W = lab.WallTracker()
    q = wall(W)
    W.on_trade("buy", 10.01, 9_000.0, MID)                # 9,000 coins print, but refills hide most of it: the level only loses 5,100 in all
    W.on_update(ASK, q, 8_000.0, 100, MID)                # -2,000 (peak stays 10,000)
    W.on_update(ASK, 8_000.0, 4_900.0, 200, MID)          # -3,100, now under half of the peak: ends
    (e,) = W.done
    assert abs(e["removed"] - 5_100 * 10.01) < 1e-6 and abs(e["executed"] - 9_000 * 10.01) < 1e-6
    assert e["cancelled"] == 0.0 and e["cancel_share"] == 0.0


def test_distance_buckets_follow_the_mid_at_the_moment():
    W = lab.WallTracker()
    q = wall(W, qty=10_000.0)
    W.on_update(ASK, q, 9_000.0, 10, 10.0095)             # the level is ~0.5bp from the mid: bucket 0 ('<= 1bp'); size stays above half
    W.on_update(ASK, 9_000.0, 8_000.0, 20, 9.99)          # 20bp away: bucket 3 ('> 10bp')
    w = W.live[ASK]
    assert abs(w["rem_b"][0] - 1_000 * 10.01) < 1e-6 and abs(w["rem_b"][3] - 1_000 * 10.01) < 1e-6 and sum(w["rem_b"]) > 0
    W.on_trade("buy", 10.01, 2_000.0, 10.0095)
    assert w["exe_b"][0] > 0 and w["exe_b"][1:] == [0.0, 0.0, 0.0]
    W.on_trade("buy", 10.01, 500.0, 10.005)                # a print while the mid is 5bp away: bucket '3-10bp'
    assert abs(w["exe_b"][2] - 500 * 10.01) < 1e-6 and abs(w["exe_b"][0] - 2_000 * 10.01) < 1e-6


def test_refills_are_counted_and_do_not_end_the_wall():
    W = lab.WallTracker()
    q = wall(W)
    W.on_update(ASK, q, 7_000.0, 100, MID)                # -3,000 (still above half of the peak)
    W.on_update(ASK, 7_000.0, 12_000.0, 200, MID)         # +5,000: replenished, new peak
    w = W.live[ASK]
    assert abs(w["added"] - 5_000 * 10.01) < 1e-6 and abs(w["peak"] - 12_000 * 10.01) < 1e-6 and ASK in W.live
    W.on_update(ASK, 12_000.0, 5_000.0, 300, MID)         # now under half of the 12,000 peak: ends
    assert W.done and W.done[0]["added"] > 0


def test_a_wall_under_the_floor_ends_and_cannot_restart_inside_the_cooldown():
    W = lab.WallTracker()
    q = wall(W, qty=2_300.0)                                          # $23,023
    W.on_update(ASK, q, 1_300.0, 1_000, MID, floor_usd=20_000.0)      # $13,013: still 56% of the peak, but under the $20k wall floor
    assert not W.live and len(W.done) == 1
    assert not W.start(ASK, 100_000.0, 1_000 + lab.COOLDOWN_MS - 1, 10.0)     # too soon
    assert W.start(ASK, 100_000.0, 1_000 + lab.COOLDOWN_MS, 10.0)              # allowed after 60 s


def test_a_snapshot_resync_and_the_end_of_data_close_with_their_own_labels():
    W = lab.WallTracker()
    wall(W, ASK)
    wall(W, BID)
    W.resync(5_000)
    assert {e["why"] for e in W.done} == {"resync"} and not W.live
    W.start(ASK, 60_000.0, 90_000, 5.0)
    W.finish(120_000)
    assert W.done[-1]["why"] == "censored" and abs(W.done[-1]["life_s"] - 30.0) < 1e-12


def test_updates_to_levels_that_are_not_followed_change_nothing():
    W = lab.WallTracker()
    wall(W, ASK)
    W.on_update((False, 10.05), 100.0, 50.0, 10, MID)
    W.on_trade("buy", 10.05, 100.0, MID)
    assert list(W.live) == [ASK] and W.live[ASK]["removed"] == 0.0 and W.live[ASK]["executed"] == 0.0


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
