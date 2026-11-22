"""Offline tests for backtest/universe_floor.py - the MN runner's two switches, the universe restriction, the paired statistics
and the registered pass bars. Synthetic data only (the shared MN data dict is replaced for the duration and restored).

    python tests/test_universe_floor.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import mn_combos as m  # noqa: E402
from backtest import moderate_retests as mr  # noqa: E402
from backtest import universe_floor as uf  # noqa: E402

T, N = 150, 30


def install(X, em_cols=None, hi=None):
    """Replace mn_combos' shared data with a synthetic panel; returns the dict to restore."""
    old = dict(m._D)
    idx = pd.date_range("2024-01-01", periods=T, freq="D")
    months = idx.strftime("%Y-%m")
    cols = [f"C{j}" for j in range(N)]
    allowed = np.ones(N, bool) if em_cols is None else np.isin(np.arange(N), em_cols)
    m._D.clear()
    m._D.update(idx=idx, X=X, cols=cols, Fx=np.zeros((T, N)), months=months,
                fv=np.full(N, (idx[0] - pd.Timedelta(days=2000)).value),
                Em={mo: allowed.copy() for mo in sorted(set(months))}, ff=X.copy(),
                R=np.zeros((T, N)), reg=None, Hi=(X * 1.001 if hi is None else hi), Op=X.copy(), Lo=X * 0.999)
    return old


def restore(old):
    m._D.clear()
    m._D.update(old)


def ladder_prices():
    """Coin j gains exactly (1 + 0.01 j) every 7 days, so a ranking by j has a known forward return."""
    t = np.arange(T)[:, None]
    return 100.0 * (1.0 + 0.01 * np.arange(N))[None, :] ** (t / 7.0)


def rand_prices(seed=0):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(0, 0.03, (T, N)), axis=0))


def test_the_runner_reproduces_scored_run_when_the_switches_are_off():
    X = rand_prices(1)
    mom, rsi = uf.score_mats(X)
    old = install(X)
    try:
        for score in (mom, rsi):
            ref = mr.scored_run(score, start=2, stop="short_only", short_stop=0.5)
            mine = uf.scored_run_floor(score, start=2)
            assert len(ref) > 5 and ref.index.equals(mine.index) and np.allclose(ref.to_numpy(), mine.to_numpy(), atol=1e-12)
    finally:
        restore(old)


def test_the_minimum_number_of_names_decides_whether_a_week_trades():
    X = rand_prices(2)
    mom, _ = uf.score_mats(X)
    old = install(X, em_cols=np.arange(15))                       # only 15 eligible names
    try:
        assert len(uf.scored_run_floor(mom, 0, min_names=20)) == 0     # the base rule skips every week
        assert len(uf.scored_run_floor(mom, 0, min_names=12)) > 5
        assert len(uf.scored_run_floor(mom, 0, min_names=16)) == 0     # 15 < 16: the comparison is on the count, not off by one
        assert len(uf.scored_run_floor(mom, 0, min_names=15)) > 5      # exactly enough names trades
    finally:
        restore(old)


def test_names_a_side_and_the_week_one_cost_are_exactly_what_the_ladder_says():
    X = ladder_prices()
    score = np.tile(np.arange(N, dtype=float), (T, 1))                 # rank = coin index: long the top k, short the bottom k
    old = install(X)
    try:
        for kf, nat in ((2, False), (None, True)):
            s = uf.scored_run_floor(score, 0, k_fixed=kf)
            k = 3 if nat else kf                                       # natural: 10% of 30 coins = 3
            fwd = (1.0 + 0.01 * np.arange(N))
            exp = 0.5 * (fwd[-k:] - 1).mean() - 0.5 * (fwd[:k] - 1).mean()
            assert abs(s.iloc[1] - exp) < 1e-9, (kf, s.iloc[1], exp)          # same baskets again: no turnover cost
            assert abs(s.iloc[0] - (exp - m.FEE * 0.5)) < 1e-9                # first week builds the whole basket: half the 4k legs turn
        assert abs(uf.scored_run_floor(score, 0, k_fixed=2).iloc[1] - uf.scored_run_floor(score, 0).iloc[1]) > 1e-4   # k matters
    finally:
        restore(old)


def test_funding_is_paid_by_longs_and_received_by_shorts():
    X = ladder_prices()
    score = np.tile(np.arange(N, dtype=float), (T, 1))
    old = install(X)
    try:
        f = 0.0001 * (1.0 + np.arange(N))                                  # per-day funding rate of coin j, constant
        m._D["Fx"] = np.tile(f, (T, 1))
        s = uf.scored_run_floor(score, 0, k_fixed=2)
        fwd = (1.0 + 0.01 * np.arange(N))
        price = 0.5 * (fwd[-2:] - 1).mean() - 0.5 * (fwd[:2] - 1).mean()
        carry = 0.5 * (-7 * f[-2:].mean()) + 0.5 * (7 * f[:2].mean())      # the long pays the top coins' funding, the short collects the bottom's
        assert abs(s.iloc[1] - (price + carry)) < 1e-9, (s.iloc[1], price + carry)
        assert carry < 0                                                   # the constructed case really has the long leg paying more
    finally:
        restore(old)


def test_coins_outside_the_universe_cannot_touch_the_result():
    X = rand_prices(3)
    X2 = X.copy()
    rng = np.random.default_rng(9)
    X2[:, 20:] = 100 * np.exp(np.cumsum(rng.normal(0.02, 0.2, (T, 10)), axis=0))      # outsiders go wild
    out = []
    for P in (X, X2):
        mom, rsi = uf.score_mats(P)
        old = install(P, em_cols=np.arange(20))
        try:
            out.append(uf.blend(mom, rsi, 1, min_names=12))
        finally:
            restore(old)
    assert len(out[0]) > 5 and out[0].index.equals(out[1].index) and np.allclose(out[0], out[1], atol=1e-12)


def test_the_blend_is_half_momentum_half_rsi():
    X = rand_prices(4)
    mom, rsi = uf.score_mats(X)
    old = install(X)
    try:
        a, b = uf.scored_run_floor(mom, 3), uf.scored_run_floor(rsi, 3)
        mix = uf.blend(mom, rsi, 3)
        assert len(mix) > 5 and np.allclose(mix.to_numpy(), 0.5 * a.reindex(mix.index).to_numpy() + 0.5 * b.reindex(mix.index).to_numpy(), atol=1e-12)
        assert np.abs(a.to_numpy() - b.to_numpy()).max() > 1e-4                         # the two rankings really differ
    finally:
        restore(old)


def test_the_short_leg_exit_fires_at_fifty_percent():
    X = ladder_prices()
    score = np.tile(np.arange(N, dtype=float), (T, 1))
    hi = X * 1.001
    hi[:, :3] = X[:, :3] * 1.8                                         # the three shorted coins spike 80% inside every week
    old = install(X, hi=hi)
    try:
        s = uf.scored_run_floor(score, 0, k_fixed=3)
        fwd = (1.0 + 0.01 * np.arange(N))
        stopped = 0.5 * (fwd[-3:] - 1).mean() - 0.5 * 0.5                  # shorts closed at +50% (the gap-free fill is the level)
        assert abs(s.iloc[1] - stopped) < 1e-6, (s.iloc[1], stopped)
    finally:
        restore(old)


def test_restrict_panel_swaps_the_eligible_months_and_empties_unknown_coins():
    PN = {"A": {"el": {"2024-01", "2024-02"}}, "B": {"el": {"2024-01"}}, "C": {"el": {"2024-03"}}}
    out = uf.restrict_panel(PN, {"A": {"2024-01"}, "B": set()})
    assert out["A"]["el"] == {"2024-01"} and out["B"]["el"] == set() and out["C"]["el"] == set()


def test_statistics():
    assert abs(uf.sharpe([0.01, 0.03, 0.02, 0.0], per=52) - (0.015 / np.std([0.01, 0.03, 0.02, 0.0], ddof=1) * np.sqrt(52))) < 1e-12
    assert np.isnan(uf.sharpe([0.01, 0.01, 0.01])) and np.isnan(uf.sharpe([0.02]))
    assert abs(uf.max_fall([-0.5, 1.0]) - 0.5) < 1e-12 and abs(uf.max_fall([0.1, -0.1]) - 0.1) < 1e-12 and uf.max_fall([0.1, 0.1]) == 0.0
    d, se, w, n = uf.paired([3, 2, 1, 5], [1, 1, 1, 1])
    assert abs(d - 1.75) < 1e-12 and w == 3 and n == 4                                  # a tie is not a win
    assert abs(se - np.std([2, 1, 0, 4], ddof=1) / np.sqrt(4)) < 1e-12                  # the standard error of the mean difference
    d2, _, w2, _ = uf.paired([1, 1, 1, 1], [3, 2, 1, 5])
    assert d2 < 0 and w2 == 0                                                         # the sign follows (a - b)
    s = pd.Series(1.0, index=pd.to_datetime(["2024-04-06", "2024-04-07", "2024-04-08"]))
    t, h = uf.halves(s)
    assert len(t) == 1 and len(h) == 2                                                 # the holdout starts on its own date


def test_the_mn_bar_needs_both_halves_and_five_weekdays():
    base = {"tune": [1.0] * 7, "hold": [1.0] * 7}
    good = {"tune": [1.1] * 7, "hold": [1.1] * 7}
    assert uf.mn_passes(good, base)
    assert not uf.mn_passes({"tune": [0.9] * 7, "hold": [1.1] * 7}, base)                # the tune half loses
    assert not uf.mn_passes({"tune": [1.1] * 7, "hold": [0.9] * 7}, base)                # the holdout loses
    four = {"tune": [1.5] * 4 + [0.95] * 3, "hold": [1.1] * 7}                            # higher on average (+0.26), higher on only 4 of 7 days
    assert np.mean(four["tune"]) > 1.0 and not uf.mn_passes(four, base)                  # better on average is not enough
    five = {"tune": [1.1] * 5 + [0.95] * 2, "hold": [1.1] * 7}
    assert uf.mn_passes(five, base) == (np.mean([1.1] * 5 + [0.95] * 2) > 1.0)           # 5 of 7 days and a higher mean passes


def test_the_daily_bar_needs_both_halves_and_a_fall_no_deeper():
    base = {"tune": np.array([1.0, 1.0]), "hold": np.array([0.5, 0.5]), "fall": np.array([0.6, 0.6])}
    assert uf.daily_passes({"tune": np.array([1.2, 1.2]), "hold": np.array([0.6, 0.6]), "fall": np.array([0.6, 0.6])}, base)
    assert not uf.daily_passes({"tune": np.array([0.9, 0.9]), "hold": np.array([0.6, 0.6]), "fall": np.array([0.5, 0.5])}, base)
    assert not uf.daily_passes({"tune": np.array([1.2, 1.2]), "hold": np.array([0.4, 0.4]), "fall": np.array([0.5, 0.5])}, base)
    assert not uf.daily_passes({"tune": np.array([1.2, 1.2]), "hold": np.array([0.6, 0.6]), "fall": np.array([0.7, 0.7])}, base)


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
