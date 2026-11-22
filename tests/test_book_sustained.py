"""Offline tests for backtest/book_sustained.py - run lengths and gaps, the causal trigger, entry/exit prices, the same-hour baseline, one planted
day through day_cells(), pooling / Holm and the fee arithmetic. Synthetic data only.

    python tests/test_book_sustained.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import book_sustained as bs  # noqa: E402

T0 = 472_222 * 3_600_000                                  # an hour boundary
assert T0 % 3_600_000 == 0


def secs(n, start=0):
    return T0 + (np.arange(n) + start) * 1000


def test_run_lengths_count_consecutive_trues_and_a_time_gap_breaks_a_run():
    c = np.array([0, 1, 1, 1, 0, 1, 1, 1, 1], bool)
    t = secs(9)
    assert bs.run_lengths(c, t).tolist() == [0, 1, 2, 3, 0, 1, 2, 3, 4]
    t2 = t.copy()
    t2[6:] += 10_000                                      # a ten-second hole between samples 5 and 6, both true
    assert bs.run_lengths(c, t2).tolist() == [0, 1, 2, 3, 0, 1, 1, 2, 3]
    assert bs.run_durations(c, t).tolist() == [3, 4]
    assert bs.run_durations(np.array([1, 0, 1, 1], bool), secs(4)).tolist() == [1, 2]       # a run of one and a run at the very end


def test_trigger_is_the_first_second_a_run_reaches_the_window_and_uses_only_the_past():
    c = np.array([0, 1, 1, 1, 1, 1, 0, 1, 1, 0], bool)
    t = secs(10)
    assert bs.trigger_idx(c, t, 3).tolist() == [3]                                            # the run 1..5 reaches 3 at index 3; the run 7..8 never does
    assert bs.trigger_idx(c, t, 1).tolist() == [1, 7]
    rng = np.random.default_rng(1)
    cc = rng.random(400) < 0.7
    tt = secs(400)
    full = bs.trigger_idx(cc, tt, 4)
    for cut in (50, 120, 399):
        part = bs.trigger_idx(cc[:cut], tt[:cut], 4)
        assert part.tolist() == [i for i in full.tolist() if i < cut]                         # later seconds never create or move an earlier trigger


def test_moves_enter_at_the_ask_exit_at_the_bid_and_void_an_exit_off_the_grid():
    n = 12
    t = secs(n)
    mid = np.linspace(100.0, 101.1, n)
    bid, ask = mid - 0.005, mid + 0.005
    v, mv, tl, ts = bs.moves(t, bid, ask, mid, np.array([2]), 3000)
    assert v.tolist() == [True]
    assert abs(mv[0] - (mid[5] / mid[2] - 1) * 1e4) < 1e-9
    assert abs(tl[0] - (bid[5] / ask[2] - 1) * 1e4) < 1e-9 and abs(ts[0] - (bid[2] / ask[5] - 1) * 1e4) < 1e-9
    assert tl[0] < mv[0] < 0 + mv[0] + 1 and tl[0] < mv[0]                                    # crossing the spread costs
    v2, *_ = bs.moves(t, bid, ask, mid, np.array([10]), 3000)
    assert v2.tolist() == [False]                                                             # the exit time is past the end of the data
    t3 = t.copy()
    t3[5:] += 5000                                                                            # the grid has a hole where the exit should be
    v3, *_ = bs.moves(t3, bid, ask, mid, np.array([2]), 3000)
    assert v3.tolist() == [False]


def test_hour_baseline_averages_within_each_clock_hour():
    t = np.array([T0, T0 + 1000, T0 + 3_600_000, T0 + 3_601_000], dtype=np.int64)
    hb = bs.hour_baseline(t, np.array([1.0, 3.0, 10.0, 99.0]), np.array([True, True, True, False]))
    assert hb == {T0 // 3_600_000: 2.0, T0 // 3_600_000 + 1: 10.0}


def planted_day(n=700):
    """Flat book at 1.0000 / 1.0002; imb1 sits at +0.9 from second 100 to 200 (101 samples); the price steps up 100 bp at second 161."""
    t = secs(n)
    bid = np.full(n, 1.0000)
    ask = np.full(n, 1.0002)
    bid[161:] = 1.0100
    ask[161:] = 1.0102
    df = pd.DataFrame(dict(t=t, bid=bid, ask=ask))
    df["mid"] = (df.bid + df.ask) / 2
    df["spread"] = (df.ask / df.bid - 1) * 1e4
    for f in bs.FEATS:
        df[f] = 0.0
    df.loc[100:200, "imb1"] = 0.9
    return df


def test_one_planted_day_through_day_cells():
    df = planted_day()
    cells = bs.day_cells(df)
    k60 = ("imb1", 0.8, 60, 1, 30)
    assert k60 in cells
    e = cells[k60]
    assert len(e["gross"]) == 1
    # trigger at index 159 (run starts at 100), entry at 160 (price still flat), exit at 190 (after the step): about +100 bp on the mid
    assert 99.0 < e["gross"][0] < 101.0
    assert e["taker0"][0] < e["gross"][0]                                                     # buying the ask and selling the bid gives up the spread
    assert abs(e["spread"][0] - 2.0) < 0.1
    assert ("imb1", 0.8, 60, -1, 30) not in cells and ("imb5", 0.8, 60, 1, 30) not in cells    # nothing else fires
    e1 = cells[("imb1", 0.8, 1, 1, 30)]
    assert len(e1["gross"]) >= 1 and e1["gross"][0] < 1.0                                      # an onset at 100: entry 101, exit 131: still flat
    assert cells[k60]["base"][0] == cells[k60]["base"][0]                                      # a baseline exists for the hour (not NaN)
    # the same hour holds the step, so the baseline is the mean over that hour's valid entries and is positive but far below 100
    assert 0 < e["base"][0] < 30


def test_trailing_window_when_the_condition_is_shorter_than_the_window_fires_nothing():
    df = planted_day()
    df.loc[100:200, "imb1"] = 0.0
    df.loc[100:140, "imb1"] = 0.9                                                             # only 41 seconds
    assert ("imb1", 0.8, 60, 1, 30) not in bs.day_cells(df)
    assert ("imb1", 0.8, 30, 1, 30) in bs.day_cells(df)


def synthetic_days(mu_gross, mu_taker0, n=150, days=7, seed=0):
    rng = np.random.default_rng(seed)
    out = {}
    for d in range(days):
        out[f"d{d}"] = {("imb1", 0.8, 60, 1, 60): dict(gross=mu_gross + rng.normal(0, 3, n), taker0=mu_taker0 + rng.normal(0, 3, n),
                                                       base=np.zeros(n), spread=np.full(n, 2.0))}
    return out


def test_pool_and_pass_need_a_net_gain_a_low_p_value_and_five_good_days():
    good = bs.pool(synthetic_days(40.0, 38.0))
    assert good[("imb1", 0.8, 60, 1, 60)]["n"] == 1050 and good[("imb1", 0.8, 60, 1, 60)]["days"] == 7
    pn, pm = bs.passes(good)
    assert ("imb1", 0.8, 60, 1, 60) in pn and ("imb1", 0.8, 60, 1, 60) in pm                  # +26 bp net of 12 bp fees, t huge, all days positive
    bad = bs.pool(synthetic_days(2.0, 0.5))
    pn2, pm2 = bs.passes(bad)
    assert not pn2 and not pm2                                                                # +0.5 bp before 12 bp of fees; +2 bp gross against the 4 bp maker bound
    mid = bs.pool(synthetic_days(8.0, 6.0))
    pn3, pm3 = bs.passes(mid)
    assert not pn3 and ("imb1", 0.8, 60, 1, 60) in pm3                                         # the maker-ideal bound can pass while the taker net does not
    days = synthetic_days(40.0, 38.0)
    for d in ("d0", "d1", "d2"):
        days[d][("imb1", 0.8, 60, 1, 60)]["taker0"] = days[d][("imb1", 0.8, 60, 1, 60)]["taker0"] - 60.0     # three days lose badly
    rows = bs.pool(days)
    assert rows[("imb1", 0.8, 60, 1, 60)]["dpos"] == 4                                        # only four days are positive
    few = synthetic_days(40.0, 38.0, n=10)
    assert not bs.passes(bs.pool(few))[0]                                                     # under MIN_EVENTS events: never a pass


def test_fee_arithmetic_leverage_multiplies_the_fee_against_margin_not_against_notional():
    assert abs(bs.margin_cost_pct(12.0, 1) - 0.12) < 1e-12
    assert abs(bs.margin_cost_pct(12.0, 10) - 1.2) < 1e-12
    assert abs(bs.margin_cost_pct(4.0, 100) - 4.0) < 1e-12
    assert abs(bs.margin_cost_pct(0.0, 100)) < 1e-12


def test_persistence_rows_report_how_long_runs_last():
    df = planted_day()
    rows = bs.persistence_rows({"d": df})
    r = [x for x in rows if x["feat"] == "imb1" and x["thr"] == 0.8 and x["side"] > 0][0]
    assert r["runs"] == 1 and r["med"] == 101 and r["p60"] == 1.0 and r["longest"] == 101
    r0 = [x for x in rows if x["feat"] == "imb20" and x["thr"] == 0.8 and x["side"] > 0][0]
    assert r0["runs"] == 0 and r0["share"] == 0.0


def test_a_run_of_one_next_to_a_run_of_one_across_a_gap_is_two_runs():
    c = np.array([1, 1], bool)
    t = np.array([T0, T0 + 20_000])
    assert bs.run_durations(c, t).tolist() == [1, 1]


def test_entry_is_the_second_AFTER_the_trigger_so_a_jump_in_that_second_is_missed():
    df = planted_day()
    df.loc[160:, "bid"] = 1.0100                                                              # the step now happens at second 160 = the entry second
    df.loc[160:, "ask"] = 1.0102
    df.loc[:159, "bid"] = 1.0000
    df.loc[:159, "ask"] = 1.0002
    df["mid"] = (df.bid + df.ask) / 2
    e = bs.day_cells(df)[("imb1", 0.8, 60, 1, 30)]
    assert abs(e["gross"][0]) < 1.0                                                           # entered AT the post-step price: nothing left to earn
    assert e["taker0"][0] < 0                                                                 # and the spread is paid


def test_the_short_side_earns_from_a_fall_and_its_baseline_has_the_same_sign():
    df = planted_day()
    df["imb1"] = 0.0
    df.loc[100:200, "imb1"] = -0.9                                                            # sellers dominate
    df.loc[:160, "bid"] = 1.0100
    df.loc[:160, "ask"] = 1.0102
    df.loc[161:, "bid"] = 1.0000
    df.loc[161:, "ask"] = 1.0002                                                              # the price steps DOWN 100 bp at second 161
    df["mid"] = (df.bid + df.ask) / 2
    e = bs.day_cells(df)[("imb1", 0.8, 60, -1, 30)]
    assert 99.0 < e["gross"][0] < 101.0 and e["taker0"][0] > 95.0                            # a short gains the fall
    assert e["base"][0] > 0                                                                  # the hour's baseline for a short is positive too (price falls in that hour)


def test_events_are_at_least_h_seconds_apart():
    df = planted_day()
    df["imb1"] = 0.0
    for a in (100, 110, 120):
        df.loc[a:a + 4, "imb1"] = 0.9                                                         # three onsets 10 s apart
    e = bs.day_cells(df)[("imb1", 0.8, 1, 1, 30)]
    assert len(e["gross"]) == 1                                                               # with a 30 s hold only the first can be taken
    e2 = bs.day_cells(df)[("imb1", 0.8, 1, 1, 30)]
    df2 = df.copy()
    for a in (100, 200, 300):
        df2.loc[a:a + 4, "imb1"] = 0.9
    assert len(bs.day_cells(df2)[("imb1", 0.8, 1, 1, 30)]["gross"]) == 3                      # far enough apart: all three


def test_pooled_columns_subtract_exactly_two_legs_of_fees():
    rows = bs.pool(synthetic_days(40.0, 38.0))
    r = rows[("imb1", 0.8, 60, 1, 60)]
    assert abs(r["net"] - (r["taker0"] - 2 * bs.TAKER_BP)) < 1e-9 and abs(r["mk"] - (r["gross"] - 2 * bs.MAKER_BP)) < 1e-9
    assert abs(r["net"] - 26.0) < 1.0 and abs(r["mk"] - 36.0) < 1.0


def test_four_good_days_of_seven_never_pass_even_with_a_huge_pooled_t():
    days = synthetic_days(40.0, 38.0)
    for d in ("d0", "d1", "d2"):
        days[d][("imb1", 0.8, 60, 1, 60)]["taker0"] = days[d][("imb1", 0.8, 60, 1, 60)]["taker0"] * 0 + 11.0       # a hair under the 12 bp of fees
        days[d][("imb1", 0.8, 60, 1, 60)]["gross"] = days[d][("imb1", 0.8, 60, 1, 60)]["gross"] * 0 + 3.5            # a hair under the 4 bp maker bound
    rows = bs.pool(days)
    r = rows[("imb1", 0.8, 60, 1, 60)]
    assert r["dpos"] == 4 and r["dmk"] == 4 and r["net_t"] > 5 and r["mk_t"] > 5
    pn, pm = bs.passes(rows)
    assert not pn and not pm


def test_persistence_boundaries_and_the_still_on_a_minute_later_share():
    t = secs(300)
    df = pd.DataFrame(dict(t=t, imb1=0.0))
    df.loc[50:59, "imb1"] = 0.9                                                               # a run of exactly 10
    df.loc[100:139, "imb1"] = 0.9                                                             # a run of exactly 40
    for f in bs.FEATS[1:]:
        df[f] = 0.0
    r = [x for x in bs.persistence_rows({"d": df}) if x["feat"] == "imb1" and x["thr"] == 0.8 and x["side"] > 0][0]
    assert r["runs"] == 2 and r["p10"] == 1.0 and r["p30"] == 0.5 and r["p60"] == 0.0
    d = planted_day()
    r2 = [x for x in bs.persistence_rows({"d": d}) if x["feat"] == "imb1" and x["thr"] == 0.8 and x["side"] > 0][0]
    assert abs(r2["still60"] - 41 / 101) < 1e-9                                               # of 101 seconds on, 41 are still on 60 s later


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
