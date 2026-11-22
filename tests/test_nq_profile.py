"""Tests for backtest/nq_profile.py: the profile (bins, TPO letters, volume spread, the value-area method), prior-session alignment, every rule where it must fire and where it must not, look-ahead (truncation) checks,
trade simulation, the matched-day control, the statistics and the gate, and two whole-pipeline markets (a planted effect must pass; a pure drift must not).

Run as a script (no pytest on this PC):  python tests/test_nq_profile.py     (exit code 0 = all passed)
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.nq_profile as pr  # noqa: E402

L = 390


# ------------------------------------------------------------------ builders

def blank(n=8, px=100.0):
    A = {k: np.full((n, L), px) for k in "ohlc"}
    A["v"] = np.ones((n, L))
    return A


def seg(*parts):
    return np.concatenate([np.full(k, p, float) for k, p in parts])


def path(A, i, closes, first_open=None):
    c = np.asarray(closes, float)
    assert len(c) == L, len(c)
    o = np.r_[c[0] if first_open is None else first_open, c[:-1]]
    A["o"][i], A["c"][i] = o, c
    A["h"][i], A["l"][i] = np.maximum(o, c), np.minimum(o, c)


def prof(n, **days):
    P = {k: np.full(n, np.nan) for k in ("poc", "val", "vah")}
    for key, (poc, val, vah) in days.items():
        j = int(key[1:])
        P["poc"][j], P["val"][j], P["vah"][j] = poc, val, vah
    return P


def flags(n, ok_days, ok2_days=()):
    ok = np.zeros(n, bool)
    ok[list(ok_days)] = True
    ok2 = np.zeros(n, bool)
    ok2[list(ok2_days)] = True
    return ok, ok2


def feats(n, arf=0.02, ib=np.nan, ibmed=np.nan):
    return dict(arf=np.full(n, arf), ib=np.full(n, ib), ibmed=np.full(n, ibmed))


def rw_market(n=60, seed=1, drift=0.0, gap_sd=0.003, sigma=0.0004):
    rng = np.random.default_rng(seed)
    A = {k: np.empty((n, L)) for k in "ohlc"}
    A["v"] = 100 + rng.integers(0, 50, (n, L)).astype(float)
    px = 20000.0
    for i in range(n):
        o0 = px * (1 + rng.normal(0, gap_sd))
        c = o0 * np.cumprod(1 + rng.normal(drift / L, sigma, L))
        o = np.r_[o0, c[:-1]]
        A["o"][i], A["c"][i] = o, c
        A["h"][i] = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.0001, L)))
        A["l"][i] = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.0001, L)))
        px = c[-1]
    return A


def dates_for(n):
    d = pd.bdate_range("2022-01-03", periods=n)
    roll = np.zeros(n, bool)
    roll[0] = True
    return d, roll


# ------------------------------------------------------------------ the registered numbers

def test_registered_constants_are_unchanged():
    assert (pr.BIN_BP, pr.TICK, pr.VA_FRAC, pr.PERIOD, pr.COST_BP, pr.MIN_TARGET_BP, pr.POC_DIST_BP) == (2.0, 0.25, 0.70, 30, 1.27, 5.0, 15.0)
    assert (pr.MIGR_ATR, pr.ATR_WIN, pr.IB_MIN, pr.IB_BASE_WIN, pr.IB_NARROW, pr.OD_EDGE, pr.OD_RANGE) == (0.25, 14, 60, 20, 0.6, 0.10, 0.25)
    assert (pr.LAST, pr.MIN_HOLD_TRADES, pr.MAX_GAP_DAYS, pr.TUNE, pr.L) == (359, 100, 4, 0.60, 390)
    assert pr.CELLS == ["R1 80% rule", "R2 back to POC", "R3 fade value edge", "R4 acceptance outside value", "R5a value migration (POC)",
                        "R5b value migration (no overlap)", "R6a IB break", "R6b IB break, narrow IB", "R7 open drive"] and pr.MODES == ("tpo", "vol")


# ------------------------------------------------------------------ the profile

def test_bin_width_is_two_basis_points_on_the_tick_lattice_and_never_below_one_tick():
    assert pr.bin_width(20000.0) == 4.0 and pr.bin_width(10000.0) == 2.0 and pr.bin_width(5000.0) == 1.0
    assert pr.bin_width(3000.0) == 0.5                                   # 0.6 -> 2.4 ticks -> 2 ticks
    assert pr.bin_width(1800.0) == 0.25 and pr.bin_width(100.0) == 0.25   # 0.36 -> 1 tick; 0.02 -> 0 ticks -> floor of one tick
    assert pr.bin_width(3500.0) == 0.75                                   # 0.7 -> 2.8 ticks ROUNDS to 3 (truncating would give 2)


def test_value_area_method_by_hand():
    # counts 1 2 5 9 5 3 1: POC bin 3; above-pair (5+3)=8 beats below-pair (2+5)=7 -> 17 of 26; still short of 18.2: above has one bin left (1), below-pair 7 wins -> 24
    assert pr.value_area(np.array([1, 2, 5, 9, 5, 3, 1.0]), 3) == (3, 1, 5)
    assert pr.value_area(np.array([0, 4, 10, 4, 0.0]), 2) == (2, 2, 4)    # a tie between the pairs goes UP; 14 of 18 is enough
    assert pr.value_area(np.array([9, 1, 1, 1.0]), 0) == (0, 0, 0)        # the POC alone already holds 75%
    assert pr.value_area(np.array([6, 10, 1, 1.0]), 1) == (1, 0, 1)       # below has ONE bin left (6) against the pair above (2): the slice must clip at 0
    assert pr.value_area(np.array([2, 2, 10, 1, 6, 1.0]), 2) == (2, 2, 4)  # the PAIR above (1 + 6 = 7) beats the pair below (2 + 2 = 4); one bin above (1) would lose
    assert pr.value_area(np.array([4, 14, 2.0]), 1) == (1, 1, 1)           # the POC alone is exactly 70% (14 of 20): enough, no further bins


def test_poc_ties_go_to_the_bin_nearest_the_close_then_the_lower():
    c = np.array([5, 1, 5, 1, 1.0])
    assert pr.value_area(c, 4)[0] == 2 and pr.value_area(c, 0)[0] == 0 and pr.value_area(c, 1)[0] == 0   # equidistant -> the lower


def test_tpo_letters_by_hand():
    h, l, v = np.zeros(L), np.zeros(L), np.ones(L)
    for p in range(13):
        sl = slice(p * 30, (p + 1) * 30)
        l[sl], h[sl] = (5000.2, 5002.7) if p == 0 else ((5001.1, 5003.9) if p == 1 else (5001.5, 5001.9))
    k0, counts, w = pr.profile_counts(h, l, v, 5000.0, "tpo")
    assert w == 1.0 and k0 == 5000 and list(counts) == [1.0, 13.0, 2.0, 1.0]       # period 0 touches bins 5000-5002, period 1 bins 5001-5003, eleven periods only bin 5001
    s = pr.session_profile(h, l, v, 5000.0, "tpo")
    assert s == dict(poc=5001.5, val=5001.0, vah=5002.0)                            # 13 of 17 letters already exceed 70%


def test_volume_profile_spreads_each_bar_evenly_over_its_bins_and_conserves_volume():
    h, l, v = np.full(L, 5001.5), np.full(L, 5001.5), np.zeros(L)
    l[0], h[0], v[0] = 5000.2, 5002.7, 30.0                                          # bins 5000, 5001, 5002: 10 each
    v[1] = 7.0                                                                      # a one-bin bar: all 7 in bin 5001
    k0, counts, w = pr.profile_counts(h, l, v, 5000.0, "vol")
    assert k0 == 5000 and np.allclose(counts, [10.0, 17.0, 10.0]) and abs(counts.sum() - 37.0) < 1e-9


def test_profile_properties_on_a_random_market():
    A = rw_market(40, seed=3)
    for mode in pr.MODES:
        for i in range(40):
            k0, counts, w = pr.profile_counts(A["h"][i], A["l"][i], A["v"][i], A["c"][i, -1], mode)
            poc, lo, hi = pr.value_area(counts, int(np.floor(A["c"][i, -1] / w)) - k0)
            assert lo <= poc <= hi and counts[lo:hi + 1].sum() >= pr.VA_FRAC * counts.sum() - 1e-6
            assert counts[poc] == counts.max()
    P = pr.profiles(A, "tpo")
    assert np.all(P["val"] < P["poc"]) and np.all(P["poc"] < P["vah"])                # the POC is a bin CENTRE, the edges are bin edges


def test_prior_flags_block_contract_changes_and_long_gaps():
    dates = pd.DatetimeIndex(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-09", "2026-01-12", "2026-01-20"])     # gaps 1, 1, 2, 3, 8 days
    roll = np.array([True, False, False, True, False, False])
    ok, ok2 = pr.prior_flags(dates, roll)
    assert list(ok) == [False, True, True, False, True, False]            # 3: a contract change; 5: eight days; Fri -> Mon (3 days) would be fine
    assert list(ok2) == [False, False, True, False, False, False]         # 4 follows 3 (a roll) so it has no day-before-yesterday
    ok, _ = pr.prior_flags(dates, np.array([True, False, False, False, False, False]))
    assert list(ok) == [False, True, True, True, True, False]


def test_day_features_exclude_today():
    A = rw_market(40, seed=5)
    base = pr.day_features(A)
    B = {k: v.copy() for k, v in A.items()}
    B["h"][25] *= 1.05                                                    # a huge range today
    f = pr.day_features(B)
    assert f["arf"][25] == base["arf"][25] and f["ibmed"][25] == base["ibmed"][25]     # known BEFORE the session: today's range is not in it
    assert f["arf"][26] != base["arf"][26] and f["ib"][25] != base["ib"][25]
    assert np.isnan(base["arf"][:pr.ATR_WIN]).all() and np.isfinite(base["arf"][pr.ATR_WIN])
    assert np.isnan(base["ibmed"][:pr.IB_BASE_WIN]).all() and np.isfinite(base["ibmed"][pr.IB_BASE_WIN])


# ------------------------------------------------------------------ the rules

def run1(rule, A, P, ok_days, ok2_days=(), F=None):
    n = A["c"].shape[0]
    return rule(A, P, *flags(n, ok_days, ok2_days), F if F is not None else feats(n))


def r1(closes, first_open, val=99.0, vah=101.0, poc=100.0, ok=True):
    A = blank()
    path(A, 5, closes, first_open)
    return run1(pr.rule_r1, A, prof(8, d4=(poc, val, vah), d5=(50.0, 1.0, 2.0)), [5] if ok else [])


def test_r1_enters_after_two_consecutive_inside_closes_toward_the_far_edge():
    assert r1(seg((30, 102.0), (30, 100.5), (330, 100.4)), 102.0) == [dict(i=5, side=-1, m=90, target=99.0)]
    assert r1(seg((30, 98.0), (30, 99.5), (330, 99.6)), 98.0) == [dict(i=5, side=1, m=90, target=101.0)]
    assert r1(seg((29, 102.0), (361, 100.5)), 102.0) == [dict(i=5, side=-1, m=60, target=99.0)]       # the first pair may be the very first checkpoint pair (29, 59)


def test_r1_needs_consecutive_closes_an_outside_open_and_a_valid_prior():
    assert r1(seg((30, 102.0), (30, 100.5), (30, 102.0), (30, 100.5), (30, 102.0), (240, 102.0)), 102.0) == []   # inside, out, inside, out: never two in a row
    assert r1(seg((30, 100.5), (360, 100.5)), 100.5) == []                                                       # the session opened INSIDE value
    assert r1(seg((30, 101.0), (30, 100.5), (330, 100.4)), 101.0) == [] and r1(seg((30, 99.0), (30, 100.5), (330, 100.4)), 99.0) == []   # an open exactly ON an edge is inside
    assert r1(seg((390, 102.0)), 102.0) == []                                                                    # never came back
    assert r1(seg((30, 102.0), (30, 100.5), (330, 100.4)), 102.0, ok=False) == []


def test_r1_value_area_edges_are_inclusive_and_the_target_must_be_five_basis_points_away():
    assert r1(seg((30, 102.0), (30, 101.0), (330, 101.0)), 102.0) == [dict(i=5, side=-1, m=90, target=99.0)]     # closes exactly ON VAH are inside
    assert r1(seg((30, 102.0), (30, 100.45), (330, 100.4)), 102.0, val=100.39) == []                            # the target (100.39) is 1bp under the entry (100.4)
    assert r1(seg((30, 102.0), (30, 100.45), (30, 100.4), (60, 101.0), (240, 101.0)), 102.0, val=100.39, vah=101.5) == []   # the first pair fails the distance test: the day is over, a later pair does not trade


def test_r1_last_decision_pair_is_329_359():
    assert r1(seg((329, 102.0), (61, 100.5)), 102.0) == [dict(i=5, side=-1, m=360, target=99.0)]
    assert r1(seg((359, 102.0), (31, 100.5)), 102.0) == []                                                       # a pair (359, 389) would enter at the 16:00 close: not allowed


def r2(c29, poc=100.0, ok=True, after=None):
    A = blank()
    path(A, 5, seg((30, c29), (360, c29 if after is None else after)), c29)
    return run1(pr.rule_r2, A, prof(8, d4=(poc, 99.0, 101.0), d5=(50.0, 49.0, 51.0)), [5] if ok else [])


def test_r2_trades_toward_the_prior_poc_only_from_fifteen_basis_points_away():
    assert r2(100.3) == [dict(i=5, side=-1, m=30, target=100.0)] and r2(99.7) == [dict(i=5, side=1, m=30, target=100.0)]
    assert r2(100.16) != [] and r2(99.84) != []
    assert r2(100.14) == [] and r2(99.86) == [] and r2(100.0) == []
    assert r2(100.3, ok=False) == []
    assert r2(100.3, after=100.0) == [dict(i=5, side=-1, m=30, target=100.0)] and r2(100.0, after=100.3) == []      # only the 10:00 close decides, not the bar after it


def r3(closes, first_open, highs=(), lows=(), poc=99.6, val=99.0, vah=101.0, ok=True):
    A = blank()
    path(A, 5, closes, first_open)
    for b, x in highs:
        A["h"][5, b] = x
    for b, x in lows:
        A["l"][5, b] = x
    return run1(pr.rule_r3, A, prof(8, d4=(poc, val, vah), d5=(50.0, 1.0, 2.0)), [5] if ok else [])


def test_r3_fades_the_first_edge_touch_after_an_inside_open_with_the_poc_as_the_target():
    assert r3(seg((50, 100.0), (340, 100.5)), 100.0, highs=[(50, 101.2)]) == [dict(i=5, side=-1, m=51, target=99.6)]
    assert r3(seg((50, 100.0), (340, 99.3)), 100.0, lows=[(50, 98.9)]) == [dict(i=5, side=1, m=51, target=99.6)]
    assert r3(seg((50, 100.0), (340, 100.5)), 100.0, highs=[(50, 101.0)]) != []                                    # touching VAH exactly counts
    spec = r3(seg((50, 100.0), (340, 100.5)), 100.0, highs=[(50, 101.2), (90, 101.5)], lows=[(120, 98.5)])
    assert len(spec) == 1 and spec[0]["m"] == 51                                                                   # only the FIRST touch trades


def test_r3_skips_an_outside_open_a_two_sided_bar_a_late_touch_and_a_target_under_five_basis_points():
    assert r3(seg((50, 102.0), (340, 100.5)), 102.0, highs=[(50, 101.2)]) == []
    assert r3(seg((50, 100.0), (340, 100.5)), 100.0, highs=[(50, 101.2)], lows=[(50, 98.8)]) == []
    assert r3(seg((359, 100.0), (31, 100.5)), 100.0, highs=[(359, 101.2)]) == [dict(i=5, side=-1, m=360, target=99.6)]
    assert r3(seg((360, 100.0), (30, 100.5)), 100.0, highs=[(360, 101.2)]) == []
    assert r3(seg((50, 100.0), (340, 100.5)), 100.0, highs=[(50, 101.2)], poc=100.49) == []
    assert r3(seg((50, 100.0), (340, 100.5)), 100.0, highs=[(50, 101.2)], ok=False) == []


def r4(closes, vah=101.0, val=99.0, ok=True):
    A = blank()
    path(A, 5, closes)
    return run1(pr.rule_r4, A, prof(8, d4=(100.0, val, vah), d5=(50.0, 1.0, 2.0)), [5] if ok else [])


def test_r4_goes_with_two_consecutive_closes_outside_value_and_only_the_first_pair_counts():
    assert r4(seg((30, 101.5), (360, 101.6))) == [dict(i=5, side=1, m=60, target=None)]
    assert r4(seg((30, 98.5), (360, 98.4))) == [dict(i=5, side=-1, m=60, target=None)]
    assert r4(seg((30, 101.5), (30, 100.0), (30, 101.5), (30, 101.5), (270, 100.0))) == [dict(i=5, side=1, m=120, target=None)]     # pair (89, 119) after a close back inside
    one = r4(seg((30, 101.5), (30, 101.5), (30, 98.5), (30, 98.5), (270, 98.0)))
    assert one == [dict(i=5, side=1, m=60, target=None)]


def test_r4_edges_are_strict_mixed_sides_do_not_pair_and_the_last_pair_is_329_359():
    assert r4(seg((390, 101.0))) == [] and r4(seg((390, 99.0))) == []                                   # ON the edge is not outside
    assert r4(seg((30, 101.5), (30, 98.5), (330, 100.0))) == []                                         # one above, one below
    assert r4(seg((329, 100.0), (61, 101.5))) == [dict(i=5, side=1, m=360, target=None)]
    assert r4(seg((359, 100.0), (31, 101.5))) == []
    assert r4(seg((30, 101.5), (360, 101.6)), ok=False) == []


def r5(p4, p3, arf=0.02, ok2=True, kind="a", v4=None, v3=None):
    A = blank()
    P = prof(8, d4=(p4, *(v4 or (98.0, 102.0))), d3=(p3, *(v3 or (98.0, 102.0))), d5=(100.0, 98.0, 102.0))
    rule = pr.rule_r5a if kind == "a" else pr.rule_r5b
    return run1(rule, A, P, [5], [5] if ok2 else [], feats(8, arf=arf))


def test_r5a_follows_the_poc_migration_when_it_is_a_quarter_of_the_average_range():
    assert r5(100.0, 99.0) == [dict(i=5, side=1, m=0, target=None)]
    assert r5(98.5, 99.5) == [dict(i=5, side=-1, m=0, target=None)]
    assert r5(99.3, 99.0) == []                                              # 0.3% is under 0.25 x 2%
    assert r5(100.0, 99.0, ok2=False) == [] and r5(100.0, 99.0, arf=np.nan) == []
    assert r5(100.0, 100.0) == []                                            # no migration at all


def test_r5b_needs_the_whole_value_area_above_or_below_the_day_before():
    assert r5(100.0, 99.0, kind="b", v4=(100.6, 102.0), v3=(98.0, 100.5)) == [dict(i=5, side=1, m=0, target=None)]
    assert r5(100.0, 99.0, kind="b", v4=(97.0, 98.9), v3=(99.0, 102.0)) == [dict(i=5, side=-1, m=0, target=None)]
    assert r5(100.0, 99.0, kind="b", v4=(100.5, 102.0), v3=(98.0, 100.5)) == []      # touching is overlap
    assert r5(100.0, 99.0, kind="b", v4=(97.0, 99.0), v3=(99.0, 102.0)) == []        # the same on the short side: VAH == the other VAL is overlap
    assert r5(100.0, 99.0, kind="b", v4=(100.6, 102.0), v3=(98.0, 100.5), ok2=False) == []


def ibday(rest, highs=(), lows=()):
    A = blank()
    closes = np.r_[np.where(np.arange(60) % 2 == 0, 99.5, 100.5), rest]
    path(A, 5, closes, 100.0)
    A["h"][5, 10], A["l"][5, 20] = 101.0, 99.0                              # the initial balance is 99.0 .. 101.0
    for b, x in highs:
        A["h"][5, b] = x
    for b, x in lows:
        A["l"][5, b] = x
    return A


def test_r6a_goes_with_the_first_one_minute_close_outside_the_initial_balance():
    assert pr.rule_r6a(ibday(seg((40, 100.8), (290, 101.5))), None, None, None, None) == [dict(i=5, side=1, m=101, target=None)]
    assert [s for s in pr.rule_r6a(ibday(seg((40, 100.2), (290, 98.5))), None, None, None, None) if s["i"] == 5] == [dict(i=5, side=-1, m=101, target=None)]
    assert pr.rule_r6a(ibday(seg((40, 100.8), (290, 101.5)), highs=[(70, 102.0)]), None, None, None, None)[0]["m"] == 101      # a high through 101 without a CLOSE is not a break


def test_r6a_initial_balance_is_exactly_the_first_sixty_bars():
    spike_after = ibday(seg((40, 100.5), (290, 101.5)), highs=[(60, 103.0)])                   # bar 60 is NOT in the IB: the break at 100 still counts
    assert [s for s in pr.rule_r6a(spike_after, None, None, None, None) if s["i"] == 5] == [dict(i=5, side=1, m=101, target=None)]
    spike_in = ibday(seg((40, 100.8), (290, 101.5)), highs=[(59, 102.0)])                      # bar 59 IS in the IB (IBH 102): 101.5 is not a break
    assert [s for s in pr.rule_r6a(spike_in, None, None, None, None) if s["i"] == 5] == []
    assert [s for s in pr.rule_r6a(ibday(seg((330, 100.5))), None, None, None, None) if s["i"] == 5] == []


def test_r6a_decision_bars_stop_at_359():
    assert pr.rule_r6a(ibday(seg((299, 100.8), (31, 101.5))), None, None, None, None)[0]["m"] == 360
    assert [s for s in pr.rule_r6a(ibday(seg((300, 100.8), (30, 101.5))), None, None, None, None) if s["i"] == 5] == []


def test_r6b_only_when_the_ib_is_narrow_against_its_own_trailing_median():
    A = ibday(seg((40, 100.8), (290, 101.5)))
    F = feats(8, ib=0.02, ibmed=0.04)
    assert [s for s in pr.rule_r6b(A, None, None, None, F) if s["i"] == 5] == [dict(i=5, side=1, m=101, target=None)]       # 2% < 0.6 x 4%
    assert [s for s in pr.rule_r6b(A, None, None, None, feats(8, ib=0.02, ibmed=0.03)) if s["i"] == 5] == []                # 2% is not < 0.6 x 3% = 1.8%
    assert [s for s in pr.rule_r6b(A, None, None, None, feats(8, ib=0.02, ibmed=np.nan)) if s["i"] == 5] == []


def odday(first_open, closes_30, tail, arf=0.02):
    A = blank()
    c = np.r_[closes_30, np.full(L - 30, tail)]
    path(A, 5, c, first_open)
    return pr.rule_r7(A, None, None, None, feats(8, arf=arf))


def test_r7_open_drive_needs_open_at_one_extreme_close_at_the_other_and_a_real_range():
    up = 100.0 + (np.arange(30) + 1) / 30.0                                  # 100.03 .. 101.0
    assert [s for s in odday(100.0, up, 101.0) if s["i"] == 5] == [dict(i=5, side=1, m=30, target=None)]
    down = 100.0 - (np.arange(30) + 1) / 30.0
    assert [s for s in odday(100.0, down, 99.0) if s["i"] == 5] == [dict(i=5, side=-1, m=30, target=None)]
    assert [s for s in odday(100.5, up, 101.0) if s["i"] == 5] == []         # the open sits mid-range
    assert [s for s in odday(100.0, up, 101.0, arf=0.1) if s["i"] == 5] == []   # a 1% range is under 0.25 x a 10% day
    assert [s for s in odday(100.0, up, 101.0, arf=np.nan) if s["i"] == 5] == []


# ------------------------------------------------------------------ look-ahead and alignment on a random market

def specs_for(A, dates, roll, rule):
    P = pr.profiles(A, "tpo")
    ok, ok2 = pr.prior_flags(dates, roll)
    return rule(A, P, ok, ok2, pr.day_features(A))


def test_no_rule_reads_the_entry_bar_or_anything_after_it_and_every_rule_actually_fires():
    n = 220
    A = rw_market(n, seed=11)
    dates, roll = dates_for(n)
    rng = np.random.default_rng(0)
    for name, rule in zip(pr.CELLS, pr.RULES):
        specs = specs_for(A, dates, roll, rule)
        assert len(specs) >= 3, (name, len(specs))                         # a vacuous test would pass anything
        for s in specs[:6]:
            B = {k: v.copy() for k, v in A.items()}
            i, m = s["i"], s["m"]
            for key in "ohlc":                                             # scramble the entry bar and everything after it ...
                B[key][i, m:] = A[key][i, m:] * (1 + rng.normal(0, 0.01, L - m))
            for key in "ohlcv":                                            # ... and every later session
                B[key][i + 1:] = A[key][i + 1:][::-1]
            again = [t for t in specs_for(B, dates, roll, rule) if t["i"] == i]
            assert again == [s], (name, s, again)


def test_rules_that_use_the_prior_session_never_fire_without_one():
    n = 80
    A = rw_market(n, seed=2)
    P = pr.profiles(A, "tpo")
    ok, ok2 = np.zeros(n, bool), np.zeros(n, bool)
    F = pr.day_features(A)
    for rule in (pr.rule_r1, pr.rule_r2, pr.rule_r3, pr.rule_r4, pr.rule_r5a, pr.rule_r5b):
        assert rule(A, P, ok, ok2, F) == []


# ------------------------------------------------------------------ trades and the matched-day control

def one_day(m=10, o=100.0, high_at=None, low_at=None, last=100.5):
    A = blank(1)
    A["c"][0, -1] = last
    A["o"][0, m] = o
    A["h"][0, :], A["l"][0, :] = 100.2, 99.8
    if high_at:
        A["h"][0, high_at[0]] = high_at[1]
    if low_at:
        A["l"][0, low_at[0]] = low_at[1]
    return A


def test_trade_exits_at_the_target_when_touched_and_at_the_close_otherwise():
    A = one_day(high_at=(20, 100.9))
    r, hit = pr.trade_ret(A, 0, 1, 10, 100.8)
    assert hit and abs(r - 0.008) < 1e-12                                  # filled AT the target, not at the high
    r, hit = pr.trade_ret(A, 0, 1, 10, 100.95)
    assert not hit and abs(r - 0.005) < 1e-12                              # never reached: out at the 16:00 close (100.5)
    r, hit = pr.trade_ret(one_day(low_at=(30, 99.2)), 0, -1, 10, 99.2)
    assert hit and abs(r - 0.008) < 1e-12                                  # a short; the touch is a >= / <= test
    r, hit = pr.trade_ret(one_day(), 0, -1, 10, 99.0)
    assert not hit and abs(r - (-0.005)) < 1e-12                           # a short held to a close 0.5% above the entry loses 0.5%


def test_the_entry_bar_counts_and_earlier_bars_do_not():
    assert pr.trade_ret(one_day(high_at=(10, 100.9)), 0, 1, 10, 100.8)[1] is True      # the target is touched IN the entry bar
    assert pr.trade_ret(one_day(high_at=(5, 102.0)), 0, 1, 10, 100.8)[1] is False      # a spike before the entry is not a fill


def test_expected_equals_a_brute_force_loop_over_the_same_days():
    A = rw_market(50, seed=7)
    J = np.arange(10, 35)
    for side in (1, -1):
        for d in (0.004, 0.0015):
            e, h = pr.expected(A, side, 45, d, J)
            rows = [pr.trade_ret(A, j, side, 45, A["o"][j, 45] * (1 + side * d)) for j in J]
            assert abs(e - np.mean([r for r, _ in rows])) < 1e-12 and abs(h - np.mean([x for _, x in rows])) < 1e-12
        e, h = pr.expected(A, side, 45, None, J)
        assert abs(e - np.mean([pr.trade_ret(A, j, side, 45, None)[0] for j in J])) < 1e-12 and math.isnan(h)


def test_expected_counts_the_entry_bar_for_both_sides():
    A = blank(3)
    A["h"][:, 10], A["l"][:, 10] = 100.9, 99.1                          # bar 10 (the entry bar) reaches +0.9% and -0.9%; nothing later does
    e, h = pr.expected(A, 1, 10, 0.008, np.arange(3))
    assert abs(e - 0.008) < 1e-12 and h == 1.0
    e, h = pr.expected(A, -1, 10, 0.008, np.arange(3))
    assert abs(e - 0.008) < 1e-12 and h == 1.0


def test_evaluate_takes_each_trades_expectation_from_its_own_half():
    A = blank(4)
    for j, g in enumerate([0.01, -0.01, 0.02, 0.04]):
        A["c"][j, -1] = 100.0 * (1 + g)
    df = pr.evaluate(A, [dict(i=1, side=1, m=0, target=None), dict(i=3, side=1, m=0, target=None)], 2)
    assert list(df.half) == [0, 1] and np.allclose(df.r, [-0.01, 0.04]) and np.allclose(df.er, [0.0, 0.03])     # tune days (+1%, -1%) average 0, holdout days (+2%, +4%) average 3%
    assert np.allclose(df.r - df.er, [-0.01, 0.01])


# ------------------------------------------------------------------ statistics and the gate

def test_half_stats_by_hand_and_costs_are_charged_once_per_trade():
    df = pd.DataFrame(dict(i=[0, 1, 2], half=[1, 1, 1], side=[1, 1, 1], r=[0.001, 0.002, 0.003], hit=[True, False, False], er=[0.0, 0.0, 0.0], eh=[0.5, 0.5, 0.5]))
    s = pr.half_stats(df, 1)
    t = 2.0 * math.sqrt(3.0)                                                           # mean 20bp, sd 10bp, n 3 -> t = 20 / (10 / sqrt 3)
    assert s["n"] == 3 and abs(s["gross"] - 20.0) < 1e-9 and abs(s["net"] - (20.0 - pr.COST_BP)) < 1e-9
    assert abs(s["ex"] - 20.0) < 1e-9 and abs(s["tex"] - t) < 1e-9
    assert abs(s["p"] - 0.5 * math.erfc(t / math.sqrt(2))) < 1e-12 and abs(s["hit"] - 1 / 3) < 1e-12 and s["ehit"] == 0.5
    assert abs(pr.half_stats(df, 1, cost_bp=5.0)["net"] - 15.0) < 1e-9
    assert pr.half_stats(df, 0)["n"] == 0 and pr.half_stats(df, 0)["p"] == 1.0


def test_holm_by_hand():
    assert np.allclose(pr.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])             # 0.01 x 3; 0.03 x 2 = 0.06; 0.04 x 1 = 0.04 -> carried up to 0.06
    assert np.allclose(pr.holm([0.5, 0.9]), [1.0, 1.0])                              # adjusted p's never fall below an earlier one


def good():
    return dict(n=500, net=2.0, ex=1.5, tex=2.5), dict(n=300, net=2.0, ex=1.5, tex=2.5, padj=0.01)


def test_the_volume_plateau_needs_a_positive_net_on_both_halves():
    pos, neg = dict(net=1.0), dict(net=-1.0)
    assert pr.plateau_ok(pos, pos) and not pr.plateau_ok(pos, neg) and not pr.plateau_ok(neg, pos) and not pr.plateau_ok(neg, neg)
    assert not pr.plateau_ok(dict(net=float("nan")), pos)                            # a half with no trades is no agreement


def test_verdicts_take_the_tpo_numbers_and_need_the_volume_construction_to_agree():
    tu, ho = good()
    vol_good = (dict(net=1.0), dict(net=1.0))
    stats = {("tpo", c): (dict(tu), dict(ho)) for c in pr.CELLS}
    stats.update({("vol", c): vol_good for c in pr.CELLS})
    stats["vol", pr.CELLS[2]] = (dict(net=1.0), dict(net=-1.0))                       # VOL fails on the holdout for one cell only
    v = pr.verdicts_from(stats)
    assert v[pr.CELLS[2]] == "LEAD" and all(v[c] == "PASS" for c in pr.CELLS if c != pr.CELLS[2])
    stats["tpo", pr.CELLS[0]] = (dict(tu, net=-1.0), dict(ho))                        # and the TPO half decides the rest
    assert pr.verdicts_from(stats)[pr.CELLS[0]] != "PASS"


def test_every_gate_clause_matters_on_its_own():
    tu, ho = good()
    assert pr.verdict(tu, ho, True) == "PASS"
    for key, bad, expect in [("net", -1.0, "no"), ("ex", -0.1, "no")]:
        t2 = dict(tu); t2[key] = bad
        h2 = dict(ho); h2[key] = bad
        assert pr.verdict(t2, ho, True) != "PASS" and pr.verdict(tu, h2, True) != "PASS", key
    h2 = dict(ho, padj=0.2)
    assert pr.verdict(tu, h2, True) == "LEAD"                                        # t >= 2 on both halves but Holm fails: a lead, not a pass
    assert pr.verdict(tu, ho, False) == "LEAD"                                       # the volume construction did not agree: a lead, not a pass
    assert pr.verdict(tu, dict(ho, n=99), True) == "UNDERPOWERED" and pr.verdict(tu, dict(ho, n=100), True) == "PASS"
    assert pr.verdict(dict(tu, tex=1.0), dict(ho, padj=0.2), True) == "no"


# ------------------------------------------------------------------ whole pipeline

def plant_ib_continuation(A, drift):
    for i in range(A["c"].shape[0]):
        r = pr._ib_break(A, i)
        if r is None:
            continue
        side, m = r
        f = 1 + side * drift * (np.arange(L - m) + 1) / (L - m)
        for key in "ohlc":
            A[key][i, m:] = A[key][i, m:] * f


def run_pipeline(A):
    n = A["c"].shape[0]
    dates, roll = dates_for(n)
    return pr.analyze(A, dates, roll, int(pr.TUNE * n))


def test_a_planted_initial_balance_continuation_passes_and_a_pure_random_walk_does_not():
    A = rw_market(700, seed=21)
    plant_ib_continuation(A, 0.01)
    blocks, stats, verdicts = run_pipeline(A)
    assert verdicts["R6a IB break"] == "PASS", stats["tpo", "R6a IB break"]
    tu, ho = stats["tpo", "R6a IB break"]
    assert tu["net"] > 20 and ho["net"] > 20 and ho["n"] > 150
    for mode in pr.MODES:                                                            # analyze() applies Holm over the nine cells of each construction
        assert np.allclose([stats[mode, c][1]["padj"] for c in pr.CELLS], pr.holm([stats[mode, c][1]["p"] for c in pr.CELLS]))
        assert any(stats[mode, c][1]["padj"] > stats[mode, c][1]["p"] + 1e-9 for c in pr.CELLS)
    _, stats, verdicts = run_pipeline(rw_market(700, seed=22))
    assert "PASS" not in verdicts.values(), (verdicts, {k: v for k, v in stats.items() if k[0] == "tpo"})


def test_a_strong_drift_flatters_the_raw_return_but_not_the_matched_excess():
    A = rw_market(700, seed=23, drift=0.006)
    _, stats, verdicts = run_pipeline(A)
    tu, ho = stats["tpo", "R6a IB break"]
    assert tu["gross"] > 5 and ho["gross"] > 5                                        # the up-drift pays the (mostly long) trades ...
    assert abs(tu["tex"]) < 3 and abs(ho["tex"]) < 3                                  # ... and the matched days pay it too: nothing left over
    assert "PASS" not in verdicts.values()


if __name__ == "__main__":
    tests = sorted((v for k, v in globals().items() if k.startswith("test_")), key=lambda f: f.__code__.co_firstlineno)
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
