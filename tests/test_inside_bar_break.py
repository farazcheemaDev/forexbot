"""Tests for backtest/inside_bar_break.py: the 30-minute bars, the mother / baby signal (every condition and its boundary), the trade management on minute bars (stop, target, gaps, the 24-hour exit),
the two fill models (sell-stop at the baby's low, market at a bar's close), the matched control, the Welch statistic, the pass rule, the printed line, the mirror and a whole planted market.

Every expected number is worked out by hand in the test. Run as a script (no pytest on this PC):  python tests/test_inside_bar_break.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.inside_bar_break as m  # noqa: E402

MIN, SLOT = 60_000, 1_800_000
CF = 0.002              # a big cost fraction so the cost term is visible in every R
CF2 = 2e-4


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def flat(n, price=100.0):
    t = np.arange(n, dtype=np.int64) * MIN
    return t, np.full(n, float(price)), np.full(n, float(price)), np.full(n, float(price)), np.full(n, float(price))


# ----------------------------------------------------------------------------------------------- constants and small helpers
def test_the_registered_constants():
    assert (m.LOOK, m.BIG, m.BABY, m.WAIT, m.HOLD_MIN, m.CTRL, m.TUNE) == (20, 1.0, 0.5, 4, 1440, 5, 0.60)
    assert m.SLOT == 30 * 60 * 1000 and m.MIN == 60_000 and close(m.STOP_SLIP, 2e-4)
    assert m.COST == {"XAUUSD": 2.94, "NSXUSD": 1.27} and m.DEFAULT_COST == 1.5


def test_mirror_negates_and_swaps_high_and_low():
    t = np.array([0, 60_000])
    o, h, l, c = np.array([100.0, 101.0]), np.array([102.0, 103.0]), np.array([99.0, 98.0]), np.array([101.0, 100.5])  # noqa: E741
    t2, o2, h2, l2, c2 = m.mirror(t, o, h, l, c)
    assert (t2 == t).all() and list(o2) == [-100.0, -101.0] and list(h2) == [-99.0, -98.0] and list(l2) == [-102.0, -103.0] and list(c2) == [-101.0, -100.5]


def test_bars30_aggregates_and_needs_ten_minutes():
    t = np.arange(70, dtype=np.int64) * MIN                      # slot 0 = minutes 0-29, slot 1 = 30-59, slot 2 = 60-69 (ten minutes)
    o = 100.0 + np.arange(70)
    h, l, c = o + 0.5, o - 0.5, o + 0.1  # noqa: E741
    s, bo, bh, bl, bc = m.bars30(t, o, h, l, c)
    assert list(s) == [0, 1, 2]
    assert bo[0] == 100.0 and bh[0] == 129.5 and bl[0] == 99.5 and close(bc[0], 129.1)
    assert bo[1] == 130.0 and bh[1] == 159.5 and bl[1] == 129.5 and close(bc[1], 159.1)
    assert bo[2] == 160.0 and bh[2] == 169.5 and bl[2] == 159.5 and close(bc[2], 169.1)
    s9, *_ = m.bars30(t[:69], o[:69], h[:69], l[:69], c[:69])    # nine minutes in the last slot: dropped
    assert list(s9) == [0, 1]


# ----------------------------------------------------------------------------------------------- the signal
def flat_bars(n=40):
    return [np.arange(n) + 1000, np.full(n, 100.5), np.full(n, 101.0), np.full(n, 100.0), np.full(n, 100.5)]


def sig(bars, look=20):
    j, S, L = m.signals(*bars, look=look)
    return [int(x) for x in j], [float(x) for x in S], [float(x) for x in L]


def pattern(bars, mi=36, mh=105.0, ml=100.0, bh=103.0, bl=101.5):
    bars[2][mi], bars[3][mi], bars[2][mi + 1], bars[3][mi + 1] = mh, ml, bh, bl
    return bars


def test_the_base_pattern_gives_the_baby_index_the_mothers_high_and_the_babys_low():
    assert sig(pattern(flat_bars())) == ([37], [105.0], [101.5])
    assert sig(flat_bars()) == ([], [], [])


def test_the_mother_must_make_a_strictly_new_high_over_the_look_back():
    b = pattern(flat_bars())
    b[2][30] = 105.0                                              # an earlier bar with the same high: not a NEW high
    assert sig(b) == ([], [], [])
    b = pattern(flat_bars())
    b[2][30] = 106.0
    assert sig(b) == ([], [], [])
    b = pattern(flat_bars())
    b[2][20] = 106.0                                              # a higher bar 16 bars back: inside a 20-bar window, outside a 10-bar one
    assert sig(b) == ([], [], [])
    assert sig(b, look=10) == ([37], [105.0], [101.5])


def test_the_mother_must_be_at_least_one_atr_big_with_the_atr_taken_over_the_14_bars_before_it():
    b = flat_bars()                                               # atr 1.0; mother range 0.99 -> not big, exactly 1.0 -> big
    pattern(b, mh=101.9, ml=100.91, bh=101.2, bl=101.0)
    assert sig(b) == ([], [], [])
    b = flat_bars()
    pattern(b, mh=101.5, ml=100.5, bh=101.2, bl=100.8)
    assert sig(b) == ([37], [101.5], [100.8])
    b = flat_bars()                                               # a wild bar at the OLD end of the window (index 36-14) lifts the atr to 2.43 > the mother's 2.0
    pattern(b, mh=102.5, ml=100.5, bh=101.8, bl=101.3)
    b[3][22] = 80.0
    assert sig(b) == ([], [], [])
    b = flat_bars()                                               # ... and at the NEW end (index 35)
    pattern(b, mh=102.5, ml=100.5, bh=101.8, bl=101.3)
    b[3][35] = 80.0
    assert sig(b) == ([], [], [])
    b = flat_bars()                                               # the same mother with a calm window is big
    pattern(b, mh=102.5, ml=100.5, bh=101.8, bl=101.3)
    assert sig(b) == ([37], [102.5], [101.3])
    b = flat_bars()                                               # a wild bar OUTSIDE the window (index 21) changes nothing
    pattern(b, mh=102.5, ml=100.5, bh=101.8, bl=101.3)
    b[3][21] = 80.0
    assert sig(b) == ([37], [102.5], [101.3])
    b = flat_bars()                                               # the mother's own range is not in its atr: a calm window, mother 1.5 vs atr 1.0 is big and a 7-range window is not
    for i in range(22, 36):
        b[3][i] = 94.0                                            # each of those bars now has range 7 -> atr 7 > the mother's 5
    pattern(b)
    assert sig(b) == ([], [], [])
    b = flat_bars()                                               # the atr is a TRUE range: a close far BELOW the next bar's range adds |high - previous close|
    pattern(b, mh=102.2, ml=100.5, bh=101.6, bl=101.2)
    b[4][30] = 90.0                                               # bar 31's true range = max(1, |101-90|, |100-90|) = 11 -> atr 24/14 = 1.714 > the mother's 1.7
    assert sig(b) == ([], [], [])
    b = flat_bars()                                               # a close far ABOVE the next bar's range adds |low - previous close|
    pattern(b, mh=102.1, ml=100.5, bh=101.5, bl=101.2)
    b[4][30] = 110.0                                              # true range max(1, 9, 10) = 10 -> atr 23/14 = 1.643 > the mother's 1.6
    assert sig(b) == ([], [], [])


def test_the_baby_must_be_inside_the_mother_and_at_most_half_its_size():
    assert sig(pattern(flat_bars(), bh=105.1, bl=103.0)) == ([], [], [])          # pokes above the mother's high (its size 2.1 is fine)
    assert sig(pattern(flat_bars(), bh=101.0, bl=99.9)) == ([], [], [])           # dips under the mother's low (its size 1.1 is fine)
    assert sig(pattern(flat_bars(), bh=103.6, bl=101.0)) == ([], [], [])          # range 2.6 > half of 5.0
    assert sig(pattern(flat_bars(), bh=103.5, bl=101.0)) == ([37], [105.0], [101.0])   # range exactly 2.5 is allowed
    assert sig(pattern(flat_bars(), bh=105.0, bl=102.5)) == ([37], [105.0], [102.5])   # the same high is inside
    assert sig(pattern(flat_bars(), bh=102.5, bl=100.0)) == ([37], [105.0], [100.0])   # the same low is inside


def test_the_baby_must_follow_the_mother_in_the_very_next_slot():
    b = pattern(flat_bars())
    b[0][37] += 1
    assert sig(b) == ([], [], [])


def test_the_first_and_last_possible_mother_positions():
    assert sig(pattern(flat_bars(), mi=35)) == ([36], [105.0], [101.5])           # look + 15 = 35 is the first mother with a full window
    assert sig(pattern(flat_bars(), mi=34)) == ([], [], [])
    assert sig(pattern(flat_bars(), mi=38)) == ([39], [105.0], [101.5])           # the baby is the last bar
    assert sig(pattern(flat_bars(41), mi=39)) == ([40], [105.0], [101.5])


# ----------------------------------------------------------------------------------------------- management
def run_manage(arr, a=10, entry=100.0, S=101.0, k=2, costf=CF):
    return m.manage(*arr, a, entry, S, k, costf)


def test_target_stop_and_the_tie():
    t, o, h, l, c = flat(1600)  # noqa: E741
    l[500] = 97.9
    assert close(run_manage((t, o, h, l, c)), 2.0 - 0.2)                          # target 98 filled at 98: gross 2, cost 0.002 x 100 / 1
    t, o, h, l, c = flat(1600)  # noqa: E741
    h[500], o[500] = 101.2, 100.5
    assert close(run_manage((t, o, h, l, c)), -1.0 - 0.2)                         # stop 101: gross -1
    t, o, h, l, c = flat(1600)  # noqa: E741
    h[500], l[500] = 101.2, 97.9
    assert close(run_manage((t, o, h, l, c)), -1.2)                               # both in one minute: the stop
    t, o, h, l, c = flat(1600)  # noqa: E741
    h[400], o[400], l[500] = 101.2, 100.5, 97.9
    assert close(run_manage((t, o, h, l, c)), -1.2)                               # the stop first
    t, o, h, l, c = flat(1600)  # noqa: E741
    l[400], h[500], o[500] = 97.9, 101.2, 100.5
    assert close(run_manage((t, o, h, l, c)), 1.8)                                # the target first


def test_stop_touched_exactly_is_a_stop_and_target_touched_exactly_is_a_target():
    t, o, h, l, c = flat(1600)  # noqa: E741
    h[500] = 101.0
    assert close(run_manage((t, o, h, l, c)), -1.2)
    t, o, h, l, c = flat(1600)  # noqa: E741
    l[500] = 98.0
    assert close(run_manage((t, o, h, l, c)), 1.8)


def test_gaps_fill_at_the_open():
    t, o, h, l, c = flat(1600)  # noqa: E741
    o[500], h[500] = 101.5, 101.5
    assert close(run_manage((t, o, h, l, c)), -1.5 - 0.2)                         # through the stop: the open, worse than the stop
    t, o, h, l, c = flat(1600)  # noqa: E741
    o[500], l[500] = 97.5, 97.5
    assert close(run_manage((t, o, h, l, c)), 2.5 - 0.2)                          # through the target: the open, better than the target


def test_the_24_hour_exit_uses_the_last_close_inside_the_window_and_nothing_after():
    t, o, h, l, c = flat(1600)  # noqa: E741
    c[1448] = 99.0                                                                # a=10 -> entry minute 9 -> the window is minutes 10..1448
    h[1449], l[1449], c[1449] = 105.0, 90.0, 50.0                                 # the first minute AFTER the window: ignored
    assert close(run_manage((t, o, h, l, c)), (100.0 - 99.0) / 1.0 - 0.2)
    t, o, h, l, c = flat(1600)  # noqa: E741
    h[1448], c[1448] = 101.5, 99.0                                                # the last minute INSIDE the window counts
    assert close(run_manage((t, o, h, l, c)), -1.2)


def test_risk_must_be_positive_and_the_cost_is_in_r_with_the_absolute_price():
    arr = flat(1600)
    assert run_manage(arr, entry=101.0, S=101.0) is None and run_manage(arr, entry=102.0, S=101.0) is None
    assert close(run_manage(arr, entry=100.0, S=102.0, k=1), -0.002 * 100.0 / 2.0)             # flat exit: gross 0, cost 0.1 R
    neg = flat(1600, price=-100.0)
    assert close(run_manage(neg, entry=-100.0, S=-98.0, k=1), -0.002 * 100.0 / 2.0)            # the same on mirrored (negative) prices


def test_no_minute_after_the_entry_gives_nothing():
    arr = flat(100)
    assert run_manage(arr, a=100) is None


def test_the_data_ending_before_24_hours_exits_at_the_last_close():
    t, o, h, l, c = flat(300)  # noqa: E741
    c[299] = 99.0
    assert close(run_manage((t, o, h, l, c)), 1.0 - 0.2)


# ----------------------------------------------------------------------------------------------- the sell-stop fill
def touch(arr, bs_j=5, S=101.0, L=99.5, k=2, cf=CF2):
    return m.trade_touch(*arr, bs_j, S, L, k, cf)


def expect_touch(entry_open_min, entry, S=101.0, cf=CF2, gross_exit=100.0):
    D = S - entry
    return (entry - gross_exit) / D - cf * abs(entry) / D, D / abs(entry)


def test_touch_fills_at_the_level_minus_slippage_when_the_minute_opens_above_it():
    arr = flat(3000)
    assert touch(arr) is None                                                     # never trades down to 99.5
    t, o, h, l, c = flat(3000)  # noqa: E741
    o[200], h[200], l[200] = 99.9, 99.9, 90.0                                     # the trigger minute: opens above 99.5, trades to 90 (below the would-be target, which must NOT count)
    r, rf, mm = touch((t, o, h, l, c))
    entry = 99.5 - 2e-4 * 99.5
    er, erf = expect_touch(200, entry)
    assert mm == 200 and close(r, er) and close(rf, erf)                          # then flat at 100 for 24 hours


def test_touch_gap_fills_at_the_open_when_the_minute_opens_below_the_level():
    t, o, h, l, c = flat(3000)  # noqa: E741
    o[200], h[200], l[200] = 99.0, 99.0, 98.9
    r, rf, mm = touch((t, o, h, l, c))
    entry = 99.0 - 2e-4 * 99.5                                                    # the slippage is taken on the LEVEL
    er, erf = expect_touch(200, entry)
    assert mm == 200 and close(r, er) and close(rf, erf)


def test_touch_is_cancelled_if_the_mothers_high_trades_first_and_not_if_it_only_nearly_does():
    t, o, h, l, c = flat(3000)  # noqa: E741
    l[200] = 99.4
    h[190] = 101.0
    assert touch((t, o, h, l, c)) is None                                         # the stop level (>=) traded before the trigger
    t, o, h, l, c = flat(3000)  # noqa: E741
    l[200] = 99.4
    h[190] = 100.99
    r, rf, mm = touch((t, o, h, l, c))
    assert mm == 200
    t, o, h, l, c = flat(3000)  # noqa: E741
    l[200] = 99.4
    h[210] = 101.5                                                                # AFTER the trigger: a normal stop-out, not a cancel
    r, rf, mm = touch((t, o, h, l, c))
    entry = 99.5 - 2e-4 * 99.5
    D = 101.0 - entry
    assert mm == 200 and close(r, -1.0 - CF2 * entry / D)


def test_touch_with_the_stop_and_the_trigger_in_the_same_minute_is_stopped():
    t, o, h, l, c = flat(3000)  # noqa: E741
    l[200], h[200] = 99.4, 101.5
    r, rf, mm = touch((t, o, h, l, c))
    entry = 99.5 - 2e-4 * 99.5
    D = 101.0 - entry
    assert mm == 200 and close(r, -1.0 - CF2 * entry / D) and close(rf, D / entry)


def test_touch_trigger_is_a_touch_of_the_level_itself():
    t, o, h, l, c = flat(3000)  # noqa: E741
    l[200] = 99.5                                                                 # exactly the baby's low
    r = touch((t, o, h, l, c))
    assert r is not None and r[2] == 200


def test_touch_window_is_the_four_bars_after_the_baby():
    for minute, expected in ((179, None), (180, 180), (299, 299), (300, None)):   # baby slot 5 -> minutes 180..299 are bars 6-9
        t, o, h, l, c = flat(3000)  # noqa: E741
        l[minute] = 99.4
        r = touch((t, o, h, l, c))
        assert (r is None) if expected is None else (r is not None and r[2] == expected), (minute, r)


# ----------------------------------------------------------------------------------------------- the market-on-close fill
def close_bars(nb=12, jb_slot=12):
    bs = jb_slot - 2 + np.arange(nb)                                              # baby at index 2 has slot jb_slot
    return [bs, np.full(nb, 100.0), np.full(nb, 100.5), np.full(nb, 99.5), np.full(nb, 100.0)]


def tclose(bars, arr, jb=2, S=101.0, L=99.5, k=2, cf=CF2):
    return m.trade_close(*arr, bars, jb, S, L, k, cf)


def test_close_fill_enters_at_the_close_of_the_first_bar_closing_under_the_level():
    bars = close_bars()
    bars[4][4] = 99.4                                                             # bar index 4 = slot 14
    arr = flat(3000)
    r, rf, mm = tclose(bars, arr)
    D = 101.0 - 99.4
    assert mm == 15 * 30 - 1 and close(r, (99.4 - 100.0) / D - CF2 * 99.4 / D) and close(rf, D / 99.4)
    bars = close_bars()
    bars[4][3] = 99.4                                                             # the first bar after the baby
    assert tclose(bars, arr)[2] == 14 * 30 - 1
    bars = close_bars()
    bars[4][3] = 99.5                                                             # closing exactly at the level is not under it
    bars[4][4] = 99.4
    assert tclose(bars, arr)[2] == 15 * 30 - 1


def test_close_fill_is_cancelled_by_the_mothers_high_in_the_same_or_an_earlier_bar_and_by_a_slot_gap():
    arr = flat(3000)
    bars = close_bars()
    bars[2][3] = 101.0                                                            # an earlier bar trades at the mother's high
    bars[4][4] = 99.4
    assert tclose(bars, arr) is None
    bars = close_bars()
    bars[2][4] = 101.0                                                            # the same bar that closes under the level
    bars[4][4] = 99.4
    assert tclose(bars, arr) is None
    bars = close_bars()
    bars[2][4] = 100.99
    bars[4][4] = 99.4
    assert tclose(bars, arr) is not None
    bars = close_bars()
    bars[0][3:] += 1                                                              # a gap between the baby and the next bar
    bars[4][3] = 99.4
    assert tclose(bars, arr) is None


def test_close_fill_waits_at_most_four_bars_and_survives_the_end_of_the_bars():
    arr = flat(3000)
    bars = close_bars()
    bars[4][6] = 99.4                                                             # the 4th bar after the baby (index 2 + 4)
    assert tclose(bars, arr)[2] == 17 * 30 - 1
    bars = close_bars()
    bars[4][7] = 99.4                                                             # the 5th: too late
    assert tclose(bars, arr) is None
    bars = close_bars(nb=4)
    assert tclose(bars, arr, jb=2) is None                                        # only one bar after the baby, no close under: no IndexError
    bars[4][3] = 99.4
    assert tclose(bars, arr, jb=2) is not None


def test_close_fill_needs_minute_bars_after_the_entry_bar():
    bars = close_bars()
    bars[4][4] = 99.4
    assert tclose(bars, flat(100)) is None                                        # entry minute 450 is past the data


# ----------------------------------------------------------------------------------------------- the matched control
def test_control_flat_market_close_kind_costs_exactly_the_cost_in_r():
    arr = flat(8640)
    out = m.control(*arr, [1, 2, 3, 4], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(0))
    assert len(out) == 5 and all(close(x, -2e-4 / 0.01) for x in out)             # entry 100, stop 101, flat exit: -costf x entry / D = -0.02


def test_control_touch_kind_pays_the_stop_slippage_too():
    arr = flat(8640)
    out = m.control(*arr, [1, 2, 3, 4], 12 * 3600 * 1000, 0.01, 2, 2e-4, "touch", np.random.default_rng(0))
    entry = 100.0 - 2e-4 * 100.0
    D = 0.01 * entry
    assert len(out) == 5 and all(close(x, (entry - 100.0) / D - 2e-4 * entry / D) for x in out)


def test_control_draws_only_from_the_pool_days_and_skips_missing_data_and_the_data_end():
    t, o, h, l, c = flat(8640)  # noqa: E741
    h[1440 + 750] = 101.5                                                         # day 1, 12:30: a stop-out for a control entered at 12:00 on day 1
    out = m.control(t, o, h, l, c, [1], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(0))
    assert len(out) == 5 and all(close(x, -1.0 - 0.02) for x in out)              # stop 101 gross -1, cost 0.02
    out = m.control(t, o, h, l, c, [2], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(0))
    assert len(out) == 5 and all(close(x, -0.02) for x in out)
    assert m.control(t, o, h, l, c, [50], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(0)) == []   # no data that day
    assert m.control(t, o, h, l, c, [5], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(0)) == []    # within 2,000 minutes of the end
    assert len(m.control(t, o, h, l, c, [4], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(0))) == 5
    assert m.control(t, o, h, l, c, [5], 0, 0.01, 2, 2e-4, "close", np.random.default_rng(0)) == []   # minute 7,200 of 8,640: the 24 hours would not fit


def test_control_management_starts_the_minute_after_the_entry_minute():
    t, o, h, l, c = flat(8640)  # noqa: E741
    h[1440 + 720] = 101.5                                                         # the entry minute's own high is not part of the management (as for the sell-stop fill)
    out = m.control(t, o, h, l, c, [1], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(0))
    assert len(out) == 5 and all(close(x, -0.02) for x in out)


def test_control_tolerates_a_two_minute_hole_at_the_target_time_but_not_three():
    t, o, h, l, c = flat(8640)  # noqa: E741
    keep = np.ones(8640, bool)
    keep[1440 + 720:1440 + 722] = False                                           # day 1 minutes 720 and 721 missing: the next bar is 2 minutes late
    a2 = (t[keep], o[keep], h[keep], l[keep], c[keep])
    assert len(m.control(*a2, [1], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(0))) == 5
    keep[1440 + 722] = False                                                      # three missing: 3 minutes late
    a3 = (t[keep], o[keep], h[keep], l[keep], c[keep])
    assert m.control(*a3, [1], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(0)) == []


def test_control_is_deterministic_for_a_seed():
    arr = flat(8640)
    a = m.control(*arr, [1, 2, 3, 4], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(3))
    b = m.control(*arr, [1, 2, 3, 4], 12 * 3600 * 1000, 0.01, 2, 2e-4, "close", np.random.default_rng(3))
    assert a == b


# ----------------------------------------------------------------------------------------------- statistics and the pass rule
def test_welch_by_hand():
    a, b = [1, 2, 3, 4, 5], [1, 1, 1, 1, 2]
    assert close(m.welch(a, b), 1.8 / np.sqrt(0.54), 1e-9)                         # means 3 and 1.2, variances 2.5 and 0.2
    a, b = [0, 1] * 3, [0, 2] * 5                                                  # unequal sizes: var 0.3 / 6 + var 10/9 / 10
    assert close(m.welch(a, b), -0.5 / np.sqrt(0.3 / 6 + (10 / 9) / 10), 1e-9)
    assert np.isnan(m.welch([1, 2, 3, 4], [1, 2, 3, 4, 5])) and np.isnan(m.welch([1, 2, 3, 4, 5], [1, 2, 3, 4]))
    assert np.isnan(m.welch([1.0] * 5, [1.0] * 5))                                 # zero variance
    assert m.welch([1, 2, 3, 4, 5], [-1, 0, 1, 2, 3]) == 2.0                       # exactly 2


def halves(a, b):
    return [list(a), list(b)]


def test_verdict_passes_only_with_a_positive_net_and_t_of_two_on_both_halves():
    good = [0.9, 1.1] * 10
    ctrl = [0.0, 0.2] * 25
    v = m.verdict(halves(good, good), halves(ctrl, ctrl))
    assert v["passed"] and v["n"] == 40 and v["win"] == 1.0 and close(v["net"], 1.0) and close(v["m0"], 1.0) and close(v["c0"], 0.1) and v["t0"] > 2 and v["t1"] > 2
    neg, nctrl = [-0.2, 0.0] * 10, [-0.6, -0.4] * 25                               # a big excess over a worse control, but the net is negative
    v = m.verdict(halves(neg, good), halves(nctrl, ctrl))
    assert v["t0"] > 2 and v["m0"] < 0 and not v["passed"]
    v = m.verdict(halves(good, neg), halves(ctrl, nctrl))
    assert v["t1"] > 2 and v["m1"] < 0 and not v["passed"]
    noisy, nz = [3.0, -2.9] * 10, [-0.05, 0.05] * 25                               # positive net, no excess
    v = m.verdict(halves(noisy, good), halves(nz, ctrl))
    assert v["m0"] > 0 and v["t0"] < 2 and not v["passed"]
    v = m.verdict(halves(good, noisy), halves(ctrl, nz))
    assert v["m1"] > 0 and v["t1"] < 2 and not v["passed"]
    five, five_c = [1, 2, 3, 4, 5], [-1, 0, 1, 2, 3]
    assert m.verdict(halves(five, five), halves(five_c, five_c))["passed"]          # t exactly 2.0 on both halves passes


def test_verdict_handles_no_trades_an_empty_half_and_zero_results():
    assert m.verdict([[], []], [[], []]) is None
    v = m.verdict(halves([1.0, 2.0, 3.0, 4.0, 5.0], []), halves([0.0] * 5, []))
    assert v["n"] == 5 and np.isnan(v["m1"]) and not v["passed"]
    v = m.verdict(halves([0.0, 1.0], [0.0, 0.0]), halves([], []))
    assert close(v["win"], 0.25)                                                   # a zero R is not a win


def test_line_format_and_pass_marker():
    good = [0.9, 1.1] * 10
    ctrl = [0.0, 0.2] * 25
    s = m.line("XAUUSD", "short", "touch", 2, 20, halves(good, good), halves(ctrl, ctrl))
    assert s.startswith("XAUUSD  short touch 2R look20: n   40 (20/20) win 100.0% net R +1.000 [tune +1.000 hold +1.000] | control [+0.100 +0.100] | excess t [")
    assert s.endswith("PASS")
    s = m.line("EURUSD", "long", "close", 2, 20, halves([-1.0] * 10, [-1.0] * 10), halves(ctrl, ctrl))
    assert s.startswith("EURUSD  long  close 2R look20: n   20 (10/10) win  0.0% net R -1.000") and not s.endswith("PASS")
    assert m.line("XAUUSD", "short", "touch", 2, 20, [[], []], [[], []]) == "XAUUSD  short touch 2R look20: no trades"


# ----------------------------------------------------------------------------------------------- a whole planted market
def market(starts, base0=100.0, step=10.0):
    """Flat 30-minute bars of range 1 with one mother / baby / break / drop pattern per start bar; the level rises `step` per pattern so every mother is a new high."""
    n = (starts[-1] + 60) * 30
    t = np.arange(n, dtype=np.int64) * MIN
    o, h, l, c = (np.zeros(n) for _ in range(4))  # noqa: E741
    bounds = [0] + [(s - 30) * 30 for s in starts[1:]] + [n]
    for k, s in enumerate(starts):
        P = base0 + k * step
        a, b = bounds[k], bounds[k + 1]
        o[a:b] = c[a:b] = P
        h[a:b], l[a:b] = P + 0.5, P - 0.5
        i = s * 30
        h[i + 10] = P + 3.0                                                       # the mother: range 3.5
        o[i + 30:i + 60] = c[i + 30:i + 60] = P + 0.4                             # the baby: high P+1.9, low P+0.2
        h[i + 30:i + 60], l[i + 30:i + 60] = P + 0.6, P + 0.2
        h[i + 40] = P + 1.9
        o[i + 60:i + 100] = c[i + 60:i + 100] = P + 0.4                           # the break bar and the next: quiet above the baby's low ...
        h[i + 60:i + 100], l[i + 60:i + 100] = P + 0.5, P + 0.3
        o[i + 65], h[i + 65], l[i + 65], c[i + 65] = P + 0.3, P + 0.3, P + 0.1, P + 0.1      # ... except one minute that trades through P+0.2
        o[i + 100], h[i + 100], l[i + 100], c[i + 100] = P - 4.0, P - 4.0, P - 6.0, P - 5.5  # the drop through the 2R target
        o[i + 101:b] = c[i + 101:b] = P - 5.5
        h[i + 101:b], l[i + 101:b] = P - 5.4, P - 5.6
    return t, o, h, l, c


def test_the_planted_market_has_exactly_the_planted_signals():
    starts = [40, 80, 120, 160, 200]
    j, S, L = m.signals(*m.bars30(*market(starts)))
    assert [int(x) for x in j] == [s + 1 for s in starts]
    assert all(close(s, 100.0 + 10 * k + 3.0) and close(x, 100.0 + 10 * k + 0.2) for k, (s, x) in enumerate(zip(S, L)))


def test_one_planted_pattern_touch_and_close_fills_end_to_end():
    arr = market([40])
    res = m.run_side(*arr, -1, (2,), ("touch", "close"), 20, 2e-4, np.random.default_rng(0))
    assert [(r[0], r[1], r[2], r[3]) for r in res] == [("short", "touch", 2, 20), ("short", "close", 2, 20)]
    entry = 100.2 - 2e-4 * 100.2
    D = 103.0 - entry
    touch_r = res[0][4][1]                                                         # a single signal lands in the holdout half
    assert res[0][4][0] == [] and len(touch_r) == 1 and close(touch_r[0], 2.0 - 2e-4 * entry / D)     # the 2R target is hit: gross 2
    D2 = 103.0 - 94.5                                                              # CLOSE: enters at the drop bar's close 94.5, nothing happens for 24 hours
    assert res[1][4][0] == [] and len(res[1][4][1]) == 1 and close(res[1][4][1][0], -2e-4 * 94.5 / D2)


def test_the_long_side_is_the_short_side_on_the_mirrored_market():
    arr = market([40])
    short = m.run_side(*arr, -1, (1, 2), ("touch", "close"), 20, 2e-4, np.random.default_rng(0))
    long_ = m.run_side(*m.mirror(*arr), 1, (1, 2), ("touch", "close"), 20, 2e-4, np.random.default_rng(0))
    assert [r[0] for r in long_] == ["long"] * 4 and [r[0] for r in short] == ["short"] * 4
    assert [r[4] for r in short] == [r[4] for r in long_]
    assert sum(len(r[4][0]) + len(r[4][1]) for r in short) == 4


def test_the_tune_holdout_split_is_the_first_60_percent_of_signals_by_time():
    arr = market([40, 80, 120, 160, 200])
    res = m.run_side(*arr, -1, (2,), ("touch",), 20, 2e-4, np.random.default_rng(0))
    S_ = res[0][4]
    assert (len(S_[0]), len(S_[1])) == (3, 2)                                      # int(5 x 0.6) = 3: signals 0-2 tune, 3-4 holdout
    for idx, got in enumerate(S_[0] + S_[1]):
        P = 100.0 + 10 * idx
        entry = (P + 0.2) - 2e-4 * (P + 0.2)
        D = (P + 3.0) - entry
        assert close(got, 2.0 - 2e-4 * entry / D), (idx, got)


def test_run_side_hands_each_signal_its_own_entry_time_risk_and_half_pool():
    starts = [40, 80, 120, 160, 200]
    arr = market(starts)
    calls = []
    saved = m.control
    m.control = lambda *a, **k: (calls.append(a), [])[1]
    try:
        m.run_side(*arr, -1, (2,), ("touch",), 20, 2e-4, np.random.default_rng(0))
    finally:
        m.control = saved
    assert len(calls) == 5
    for idx, a in enumerate(calls):
        P = 100.0 + 10 * idx
        entry = (P + 0.2) - 2e-4 * (P + 0.2)
        D = (P + 3.0) - entry
        assert a[6] == ((starts[idx] * 30 + 65) % 1440) * MIN                      # the ENTRY minute's time of day (not the baby bar's)
        assert close(a[7], D / entry) and a[8] == 2 and a[9] == 2e-4 and a[10] == "touch"
        assert [int(x) for x in a[5]] == ([0, 1, 2] if idx < 3 else [3, 4, 5])      # tune signals draw days before the cut, holdout signals the days from it


def test_study_picks_the_cost_per_market_and_labels_the_cells():
    saved = m.load
    try:
        m.load = lambda sym: market([40])
        for sym, bp in (("FAKE", 1.5), ("XAUUSD", 2.94), ("NSXUSD", 1.27)):
            res = m.study(sym, ks=(2,), kinds=("touch",), sides=(-1,), rng=np.random.default_rng(0))
            assert len(res) == 1 and res[0][:5] == (sym, "short", "touch", 2, 20)
            entry = 100.2 - 2e-4 * 100.2
            D = 103.0 - entry
            assert close(res[0][5][1][0], 2.0 - bp * 1e-4 * entry / D), sym
        both = m.study("FAKE", ks=(1, 2), sides=(-1, 1), rng=np.random.default_rng(0))
        assert [(r[1], r[2], r[3]) for r in both] == [("short", "touch", 1), ("short", "touch", 2), ("short", "close", 1), ("short", "close", 2),
                                                      ("long", "touch", 1), ("long", "touch", 2), ("long", "close", 1), ("long", "close", 2)] \
            or [(r[1], r[2], r[3]) for r in both][:2] == [("short", "touch", 1), ("short", "touch", 2)]
    finally:
        m.load = saved


if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for name, fn in tests:
        fn()
    print(f"{len(tests)} tests passed")
