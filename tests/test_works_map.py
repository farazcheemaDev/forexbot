"""Offline tests for backtest/works_map.py's measurements - annualising, a state cell and its both-halves flag, the pairwise weekly
correlation from the later start, the worst / best weeks, the NEXT-30-days sum (no look-back, no same-day) and the per-half Spearman.

    python tests/test_works_map.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import works_map as wm  # noqa: E402


def test_state_cell_annualises_and_flags_both_halves():
    idx = pd.date_range("2024-07-01", periods=120, freq="D")
    x = pd.Series(0.001, index=idx)
    x[idx >= wm.CUT] = -0.002
    m = pd.Series(True, index=idx)
    c = wm.state_cell(x, m)
    a = (idx < wm.CUT).sum()
    assert c["n"] == 120 and abs(c["tu"] - 0.365) < 1e-12 and abs(c["ho"] + 0.73) < 1e-12 and not c["both"]
    assert abs(c["ann"] - (0.001 * a - 0.002 * (120 - a)) / 120 * 365) < 1e-12
    x2 = pd.Series(0.001, index=idx)
    assert wm.state_cell(x2, m)["both"] and not wm.state_cell(x2, m & (idx < wm.CUT))["both"]   # one half empty: not 'both'
    few = m & ((idx < wm.CUT) | (idx < wm.CUT + pd.Timedelta(days=15)))                       # 15 holdout days only
    assert not wm.state_cell(x2, few)["both"]


def test_pair_corr_starts_at_the_later_book():
    idx = pd.date_range("2020-01-05", periods=40, freq="W-SUN")
    rng = np.random.default_rng(1)
    a = pd.Series(rng.normal(size=40), index=idx)
    b = a.copy()
    b[:20] = -a[:20]                                                                          # before b's start it is the mirror
    W = pd.DataFrame(dict(a=a, b=b))
    R = wm.pair_corr(W, dict(a=idx[0], b=idx[20]))
    assert abs(R.loc["a", "b"] - 1.0) < 1e-12 and R.loc["a", "a"] == 1.0


def test_extreme_weeks():
    idx = pd.date_range("2020-01-05", periods=10, freq="W-SUN")
    W = pd.DataFrame(dict(x=np.arange(10.0), y=-np.arange(10.0)), index=idx)
    tot = W.x
    w = wm.extreme_weeks(W, tot, q=0.2, worst=True)
    b = wm.extreme_weeks(W, tot, q=0.2, worst=False)
    assert abs(w.x - np.mean([0.0, 1.0])) < 1e-12 and abs(b.y + np.mean([8.0, 9.0])) < 1e-12
    idx2 = pd.date_range("2020-01-05", periods=11, freq="W-SUN")
    W2 = pd.DataFrame(dict(x=np.arange(11.0)), index=idx2)
    assert abs(wm.extreme_weeks(W2, W2.x, q=0.1).x - 0.5) < 1e-12                              # the cut (1.0) is itself a week: kept


def test_forward_is_the_next_k_days_only():
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    x = pd.Series(np.arange(10.0), index=idx)
    f = wm.forward(x, k=3)
    assert f.iloc[0] == 1 + 2 + 3 and f.iloc[6] == 7 + 8 + 9 and np.isnan(f.iloc[7])


def test_spearman_halves_samples_every_step_and_splits():
    idx = pd.date_range("2023-01-01", "2026-01-01", freq="D")
    s = pd.Series(np.arange(len(idx), dtype=float), index=idx)
    y = s.copy()
    y[idx >= wm.CUT] = -y[idx >= wm.CUT]
    a, b = wm.spearman_halves(s, y, step=10)
    assert abs(a - 1.0) < 1e-12 and abs(b + 1.0) < 1e-12
    a3, _ = wm.spearman_halves(s, s ** 4, step=10)
    assert abs(a3 - 1.0) < 1e-12                                                              # monotone, not linear: ranks


def test_ann_and_sharpe():
    x = pd.Series([0.01, -0.01, 0.02, 0.0])
    assert abs(wm.ann(x) - 0.005 * 365) < 1e-12
    assert abs(wm.sharpe(x) - 0.005 / x.std(ddof=1) * np.sqrt(365)) < 1e-12


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
