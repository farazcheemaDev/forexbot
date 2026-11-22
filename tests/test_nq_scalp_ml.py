"""Tests for backtest/nq_scalp_ml.py: no look-ahead in the features, the forward-return targets, strict walk-forward training, top-share selection with costs, and the required-IC formula.

Run as a script (no pytest on this PC):  python tests/test_nq_scalp_ml.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.nq_scalp_ml as sm  # noqa: E402


def toy(n=40, seed=6):
    rng = np.random.default_rng(seed)
    C = 100 * np.exp(np.cumsum(rng.normal(0, 0.0003, (n, 390)), axis=1))
    O = np.concatenate([C[:, :1], C[:, :-1]], axis=1)
    H, Lo = np.maximum(O, C) * 1.0001, np.minimum(O, C) * 0.9999
    V = rng.integers(50, 150, (n, 390)).astype(float)
    A = dict(o=O, h=H, l=Lo, c=C, v=V)
    prev = np.r_[np.nan, C[:-1, -1]]
    dates = pd.bdate_range("2026-01-05", periods=n)
    return A, dates, prev


def row(X, S, M, i, m):
    sel = (S == i) & (M == m)
    assert sel.sum() == 1
    return np.flatnonzero(sel)[0]


def test_features_never_read_a_bar_after_the_decision_close_but_the_target_does():
    A, dates, prev = toy()
    X, Y, S, M = sm.build(A, dates, prev)
    i, m = 30, 120
    r = row(X, S, M, i, m)
    A2 = {k: v.copy() for k, v in A.items()}
    for k in "hlc":
        A2[k][i, m + 1:] *= 1.04                                          # the entry minute's own high / low / close are the future too: a feature must not read them
    A2["o"][i, m + 2:] *= 1.04                                            # only the entry minute's OPEN stays (it is the fill price)
    A2["v"][i, m + 1:] *= 3.0
    X2, Y2, S2, M2 = sm.build(A2, dates, prev)
    assert np.allclose(X[r], X2[r], equal_nan=True)                       # the decision's features are untouched by the rewritten future
    assert abs(Y[3][r] - Y2[3][r]) > 1.0                                  # while the forward return, of course, moved


def test_the_forward_return_enters_at_the_next_open_and_exits_h_minutes_later():
    A, dates, prev = toy()
    X, Y, S, M = sm.build(A, dates, prev)
    i, m = 25, 90
    r = row(X, S, M, i, m)
    for h in sm.HORIZONS:
        assert abs(Y[h][r] - (A["o"][i, m + 1 + h] / A["o"][i, m + 1] - 1) * 1e4) < 1e-9


def test_features_are_signed_by_direction_of_the_move_and_volume_imbalance_by_the_candle_colour():
    A, dates, prev = toy()
    i, m = 28, 150
    A["o"][i, m - 4:m + 1] = A["c"][i, m - 4:m + 1] * 0.999                # five green candles: close above open
    X, Y, S, M = sm.build(A, dates, prev)
    r = row(X, S, M, i, m)
    assert abs(X[r, sm.FEATS.index("sv5")] - 1.0) < 1e-9                  # all signed volume is buying
    A["o"][i, m - 4:m + 1] = A["c"][i, m - 4:m + 1] * 1.001                # five red candles
    X, Y, S, M = sm.build(A, dates, prev)
    assert abs(X[row(X, S, M, i, m), sm.FEATS.index("sv5")] + 1.0) < 1e-9


def test_walk_forward_trains_only_on_earlier_years_a_relationship_that_flips_is_predicted_wrongly():
    rng = np.random.default_rng(1)
    year = np.repeat(np.arange(2010, 2024), 3000)
    x = rng.normal(0, 1, len(year))
    y = np.where(year < 2020, x, -x) + rng.normal(0, 0.5, len(year))     # the sign of the relationship flips in 2020
    X = np.column_stack([x] + [rng.normal(0, 1, len(year)) for _ in range(len(sm.FEATS) - 1)])
    pred = sm.walk_forward(X, y, year, sm.make_models()["ridge"], list(range(len(sm.FEATS))), [2020])
    te = year == 2020
    assert np.isfinite(pred[te]).all() and np.isnan(pred[~te]).all()
    assert sm.rank_ic(pred[te], y[te]) < -0.5                              # trained on the old regime only: confidently wrong, not leaking 2020
    early = sm.walk_forward(X, y, year, sm.make_models()["ridge"], list(range(len(sm.FEATS))), [2011, 2012])
    assert np.isnan(early).all()                                           # fewer than three earlier years: no prediction
    y2 = np.where(year == 2020, x, rng.normal(0, 1, len(year)))             # x matters ONLY in 2020; before that y is pure noise
    p2 = sm.walk_forward(X, y2, year, sm.make_models()["ridge"], list(range(len(sm.FEATS))), [2020])
    assert abs(sm.rank_ic(p2[year == 2020], y2[year == 2020])) < 0.1        # a model that had seen 2020 would score ~0.5 here


def test_scale_and_volume_ratios_equal_the_hand_formulas():
    A, dates, prev = toy(n=60)
    i, m = 40, 120
    A["v"][i, m - 4:m + 1] = 300.0                                         # the last 5 minutes: busy
    A["v"][i, m - 29:m - 4] = 100.0                                        # the 25 before them: ordinary
    A["v"][:i, :] = 100.0                                                  # every earlier session: 100 a minute
    X, Y, S, M = sm.build(A, dates, prev)
    r = row(X, S, M, i, m)
    C = A["c"]
    sd = np.std(np.diff(C, axis=1) / C[:, :-1], axis=1) * 1e4
    scale = sd[i - 20:i].mean()                                            # the 20 sessions BEFORE this one, per-minute volatility in bp
    z1 = (C[i, m] / C[i, m - 1] - 1) * 1e4 / scale
    assert abs(X[r, sm.FEATS.index("z1")] - np.clip(z1, -10, 10)) < 1e-9
    z15 = (C[i, m] / C[i, m - 15] - 1) * 1e4 / (scale * np.sqrt(15))
    assert abs(X[r, sm.FEATS.index("z15")] - np.clip(z15, -10, 10)) < 1e-9
    assert abs(X[r, sm.FEATS.index("vol5")] - 1500.0 / 500.0) < 1e-9       # 5 minutes of 300 against the earlier sessions' 5 x 100
    assert abs(X[r, sm.FEATS.index("vol30")] - (1500.0 + 2500.0) / 3000.0) < 1e-9


def test_extreme_moves_are_clipped_so_one_bad_print_cannot_dominate_a_fit():
    A, dates, prev = toy()
    i, m = 22, 99                                                          # decisions fall on minutes 30, 33, ... so 99 is one
    A["c"][i, m] *= 1.5                                                   # a 50% one-minute print
    A["h"][i, m] = A["c"][i, m] * 1.0001
    X, Y, S, M = sm.build(A, dates, prev)
    r = row(X, S, M, i, m)
    for name in ("z1", "z3", "z5", "z_open", "z_vwap"):
        assert abs(X[r, sm.FEATS.index(name)]) <= 10.0 + 1e-12
    assert X[r, sm.FEATS.index("z1")] == 10.0
    assert X[r, sm.FEATS.index("pos")] <= 1.0                              # the unclipped range position stays a fraction


def test_top_share_selection_takes_the_largest_absolute_predictions_each_year_and_charges_the_cost():
    year = np.array([2020] * 10 + [2021] * 10)
    base = np.array([-5.5, -4.2, -3.3, -2.1, -1.7, 0.4, 1.1, 2.6, 3.9, 4.8])      # ten distinct magnitudes
    pred = np.r_[base, base * 10]
    y = np.sign(pred) * 3.0                                               # the sign is always right and worth 3 bp
    sel, net = sm.top_trades(pred, y, year, 0.2, 1.0)
    assert sel.sum() == 4 and np.allclose(net, 2.0)                       # 2 of 10 each year, +3 gross - 1 cost
    assert set(np.abs(pred[sel][:2])) == {5.5, 4.8} and set(np.abs(pred[sel][2:])) == {55.0, 48.0}
    wrong = sm.top_trades(pred, -y, year, 0.2, 1.0)[1]
    assert np.allclose(wrong, -4.0)                                       # trading the wrong way loses 3 + 1


def test_required_ic_matches_the_hand_formula():
    assert abs(sm.required_ic(0.77, 8.1) - 0.77 / (1.755 * 8.1)) < 1e-12


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
