"""Tests for backtest/know_when_not_to.py: the target / disaster logic, signed features, no look-ahead, the train / test split and the keep-the-safest ranking.

Run as a script (no pytest on this PC):  python tests/test_know_when_not_to.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.know_when_not_to as kw  # noqa: E402

COL = {n: i for i, n in enumerate(kw.FEATS)}


def toy(n=20, seed=1):
    """n sessions x 390 minutes of a gentle random walk with the OHLC arrays and a previous-close vector."""
    rng = np.random.default_rng(seed)
    C = 100 * np.exp(np.cumsum(rng.normal(0, 0.0003, (n, 390)), axis=1))
    O = np.concatenate([C[:, :1], C[:, :-1]], axis=1)
    A = dict(o=O, h=np.maximum(O, C) * 1.0001, l=np.minimum(O, C) * 0.9999, c=C)
    prev = np.r_[np.nan, C[:-1, -1]]
    dates = pd.bdate_range("2026-01-05", periods=n)
    return A, prev, dates


def rows_for(F, out, dis, day, side, i, m, s):
    sel = (day == i) & (F[:, COL["m"]] == m) & (side == s)
    assert sel.sum() == 1
    return F[sel][0], out[sel][0], dis[sel][0]


def test_a_long_that_touches_the_target_wins_target_minus_cost_and_a_miss_loses_the_drift_to_the_close():
    A, prev, dates = toy()
    i, m = 16, 60
    e = A["o"][i, m + 1]
    A["h"][i, m + 5:] = e * 0.99                                            # nothing later reaches +2.5 bp
    A["h"][i, :] = np.minimum(A["h"][i, :], e * 0.9999)
    F, out, dis, day, side = kw.build(A, prev, dates)
    f, o, d = rows_for(F, out, dis, day, side, i, m, 1)
    assert d and abs(o - ((A["c"][i, -1] / e - 1) * 1e4 - kw.COST_BP)) < 1e-9
    A["h"][i, m + 10] = e * (1 + 3.0 / 1e4)                                 # now a later high touches +3 bp
    F, out, dis, day, side = kw.build(A, prev, dates)
    f, o, d = rows_for(F, out, dis, day, side, i, m, 1)
    assert not d and abs(o - (kw.T_BP - kw.COST_BP)) < 1e-9


def test_a_short_needs_a_later_LOW_and_its_features_are_signed_by_the_side():
    A, prev, dates = toy()
    i, m = 16, 120
    F, out, dis, day, side = kw.build(A, prev, dates)
    fl, _, _ = rows_for(F, out, dis, day, side, i, m, 1)
    fs, _, _ = rows_for(F, out, dis, day, side, i, m, -1)
    assert abs(fl[COL["ret_bp"]] + fs[COL["ret_bp"]]) < 1e-9 and abs(fl[COL["mom30_bp"]] + fs[COL["mom30_bp"]]) < 1e-9
    assert abs(fl[COL["pos_side"]] + fs[COL["pos_side"]] - 1.0) < 1e-9 and fl[COL["abs_gap_bp"]] == fs[COL["abs_gap_bp"]]
    e = A["o"][i, m + 1]
    A["l"][i, m + 3] = e * (1 - 4.0 / 1e4)
    A["h"][i, m + 1:] = e * 1.00001
    F, out, dis, day, side = kw.build(A, prev, dates)
    _, o, d = rows_for(F, out, dis, day, side, i, m, -1)
    assert not d and abs(o - (kw.T_BP - kw.COST_BP)) < 1e-9


def test_a_short_that_misses_its_target_loses_when_the_price_rises():
    A, prev, dates = toy()
    i, m = 16, 90
    e = A["o"][i, m + 1]
    A["l"][i, m + 1:] = np.maximum(A["l"][i, m + 1:], e * 0.99995)             # no later low gets 2.5 bp below the entry
    A["c"][i, -1] = e * 1.002                                                  # the session ends 20 bp ABOVE the short's entry
    A["h"][i, -1] = max(A["h"][i, -1], A["c"][i, -1])
    F, out, dis, day, side = kw.build(A, prev, dates)
    _, o, d = rows_for(F, out, dis, day, side, i, m, -1)
    assert d and abs(o - (-(A["c"][i, -1] / e - 1) * 1e4 - kw.COST_BP)) < 1e-9 and o < -19


def test_features_do_not_read_anything_after_the_decision_close():
    A, prev, dates = toy()
    i, m = 16, 180
    F1, _, _, day, side = kw.build(A, prev, dates)
    base = rows_for(F1, np.zeros(len(F1)), np.zeros(len(F1), bool), day, side, i, m, 1)[0]
    A2 = {k: v.copy() for k, v in A.items()}
    A2["c"][i, m + 1:] *= 1.05                                              # rewrite the future of that session
    A2["h"][i, m + 1:] *= 1.05
    A2["l"][i, m + 1:] *= 1.05
    A2["o"][i, m + 2:] *= 1.05                                              # (the entry minute's open, o[m + 1], is the trade's price, not a feature)
    F2, _, _, _, _ = kw.build(A2, prev, dates)
    assert np.allclose(base, rows_for(F2, np.zeros(len(F2)), np.zeros(len(F2), bool), day, side, i, m, 1)[0], equal_nan=True)


def test_the_split_is_in_time_order_and_the_safest_fraction_is_the_lowest_scores():
    day = np.repeat(np.arange(100), 5)
    cut = kw.split_sessions(day, 0.6)
    assert cut == 60
    p = np.array([0.9, 0.1, 0.5, 0.3, 0.7, 0.2])
    assert list(kw.keep_safest(p, 0.5)) == [1, 5, 3]
    assert len(kw.keep_safest(p, 0.01)) == 1 and kw.keep_safest(p, 0.01)[0] == 1


def test_train_and_test_rows_never_share_a_session_and_unusable_rows_are_in_neither():
    day = np.repeat(np.arange(100), 4)
    ok = np.ones(len(day), bool)
    ok[:8] = False                                                          # sessions 0 and 1 have no features yet
    tr, te = kw.masks(day, ok, 0.6)
    assert not (tr & te).any() and not tr[:8].any() and not te[:8].any()
    assert day[tr].max() < day[te].min() and tr.sum() + te.sum() == ok.sum()
    assert abs(len(np.unique(day[tr])) / (len(np.unique(day[tr])) + len(np.unique(day[te]))) - 0.6) < 0.02


def test_evaluate_trains_before_it_tests_and_an_informative_feature_gets_an_auc_above_one_half():
    rng = np.random.default_rng(3)
    n_days, per = 200, 30
    day = np.repeat(np.arange(n_days), per)
    x = rng.normal(0, 1, len(day))
    dis = rng.random(len(day)) < 1 / (1 + np.exp(-(x * 2.0 - 2.5)))        # the disaster really does depend on x
    out = np.where(dis, -40.0, 1.0)
    F = np.column_stack([x] + [rng.normal(0, 1, len(day)) for _ in range(len(kw.FEATS) - 1)])
    res = kw.evaluate(F, out, dis, day, kw.make_models())
    assert res["logistic"]["auc"] > 0.8 and res["boosting"]["auc"] > 0.8
    k = res["logistic"]["keeps"]
    assert k[0.1]["win"] > res["baseline"]["win"] and k[0.1]["ev"] > res["baseline"]["ev"]      # keeping the safest tenth really is safer here


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
