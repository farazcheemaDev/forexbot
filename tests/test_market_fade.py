"""Offline tests for backtest/market_fade.py - the market series, the entry timing, the z-score's causality, the one-trade rule, the
shift null and the pass rule. No network, no archive.

    python tests/test_market_fade.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import candle_scan as cs  # noqa: E402
from backtest import market_fade as mf  # noqa: E402


def test_bar_returns_average_only_members_and_need_enough_coins():
    O = np.array([[100.0, 50.0, 10.0], [100.0, 50.0, 10.0]])
    C = np.array([[110.0, 55.0, 20.0], [90.0, 50.0, 12.0]])
    M = np.array([[True, True, False], [True, True, True]])
    R = mf.bar_returns(O, C, M, min_coins=2)
    assert abs(R[0] - 0.10) < 1e-12                                       # coin 3 is not a member of bar 0 (+100% ignored)
    assert abs(R[1] - np.mean([-0.10, 0.0, 0.20])) < 1e-12
    assert np.isnan(mf.bar_returns(O, C, M, min_coins=3)[0]) and not np.isnan(mf.bar_returns(O, C, M, min_coins=3)[1])


def test_forward_return_enters_at_the_next_open_and_leaves_h_bars_after_the_signal():
    O = np.array([[10.0, 20.0], [11.0, 22.0], [12.0, 24.0], [13.0, 26.0], [14.0, 28.0]])
    C = np.array([[10.5, 21.0], [11.5, 23.0], [13.2, 22.0], [13.5, 27.0], [14.5, 29.0]])
    M = np.ones((5, 2), bool)
    F, fwd = mf.forward_returns(O, C, M, 2, min_coins=2)
    assert abs(fwd[0, 0] - (C[2, 0] / O[1, 0] - 1)) < 1e-12 and abs(fwd[0, 1] - (C[2, 1] / O[1, 1] - 1)) < 1e-12
    assert abs(F[0] - np.mean([13.2 / 11 - 1, 22 / 22 - 1])) < 1e-12
    assert np.isnan(F[3]) and np.isnan(F[4])                               # no room for the exit
    M2 = M.copy()
    M2[0, 1] = False                                                       # membership is read at the SIGNAL bar
    assert np.isnan(mf.forward_returns(O, C, M2, 2, min_coins=2)[0][0])
    assert abs(mf.forward_returns(O, C, M2, 2, min_coins=1)[0][0] - (13.2 / 11 - 1)) < 1e-12


def test_the_zscore_scale_comes_only_from_earlier_bars():
    rng = np.random.default_rng(0)
    R = rng.normal(0, 0.01, 400)
    z = mf.zscore(R, win=60, min_periods=40)
    assert np.isnan(z[:40]).all() and np.isfinite(z[41])
    R2 = R.copy()
    R2[200:] = rng.normal(0, 0.05, 200)                                    # the future changes
    assert np.allclose(mf.zscore(R2, win=60, min_periods=40)[:200], z[:200], equal_nan=True)
    R3 = R.copy()
    R3[150] *= 2.0                                                         # the bar itself is not in its own scale
    assert abs(mf.zscore(R3, win=60, min_periods=40)[150] - 2.0 * z[150]) < 1e-9


def test_one_trade_at_a_time():
    f = np.zeros(14, bool)
    f[[2, 3, 4, 9]] = True
    assert mf.pick_events(f, 3).tolist() == [2, 9]
    f2 = np.zeros(14, bool)
    f2[[2, 5]] = True
    assert mf.pick_events(f2, 3).tolist() == [2, 5]                        # a signal ON the exit bar is allowed


def test_event_net_signs_and_costs():
    F = np.array([0.0, 0.03, -0.02, 0.0])
    assert np.allclose(mf.event_net(F, [1, 2], "short", 5), [-0.03 - mf.FEE, 0.02 - mf.FEE])
    assert np.allclose(mf.event_net(F, [1, 2], "long", 5), [0.03 - mf.FEE - mf.FUND_H * 20, -0.02 - mf.FEE - mf.FUND_H * 20])


def test_shifts_are_whole_days_and_leave_room():
    s = mf.draw_shifts(8000, n=400, seed=3)
    assert (s % mf.SHIFT_STEP == 0).all() and s.min() >= mf.MIN_SHIFT and s.max() <= 8000 - mf.MIN_SHIFT


def planted(effect, seed=5, n=8760):
    rng = np.random.default_rng(seed)
    t = np.datetime64("2022-01-01T00", "ns") + np.arange(n) * mf.STEP
    z = rng.normal(0, 1, n)
    F = rng.normal(0, 0.01, n)
    F[z >= 2.0] -= effect                                                  # the market falls after a strong up-move
    F[-12:] = np.nan                                                       # as in the real series: no room for the exit at the end
    return cs.day_index(t), F, z


def test_a_planted_reversal_is_found_and_a_placebo_is_not():
    days, F, z = planted(0.02)
    shifts = mf.draw_shifts(len(F), n=300)
    c = mf.cell(days, F, z, 2.0, 5, "short", shifts)
    assert c["tu"]["net"] > 0.01 and c["ho"]["net"] > 0.01 and c["tu"]["t"] > 4 and c["ho"]["t"] > 4
    assert c["tu"]["p"] < 0.02 and c["ho"]["p"] < 0.02
    days, F, z = planted(0.0)
    c0 = mf.cell(days, F, z, 2.0, 5, "short", shifts)
    assert c0["tu"]["p"] > 0.05 and c0["ho"]["p"] > 0.05 and abs(c0["tu"]["t"]) < 3 and abs(c0["ho"]["t"]) < 3     # no effect, no finding
    cl = mf.cell(days, F, z, 2.0, 5, "long", shifts)                       # the mirror side uses z <= -thr, not z >= thr
    flag = (z <= -2.0) & np.isfinite(F)
    assert cl["n"] == len(mf.pick_events(flag, 5)) and cl["n"] != c0["n"]


def test_the_three_fold_pass_rule():
    good = dict(tu=dict(net=0.004, t=2.5, p=0.01), ho=dict(net=0.003, t=2.2, p=0.03))
    assert mf.passes(good, 7) and mf.passes(good, 9)
    assert not mf.passes(good, 6)                                          # no plateau
    assert not mf.passes(dict(good, ho=dict(net=0.003, t=2.2, p=0.06)), 9)  # the null says the timing does not matter
    assert not mf.passes(dict(good, tu=dict(net=0.004, t=1.9, p=0.01)), 9)
    assert not mf.passes(dict(good, tu=dict(net=-0.001, t=2.5, p=0.01)), 9)
    assert not mf.passes(None, 9)
    pos = dict(tu=dict(n=10, net=0.001), ho=dict(n=10, net=0.002))
    assert mf.positive_both(pos) and not mf.positive_both(dict(pos, ho=dict(n=10, net=-0.001))) and not mf.positive_both(None)


def test_the_t_has_the_sign_of_the_mean():
    days, F, z = planted(0.02)
    c = mf.cell(days, F, z, 2.0, 5, "long", mf.draw_shifts(len(F), n=50))     # buying after up-moves that then fall
    assert c["tu"]["net"] < 0 and c["tu"]["t"] < 0 and c["ho"]["net"] < 0 and c["ho"]["t"] < 0


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
