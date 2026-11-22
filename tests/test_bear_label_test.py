"""Offline tests for backtest/bear_label_test.py - the label, the sleeve decision, the matched-risk scaling and the candidate rule.
No network, no price panel.

    python tests/test_bear_label_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import bear_label_test as bl  # noqa: E402


def series(vals):
    return pd.Series(np.asarray(vals, float), index=pd.date_range("2024-01-01", periods=len(vals), freq="D"))


def test_label_is_close_under_average_and_average_falling_and_knowable_next_day():
    up = np.linspace(100, 160, 70)
    down = np.linspace(160, 120, 30)                     # a fall after a rise
    s = series(np.r_[up, down])
    bear_price = bl.label(s, 30, None)
    bear_slope = bl.label(s, 30, 0.0)
    assert not bear_price.iloc[:69].any()                # a rising market is never BEAR
    assert bear_price.iloc[-1] and bear_slope.iloc[-1]   # deep in the fall both labels agree
    first_price = bear_price.idxmax()
    # the day a close first sits under its average, the label says BEAR only the NEXT day (knowable): shift 1
    raw = (s < s.rolling(30).mean())
    assert first_price == raw.idxmax() + pd.Timedelta(days=1)
    # the slope condition delays it: the average keeps rising for a while after the price turns
    assert bear_slope.idxmax() > first_price


def test_a_slower_average_flags_later_and_the_live_label_is_the_slowest():
    s = series(np.r_[np.linspace(100, 150, 120), np.linspace(150, 100, 60)])
    first = {k: bl.label(s, *k).idxmax() for k in ((20, None), (30, 0.0), (50, -0.02))}
    assert first[(20, None)] <= first[(30, 0.0)] <= first[(50, -0.02)]
    assert first[(20, None)] < first[(50, -0.02)]


def test_sleeve_decision_longs_low_breadth_shorts_high_and_does_nothing_outside_bear():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    bear = pd.Series([True, True, True, False, True], index=idx)
    br = pd.Series([0.05, 0.20, 0.30, 0.05, 0.10], index=idx)
    out = bl.signal(bear, br).tolist()
    assert out == [1.0, 0.0, -1.0, 0.0, 1.0]             # 0.10 is the boundary: included; breadth 0.05 outside BEAR: nothing


def test_expanding_cutoffs_use_only_earlier_bear_days_and_need_enough_history():
    n = 200
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    bear = pd.Series(True, index=idx)
    br = pd.Series(np.linspace(0.0, 1.0, n), index=idx)               # breadth rises through the sample
    out = bl.signal_expanding(bear, br, min_prior=60)
    assert (out.iloc[:60] == 0).all()                                 # no decision before 60 prior bear days
    assert out.iloc[100] == -1.0        # history = days 0..99 (breadth 0..0.50, top third from ~0.33): today's 0.50 is high -> short
    br2 = br.copy()
    br2.iloc[100] = 0.0                 # today's own value is NOT in today's history: the cut-offs do not move, 0.0 is low -> long
    assert bl.signal_expanding(bear, br2, 60).iloc[100] == 1.0
    # short history so one value matters: prior bear days 0.2 / 0.4 / 0.6 give cut-offs 0.33 / 0.47; today 0.35 sits BETWEEN them -> 0.
    # (with today wrongly inside its own history the lower cut-off would drop to 0.35 and today would read as LOW -> +1)
    i4 = pd.date_range("2024-01-01", periods=4, freq="D")
    o4 = bl.signal_expanding(pd.Series(True, index=i4), pd.Series([0.2, 0.4, 0.6, 0.35], index=i4), min_prior=3)
    assert o4.iloc[3] == 0.0
    bear2 = bear.copy()
    bear2.iloc[:80] = False             # non-bear days neither trade nor enter the history
    o2 = bl.signal_expanding(bear2, br, 60)
    assert (o2.iloc[:140] == 0).all()   # history starts at day 80: 60 bear days exist only from day 140
    assert o2.iloc[140] == -1.0         # days 80..139 span breadth 0.40..0.70; today's 0.70 is above the top third


def test_matched_risk_scaling_hits_the_target_fall():
    x = series([0.01, -0.03, 0.02, -0.05, 0.01, 0.02, -0.02, 0.03] * 30)
    base = bl.dd_of(x)
    k = bl.match_k(x, base * 2)
    assert k > 1.5
    assert abs(bl.dd_of(x, k) - base * 2) < 0.05
    assert bl.match_k(x, base) == np.float64(bl.match_k(x, base))    # deterministic
    assert abs(bl.match_k(x, base) - 1.0) < 0.02


def test_candidate_rule_needs_every_check():
    live = dict(tune=30, hold=18, sharpe=1.2, dd=20, ww=-9.5)
    good = dict(tune=35, hold=24, sharpe=1.3, dd=24, ww=-12)
    assert bl.judge(good, live, matched_hold=20)["ok"]
    assert not bl.judge(dict(good, hold=17), live, 10)["ok"]            # loses the holdout
    assert not bl.judge(dict(good, tune=29), live, 10)["ok"]            # loses the tune half
    assert not bl.judge(dict(good, sharpe=1.1), live, 10)["ok"]         # worse risk-adjusted
    assert not bl.judge(dict(good, dd=26), live, 10)["ok"]              # fall more than 5 points deeper
    assert not bl.judge(dict(good, ww=-15), live, 10)["ok"]             # worst week more than 5 points worse
    assert not bl.judge(good, live, matched_hold=25)["ok"]              # 'just bet more' on the live sleeve earns more


def test_today_table_projects_the_flip_with_the_same_rule():
    closes = np.r_[np.linspace(100, 130, 80), np.linspace(130, 118, 10)]      # just turned down
    t = bl.today_table(closes, 118.0)
    assert t[(20, None)][0] is True or t[(20, None)][1] is not None
    n_live, d_live = t[bl.LIVE]
    assert n_live is False or d_live is None
    # a faster label never flips LATER than a slower one at the same price
    assert (t[(20, None)][1] or 0) <= (t[bl.LIVE][1] or 99) or t[(20, None)][0]


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
