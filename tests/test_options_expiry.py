"""Offline tests for backtest/options_expiry.py - the expiry calendar, window returns, a cell's direction / net / excess, the pass rule,
Holm and the pinning ratio. Synthetic data only.

    python tests/test_options_expiry.py
"""
from __future__ import annotations

import sys
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import options_expiry as ox  # noqa: E402

H = ox.H


def ms(s):
    return int(pd.Timestamp(s, tz="UTC").value // 10**6)


def test_last_friday_by_hand():
    assert ox.last_friday(2026, 10) == pd.Timestamp("2026-10-30") and ox.last_friday(2024, 3) == pd.Timestamp("2024-03-29")
    assert ox.last_friday(2026, 11) == pd.Timestamp("2026-11-27") and ox.last_friday(2025, 2) == pd.Timestamp("2025-02-28")
    assert ox.last_friday(2020, 7) == pd.Timestamp("2020-07-31")                      # the month ends on a Friday


def test_the_calendar_splits_monthly_quarterly_ordinary_fridays_and_weekdays():
    m, q, f, o = ox.calendar("2024-01-01", "2024-03-31")
    assert m == [ms("2024-01-26 08:00"), ms("2024-02-23 08:00"), ms("2024-03-29 08:00")] and q == [ms("2024-03-29 08:00")]
    assert ms("2024-01-19 08:00") in f and ms("2024-01-26 08:00") not in f and len(f) == 13 - 3   # 13 Fridays in the quarter
    assert ms("2024-01-01 08:00") in o and ms("2024-01-05 08:00") not in o and ms("2024-01-06 08:00") not in o
    assert all(pd.Timestamp(t, unit="ms").dayofweek < 4 for t in o) and len(o) == 13 * 4 + 0     # Mon-Thu, 13 weeks
    m2, _, _, _ = ox.calendar("2024-01-27", "2024-02-22")
    assert m2 == []                                                                     # no last Friday inside the range


def test_window_returns_use_the_bar_opens_at_the_window_ends():
    T = ms("2024-03-29 08:00")
    px = {T - 4 * H: 100.0, T: 110.0, T + 24 * H: 99.0}
    assert abs(ox.window_return(px, T, -4, 0) - 0.10) < 1e-12 and abs(ox.window_return(px, T, 0, 24) - (99 / 110 - 1)) < 1e-12
    assert np.isnan(ox.window_return(px, T, 0, 4))


def test_cost_is_fee_plus_funding_for_the_hours_held():
    assert abs(ox.cost("into24") - (12e-4 + 3e-4)) < 1e-15 and abs(ox.cost("after4") - (12e-4 + 0.5e-4)) < 1e-15


def test_a_cell_takes_its_direction_from_the_tune_half_and_nets_costs():
    tu_t, ho_t = ox.CUT_MS - 10 * 86_400_000, ox.CUT_MS + 10 * 86_400_000
    ev_t = [tu_t] * 3 + [ho_t] * 3
    ev_r = [-0.02, -0.03, -0.01, -0.01, -0.02, np.nan]
    ct_t = [tu_t] * 2 + [ho_t] * 2
    ct_r = [0.001, -0.001, 0.002, 0.0]
    c = ox.cell(ev_t, ev_r, ct_t, ct_r, "after4")
    assert c["dir"] == -1.0                                                             # the tune excess is negative: short
    assert c["tu"]["n"] == 3 and c["ho"]["n"] == 2                                       # the NaN is dropped
    assert abs(c["tu"]["excess"] - (-0.02 - 0.0)) < 1e-12 and abs(c["ho"]["excess"] - (-0.015 - 0.001)) < 1e-12
    assert abs(c["ho"]["net"] - (0.015 - ox.cost("after4"))) < 1e-12
    x = np.array([0.02, 0.03, 0.01]) - ox.cost("after4")
    assert abs(c["tu"]["net_t"] - x.mean() / (x.std(ddof=1) / sqrt(3))) < 1e-9


def test_the_direction_comes_from_the_tune_half_even_when_the_holdout_disagrees():
    tu_t, ho_t = ox.CUT_MS - 86_400_000, ox.CUT_MS + 86_400_000
    c = ox.cell([tu_t, tu_t, ho_t, ho_t], [0.01, 0.02, -0.03, -0.01], [tu_t, ho_t], [0.0, 0.0], "into4")
    assert c["dir"] == 1.0 and c["ho"]["net"] < 0                                        # long from the tune half, loses on the holdout


def test_the_pass_rule_needs_both_halves_the_excess_and_holm():
    def half(net=5e-3, t=2.5, ex=1e-3):
        return dict(net=net, net_t=t, excess=ex)
    good = dict(dir=1.0, tu=half(), ho=half())
    assert ox.passes(good, 0.01) and not ox.passes(good, 0.06)
    for kw in (dict(net=-1e-4), dict(t=1.9), dict(ex=-1e-4)):
        assert not ox.passes(dict(dir=1.0, tu=half(**kw), ho=half()), 0.01), kw
        assert not ox.passes(dict(dir=1.0, tu=half(), ho=half(**kw)), 0.01), kw
    assert ox.passes(dict(dir=-1.0, tu=half(ex=-1e-3), ho=half(ex=-2e-3)), 0.01)          # a short needs a NEGATIVE excess


def test_holm_and_the_family_use_the_weaker_half():
    assert ox.holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    cells = {"a": dict(tu=dict(net_t=3.0), ho=dict(net_t=1.0)), "b": dict(tu=dict(net_t=4.0), ho=dict(net_t=4.0))}
    f = ox.family(cells)
    assert abs(f["a"] - ox.p_one(1.0)) < 1e-12 and abs(f["b"] - 2 * ox.p_one(4.0)) < 1e-12          # a is second: x1


def test_the_pinning_ratio():
    r, t = ox.abs_ratio([0.01, -0.012, 0.008, np.nan], [0.02, -0.025, 0.015])
    assert abs(r - 0.5) < 1e-12 and t < 0


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
