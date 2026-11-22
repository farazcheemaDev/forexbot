"""Tests for backtest/blindness_check.py: the clustered t, Holm over the studies' 6 cells, the gate, the planted sides, the true edge, the desk's planted
skill and its 30-bet window. Run as a script: python tests/test_blindness_check.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.blindness_check as bc  # noqa: E402
from backtest import sweep_confluence as sc  # noqa: E402


def test_the_fast_clustered_t_is_the_studies_own():
    rng = np.random.default_rng(1)
    y = rng.normal(0.1, 1.0, 500)
    day = pd.Series(np.repeat(pd.date_range("2025-01-01", periods=100), 5))
    codes = pd.factorize(day.to_numpy())[0]
    assert abs(bc.t_clustered(y, codes, codes.max() + 1) - sc.t_by_day(pd.Series(y), day)) < 1e-9


def test_holm_counts_the_four_null_cells_too():
    assert bc.holm_min_ok([0.005, 0.5]) == [True, False]        # 0.005 x 6 = 0.03
    assert bc.holm_min_ok([0.009]) == [False]                   # 0.009 x 6 = 0.054
    assert bc.holm_min_ok([0.008, 0.009]) == [True, True]       # 0.008 x 6 = 0.048; then max(0.048, 0.009 x 5 = 0.045) = 0.048 < 0.05
    assert bc.holm_min_ok([0.004, 0.011]) == [True, False]      # 0.024; then 0.011 x 5 = 0.055
    assert bc.holm_min_ok([0.009, 0.0095]) == [False, False]    # step-down: once 0.054 fails, the next fails too (0.0095 x 5 = 0.0475 alone would pass)


def _world(n_tune, n_hold, mu_t, mu_h, ctrl=-0.1, sides=(1, -1), seed=0):
    rng = np.random.default_rng(seed)
    n = n_tune + n_hold
    hold = np.r_[np.zeros(n_tune, bool), np.ones(n_hold, bool)]
    R = np.where(hold, mu_h, mu_t) + rng.normal(0, 0.3, n)
    C = np.full(n, ctrl)
    side = np.resize(np.array(sides), n)
    codes = np.arange(n) // 2                                    # two trades a day
    return R, C, side, hold, codes, codes.max() + 1


def test_the_gate_passes_a_clear_edge_and_refuses_each_missing_part():
    R, C, side, hold, codes, G = _world(600, 600, 0.3, 0.3)
    g = bc.gate(R, C, side, hold, codes, G)
    assert g["any"] and g["both"] and g["stats_any"]
    R, C, side, hold, codes, G = _world(600, 120, 0.3, 0.3)     # 60 holdout trades a side: the statistics pass, the 100-trade rule does not
    g = bc.gate(R, C, side, hold, codes, G)
    assert not g["any"] and g["stats_any"]
    R, C, side, hold, codes, G = _world(600, 600, -0.05, 0.3)   # the tune half loses
    assert not bc.gate(R, C, side, hold, codes, G)["stats_any"]
    R, C, side, hold, codes, G = _world(600, 600, 0.3, 0.3, ctrl=0.5)   # the control does better: no excess
    assert not bc.gate(R, C, side, hold, codes, G)["stats_any"]
    R, C, side, hold, codes, G = _world(600, 600, 0.3, 0.012, seed=3)   # a holdout edge too small to be significant after Holm
    assert not bc.gate(R, C, side, hold, codes, G)["stats_any"]


def test_the_gate_judges_each_side_on_its_own():
    R, C, side, hold, codes, G = _world(600, 600, 0.3, 0.3)
    R = np.where(side < 0, -0.5, R)                              # the short side loses everywhere
    g = bc.gate(R, C, side, hold, codes, G)
    assert g["any"] and not g["both"]


def _events():
    return pd.DataFrame(dict(d=[1, -1, 1, -1], RL=[2.0, -1.0, -1.0, 3.0], RS=[-1.0, 2.5, 0.5, -1.0], CL=[0.1, 0.2, 0.3, 0.4], CS=[-0.1, -0.2, -0.3, -0.4]))


def test_planted_sides_follow_p_and_pick_that_sides_outcome():
    E = _events()
    rng = np.random.default_rng(0)
    side, R, C = bc.plant(E, 1.0, rng)
    assert list(side) == [1, -1, 1, -1] and list(R) == [2.0, 2.5, -1.0, -1.0] and list(C) == [0.1, -0.2, 0.3, -0.4]
    side, R, C = bc.plant(E, 0.0, rng)
    assert list(side) == [-1, 1, -1, 1] and list(R) == [-1.0, -1.0, 0.5, 3.0] and list(C) == [-0.1, 0.2, -0.3, 0.4]
    big = pd.concat([E] * 2500, ignore_index=True)
    side, _, _ = bc.plant(big, 0.6, np.random.default_rng(5))
    assert abs(np.mean(side == big.d.to_numpy()) - 0.6) < 0.02


def test_the_true_edge_weights_the_right_and_wrong_side_by_p():
    E = _events()
    right = np.array([2.0, 2.5, -1.0, -1.0])
    wrong = np.array([-1.0, -1.0, 0.5, 3.0])
    for p in (0.5, 0.7, 1.0):
        assert abs(bc.true_edge(E, p) - (p * right + (1 - p) * wrong).mean()) < 1e-12


def _calls():
    rows = []
    for k, (day, side, st) in enumerate([("2025-01-01", "long", "LOSS"), ("2025-01-01", "long", "WIN"), ("2025-01-01", "short", "EXPIRED"),
                                         ("2025-01-02", "long", "LOSS"), ("2025-01-03", "short", "LOSS")]):
        rows.append(dict(id=k, made_ms=k, day=day, side=side, method="SMC", status=st, stop_pct=0.01, r=-1.12 if st == "LOSS" else (2.0 if st == "WIN" else -0.3),
                         base=0.2, win_r=2.5 - 0.0012 / 0.01))
    return rows


def test_planted_desk_skill_turns_losers_into_winners_at_their_own_reward():
    rows = _calls()
    assert bc.flip(rows, 0.0, np.random.default_rng(0)) == rows
    allw = bc.flip(rows, 1.0, np.random.default_rng(0))
    assert all(r["status"] == "WIN" for r in allw)
    assert [r["r"] for r in allw] == [2.38, 2.0, 2.38, 2.38, 2.38]          # a real WIN keeps its own R; a flipped call gets reward:risk less 12bp in R
    assert rows[0]["status"] == "LOSS"                                        # the pool itself is not changed


def test_the_window_holds_exactly_n_bets_from_the_start_day():
    rows = _calls()
    w = bc.window(rows, "2025-01-01", 3)
    assert [(r["day"], r["side"]) for r in w] == [("2025-01-01", "long"), ("2025-01-01", "long"), ("2025-01-01", "short"), ("2025-01-02", "long")]
    assert [(r["day"], r["side"]) for r in bc.window(rows, "2025-01-02", 2)] == [("2025-01-02", "long"), ("2025-01-03", "short")]
    assert bc.window(rows, "2025-01-02", 3) == []                             # not enough bets left: no window


def test_the_pool_mean_is_a_mean_over_bets_not_calls():
    rows = _calls()
    assert abs(bc.pool_bet_mean(rows) - np.mean([(-1.12 + 2.0) / 2, -0.3, -1.12, -1.12])) < 1e-12


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
