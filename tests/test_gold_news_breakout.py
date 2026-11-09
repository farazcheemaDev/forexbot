"""Tests for backtest/gold_news_breakout.py: the price lookup, the three rules (follow / break the range / straddle) with their three fill models,
the stop logic, the straddle statistics, the controls (New York clock, DST), the pass rule, the clock guard and the cost constants.

Every expected number is worked out by hand in the test. Run as a script (no pytest on this PC):  python tests/test_gold_news_breakout.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.gold_news_breakout as g  # noqa: E402

MIN = 60_000
BASE = int(pd.Timestamp("2026-03-02 13:30", tz="UTC").value // 10**6)       # 08:30 New York (EST) on a Monday


def make(segments, overrides=None, start=-60, end=300, base=BASE):
    """flat 1-minute bars: `segments` = [(from_minute, price), ...]; `overrides` = {minute: (o, h, l, c)}."""
    segs = sorted(segments)
    rows = []
    for m in range(start, end):
        p = next(price for frm, price in reversed(segs) if m >= frm)
        rows.append((base + m * MIN,) + (overrides or {}).get(m, (p, p, p, p)))
    t, o, h, l, c = zip(*rows)  # noqa: E741
    return g.Bars(t, o, h, l, c)


def drop(b, minutes, base=BASE):
    keep = ~np.isin(b.t, [base + m * MIN for m in minutes])
    return g.Bars(b.t[keep], b.o[keep], b.h[keep], b.l[keep], b.c[keep])


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


NET = g.NEWS_COST
NETS = g.NEWS_COST + g.STOP_SLIP


# ----------------------------------------------------------------------------------------------- constants, inventory
def test_costs_are_the_gold_focus_figures_and_the_split_is_60_40():
    assert close(g.NEWS_COST, (2.44 + 0.5) / 1e4) and close(g.STOP_SLIP, 2.0 / 1e4) and g.TUNE == 0.60 and g.STALE == 30 * g.MIN


def test_the_cell_table_has_21_cells_6_follow_6_break_9_straddle_with_unique_labels():
    kinds = [k for _, k, _ in g.CELLS]
    assert len(g.CELLS) == 21 and (kinds.count("A"), kinds.count("B"), kinds.count("C")) == (6, 6, 9)
    assert len({lab for lab, _, _ in g.CELLS}) == 21
    assert {p["fill"] for _, k, p in g.CELLS if k in "BC"} == {"level", "close", "extreme"}


# ----------------------------------------------------------------------------------------------- price lookup
def test_px_at_is_the_open_of_the_bar_starting_then_else_the_previous_close():
    b = make([(-100, 1000.0)], {0: (1000.0, 1010.0, 999.0, 1008.0)})
    assert b.px_at(BASE) == 1000.0                                  # the open of the bar that starts at T
    assert b.px_at(BASE + 30_000) == 1008.0                         # 30 s into the bar: the last close before the next bar... of bar T
    assert np.isnan(b.px_at(BASE - 10_000 * MIN))                   # before the first bar


def test_px_at_refuses_a_stale_price_but_accepts_a_close_one():
    b = g.Bars([BASE, BASE + MIN], [1, 2], [1, 2], [1, 2], [1, 2])
    assert b.px_at(BASE + MIN + 29 * MIN) == 2 and np.isnan(b.px_at(BASE + MIN + 31 * MIN))


# ----------------------------------------------------------------------------------------------- A: follow
def test_follow_goes_with_an_up_jump_and_pays_the_news_cost():
    b = make([(-100, 1000.0), (1, 1010.0), (16, 1015.0)], {0: (1000.0, 1012.0, 999.0, 1010.0)})
    gross, net = g.rule_a(b, BASE, 1, 15)
    assert close(gross, 1015 / 1010 - 1) and close(net, gross - NET)          # long: enters at the open of minute +1, exits at +16


def test_follow_goes_short_after_a_down_jump():
    b = make([(-100, 1000.0), (1, 990.0), (16, 985.0)], {0: (1000.0, 1000.5, 988.0, 990.0)})
    gross, net = g.rule_a(b, BASE, 1, 15)
    assert close(gross, -(985 / 990 - 1)) and gross > 0 and close(net, gross - NET)


def test_follow_enters_at_the_delay_and_the_direction_is_fixed_at_entry_not_by_what_follows():
    b = make([(-100, 1000.0), (1, 1010.0), (2, 1020.0), (17, 1025.0)])
    gross, _ = g.rule_a(b, BASE, 2, 15)
    assert close(gross, 1025 / 1020 - 1)                                       # entry price is the open at +2, not at +1
    c = make([(-100, 1000.0), (1, 1010.0), (16, 990.0)])
    gross, _ = g.rule_a(c, BASE, 1, 15)
    assert gross < 0 and close(gross, 990 / 1010 - 1)                          # still LONG when price falls after the entry


def test_follow_has_no_trade_when_price_has_not_moved_or_a_price_is_missing():
    b = make([(-100, 1000.0)])
    assert np.isnan(g.rule_a(b, BASE, 1, 15)[0])
    assert np.isnan(g.rule_a(g.Bars([BASE], [1], [1], [1], [1]), BASE + 500 * MIN, 1, 15)[0])


# ----------------------------------------------------------------------------------------------- B: break the first range
def b_bars(over7, tail=1020.0, extra=None):
    ov = {0: (1000.0, 1010.0, 995.0, 1005.0), 7: over7}
    ov.update(extra or {})
    return make([(-100, 1005.0), (8, tail)], ov)                                # range of the first 5 minutes: hi 1010, lo 995


def test_break_long_fills_at_the_level_the_close_or_the_extreme():
    b = b_bars((1009.0, 1012.0, 1008.0, 1011.0))
    for fill, entry in (("level", 1010.0), ("close", 1011.0), ("extreme", 1012.0)):
        gross, net = g.rule_b(b, BASE, 5, fill)
        assert close(gross, 1020 / entry - 1) and close(net, gross - NETS), fill


def test_break_that_gaps_past_the_level_fills_at_the_open_not_the_level():
    b = b_bars((1015.0, 1016.0, 1014.0, 1015.0))
    gross, _ = g.rule_b(b, BASE, 5, "level")
    assert close(gross, 1020 / 1015 - 1)


def test_break_short_enters_below_the_low_and_profits_from_a_fall():
    b = b_bars((996.0, 997.0, 993.0, 994.0), tail=980.0)
    gross, net = g.rule_b(b, BASE, 5, "level")
    assert close(gross, -(980 / 995 - 1)) and gross > 0 and close(net, gross - NETS)


def test_a_bar_that_takes_out_both_sides_is_no_trade():
    b = b_bars((1005.0, 1012.0, 990.0, 1000.0))
    assert np.isnan(g.rule_b(b, BASE, 5, "level")[0])


def test_break_stops_at_the_other_side_of_the_range_and_a_gap_fills_at_the_open():
    b = b_bars((1009.0, 1012.0, 1008.0, 1011.0), extra={9: (1005.0, 1006.0, 990.0, 992.0)})
    gross, _ = g.rule_b(b, BASE, 5, "level")
    assert close(gross, 995 / 1010 - 1)                                        # stopped at the low of the range
    b = b_bars((1009.0, 1012.0, 1008.0, 1011.0), extra={9: (990.0, 991.0, 988.0, 989.0)})
    gross, _ = g.rule_b(b, BASE, 5, "level")
    assert close(gross, 990 / 1010 - 1)                                        # opened below the stop: filled at the open


def test_no_break_inside_the_hour_or_too_few_range_bars_is_no_trade():
    flat = make([(-100, 1005.0)], {0: (1000.0, 1010.0, 995.0, 1005.0)})
    assert np.isnan(g.rule_b(flat, BASE, 5, "level")[0])
    thin = drop(b_bars((1009.0, 1012.0, 1008.0, 1011.0)), [0, 1, 2, 3])
    assert np.isnan(g.rule_b(thin, BASE, 5, "level")[0])


def test_manage_a_stop_touched_in_the_entry_bar_fills_at_the_stop_but_a_later_gap_at_the_open():
    b = make([(-100, 1000.0)], {5: (990.0, 991.0, 988.0, 989.0)})
    j = int(np.searchsorted(b.t, BASE + 5 * MIN))
    assert g.manage(b, j, j, 1, 995.0, BASE + 50 * MIN) == 995.0               # same bar as the entry: the stop price
    assert g.manage(b, j, j - 1, 1, 995.0, BASE + 50 * MIN) == 990.0           # a later bar that opens through it: the open
    assert g.manage(b, j, j - 1, 1, 900.0, BASE + 50 * MIN) == 1000.0          # never touched: the price at the exit time


# ----------------------------------------------------------------------------------------------- C: straddle
LONG_TRIG = {2: (1000.5, 1003.0, 1000.0, 1002.0)}


def test_straddle_long_trigger_fills_at_level_close_or_extreme_with_the_other_side_as_stop():
    b = make([(-100, 1000.0), (3, 1010.0)], LONG_TRIG)
    for fill, entry in (("level", 1001.0), ("close", 1002.0), ("extreme", 1003.0)):
        gross, net = g.rule_c(b, BASE, 10, fill)
        assert close(gross, 1010 / entry - 1) and close(net, gross - NETS), fill


def test_straddle_stop_is_the_opposite_side():
    b = make([(-100, 1000.0), (3, 1010.0)], {**LONG_TRIG, 4: (1002.0, 1002.0, 998.0, 999.0)})
    gross, _ = g.rule_c(b, BASE, 10, "level")
    assert close(gross, 999 / 1001 - 1)


def test_straddle_short_trigger_profits_from_a_fall():
    b = make([(-100, 1000.0), (3, 990.0)], {2: (999.5, 1000.0, 998.0, 998.5)})
    gross, _ = g.rule_c(b, BASE, 10, "level")
    assert close(gross, -(990 / 999 - 1)) and gross > 0


def test_a_minute_that_touches_both_sides_is_the_whipsaw_loss_under_every_fill():
    b = make([(-100, 1000.0)], {0: (1000.0, 1002.0, 998.0, 1000.0)})
    for fill in ("level", "close", "extreme"):
        gross, net = g.rule_c(b, BASE, 10, fill)
        assert close(gross, 999 / 1001 - 1) and gross < 0 and close(net, gross - NETS)


def test_straddle_that_never_triggers_is_no_trade():
    assert np.isnan(g.rule_c(make([(-100, 1000.0)]), BASE, 10, "level")[0])


def test_trigger_stats_count_whipsaws_and_the_run_past_the_level():
    t2 = BASE + 600 * MIN
    b = make([(-100, 1000.0)], {2: LONG_TRIG[2], 600: (1000.0, 1002.0, 998.0, 1000.0)}, end=700)
    both, n, med, mean = g.trigger_stats(b, [BASE, t2], 10)
    assert (both, n) == (1, 2) and close(med, 20.0) and close(mean, 20.0)       # (1003 - 1001) / 1000 = 20 bp past the level


# ----------------------------------------------------------------------------------------------- statistics and the pass rule
def test_welch_matches_a_hand_computed_value_and_ignores_nan():
    a, b = [1, 2, 3, 4, 5], [3, 4, 5, 6, 7]
    assert close(g.welch(a, b), -2.0)                                          # means 3 vs 5, variances 2.5 each, se 1
    assert close(g.welch(a + [np.nan], b), -2.0) and np.isnan(g.welch([1, 2, 3], b))


def halves(ne_early, ne_late, nc_early, nc_late):
    ne = np.array(list(ne_early) + list(ne_late), float)
    nc = np.array(list(nc_early) + list(nc_late), float)
    return ne, nc, np.r_[np.ones(len(ne_early), bool), np.zeros(len(ne_late), bool)], np.r_[np.ones(len(nc_early), bool), np.zeros(len(nc_late), bool)]


def test_verdict_passes_only_when_both_halves_are_positive_and_significant():
    good, ctl = [9.0, 10.0, 11.0] * 8, [-4.0, -3.0, -2.0] * 20
    assert g.verdict(*halves(good, good, ctl, ctl))["ok"]
    assert not g.verdict(*halves(good, [-2.0, -1.0, 0.0] * 8, ctl, ctl))["ok"]              # holdout net negative
    assert not g.verdict(*halves([9.0, 10.0, 11.0] * 8, [60.0, -50.0, 5.0, 55.0, -45.0, 0.0] * 4, ctl, ctl))["ok"]   # holdout positive but t < 2
    assert not g.verdict(*halves([-2.0, -1.0, 0.0] * 8, good, ctl, ctl))["ok"]              # tune half fails
    v = g.verdict(*halves(good, good, ctl, ctl))
    assert v["taken"] == 48 and close(v["net"], 10.0) and close(v["ctl"], -3.0) and close(v["excess"], 13.0)


def test_verdict_needs_a_positive_net_not_just_a_positive_excess():
    ne = [-1.0, -2.0, -3.0] * 8
    ctl = [-9.0, -8.0, -7.0] * 20
    assert not g.verdict(*halves(ne, ne, ctl, ctl))["ok"]                                   # beats the control, still loses money


# ----------------------------------------------------------------------------------------------- events, controls, time units
def test_to_ms_is_unit_proof():
    s = pd.DatetimeIndex(np.array(["2026-03-02T13:30"], dtype="datetime64[s]"))
    u = pd.DatetimeIndex(np.array(["2026-03-02T13:30"], dtype="datetime64[us]"))
    assert g.to_ms(s)[0] == BASE and g.to_ms(u)[0] == BASE


def test_at_ny_clock_drops_statements_at_the_other_clock_time():
    ev = pd.DatetimeIndex(["2013-03-20 18:00", "2012-06-20 18:15", "2013-01-30 19:00", "2014-12-17 19:00"])
    kept = g.at_ny_clock(ev, 14, 0)
    assert [str(x) for x in kept] == ["2013-03-20 18:00:00", "2013-01-30 19:00:00", "2014-12-17 19:00:00"]     # 14:00 in EDT and in EST; 14:15 dropped


def test_control_times_use_the_new_york_clock_across_the_dst_change_and_skip_event_days():
    ev = pd.DatetimeIndex(["2026-03-06 13:30"])
    ctl = g.control_times(ev, 8, 30, "2026-03-02", "2026-03-13")
    stamps = [pd.Timestamp(x, unit="ms") for x in ctl]
    assert len(ctl) == 9 and pd.Timestamp("2026-03-06 13:30") not in stamps               # ten weekdays minus the event day
    assert pd.Timestamp("2026-03-05 13:30") in stamps                                      # EST: 08:30 = 13:30 UTC
    assert pd.Timestamp("2026-03-09 12:30") in stamps                                      # EDT from March 8: 08:30 = 12:30 UTC
    assert all(x.dayofweek < 5 for x in stamps)


# ----------------------------------------------------------------------------------------------- end to end, and the clock guard
def synthetic(spike_offset, n=60):
    fridays = pd.date_range("2011-01-07", periods=n, freq="7D")
    utc = [pd.Timestamp(f"{d.date()} 08:30", tz=g.NY).tz_convert("UTC").tz_localize(None) for d in fridays]
    t, o, h, l, c = [], [], [], [], []  # noqa: E741
    for T in utc:
        t0 = int(T.value // 10**6)
        for m in range(-20, 21):
            p = 1000.0 if m < spike_offset else 1020.0
            bar = (1000.0, 1020.0, 1000.0, 1020.0) if m == spike_offset else (p, p, p, p)
            t.append(t0 + m * MIN)
            for lst, v in zip((o, h, l, c), bar):
                lst.append(v)
    ff = pd.DataFrame({"currency": "USD", "name": "Non-Farm Employment Change", "utc": utc})
    return g.Bars(t, o, h, l, c), ff


def test_run_raises_when_the_biggest_move_is_not_in_the_release_minute():
    b, ff = synthetic(spike_offset=5)
    try:
        g.run(b, ff, "NFP", "Non-Farm Employment Change", 8, 30)
    except RuntimeError as e:
        assert "clock" in str(e)
    else:
        raise AssertionError("a calendar clock that is 5 minutes off was not caught")


def test_run_end_to_end_on_a_release_minute_spike():
    b, ff = synthetic(spike_offset=0)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)                            # empty control windows in the synthetic data
        lines, npass = g.run(b, ff, "NFP", "Non-Farm Employment Change", 8, 30)
    text = "\n".join(lines)
    assert lines[0].startswith("==== NFP: 60 events") and "clock check summer" in text and "release-minute |move|" in text
    assert "cells passing both halves:" in lines[-1] and isinstance(npass, int)
    assert "event median 200.0bp" in text                                                  # 1000 -> 1020 in the release minute = 200 bp, at every event


# ----------------------------------------------------------------------------------------------- second pass: what the first planted-bug round left alive
def test_follow_exits_at_the_hold_asked_for_not_a_fixed_one():
    b = make([(-100, 1000.0), (1, 1010.0), (16, 1015.0), (61, 1040.0)], {0: (1000.0, 1012.0, 999.0, 1010.0)})
    assert close(g.rule_a(b, BASE, 1, 15)[0], 1015 / 1010 - 1) and close(g.rule_a(b, BASE, 1, 60)[0], 1040 / 1010 - 1)


def test_follow_measures_the_jump_from_the_minute_before_the_release():
    b = make([(-100, 990.0), (-1, 1000.0)])                                    # price was 990 two minutes before, 1000 one minute before, 1000 after
    assert np.isnan(g.rule_a(b, BASE, 1, 15)[0])                               # no jump in the release window: no trade


def test_enter_returns_the_price_and_the_first_bar_a_stop_can_act_on():
    b = make([(-100, 1000.0)], {5: (1009.0, 1012.0, 1008.0, 1011.0)})
    j = int(np.searchsorted(b.t, BASE + 5 * MIN))
    assert g.enter(b, "level", j, 1, 1010.0) == (1010.0, j) and g.enter(b, "level", j, -1, 1010.0) == (1009.0, j)
    assert g.enter(b, "close", j, 1, 1010.0) == (1011.0, j + 1) and g.enter(b, "extreme", j, 1, 1010.0) == (1012.0, j + 1)
    assert g.enter(b, "extreme", j, -1, 1010.0) == (1008.0, j + 1)


def test_manage_short_side_stop_gap_and_boundary():
    b = make([(-100, 1000.0)], {5: (1012.0, 1014.0, 1011.0, 1013.0)})
    j = int(np.searchsorted(b.t, BASE + 5 * MIN))
    assert g.manage(b, j, j - 1, -1, 1010.0, BASE + 50 * MIN) == 1012.0        # a short whose stop is gapped through fills at the open
    assert g.manage(b, j, j, -1, 1010.0, BASE + 50 * MIN) == 1010.0            # in the entry bar: the stop price
    c = make([(-100, 1001.0), (6, 990.0)], {5: (1001.0, 1001.0, 995.0, 1001.0)})        # the price afterwards (990) differs from both stops
    j = int(np.searchsorted(c.t, BASE + 5 * MIN))
    assert g.manage(c, j, j, 1, 995.0, BASE + 50 * MIN) == 995.0               # a low exactly at the stop IS the stop
    assert g.manage(c, j, j, -1, 1001.0, BASE + 50 * MIN) == 1001.0            # a high exactly at a short's stop too


def test_break_short_is_stopped_at_the_top_of_the_range():
    b = b_bars((996.0, 997.0, 993.0, 994.0), tail=980.0, extra={9: (1005.0, 1012.0, 1004.0, 1011.0)})
    gross, _ = g.rule_b(b, BASE, 5, "level")
    assert close(gross, -(1010 / 995 - 1))                                     # short from 995, stopped at the range high 1010


def test_a_high_exactly_at_the_range_high_is_not_a_break():
    b = b_bars((1009.0, 1010.0, 1008.0, 1009.0), tail=1005.0)                  # no jump afterwards, so the touch is the only candidate
    assert np.isnan(g.rule_b(b, BASE, 5, "level")[0])                          # strictly above is needed


def test_break_exits_three_hours_after_the_range_ends_and_only_breaks_inside_the_hour_count():
    ov = {m: (1050.0, 1050.0, 1050.0, 1050.0) for m in range(65, 180)}
    ov.update({m: (1080.0, 1080.0, 1080.0, 1080.0) for m in range(180, 300)})
    b = make([(-100, 1005.0), (8, 1020.0)], {0: (1000.0, 1010.0, 995.0, 1005.0), 7: (1009.0, 1012.0, 1008.0, 1011.0), **ov})
    assert close(g.rule_b(b, BASE, 5, "level")[0], 1080 / 1010 - 1)            # exit at minute 185 = 1080 (not 1020 at minute 8, not 1050 at minute 65)
    late = make([(-100, 1005.0)], {0: (1000.0, 1010.0, 995.0, 1005.0), 70: (1009.0, 1012.0, 1008.0, 1011.0)})
    assert np.isnan(g.rule_b(late, BASE, 5, "level")[0])                       # a break 65 minutes after the range ended is outside the window
    inside = make([(-100, 1005.0)], {0: (1000.0, 1010.0, 995.0, 1005.0), 60: (1009.0, 1012.0, 1008.0, 1011.0)})
    assert not np.isnan(g.rule_b(inside, BASE, 5, "level")[0])                 # minute 60 is 55 minutes after the range ended: inside


def test_straddle_triggers_on_a_touch_of_the_level():
    up = 1000.0 * (1 + 100 / 1e4)                                              # the same expression the rule uses, so the bar's high IS the level
    b = make([(-100, 1000.0), (3, 1020.0)], {2: (1000.0, up, 1000.0, 1005.0)})
    gross, _ = g.rule_c(b, BASE, 100, "level")
    assert close(gross, 1020 / up - 1)


def test_straddle_short_is_stopped_at_the_up_level():
    b = make([(-100, 1000.0), (3, 990.0)], {2: (999.5, 1000.0, 998.0, 998.5), 4: (999.0, 1002.0, 999.0, 1001.5)})
    gross, _ = g.rule_c(b, BASE, 10, "level")
    assert close(gross, -(1001 / 999 - 1))                                     # in at 999, stopped at 1001


def test_straddle_exits_two_hours_after_the_release_and_is_centred_on_the_price_at_the_release():
    ov = {m: (1030.0, 1030.0, 1030.0, 1030.0) for m in range(60, 300)}
    b = make([(-100, 1000.0), (3, 1010.0)], {**LONG_TRIG, **ov})
    assert close(g.rule_c(b, BASE, 10, "level")[0], 1030 / 1001 - 1)           # exit at minute 120 = 1030
    stepped = make([(-100, 1000.0), (0, 1010.0)])                              # price 1000 before the release, 1010 from the release on
    assert np.isnan(g.rule_c(stepped, BASE, 10, "level")[0])                   # centred on 1010 (the price at T): nothing triggers


def test_trigger_stats_short_run_is_measured_in_the_right_direction():
    t2, t3 = BASE + 600 * MIN, BASE + 1200 * MIN
    b = make([(-100, 1000.0)], {2: LONG_TRIG[2], 600: (1000.0, 1002.0, 998.0, 1000.0), 1202: (999.5, 1000.0, 998.0, 998.5)}, end=1300)
    both, n, med, mean = g.trigger_stats(b, [BASE, t2, t3], 10)
    assert (both, n) == (1, 3) and close(med, 15.0) and close(mean, 15.0)      # long run 20 bp, short run (999 - 998) / 1000 = 10 bp


def test_welch_uses_each_samples_own_size():
    a = [0.0, 0.0, 0.0, 0.0, 10.0]                                             # n 5, mean 2, variance 20
    b = [0.0, 2.0] * 5                                                         # n 10, mean 1, variance 10 / 9
    assert close(g.welch(a, b), 1.0 / np.sqrt(20 / 5 + (10 / 9) / 10), 1e-12)


def test_run_splits_at_sixty_percent_of_the_events_by_date():
    b, ff = synthetic(spike_offset=0)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        lines, _ = g.run(b, ff, "NFP", "Non-Farm Employment Change", 8, 30)
    assert "split 2011-09-16" in lines[0]                                      # event 36 of 60 weekly Fridays from 2011-01-07


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
