"""Offline tests for backtest/analyst_states.py - each gate keeps the calls its rule says, the bet unit (day + side), the improvement
(kept minus dropped hit-over-random, at the bet level) and the per-bet R. Synthetic data only.

    python tests/test_analyst_states.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import analyst_states as A  # noqa: E402


def _d():
    rows = [
        dict(side="long", method="FIB", btc="bull", fuel="HIGH", alt30=0.05),     # 0 momentum state
        dict(side="long", method="SR", btc="bull", fuel="LOW", alt30=0.05),       # 1 fuel low
        dict(side="long", method="SMC", btc="chop", fuel="MID", alt30=-0.20),     # 2 bleed
        dict(side="short", method="SMC", btc="chop", fuel="MID", alt30=-0.20),    # 3 bleed short
        dict(side="short", method="FIB", btc="bear", fuel="MID", alt30=0.00),     # 4 bear short
        dict(side="short", method="SR", btc="bull", fuel="HIGH", alt30=0.10),     # 5 short in a run
        dict(side="short", method="SR", btc="chop", fuel="LOW", alt30=-0.30),     # 6 deep bleed short
        dict(side="long", method="FIB", btc="chop", fuel="LOW", alt30=-0.30),     # 7 deep bleed long FIB
        dict(side="long", method="SR", btc="bull", fuel="MID", alt30=-0.15),      # 8 exactly at the bleed line
    ]
    return pd.DataFrame(rows)


def test_g1_family_state():
    assert list(A.keep("G1", _d())) == [True, False, False, True, True, False, True, False, False]


def test_g2_btc_label():
    assert list(A.keep("G2", _d())) == [True, True, False, False, True, False, False, False, True]


def test_g3_deep_bleed_longs_only():
    assert list(A.keep("G3", _d())) == [True, True, True, True, True, True, False, True, True]


def test_g4_method_state():
    assert list(A.keep("G4", _d())) == [True, True, True, True, True, False, True, False, True]           # row 4: FIB in a momentum state


def test_bets_group_day_and_side_and_score_differences():
    d = pd.DataFrame(dict(day=["a", "a", "a", "b", "b", "c", "c", "d"], side=["long", "long", "short", "long", "short", "long", "long", "short"],
                          win=[1, 0, 1, 1, 0, 0, 1, 0.0], base_p=[0.2] * 8, r_net=[2, -1, 2, 2, -1, -1, 2, -1.0]))
    b = A.bets(d)
    assert len(b) == 6 and abs(b.loc[("a", "long"), "ex"] - 0.3) < 1e-12 and b.loc[("a", "long"), "n"] == 2
    k = pd.Series([True, True, False, True, False, True, True, False])
    s = A.score(d, k)
    kept = A.bets(d[k]).ex.to_numpy()
    drop = A.bets(d[~k]).ex.to_numpy()
    assert abs(s["imp"] - (kept.mean() - drop.mean())) < 1e-12 and s["n"] == 5 and abs(s["share"] - 5 / 8) < 1e-12
    assert abs(s["Rbet"] - A.bets(d[k]).R.mean()) < 1e-12


def test_welch_and_t_mean():
    a, b = np.array([1.0, 2.0, 3.0]), np.array([0.0, 0.0, 1.0])
    se = np.sqrt(a.var(ddof=1) / 3 + b.var(ddof=1) / 3)
    assert abs(A.welch_t(a, b) - (2.0 - 1 / 3) / se) < 1e-12
    assert abs(A.t_mean(a) - 2.0 / (1.0 / np.sqrt(3))) < 1e-12


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
