"""Tests for backtest/combo_wide.py (out-of-universe candidates, frozen model), combo_rangerev.py (same-side control, matched strata, shift-null) and combo_rowcheck.py (per-call statistic) - against hand cases.

Run as a script (no pytest on this PC):  python tests/test_combo_wide.py     (exit code 0 = all passed)
"""
import gzip
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.combo_direction as cd  # noqa: E402
import backtest.combo_meta as cm  # noqa: E402
import backtest.combo_rangerev as rr  # noqa: E402
import backtest.combo_rowcheck as rc  # noqa: E402
import backtest.combo_screen as cs  # noqa: E402
import backtest.combo_wide as cw  # noqa: E402

H1 = cm.H1


def near(a, b, tol=1e-9):
    return abs(a - b) < tol


# ------------------------------------------------------------------ combo_wide

def test_an_entry_needs_the_previous_24_hours_and_the_whole_bracket_to_be_consecutive_hours_on_the_timestamps():
    hrs = np.r_[np.arange(0, 100), np.arange(101, 201)]                 # one hour missing between index 99 and 100
    t = hrs * H1
    j = np.array([5, 90, 110, 130, 190, 150])
    ok = cw.contiguous_entries(t, j, 24)
    assert ok.tolist() == [False, False, False, True, False, True]
    # j=5: fewer than 24 bars before it; j=90: the bracket 90..113 spans the hole; j=110: the 24 bars before it span the hole;
    # j=130: clean on both sides; j=190: the bracket would run past the end of the data; j=150: clean
    t2 = np.arange(0, 200) * H1
    t2[25:] += 19 * H1                                                      # a 19-hour hole right after bar 24: bars 24..28 then span exactly 23 hours
    assert cw.contiguous_entries(t2, np.array([5]), 24).tolist() == [False]  # j=5 still has fewer than 24 bars before it, whatever the clock between bars 24 and 28 looks like


def test_month_of_gives_the_calendar_month_of_the_open_time():
    ms = np.array([pd.Timestamp("2023-01-31 23:00").value // 10 ** 6, pd.Timestamp("2023-02-01 00:00").value // 10 ** 6])
    assert cw.month_of(ms).tolist() == ["2023-01", "2023-02"]


def walk(n, seed, start="2023-01-01"):
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp(start).value // 10 ** 6
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame(dict(o=o, h=np.maximum(o, c) * 1.002, l=np.minimum(o, c) * 0.998, c=c), index=(t0 + np.arange(n) * H1).astype("int64"))


def test_candidates_exist_only_in_a_coins_eligible_months_at_the_four_hours_and_both_sides():
    bars = {"AAA": walk(24 * 70, 1), "BBB": walk(24 * 70, 2)}
    elig = {"AAA": {"2023-01"}, "BBB": {"2023-01", "2023-02"}}
    d = cw.wide_candidates(bars, elig, (0.012, 0.024, 24))
    mon = pd.to_datetime(d.made_ms, unit="ms").dt.strftime("%Y-%m")
    assert set(mon[d.symbol == "AAA"]) == {"2023-01"}
    assert set(mon[d.symbol == "BBB"]) == {"2023-01", "2023-02"}
    assert set(((d.made_ms // H1) % 24)) == {0, 6, 12, 18} and set(d.side) == {"long", "short"}
    n_a, n_b = (d.symbol == "AAA").sum(), (d.symbol == "BBB").sum()
    assert n_a == 31 * 4 * 2 - 0 or n_a <= 31 * 4 * 2                      # at most 31 days x 4 hours x 2 sides
    assert n_b > n_a and (d.base_p.between(0, 1)).all()
    q = d.t.dt.to_period("Q").astype(str)
    for (qq, sd), g in d.groupby([q, d.side]):
        assert np.allclose(g.base_p, g.win.mean())


def test_a_hole_in_the_candles_removes_the_candidates_whose_bracket_or_history_would_span_it():
    b = walk(24 * 30, 3)
    b = b.drop(b.index[24 * 15])                                           # one hour missing mid-month
    d = cw.wide_candidates({"AAA": b}, {"AAA": {"2023-01"}}, (0.012, 0.024, 24))
    hole = int(b.index[24 * 15 - 1]) + H1                                  # the missing hour's open time
    s = d.made_ms.to_numpy()
    assert not ((s > hole - 24 * H1) & (s <= hole)).any()                  # no entry whose 24-hour bracket contains the hole
    assert not ((s >= hole) & (s < hole + 24 * H1)).any()                  # no entry whose 24 previous bars contain the hole


def test_load_perp_keeps_the_first_continuous_episode_and_drops_bad_rows():
    with tempfile.TemporaryDirectory() as td:
        old = cw.PERPS
        cw.PERPS = Path(td)
        try:
            t1 = pd.date_range("2023-01-01", periods=1000, freq="h")
            t2 = pd.date_range(t1[-1] + pd.Timedelta(hours=100), periods=500, freq="h")           # a relisting after a 100-hour gap
            tt = t1.append(t2)
            df = pd.DataFrame(dict(time=tt.strftime("%Y-%m-%d %H:%M:%S"), open=1.0, high=1.1, low=0.9, close=1.0, qvol=1.0))
            df.loc[3, "close"] = 0.0                                                              # a zero close is dropped
            with gzip.open(Path(td) / "XXXUSDT_1h.csv.gz", "wt") as f:
                df.to_csv(f, index=False)
            b = cw.load_perp("XXXUSDT")
            assert b is not None and len(b) == 999 and b.index.max() == int(t1[-1].value // 10 ** 6)
            short = df.iloc[:300]
            with gzip.open(Path(td) / "SHORTUSDT_1h.csv.gz", "wt") as f:
                short.to_csv(f, index=False)
            assert cw.load_perp("SHORTUSDT") is None and cw.load_perp("NOPEUSDT") is None
        finally:
            cw.PERPS = old


def synth_universe(n, seed, start="2022-01-01", end="2024-07-01", syms=("AAA", "BBB", "CCC")):
    rng = np.random.default_rng(seed)
    ms = np.sort(rng.integers(pd.Timestamp(start).value // 10 ** 6, pd.Timestamp(end).value // 10 ** 6, n))
    d = pd.DataFrame(dict(made_ms=ms, symbol=rng.choice(syms, n), side=rng.choice(["long", "short"], n)))
    d["t"] = pd.to_datetime(d.made_ms, unit="ms")
    X = pd.DataFrame(rng.normal(size=(n, 3)), columns=["x1", "x2", "x3"])
    d["r_net"] = 0.3 * X.x1.to_numpy() + rng.normal(size=n)
    return d, X


def test_the_frozen_model_uses_only_training_candidates_before_each_fold_and_the_embargo():
    tr, Xtr = synth_universe(9000, 5)
    te, Xte = synth_universe(3000, 6, syms=("ZZZ",))
    base = cw.frozen_predictions(tr, Xtr, te, Xte)
    assert base.pred.notna().sum() > 1000
    fold_a = pd.Timestamp("2023-07-01")
    cut = int(fold_a.timestamp() * 1000)
    tr2 = tr.copy()
    late = tr2.made_ms >= cut                                              # labels from the fold start on can never have been used for that fold
    tr2.loc[late, "r_net"] += 100.0 * (Xtr.loc[late, "x2"] > 0)
    w2 = cw.frozen_predictions(tr2, Xtr, te, Xte)
    inside = (te.t >= fold_a) & (te.t < pd.Timestamp("2023-10-01"))
    assert inside.sum() > 100 and np.allclose(base.pred[inside], w2.pred[inside])
    emb = (tr.made_ms >= cut - cm.EMBARGO_MS) & (tr.made_ms < cut)        # the 72 hours before the fold start are embargoed
    tr3 = tr.copy()
    tr3.loc[emb, "r_net"] += 100.0 * (Xtr.loc[emb, "x2"] > 0)
    w3 = cw.frozen_predictions(tr3, Xtr, te, Xte)
    assert emb.sum() > 5 and np.allclose(base.pred[inside], w3.pred[inside])
    after = (te.t >= pd.Timestamp("2024-01-01"))
    assert after.sum() > 100 and not np.allclose(base.pred[after], w2.pred[after])      # but later folds DO learn from them


# ------------------------------------------------------------------ combo_rangerev

def test_the_reversal_score_is_centred_and_points_long_at_the_low_and_short_at_the_high():
    pos = np.array([0.1, 0.9, 0.9, 0.1, 0.5])
    side = np.array([1.0, -1.0, 1.0, -1.0, 1.0])
    assert np.allclose(rr.reversal_score(pos, side), [0.4, 0.4, -0.4, -0.4, 0.0])


def synth_sides(n_days=200, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n_days):
        for sym in ("AAA", "BBB"):
            for hr in (0, 6, 12, 18):
                for side in ("long", "short"):
                    rows.append((pd.Timestamp("2023-01-01") + pd.Timedelta(days=k, hours=hr), sym, side))
    d = pd.DataFrame(rows, columns=["t", "symbol", "side"])
    d["made_ms"] = (d.t.astype("datetime64[ns]").astype("int64") // 10 ** 6).to_numpy()
    d["day"] = d.t.dt.strftime("%Y-%m-%d")
    d["stop_pct"] = 0.012
    d["win"] = 0.0
    d["base_p"] = 0.25
    d["r_net"] = rng.normal(0, 1, len(d))
    return d


def test_selection_takes_the_top_fraction_within_each_quarter_and_side_and_never_a_missing_score():
    d = synth_sides(180)
    rng = np.random.default_rng(3)
    score = rng.normal(size=len(d))
    score[::17] = np.nan
    sel = rr.select_by_side(d, score, 0.10)
    s = pd.Series(score, index=d.index)
    q = rr.quarter_key(d.t)
    assert not sel[s.isna()].any()
    for (qq, sd), g in d.groupby([q, d.side]):
        v = s[g.index].dropna()
        k = int(sel[g.index].sum())
        assert abs(k - 0.10 * len(v)) <= 1
        assert (v[sel[g.index][v.index]].min() >= v[~sel[g.index][v.index]].max())   # every selected score beats every unselected one in its group


def test_the_same_side_control_does_not_credit_a_side_drift_to_the_signal():
    d = synth_sides(300)
    drift = np.where(d.side == "short", 0.30, -0.30)                       # shorts earn +0.30, longs -0.30 for every candidate
    d["r_net"] = drift + np.random.default_rng(9).normal(0, 0.6, len(d))
    rng = np.random.default_rng(10)
    sel = pd.Series((d.side == "short").to_numpy() & (rng.random(len(d)) < 0.10), index=d.index)       # a random 10% of the SHORTS: no skill at all
    st = rr.same_side_diff(d, sel)
    assert abs(st["diff"]) < 0.08                                          # not the +0.3 an all-sides baseline would show (0.30 vs the pooled mean 0.0)
    assert st["sel_r"] > 0.2 and near(st["ctl_r"], d[d.side == "short"].groupby(["day", "side"]).r_net.mean().mean())


def test_same_side_diff_by_hand_and_the_within_bet_uplift():
    days = list("abcdef")
    first = [1.0, 2.0, 0.0, 1.0, 3.0, 0.5]                                  # the first call of each day; the second call of each day is below
    second = [-1.0, 0.0, 0.0, 1.0, -1.0, 0.5]
    d = pd.DataFrame(dict(day=days * 2, side=["long"] * 12, r_net=first + second))
    sel = pd.Series([True] * 5 + [False] + [False] * 6)                      # the first call of days a-e is selected; day f has none
    st = rr.same_side_diff(d, sel)
    # selected bets: a 1, b 2, c 0, d 1, e 3 (mean 1.4); all bets (day means): 0, 1, 0, 1, 1, 0.5 (mean 3.5 / 6)
    assert near(st["sel_r"], 1.4) and near(st["ctl_r"], 3.5 / 6) and near(st["diff"], 1.4 - 3.5 / 6) and st["bets"] == 5 and st["n"] == 5
    assert near(st["uplift"], ((1 - 0) + (2 - 1) + (0 - 0) + (1 - 1) + (3 - 1)) / 5) and np.isfinite(st["t"])
    few = rr.same_side_diff(d.iloc[[0, 1, 6, 7]].reset_index(drop=True), pd.Series([True, True, False, False]))
    assert not np.isfinite(few["t"])                                         # fewer than five bets: no t


def test_matched_diff_is_the_selected_minus_unselected_of_the_same_stratum_and_side_weighted_by_selected_calls():
    rows = []
    for stratum, (sel_mean, un_mean, n_sel) in {"s1": (1.0, 0.0, 3), "s2": (0.5, 0.0, 1)}.items():
        for k in range(n_sel):
            rows.append((stratum, "long", True, sel_mean))
        for k in range(10):
            rows.append((stratum, "long", False, un_mean))
    rows += [("s3", "long", True, 9.0)] + [("s3", "long", False, 0.0)] * 2           # too few unselected (< 5): skipped
    d = pd.DataFrame(rows, columns=["stratum", "side", "sel", "r_net"])
    diff, n = rr.matched_diff(d, d.sel, ["stratum"])
    assert n == 4 and near(diff, (1.0 * 3 + 0.5 * 1) / 4)


def test_the_shift_null_finds_a_selection_tied_to_outcomes_and_not_a_random_one():
    d = synth_sides(400, seed=4).sort_values("made_ms", kind="stable").reset_index(drop=True)
    rng = np.random.default_rng(5)
    sel_rand = pd.Series(rng.random(len(d)) < 0.05, index=d.index)
    d_planted = d.copy()
    d_planted.loc[sel_rand, "r_net"] += 1.5
    obs, p, sd = rr.shift_null(d_planted, sel_rand, np.random.default_rng(6), shifts=200)
    assert obs > 1.2 and p < 0.02
    obs0, p0, sd0 = rr.shift_null(d, sel_rand, np.random.default_rng(7), shifts=200)
    assert abs(obs0) < 0.4 and p0 > 0.05


def test_slippage_is_charged_in_r_as_basis_points_over_the_stop():
    d = pd.DataFrame(dict(r_net=[0.5, -1.0], stop_pct=[0.012, 0.02]))
    assert np.allclose(rr.slip_adjusted(d, 6.0), [0.5 - 0.0006 / 0.012, -1.0 - 0.0006 / 0.02])


# ------------------------------------------------------------------ combo_rowcheck

def test_per_call_excess_uses_the_same_side_mean_and_a_weekly_cluster_standard_error_by_hand():
    wa = pd.Timestamp("2023-01-04")                                         # two different ISO weeks
    wb = pd.Timestamp("2023-01-11")
    rows = [(wa, "short", 0.9, True)] * 10 + [(wb, "short", 1.1, True)] * 10 + [(wa, "short", -1.0, False)] * 10 + [(wa, "long", 5.0, False)] * 12
    d = pd.DataFrame(rows, columns=["t", "side", "r_net", "sel"])
    st = rc.per_call(d, d.sel)
    ctl = (9.0 + 11.0 - 10.0) / 30                                          # the mean of ALL shorts; the longs do not enter
    m = ((0.9 - ctl) + (1.1 - ctl)) / 2
    se = math.sqrt(2.0) / 20                                                # weekly residuals -1 and +1 (see the derivation in the test above)
    assert st["n"] == 20 and near(st["sel_r"], 1.0) and near(st["ctl_r"], ctl) and near(st["diff"], m)
    assert abs(st["t"] - m / se) < 1e-6


def test_per_call_needs_twenty_selected_calls():
    d = pd.DataFrame(dict(t=pd.Timestamp("2023-01-01"), side="long", r_net=0.1, sel=[True] * 19 + [False] * 5))
    assert not np.isfinite(rc.per_call(d, d.sel)["diff"])


def test_a_selection_of_all_shorts_in_a_short_drift_period_has_no_excess_per_call():
    d = synth_sides(250, seed=8)
    d["r_net"] = np.where(d.side == "short", 0.4, -0.4) + np.random.default_rng(2).normal(0, 0.5, len(d))
    sel = pd.Series((d.side == "short").to_numpy(), index=d.index)
    st = rc.per_call(d, sel)
    assert abs(st["diff"]) < 1e-9 and st["sel_r"] > 0.3                       # every short is selected: the same-side excess is exactly zero


# ------------------------------------------------------------------ combo_direction / combo_screen helpers

def test_the_direction_columns_are_the_thirteen_aligned_features_and_nothing_else():
    assert len(cd.DIRECTION) == 13 and len(set(cd.DIRECTION)) == 13
    assert all(c.startswith("a_") or c in ("rsi_aligned", "d_rsi_aligned") for c in cd.DIRECTION)
    assert "side" not in cd.DIRECTION and "atr_pct" not in cd.DIRECTION
    X = pd.DataFrame(np.zeros((2, 14)), columns=cd.DIRECTION + ["atr_pct"])
    assert cd.direction_columns(X) == cd.DIRECTION
    try:
        cd.direction_columns(X.drop(columns=["a_ret24"]))
        raise SystemExit("a missing direction feature must raise")
    except AssertionError:
        pass


def test_screened_names_report_the_features_the_training_fold_ranks_by_absolute_correlation():
    rng = np.random.default_rng(11)
    n = 9000
    ms = np.sort(rng.integers(pd.Timestamp("2022-01-01").value // 10 ** 6, pd.Timestamp("2024-07-01").value // 10 ** 6, n))
    c = pd.DataFrame(dict(made_ms=ms))
    c["t"] = pd.to_datetime(ms, unit="ms")
    X = pd.DataFrame(rng.normal(size=(n, 20)), columns=[f"f{i}" for i in range(20)])
    c["r_net"] = -0.5 * X.f4.to_numpy() + 0.4 * X.f11.to_numpy() + rng.normal(size=n)                   # a NEGATIVE and a positive real feature
    names = cs.screened_names(X, c)
    assert len(names) >= 4 and all("f4" in n_[:3] and "f11" in n_[:3] for n_ in names)
    assert all(len(n_) == cm.SCREEN_K for n_ in names)


if __name__ == "__main__":
    tests = sorted((v for k, v in globals().items() if k.startswith("test_")), key=lambda f: f.__code__.co_firstlineno)
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
