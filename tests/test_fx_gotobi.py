"""Tests for backtest/fx_gotobi.py: the gotobi calendar (D1/D2/D3), the minute-window return, the cost conversion, the statistics and the tune / holdout split.

Run as a script (no pytest on this PC):  python tests/test_fx_gotobi.py
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.fx_gotobi as g  # noqa: E402


def days(idx, mask):
    return sorted(str(d.date())[5:] for d in pd.DatetimeIndex(idx)[mask])


def test_calendar_d1_takes_weekday_gotobi_and_the_last_weekday_of_the_month():
    dates = pd.bdate_range("2026-09-01", "2026-10-31")
    got = days(dates, g.gotobi_days(dates, "D1"))
    assert got == ["09-10", "09-15", "09-25", "09-30", "10-05", "10-15", "10-20", "10-30"]       # Sep 5 and 20 / Oct 10 and 25 are weekends: skipped; Oct 31 is a Saturday so Fri Oct 30 is the month end


def test_calendar_d2_moves_a_weekend_gotobi_to_the_friday_before_and_d3_to_the_monday_after():
    dates = pd.bdate_range("2026-09-01", "2026-10-31")
    d1 = set(days(dates, g.gotobi_days(dates, "D1")))
    d2 = set(days(dates, g.gotobi_days(dates, "D2")))
    d3 = set(days(dates, g.gotobi_days(dates, "D3")))
    assert d2 - d1 == {"09-04", "09-18", "10-09", "10-23"} and d1 <= d2
    assert d3 - d1 == {"09-07", "09-21", "10-12", "10-26"} and d1 <= d3


def test_february_month_end_is_the_last_weekday():
    dates = pd.bdate_range("2026-02-01", "2026-02-28")
    got = days(dates, g.gotobi_days(dates, "D1"))
    assert got == ["02-05", "02-10", "02-20", "02-25", "02-27"]          # Feb 15 2026 is a Sunday (skipped), Feb 28 a Saturday so Fri Feb 27 is the month end


def mk(df_rows):
    return pd.DataFrame(df_rows, columns=["t", "o"]).assign(h=lambda d: d.o, l=lambda d: d.o, c=lambda d: d.o)


def ms(ts):
    return int(pd.Timestamp(ts).value // 10**6)


def test_window_return_is_open_to_open_in_bp_and_long_means_up_is_positive():
    rows = [(ms("2026-03-02 00:00"), 100.0), (ms("2026-03-02 00:55"), 101.0), (ms("2026-03-02 02:00"), 99.0)]
    df = mk(rows)
    dates = pd.DatetimeIndex(["2026-03-02"])
    r, px = g.window_returns(df, dates, 0, 55)
    assert abs(r[0] - 100.0) < 1e-9 and px[0] == 100.0
    r3, _ = g.window_returns(df, dates, 0, 120)
    assert abs(r3[0] - (-100.0)) < 1e-9                                       # 99 / 100 - 1 = -1% = -100 bp


def test_window_can_start_the_evening_before_and_tolerates_a_late_bar_but_not_a_missing_one():
    rows = [(ms("2026-03-01 23:00"), 100.0), (ms("2026-03-02 00:02"), 100.5), (ms("2026-03-02 00:57"), 102.0)]
    df = mk(rows)
    dates = pd.DatetimeIndex(["2026-03-02"])
    r, px = g.window_returns(df, dates, -60, 55)
    assert abs(r[0] - 200.0) < 1e-9 and px[0] == 100.0                        # 23:00 the evening before to the 00:57 bar (2 minutes late: accepted)
    rows2 = [(ms("2026-03-01 23:00"), 100.0), (ms("2026-03-02 00:30"), 100.5), (ms("2026-03-02 00:57"), 102.0), (ms("2026-03-02 05:00"), 103.0)]
    r2, _ = g.window_returns(mk(rows2), dates, 0, 55)                         # the entry bar at 00:00 is missing: first bar after it is 30 minutes late
    assert np.isnan(r2[0])
    dates_ms = dates.as_unit("ms")
    r3, _ = g.window_returns(df, dates_ms, -60, 55)                           # a millisecond-unit index must not empty the window (the datetime-unit trap)
    assert abs(r3[0] - 200.0) < 1e-9


def test_cost_converts_pips_to_bp_of_the_price_for_both_pip_sizes():
    assert abs(g.cost_bp(150.0) - 1.2 * 0.01 / 150.0 * 1e4) < 1e-12 and abs(g.cost_bp(150.0) - 0.8) < 1e-12
    assert abs(g.cost_bp(1.10, 1.2, 0.0001) - 1.2 * 0.0001 / 1.10 * 1e4) < 1e-12
    assert g.cost_bp(75.0) > g.cost_bp(150.0)                                  # the same pip costs more bp at a cheaper yen


def test_statistics_match_the_hand_formulas():
    a, b = np.array([1.0, 2.0, 3.0, 4.0]), np.array([0.0, 1.0, 1.0, 2.0])
    se = math.sqrt(a.var(ddof=1) / 4 + b.var(ddof=1) / 4)
    assert abs(g.welch_t(a, b) - (a.mean() - b.mean()) / se) < 1e-12 and g.welch_t(a, b) > 0 > g.welch_t(b, a)
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert abs(g.one_sample_t(x) - 3.0 / (math.sqrt(2.5) / math.sqrt(5))) < 1e-12
    assert abs(g.p_one_sided(0.0) - 0.5) < 1e-12 and g.p_one_sided(3.0) < 0.002 and g.p_one_sided(-3.0) > 0.998


def test_holm_is_step_down_not_bonferroni_and_stops_at_the_first_failure():
    assert list(g.holm(np.array([0.01, 0.04, 0.03]))) == [True, False, False]          # 0.01 <= 0.05/3, then 0.03 > 0.05/2
    assert list(g.holm(np.array([0.001, 0.02, 0.5]))) == [True, True, False]           # 0.02 <= 0.05/2 would fail a plain 0.05/3 Bonferroni
    assert list(g.holm(np.array([0.2, 0.001]))) == [False, True]                       # order of the input does not matter
    assert list(g.holm(np.array([0.2, 0.3]))) == [False, False]


def test_split_is_the_first_sixty_percent_in_date_order():
    m = g.split_60_40(10)
    assert list(m) == [True] * 6 + [False] * 4 and g.split_60_40(7).sum() == 4


def test_cell_gotobi_edge_is_measured_against_other_days_net_of_cost_with_tune_before_holdout():
    dates = pd.bdate_range("2020-01-06", periods=300)
    gm = np.zeros(len(dates), bool)
    gm[::5] = True                                                            # 60 "gotobi" days
    rows, rets = [], np.zeros(len(dates))
    k = np.cumsum(gm)
    rets[gm] = np.where(k[gm] <= 36, 4.0, 14.0)                              # +4 bp in the first 60% of gotobi days, +14 bp in the last 40%
    for d, r in zip(dates, rets):
        rows.append((ms(d), 100.0))
        rows.append((ms(d + pd.Timedelta(minutes=55)), 100.0 * (1 + r / 1e4)))
    res = g.cell(mk(rows), dates, gm, 0, 55)
    cost = g.cost_bp(100.0)
    assert res["n"] == 60 and abs(res["gross"] - (36 * 4 + 24 * 14) / 60) < 1e-6 and abs(res["other"]) < 1e-9
    assert abs(res["net"] - (res["gross"] - cost)) < 1e-6
    assert abs(res["tune"] - (4.0 - cost)) < 1e-6 and abs(res["hold"] - (14.0 - cost)) < 1e-6          # tune = EARLIER gotobi days
    assert abs(res["dbl"] - (res["gross"] - 2 * cost)) < 1e-6


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
