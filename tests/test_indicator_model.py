"""Offline tests for backtest/indicator_model.py - ranks, forward returns, feature causality, the walk-forward embargo, the single-feature
choice, the daily scores, the entry-alignment statistics and the pass rule. Synthetic data only.

    python tests/test_indicator_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import candle_scan as cs  # noqa: E402
from backtest import indicator_model as im  # noqa: E402


def test_xs_rank_is_centred_among_the_masked_names_only():
    X = np.array([[10.0, 30.0, 20.0, 99.0], [5.0, np.nan, 7.0, 6.0]])
    mask = np.array([[True, True, True, False], [True, True, True, True]])
    r = im.xs_rank(X, mask)
    assert np.allclose(r[0, :3], [-1 / 3, 1 / 3, 0.0]) and np.isnan(r[0, 3])        # the unmasked 99 does not take part
    assert np.isnan(r[1, 1]) and np.allclose(r[1, [0, 2, 3]], [-1 / 3, 1 / 3, 0.0])    # a missing value stays missing


def test_forward_return_enters_next_open_exits_h_later_and_a_ended_coin_stays_at_its_last_close():
    O = np.array([[10.0, 20.0], [11.0, 21.0], [12.0, 22.0], [13.0, 23.0], [14.0, 24.0], [15.0, np.nan], [16.0, np.nan], [17.0, np.nan]])
    C = np.array([[10.5, 20.5], [11.5, 21.5], [12.5, 22.5], [13.5, 23.5], [14.5, 24.5], [15.5, np.nan], [16.5, np.nan], [17.5, np.nan]])
    F = im.forward_returns(O, C, 3)
    assert abs(F[0, 0] - (C[3, 0] / O[1, 0] - 1)) < 1e-12 and abs(F[2, 0] - (C[5, 0] / O[3, 0] - 1)) < 1e-12
    assert np.isnan(F[5:, 0]).all()                                                # no room for the exit
    assert abs(F[2, 1] - (C[4, 1] / O[3, 1] - 1)) < 1e-12                          # coin 1 ends at day 4: left at its last close
    assert np.isnan(F[4, 1])                                                       # no entry open on day 5


def panel(T=250, N=6, seed=1):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, (T, N)), axis=0))
    o = np.vstack([c[:1], c[:-1]]) * np.exp(rng.normal(0, 0.005, (T, N)))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.01, (T, N))))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.01, (T, N))))
    v = np.exp(rng.normal(15, 0.5, (T, N)))
    return o, h, l, c, v


def test_every_feature_reads_only_days_up_to_the_signal_day():
    o, h, l, c, v = panel()
    full = im.feature_panels(o, h, l, c, v, 0)
    assert set(full) == set(im.FEATURES) and len(full) == 32
    t0 = 180
    rng = np.random.default_rng(9)
    o2, h2, l2, c2, v2 = (x.copy() for x in (o, h, l, c, v))
    for a in (o2, h2, l2, c2, v2):
        a[t0 + 1:] = a[t0 + 1:] * np.exp(rng.normal(0, 0.5, a[t0 + 1:].shape))        # the future changes completely
    pert = im.feature_panels(o2, h2, l2, c2, v2, 0)
    for k in im.FEATURES:
        assert np.allclose(full[k][:t0 + 1], pert[k][:t0 + 1], equal_nan=True), k
        assert np.isfinite(full[k][t0]).sum() >= 4, k                                 # and the comparison is not empty


def test_blocks_are_calendar_quarters_and_the_embargo_is_h_plus_one():
    dates = np.arange(np.datetime64("2021-10-01"), np.datetime64("2023-01-15"))
    b = im.make_blocks(dates, first_oos=np.datetime64("2022-01-01"))
    assert dates[b[0][0]] == np.datetime64("2022-01-01") and dates[b[1][0]] == np.datetime64("2022-04-01") and b[-1][1] == len(dates)
    assert all(x[1] == y[0] for x, y in zip(b, b[1:]))
    assert im.train_cutoff(100, 5) == 94 and im.train_cutoff(100, 1) == 98


def synth(T=700, N=40, nf=4, seed=3):
    rng = np.random.default_rng(seed)
    X = rng.uniform(-0.5, 0.5, (T, N, nf)).astype(np.float32)
    return rng, X, np.ones((T, N), bool)


def ic_of(pred, Y, a, b):
    ics = []
    for t in range(a, b):
        ok = np.isfinite(pred[t]) & np.isfinite(Y[t])
        if ok.sum() > 5:
            ics.append(np.corrcoef(pred[t, ok], Y[t, ok])[0, 1])
    return float(np.mean(ics))


def test_a_planted_relation_is_recovered_out_of_sample_and_noise_is_not():
    rng, X, mem = synth()
    sig = im.xs_rank(0.8 * X[:, :, 0] + 0.3 * rng.normal(size=X.shape[:2]), mem)
    pred, _ = im.walk_forward(X, sig, mem, [(400, 500), (500, 600)], 1, "ridge")
    assert ic_of(pred, sig, 400, 600) > 0.3
    noise = im.xs_rank(rng.normal(size=X.shape[:2]), mem)
    pred0, _ = im.walk_forward(X, noise, mem, [(400, 500), (500, 600)], 1, "ridge")
    assert abs(ic_of(pred0, noise, 400, 600)) < 0.06
    assert np.isnan(pred[:400]).all() and np.isnan(pred[600:]).all()                 # predictions exist only inside the blocks
    holes = sig.copy()
    holes[100:110, :5] = np.nan                                                      # coins whose forward return is unknown are not training rows
    predh, _ = im.walk_forward(X, holes, mem, [(400, 500)], 1, "ridge")
    assert np.isfinite(predh[400:500]).all() and ic_of(predh, sig, 400, 500) > 0.3


def test_the_model_never_trains_on_rows_whose_window_reaches_into_the_block():
    rng, X, mem = synth(T=500, N=40, nf=3, seed=5)
    H = 30
    a = 300
    Y = im.xs_rank(rng.normal(size=X.shape[:2]), mem)                                # before the cut-off the target is pure noise
    Y[a - H:, :] = im.xs_rank(X[:, :, 0].astype(float), mem)[a - H:, :]               # from a - H on (inside the embargo and the block) it equals feature 0
    pred, _ = im.walk_forward(X, Y, mem, [(a, 360)], H, "ridge")
    assert abs(ic_of(pred, Y, a, 360)) < 0.2                                         # a model that saw those rows would score close to 1


def test_single_feature_is_the_best_one_in_its_own_direction():
    rng, X, mem = synth(nf=5, seed=11)
    Y = im.xs_rank(-0.9 * X[:, :, 2].astype(float) + 0.3 * rng.normal(size=X.shape[:2]), mem)       # feature 2, NEGATIVELY related
    pred, info = im.walk_forward(X, Y, mem, [(400, 500)], 1, "single")
    assert info == [2] and ic_of(pred, Y, 400, 500) > 0.5


def test_day_scores_spread_ic_and_the_names_rule():
    rng = np.random.default_rng(2)
    f = rng.normal(0, 0.03, (3, 20))
    M = np.ones((3, 20), bool)
    ic, sp, lx, nn = im.day_scores(f.copy(), f, M)                                   # a perfect forecast
    assert np.allclose(ic, 1.0) and (sp > 0).all() and (nn == 20).all()
    k = 4                                                                            # top and bottom fifth of 20 names
    o = np.argsort(f[0])
    assert abs(sp[0] - (f[0, o[-k:]].mean() - f[0, o[:k]].mean())) < 1e-12 and abs(lx[0] - (f[0, o[-k:]].mean() - f[0].mean())) < 1e-12
    ic2, sp2, _, _ = im.day_scores(-f, f, M)                                         # a perfectly wrong one
    assert np.allclose(ic2, -1.0) and (sp2 < 0).all()
    M2 = M.copy()
    M2[1, 5:] = False                                                                # only 5 names on day 1: no score
    ic3, sp3, _, nn3 = im.day_scores(f, f, M2)
    assert np.isnan(ic3[1]) and np.isnan(sp3[1]) and nn3[0] == 20


def test_net_spread_costs_and_entry_alignments():
    assert abs(im.net_spread(0.01, 7) - (0.01 - 0.0024 - cs.FUND_H * 24 * 7)) < 1e-15
    x = np.where(np.arange(400) % 2 == 0, 1.0, -1.0) + np.random.default_rng(0).normal(0, 0.1, 400)
    s = im.offset_stats(x, 2, np.ones(400, bool))
    assert abs(s["mean"]) < 0.05 and s["worst"] < -0.9 and s["n"] == 200               # alignments +1 and -1: the average hides it, the worst shows it
    s1 = im.offset_stats(x, 1, np.ones(400, bool))
    assert s1["n"] == 400
    neg = im.offset_stats(-np.abs(x) - 1, 3, np.ones(400, bool))
    assert neg["mean"] < 0 and neg["t"] < 0                                          # the sign of t is the sign of the mean


def test_the_pass_rule_needs_everything_on_both_halves():
    def half(net=5e-4, t=2.5, worst=1e-4, ict=2.5):
        return dict(net=dict(mean=net, t=t, worst=worst), ic=dict(t=ict))
    good = dict(tu=half(), ho=half())
    assert im.passes(good, 0.01)
    assert not im.passes(good, 0.06)
    for kw in (dict(net=-1e-4), dict(t=1.9), dict(worst=-1e-4), dict(ict=1.0)):
        assert not im.passes(dict(tu=half(**kw), ho=half()), 0.01), kw
        assert not im.passes(dict(tu=half(), ho=half(**kw)), 0.01), kw


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
