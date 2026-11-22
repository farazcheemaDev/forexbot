"""Offline tests for backtest/liq_sweep.py - what the sweep bar liquidated in the map (read before the bar books its own open
interest), the real open-interest change, the reset on a gap, matching a sweep to its bar, the tune-only cuts, the 'both' flag and the
pass rule. Synthetic data only.

    python tests/test_liq_sweep.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import liq_map as lm  # noqa: E402
from backtest import liq_sweep as ls  # noqa: E402

H = lm.H


def _coin(n=8):
    t = np.arange(n) * H + 1_000 * H
    h, l, c = np.full(n, 100.05), np.full(n, 99.95), np.full(n, 100.0)  # noqa: E741
    return t, h, l, c


def test_the_sweep_bar_liquidates_what_the_map_held_at_or_above_its_low():
    t, h, l, c = _coin()  # noqa: E741
    oi = np.array([100.0, 100.0, 200.0, 200.0, 180.0, 180.0, 180.0, 180.0])
    l[3] = 94.0                                                                               # reaches the 20x / 50x / 100x bins (95, 98, 99), not 10x (90)
    liqL, liqS, doi, age = ls.liq_series(t, h, l, c, oi)
    v = (200 - 100) * 100.0 / 4                                                               # booked at bar 2, P = 100, a quarter per leverage
    assert abs(liqL[3] - 3 * v / (200 * 100.0)) < 1e-9
    assert liqS[3] == 0.0 and abs(doi[3] - 0.0) < 1e-12 and abs(doi[4] - (180 / 200 - 1)) < 1e-12
    assert age[0] == 0 and age[5] == 5


def test_a_bar_does_not_see_its_own_new_positions():
    t, h, l, c = _coin()  # noqa: E741
    oi = np.array([100.0, 100.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0])
    l[2] = 90.0                                                                               # the same bar books new positions
    liqL, *_ = ls.liq_series(t, h, l, c, oi)
    assert liqL[2] == 0.0                                                                      # nothing was held before it


def test_short_side_and_the_value_base_is_the_hour_before():
    t, h, l, c = _coin()  # noqa: E741
    oi = np.array([100.0, 100.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0])
    c[3] = 102.0                                                                              # the sweep bar's own close is NOT the base
    h[3] = 103.0                                                                              # reaches 101.01 (100x) and 102.04 (50x)
    _, liqS, *_ = ls.liq_series(t, h, l, c, oi)
    v = (200 - 100) * 100.0 / 4
    assert abs(liqS[3] - 2 * v / (200 * c[2])) < 1e-9


def test_a_gap_in_open_interest_resets_the_map_and_its_age():
    n = 10
    t = np.r_[np.arange(5), np.arange(5) + 60].astype(np.int64) * H                        # 55 hours missing
    h, l, c = np.full(n, 100.05), np.full(n, 99.95), np.full(n, 100.0)  # noqa: E741
    oi = np.array([100.0, 200.0, 200.0, 200.0, 200.0, 50.0, 50.0, 50.0, 50.0, 50.0])
    l[6] = 80.0
    liqL, _, doi, age = ls.liq_series(t, h, l, c, oi)
    assert liqL[6] == 0.0 and age[5] == 0 and age[9] == 4 and np.isnan(doi[5]) and np.isnan(liqL[5])


def test_doi_is_not_read_across_a_short_hole():
    t = np.r_[np.arange(4), np.arange(4) + 14].astype(np.int64) * H                         # 10 hours missing: no reset, no change
    h, l, c = np.full(8, 100.05), np.full(8, 99.95), np.full(8, 100.0)  # noqa: E741
    oi = np.array([100.0, 100.0, 100.0, 100.0, 150.0, 150.0, 150.0, 150.0])
    _, _, doi, age = ls.liq_series(t, h, l, c, oi)
    assert np.isnan(doi[4]) and doi[5] == 0.0 and age[7] == 7


def test_doi_needs_consecutive_hours_and_both_readings():
    t, h, l, c = _coin()  # noqa: E741
    oi = np.array([100.0, np.nan, 120.0, 130.0, 130.0, 130.0, 130.0, 130.0])
    _, _, doi, _ = ls.liq_series(t, h, l, c, oi)
    assert np.isnan(doi[1]) and np.isnan(doi[2]) and abs(doi[3] - (130 / 120 - 1)) < 1e-12


def test_attach_finds_the_sweep_bar_an_hour_before_the_entry():
    t, h, l, c = _coin()  # noqa: E741
    l[4] = 97.0
    h[5] = 104.0
    liqL, liqS = np.arange(8) / 100.0, np.arange(8) / 1000.0
    doi, age = np.full(8, 0.02), np.arange(8.0)
    T = pd.DataFrame(dict(coin=["X", "X", "Y"], side=[1, -1, 1], dist=[0.03, 0.04, 0.01],
                          t_in=pd.to_datetime(np.array([t[4] + H, t[5] + H, t[0] + H]), unit="ms")))
    A = ls.attach(T, {"X": (t, h, l, c, liqL, liqS, doi, age)})
    assert list(A.bar) == [4, 5, -1]
    assert A.liq.iat[0] == 0.04 and A.liq.iat[1] == 0.005 and A.flush.iat[0] == -0.02 and A.age.iat[1] == 5
    assert abs(A.dist_chk.iat[0] - 0.03) < 1e-12 and abs(A.dist_chk.iat[1] - 0.04) < 1e-12


def _K():
    rows = []
    for k in range(12):
        rows.append(dict(side=1, liq=float(k), flush=float(11 - k), t_in=pd.Timestamp("2023-01-01") + pd.Timedelta(days=k)))
    for k in range(6):
        rows.append(dict(side=1, liq=100.0, flush=100.0, t_in=pd.Timestamp("2025-01-01") + pd.Timedelta(days=k)))
    for k in range(6):
        rows.append(dict(side=-1, liq=float(k), flush=float(k), t_in=pd.Timestamp("2023-01-01") + pd.Timedelta(days=k)))
    return pd.DataFrame(rows)


def test_cuts_come_from_the_tune_half_and_both_needs_both():
    K = _K()
    tune = K.t_in < pd.Timestamp("2024-04-07")
    cuts, F = ls.flags(K, tune)
    assert abs(cuts[1, "liq"] - np.quantile(np.arange(12.0), 2 / 3)) < 1e-12                  # the holdout's 100s are not used
    g = K.side == 1
    assert F.loc[g & tune, "liq"].sum() == 4 and F.loc[g & tune, "flush"].sum() == 4
    assert F.loc[g & tune, "both"].sum() == 0 and F.loc[g & ~tune, "both"].all()
    assert F.loc[K.side == -1, "both"].sum() == F.loc[K.side == -1, "liq"].sum()


def test_keep_drops_early_unmatched_cold_and_missing():
    T = pd.DataFrame(dict(t_in=pd.to_datetime(["2021-12-01", "2023-01-01", "2023-01-01", "2023-01-01", "2023-01-01", "2023-01-01",
                                               "2023-01-01", "2023-01-01"]),
                          bar=[5, 5, -1, 5, 5, 5, 5, 0], age=[999, 999, 999, ls.WARM - 1, 999, 999, ls.WARM, 999],
                          liq=[0.1, 0.1, 0.1, 0.1, np.nan, 0.1, 0.1, 0.1], flush=[0.1, 0.1, 0.1, 0.1, 0.1, np.nan, 0.1, 0.1]))
    assert list(ls.keep(T).index) == [1, 6, 7]


def test_half_stats_and_the_pass_rule():
    x = pd.DataFrame(dict(net=[0.01, 0.02, 0.03, 0.01], ex=[0.0] * 4, day=["a", "b", "c", "d"]))
    r = pd.DataFrame(dict(net=[0.0, -0.01, 0.01, 0.0], ex=[0.0] * 4, day=["a", "b", "c", "d"]))
    s = ls.half_stats(x, r)
    assert s["n"] == 4 and abs(s["net"] - 0.0175) < 1e-12 and abs(s["sp"] - 0.0175) < 1e-12

    def hh(net=1e-3, t=2.5, sp=1e-3, spt=2.5, n=200):
        return dict(net=net, t=t, sp=sp, sp_t=spt, n=n)
    assert ls.passes(dict(tu=hh(), ho=hh()), 0.01) and not ls.passes(dict(tu=hh(), ho=hh()), 0.06)
    assert not ls.passes(dict(tu=hh(), ho=hh(n=99)), 0.01) and ls.passes(dict(tu=hh(), ho=hh(n=100)), 0.01)
    for kw in (dict(net=-1e-4), dict(t=1.9), dict(sp=-1e-4), dict(spt=1.9)):
        assert not ls.passes(dict(tu=hh(**kw), ho=hh()), 0.01) and not ls.passes(dict(tu=hh(), ho=hh(**kw)), 0.01), kw


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
