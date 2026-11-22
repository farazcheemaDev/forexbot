"""Tests for backtest/his_losers.py: outcome buckets, percentile ranks and the market-context numbers.

Run as a script (no pytest on this PC):  python tests/test_his_losers.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.his_losers as hl  # noqa: E402


def test_percentile_among_counts_ties_as_half():
    assert hl.percentile_among(2.5, [1, 2, 3, 4]) == 50.0
    assert hl.percentile_among(2, [1, 2, 3, 4]) == 37.5
    assert np.isnan(hl.percentile_among(1.0, [np.nan]))


def test_buckets_put_each_outcome_in_its_own_row_and_shares_add_up():
    n = pd.DataFrame(dict(pts=[-5.0, 0.5, 2.0, 5.0, 7.0, 9.0, 20.0], hold_s=60.0, net=[-10.0, 1.0, 2.0, 5.0, 7.0, 9.0, 20.0]))
    t = hl.outcome_buckets(n)
    assert list(t.n) == [1] * 7 and abs(t.share_of_profit.sum() - 100) < 1e-9
    edge = hl.outcome_buckets(pd.DataFrame(dict(pts=[7.5, 6.5], hold_s=1.0, net=[1.0, 1.0])))
    assert edge.n.tolist() == [0, 0, 0, 1, 1, 0, 0]                    # 6.5 is 'short of target', 7.5 still counts as the +7


def test_a_trade_just_above_the_plus_seven_band_goes_to_the_next_bucket():
    t = hl.outcome_buckets(pd.DataFrame(dict(pts=[7.7, 7.4], hold_s=1.0, net=[1.0, 1.0])))
    assert t.n.tolist() == [0, 0, 0, 0, 1, 1, 0]                       # 7.4 is 'the +7', 7.7 is in 7.5..12


def bars_rising(n=900, step=1.0):
    t = np.arange(n, dtype="int64") * 60_000
    c = 100 + step * np.arange(n)
    return pd.DataFrame(dict(t=t, o=c, h=c + 0.5, l=c - 0.5, c=c))


def test_context_reads_the_move_in_his_direction_and_the_range_position():
    b = bars_rising()
    t0 = int(b.t.iloc[700]) + 20_000                                   # 20 s into minute 700
    c = hl.context(b, t0, +1, 60.0)
    assert abs(c["mv5"] - 5.0) < 1e-9 and abs(c["mv30"] - 30.0) < 1e-9 and abs(c["mv120"] - 120.0) < 1e-9
    assert c["cheap"] > 0.99                                           # a buy at the top of a steady rise is the expensive end
    s = hl.context(b, t0, -1, 60.0)
    assert abs(s["mv5"] + 5.0) < 1e-9 and s["cheap"] < 0.01             # a sell there is at the cheap end of ITS direction


def test_context_tracks_the_worst_and_best_price_during_the_hold_and_the_aftermath():
    b = bars_rising()
    b.loc[702, "l"] = b.loc[702, "c"] - 9.0                             # a spike down during the hold
    t0 = int(b.t.iloc[700]) + 20_000
    c = hl.context(b, t0, +1, 150.0)                                    # held through minute 702
    p0 = b.c.iloc[699]
    assert abs(c["mae"] - (b.l.iloc[700:703].min() - p0)) < 1e-9 and abs(c["mfe"] - (b.h.iloc[700:703].max() - p0)) < 1e-9
    assert abs(c["after60"] - (b.c.iloc[702 + 60] - b.c.iloc[702])) < 1e-9


def test_the_hour_after_the_exit_is_counted_in_his_direction_for_a_sell_too():
    b = bars_rising()
    t0 = int(b.t.iloc[700]) + 20_000
    assert abs(hl.context(b, t0, +1, 150.0)["after60"] - 60.0) < 1e-9       # the price kept rising: good for a buy
    assert abs(hl.context(b, t0, -1, 150.0)["after60"] + 60.0) < 1e-9       # the same rise is 60 points AGAINST a sell


def test_context_refuses_when_there_is_too_little_history_or_the_bar_is_missing():
    b = bars_rising()
    assert hl.context(b, int(b.t.iloc[100]) + 1000, 1, 60.0) is None
    gap = b.drop(index=range(700, 705)).reset_index(drop=True)          # the entry falls in a hole in the data
    assert hl.context(gap, int(b.t.iloc[702]) + 1000, 1, 60.0) is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
