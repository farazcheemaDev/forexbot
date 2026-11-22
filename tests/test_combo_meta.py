"""Tests for backtest/combo_meta.py: candle features use only bars up to the call, the call reads the last CLOSED hour, the panel join uses the previous day, the walk-forward never trains on an unfinished outcome, selection / uplift / IC /
gate arithmetic by hand, and the pipeline recovers a planted skill but not a shuffled placebo.

Run as a script (no pytest on this PC):  python tests/test_combo_meta.py     (exit code 0 = all passed)
"""
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.combo_meta as cm  # noqa: E402

H1, D1 = cm.H1, cm.D1
T0 = int(pd.Timestamp("2023-03-01").timestamp() * 1000)


def bars(n=2600, seed=1, start=T0):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.001, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.001, n)))
    return pd.DataFrame(dict(o=o, h=h, l=l, c=c), index=(start + np.arange(n) * H1).astype("int64"))


def universe(seed=1):
    return {s: bars(seed=seed + i) for i, s in enumerate(cm.SYMS)}


def calls_at(made, sym="ETHUSDT", side="long", method="SR"):
    n = len(made)
    return pd.DataFrame(dict(made_ms=np.array(made, dtype="int64"), symbol=sym, side=side, method=method, stop_pct=0.01, target_pct=0.02, rr=2.0, hours=24, base_p=0.2,
                             r_net=0.0, status="LOSS"))


def feats_of(b):
    f = {s: cm.symbol_features(x) for s, x in b.items()}
    return f, cm.market_frame(f)


def eq(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a.shape == b.shape and np.allclose(a, b, equal_nan=True)


# ------------------------------------------------------------------ look-ahead and the call's bar

def test_candle_features_use_only_bars_up_to_the_call():
    b = universe()
    i0 = 2000
    made = [T0 + i0 * H1 + 7 * 60_000, T0 + (i0 + 400) * H1 + 7 * 60_000, T0 + (i0 + 55) * H1]          # two live-style (:07) calls and one on the hour
    calls = cm.finish_calls(calls_at(made))
    calls["r_net"] = 0.0
    f, m = feats_of(b)
    x0 = cm.call_features(calls, f, m)
    last_closed = (np.array(made) // H1) * H1 - H1
    rng = np.random.default_rng(9)
    first_closed = last_closed.min()
    scr2 = {s: x.copy() for s, x in b.items()}
    for s, x in scr2.items():
        later = x.index > first_closed
        x.loc[later, ["o", "h", "l", "c"]] = x.loc[later, ["o", "h", "l", "c"]].to_numpy() * rng.uniform(0.5, 2.0, (later.sum(), 1))
    f2, m2 = feats_of(scr2)
    x2 = cm.call_features(calls, f2, m2)
    j = int(np.argmin(last_closed))
    assert eq(x0.iloc[j].to_numpy(), x2.iloc[j].to_numpy())                                               # the earliest call is blind to everything after its bar
    assert not eq(x0.iloc[1].to_numpy(), x2.iloc[1].to_numpy())                                           # and the scramble really changes the later calls (the check can fail)


def test_a_call_reads_the_last_closed_hour_whether_made_on_the_hour_or_at_minute_seven():
    b = universe()
    f, m = feats_of(b)
    h = 1500
    on_hour = T0 + h * H1
    late = on_hour + 7 * 60_000
    calls = cm.finish_calls(calls_at([on_hour, late]))
    x = cm.call_features(calls, f, m)
    want = math.log(b["ETHUSDT"].c.iloc[h - 1] / b["ETHUSDT"].c.iloc[h - 2])                              # the bar that opened one hour BEFORE the call's hour
    assert abs(x.ret1.iloc[0] - want) < 1e-12 and abs(x.ret1.iloc[1] - want) < 1e-12


def test_daily_context_is_the_previous_complete_day():
    b = {s: bars(n=24 * 80, seed=3 + i, start=int(pd.Timestamp("2023-01-01").timestamp() * 1000)) for i, s in enumerate(cm.SYMS)}
    f = cm.symbol_features(b["BTCUSDT"])
    day = b["BTCUSDT"].index.to_numpy() // D1
    dc = b["BTCUSDT"].c.groupby(day).last()
    k = 60
    mid = np.flatnonzero(day == day[0] + k)[5]                                                             # 05:00 on day k
    want = math.log(dc.iloc[k - 1] / dc.iloc[k - 2])                                                       # day k-1's 1-day return (day k-1 is complete at 00:00 of day k)
    assert abs(f.d_ret1.iloc[mid] - want) < 1e-12
    assert abs(f.d_ret1.iloc[np.flatnonzero(day == day[0] + k)[-1]] - want) < 1e-12                        # still that value at 23:00: today's close does not leak in


def test_the_side_aligned_features_flip_with_the_side():
    b = universe()
    f, m = feats_of(b)
    made = [T0 + 1800 * H1]
    xl = cm.call_features(cm.finish_calls(calls_at(made, side="long")), f, m)
    xs = cm.call_features(cm.finish_calls(calls_at(made, side="short")), f, m)
    for k in ("a_ret24", "a_d_ma1000", "a_bb_z", "a_rel_btc24"):
        assert abs(xl[k].iloc[0] + xs[k].iloc[0]) < 1e-12 and abs(xl[k].iloc[0]) > 0
    assert xl.side.iloc[0] == 1 and xs.side.iloc[0] == -1 and xl.m_SR.iloc[0] == 1 and xl.m_SMC.iloc[0] == 0


def test_panel_join_uses_the_previous_day_and_nan_outside_the_panel():
    d0 = np.datetime64("2023-01-01")
    dates = d0 + np.arange(30)
    coins = np.array(["BTCUSDT", "ETHUSDT"])
    ret1 = np.tile(np.arange(30, dtype=float)[:, None], (1, 2)) + np.array([0.0, 100.0])               # f_ret1[row, coin] = row (+100 for ETH)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "p.npz"
        np.savez(path, dates=dates, coins=coins, f_ret1=ret1, f_crowd=ret1 * 2, m_fng=np.arange(30, dtype=float) * 10)
        old = cm.PANEL
        cm.PANEL = path
        try:
            ts = lambda s: int(pd.Timestamp(s).timestamp() * 1000)
            calls = cm.finish_calls(calls_at([ts("2023-01-11 09:00"), ts("2023-01-01 05:00"), ts("2023-02-15 05:00"), ts("2023-01-30 23:59")], sym="ETHUSDT"))
            e = cm.panel_features(calls)
        finally:
            cm.PANEL = old
    assert e.f_ret1.iloc[0] == 109 and e.f_crowd.iloc[0] == 218 and e.m_fng.iloc[0] == 90            # a call on 01-11 reads row 01-10 (index 9; +100 for ETH), never row 01-11
    assert e.a_f_crowd.iloc[0] == 218                                                                  # long: the aligned copy equals the raw one
    assert np.isnan(e.f_ret1.iloc[1]) and np.isnan(e.m_fng.iloc[1])                                  # the previous day (2022-12-31) is before the panel starts
    assert np.isnan(e.f_ret1.iloc[2]) and np.isnan(e.m_fng.iloc[2])                                  # 2023-02-14 is after it ends
    assert e.f_ret1.iloc[3] == 128 and e.m_fng.iloc[3] == 280                                        # a call at 23:59 on 01-30 still reads 01-29, not the day it is in


# ------------------------------------------------------------------ walk-forward

def synth_calls(n=6000, seed=0, start="2022-02-01", end="2025-12-31", market_level=False):
    rng = np.random.default_rng(seed)
    t = np.sort(rng.integers(int(pd.Timestamp(start).timestamp() * 1000), int(pd.Timestamp(end).timestamp() * 1000), n))
    c = pd.DataFrame(dict(made_ms=t, symbol=rng.choice(cm.SYMS, n), side=rng.choice(["long", "short"], n), method="SR", stop_pct=0.01, target_pct=0.02, rr=2.0, hours=24, base_p=0.2))
    c["r_net"] = rng.normal(0, 1, n)
    c["status"] = np.where(c.r_net > 1, "WIN", "LOSS")
    c = cm.finish_calls(c)
    X = pd.DataFrame(dict(a_ret24=rng.normal(0, 1, n), x1=rng.normal(0, 1, n), x2=rng.normal(0, 1, n)), index=c.index)
    if market_level:                                                                                         # the same value for every call of a (day, side): a regime feature
        codes, _ = pd.factorize(c.day + c.side)
        X["a_ret24"] = rng.normal(0, 1, codes.max() + 1)[codes]
    return c, X


def test_walk_forward_trains_only_on_calls_whose_outcome_is_known_and_predicts_every_oos_call():
    c, X = synth_calls(7000, seed=1)
    seen = []
    real = cm.fit_model

    def spy(kind, Xtr, ytr, seed=0):
        seen.append(len(Xtr))
        return lambda Z: np.zeros(len(Z))

    cm.fit_model = spy
    try:
        wf = cm.walk_forward(c, X, "ridge")
    finally:
        cm.fit_model = real
    starts = cm.fold_starts(c.t)
    want = [int((c.made_ms + cm.EMBARGO_MS < int(a.timestamp() * 1000)).sum()) for a, b in zip(starts[:-1], starts[1:]) if ((c.t >= a) & (c.t < b)).any() and (c.made_ms + cm.EMBARGO_MS < int(a.timestamp() * 1000)).sum() >= cm.MIN_TRAIN]
    assert seen == want and len(seen) >= 8
    oos = c.t >= cm.FIRST_OOS
    assert wf.pred[oos].notna().all() and wf.pred[~oos].isna().all()                                      # every OOS call (the last partial quarter included) is predicted, nothing earlier is


def test_folds_with_too_little_training_data_are_skipped_not_fitted():
    c, X = synth_calls(3000, seed=1)                                                                         # only 716 calls are known at the start of 2023: those quarters must stay unpredicted
    wf = cm.walk_forward(c, X, "ridge")
    first = pd.Timestamp("2024-04-01")                                                                      # the first quarter with >= 1500 known outcomes (1685)
    assert wf.pred[c.t < first].isna().all() and wf.pred[c.t >= first].notna().all()


def test_a_future_label_cannot_change_an_earlier_prediction():
    c, X = synth_calls(7000, seed=2)
    wf1 = cm.walk_forward(c, X, "ridge")
    y2 = c.r_net.to_numpy().copy()
    late = c.t >= pd.Timestamp("2025-04-01")
    y2[late.to_numpy()] += 50.0                                                                              # absurd labels in the last three quarters
    wf2 = cm.walk_forward(c, X, "ridge", y=y2)
    early = (c.t < pd.Timestamp("2025-04-01")) & (c.t >= cm.FIRST_OOS) & wf1.pred.notna()
    assert np.allclose(wf1.pred[early], wf2.pred[early])                                                    # earlier folds never saw them
    assert not np.allclose(wf1.pred[late & wf1.pred.notna()], wf2.pred[late & wf2.pred.notna()])           # and the later folds DO react (the check can fail)


def test_the_fit_target_is_clipped_so_one_huge_winner_cannot_steer_the_model():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(600, 30))                                                                          # more features than the screen keeps, so the screening step matters
    y = 0.3 * X[:, 0] + rng.normal(size=600)
    y_big = y.copy()
    y_big[7] = 5000.0                                                                                       # one absurd winner
    y_clip = y.copy()
    y_clip[7] = cm.CLIP_HI
    for kind in ("ridge", "sridge", "hgb"):
        assert np.allclose(cm.fit_model(kind, X, y_big)(X[:50]), cm.fit_model(kind, X, y_clip)(X[:50]))   # the model sees +4, not +5000
    y_low = y.copy()
    y_low[9] = -300.0
    y_lowc = y.copy()
    y_lowc[9] = cm.CLIP_LO
    assert np.allclose(cm.fit_model("ridge", X, y_low)(X[:50]), cm.fit_model("ridge", X, y_lowc)(X[:50]))


def test_constant_and_all_missing_signals_are_dropped_per_fold_instead_of_crashing_the_trees():
    rng = np.random.default_rng(4)
    X = rng.normal(size=(500, 3))
    y = 0.4 * X[:, 0] + rng.normal(size=500)
    Xbad = np.c_[X, np.full(500, 7.0), np.full(500, np.nan), np.r_[np.full(499, 1.0), np.nan]]            # a constant, an all-missing and a one-value-plus-missing column
    assert list(cm.usable_columns(Xbad)) == [True, True, True, False, False, False]
    for kind in ("ridge", "hgb"):
        with_bad = cm.fit_model(kind, Xbad, y)(Xbad[:40])
        without = cm.fit_model(kind, X, y)(X[:40])
        assert np.allclose(with_bad, without)


def test_screening_keeps_the_features_most_correlated_with_the_outcome_by_absolute_value():
    rng = np.random.default_rng(2)
    Z = rng.normal(size=(5000, 12))
    y = 0.8 * Z[:, 3] - 0.6 * Z[:, 7] + 0.4 * Z[:, 1] + rng.normal(size=5000)                              # features 3, 7 (NEGATIVE sign) and 1 carry the signal
    top = cm.screen_top(Z, y, 3)
    assert set(top) == {3, 7, 1} and top[0] == 3 and top[1] == 7                                            # ordered by |corr|; the negative one is kept
    assert len(cm.screen_top(Z, y, 8)) == 8 and set(cm.screen_top(Z, y, 3)) <= set(cm.screen_top(Z, y, 8))


def test_the_screened_ridge_uses_only_its_k_features_and_finds_a_weak_one_the_full_ridge_buries():
    rng = np.random.default_rng(5)
    n = 6000
    X = rng.normal(size=(n, 60))
    y = 0.10 * X[:, 17] + rng.normal(size=n) * 1.5
    pred_s = cm.fit_model("sridge", X, y)(X)
    assert np.corrcoef(pred_s, X[:, 17])[0, 1] > 0.5                                                        # the screened model is mostly the one real feature
    Xo = X.copy()
    keep = set(cm.screen_top((X - X.mean(0)) / X.std(0), np.clip(y, cm.CLIP_LO, cm.CLIP_HI), cm.SCREEN_K))
    drop = [j for j in range(60) if j not in keep][0]
    Xo[:, drop] += 100.0                                                                                    # a feature that was NOT screened in cannot move the prediction
    f = cm.fit_model("sridge", X, y)
    assert np.allclose(f(Xo[:50]), f(X[:50]))


def test_the_screening_step_cannot_see_future_labels():
    c, X = synth_calls(7000, seed=12)
    wf1 = cm.walk_forward(c, X, "sridge")
    y2 = c.r_net.to_numpy().copy()
    late = c.t >= pd.Timestamp("2025-04-01")
    y2[late.to_numpy()] += 50.0 * (X.x1.to_numpy()[late.to_numpy()] > 0)                                                     # absurd, feature-dependent labels in the last three quarters
    wf2 = cm.walk_forward(c, X, "sridge", y=y2)
    early = (c.t < pd.Timestamp("2025-04-01")) & (c.t >= cm.FIRST_OOS) & wf1.pred.notna()
    assert np.allclose(wf1.pred[early], wf2.pred[early])


def test_prep_learns_on_the_training_fold_only_and_clips_extremes():
    tr = np.array([[1.0, np.nan], [2.0, 10.0], [3.0, 20.0], [4.0, 30.0]] * 30)
    p = cm.Prep().fit(tr)
    z = p.transform(np.array([[1e9, np.nan], [-1e9, 1e9]]))
    assert np.isfinite(z).all() and abs(z[0, 0]) < 3 and abs(z[1, 1]) < 3                                    # extreme / missing test values cannot blow up the linear model
    assert abs(p.transform(tr)[:, 0].mean()) < 0.05                                                         # standardised on its own fold


# ------------------------------------------------------------------ selection, uplift, IC, gate

def test_selection_is_the_top_fraction_within_each_fold():
    df = pd.DataFrame(dict(fold=np.repeat([1, 2], 10), pred=np.r_[np.arange(10), np.arange(10)[::-1] * 5.0]))
    sel = cm.select(df, "pred", 0.30)
    assert sel.sum() == 6 and list(df.pred[sel & (df.fold == 1)]) == [7, 8, 9] and list(df.pred[sel & (df.fold == 2)]) == [45.0, 40.0, 35.0]


def test_selected_bets_against_all_bets_and_the_within_bet_uplift_by_hand():
    rows = []
    spec = [("d1", "long", [1.0, -1.0, 0.0], [1, 0, 0]),       # bet mean 0; selected 1
            ("d2", "short", [2.0, 0.0], [0, 1]),               # bet mean 1; selected 0
            ("d3", "long", [3.0, 1.0], [1, 1]),                # bet mean 2; selected 2
            ("d4", "long", [0.5, -0.5, 0.0], [1, 0, 0]),       # bet mean 0; selected 0.5
            ("d5", "short", [-1.0, 1.0], [0, 1]),              # bet mean 0; selected 1
            ("d6", "long", [0.0, 0.0], [1, 0]),                # bet mean 0; selected 0
            ("d7", "short", [-2.0, 0.0], [0, 0])]              # bet mean -1; nothing selected
    for day, side, rs, sl in spec:
        for r, s_ in zip(rs, sl):
            rows.append(dict(day=day, side=side, r_net=r, sel=bool(s_), win=float(r > 0.9), base_p=0.25 if s_ else 0.60))      # the unselected calls have DIFFERENT random-entry odds
    df = pd.DataFrame(rows)
    st = cm.half_stats(df, df.sel)
    all_b = np.array([0.0, 1.0, 2.0, 0.0, 0.0, 0.0, -1.0])
    sel_b = np.array([1.0, 0.0, 2.0, 0.5, 1.0, 0.0])
    se = math.sqrt(sel_b.var(ddof=1) / 6 + all_b.var(ddof=1) / 7)
    assert st["bets"] == 6 and st["all_bets"] == 7 and st["n"] == 7
    assert abs(st["sel_r"] - sel_b.mean()) < 1e-12 and abs(st["all_r"] - all_b.mean()) < 1e-12 and abs(st["diff"] - (sel_b.mean() - all_b.mean())) < 1e-12
    assert abs(st["t"] - st["diff"] / se) < 1e-12                                                            # PRIMARY: selected bets vs ALL bets, Welch
    ups = np.array([1.0, -1.0, 0.0, 0.5, 1.0, 0.0])                                                          # DIAGNOSTIC: within the same bet
    assert abs(st["uplift"] - ups.mean()) < 1e-12 and abs(st["t_within"] - ups.mean() / (ups.std(ddof=1) / math.sqrt(6))) < 1e-12
    assert abs(st["hit"] - 4 / 7) < 1e-12 and abs(st["base"] - 0.25) < 1e-12
    assert cm.half_stats(df, df.sel & False)["n"] == 0


def test_holm_and_p_by_hand():
    assert np.allclose(cm.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06]) and np.allclose(cm.holm([0.5, 0.9]), [1.0, 1.0])
    assert abs(cm.p_up(2.0) - 0.5 * math.erfc(2.0 / math.sqrt(2))) < 1e-12 and cm.p_up(float("nan")) == 1.0


def good_cell():
    h = dict(n=400, bets=300, all_bets=900, sel_r=0.2, all_r=-0.1, diff=0.3, t=3.0, uplift=0.0, t_within=0.0, hit=0.3, base=0.2)
    return dict(full=dict(h), h1=dict(h), h2=dict(h), p=0.001)


def test_every_gate_clause_matters_on_its_own():
    c = good_cell()
    assert cm.passes(c, 0.01)
    for part, key, bad in [("full", "t", 1.9), ("full", "diff", -0.01), ("full", "sel_r", 0.04), ("full", "bets", 149), ("h1", "diff", -0.01), ("h2", "diff", 0.0), ("h1", "sel_r", 0.0), ("h2", "sel_r", -0.01),
                           ("h1", "hit", 0.2), ("h2", "hit", 0.1)]:
        c2 = good_cell()
        c2[part][key] = bad
        assert not cm.passes(c2, 0.01), (part, key)
    assert not cm.passes(c, 0.06)                                                                             # Holm


def test_rank_ic_matches_scipy_and_its_range_covers_the_truth():
    rng = np.random.default_rng(5)
    n = 4000
    day = np.repeat(np.arange(800), 5)[:n]
    pred = rng.normal(size=n)
    r = 0.3 * pred + rng.normal(size=n)
    df = pd.DataFrame(dict(day=[f"d{d}" for d in day], pred=pred, r_net=r))
    ic, lo, hi = cm.rank_ic(df, "pred", np.random.default_rng(1))
    from scipy import stats as sps
    assert abs(ic - sps.spearmanr(pred, r)[0]) < 1e-12 and lo < ic < hi and lo > 0.1
    df2 = pd.DataFrame(dict(day=df.day, pred=pred, r_net=rng.normal(size=n)))
    ic2, lo2, hi2 = cm.rank_ic(df2, "pred", np.random.default_rng(1))
    assert lo2 < 0 < hi2


# ------------------------------------------------------------------ the pipeline can see a real skill and not a shuffled one

def run_cell(c, X, y):
    c2 = c.copy()
    c2["r_net"] = y
    wf = cm.walk_forward(c2, X, "ridge", y=y)
    return cm.cell(c2.join(wf), "pred", 0.20)


def test_a_planted_skill_is_recovered_and_a_shuffled_placebo_is_not():
    c, X = synth_calls(9000, seed=4)
    y = cm.plant(c, X, 0.35)
    planted = run_cell(c, X, y)
    assert planted["full"]["diff"] > 0.15 and planted["full"]["t"] > 4 and planted["h1"]["diff"] > 0 and planted["h2"]["diff"] > 0
    rng = np.random.default_rng(7)
    ysh = c.r_net.to_numpy().copy()
    rng.shuffle(ysh)
    plac = run_cell(c, X, ysh)
    assert abs(plac["full"]["t"]) < 3.0 and abs(plac["full"]["diff"]) < 0.15


def test_a_market_level_skill_is_seen_by_the_gate_but_cancelled_by_the_within_bet_uplift():
    c, X = synth_calls(9000, seed=8, market_level=True)                                                      # the aligned return is the SAME for every call of a day + side
    y = cm.plant(c, X, 0.35)
    r = run_cell(c, X, y)
    assert r["full"]["diff"] > 0.15 and r["full"]["t"] > 4                                                   # the primary measure sees 'trade only when the market says so'
    assert abs(r["full"]["uplift"]) < 0.05                                                                   # while the paired comparison inside a bet has nothing to find: why the first run's power check failed


def test_plant_adds_a_rank_normal_score_of_the_aligned_return_so_heavy_tails_do_not_shrink_it():
    c, X = synth_calls(800, seed=6)
    X.loc[X.index[:5], "a_ret24"] = [50.0, -60.0, 70.0, -80.0, 90.0]                                         # extreme outliers: a raw z-score would make everyone else look ~0
    y = cm.plant(c, X, 0.25)
    add = (y - c.r_net.to_numpy()) / 0.25
    assert abs(add.mean()) < 0.02 and abs(add.std() - 1.0) < 0.02 and np.std(add[5:]) > 0.95              # a standard-normal score whatever the tails: the bulk keeps its unit spread (a raw z-score would squeeze it to ~0.1)
    from scipy import stats as sps
    assert sps.spearmanr(add, X.a_ret24)[0] > 0.999                                                          # and it keeps the ranking exactly
    X2 = X.copy()
    X2.loc[X2.index[10], "a_ret24"] = np.nan
    y2 = cm.plant(c, X2, 0.25)
    assert y2[10] == c.r_net.iloc[10]                                                                          # a missing signal plants nothing


def test_registered_constants_are_unchanged():
    assert (cm.FRACS, cm.MIN_BETS, cm.MIN_SEL_R, cm.EMBARGO_MS, cm.CLIP_LO, cm.CLIP_HI, cm.MIN_TRAIN) == ((0.10, 0.20, 0.33), 150, 0.05, 72 * H1, -2.0, 4.0, 1500)
    assert cm.FIRST_OOS == pd.Timestamp("2023-01-01") and cm.HALF_SPLIT == pd.Timestamp("2025-01-01") and cm.SYMS == ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]


if __name__ == "__main__":
    tests = sorted((v for k, v in globals().items() if k.startswith("test_")), key=lambda f: f.__code__.co_firstlineno)
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
