"""Offline tests for backtest/liq_map_past.py - the order resting k past a cluster: it trades only after the cluster level, fills only
0.05% through its own level and inside the cancel window, fills at the open on a gap, mirrors for shorts, reproduces liq_map_1m.py
at k = 0; the per-k rows, fill rates and the per-order mean (unfilled = 0). Synthetic data only.

    python tests/test_liq_map_past.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import liq_map_1m as m1  # noqa: E402
from backtest import liq_map_past as lp  # noqa: E402


def _w(px=100.0, n=m1.WIN_MIN):
    w = np.zeros((n, 4))
    w[:, 0], w[:, 1], w[:, 2], w[:, 3] = px, px + 0.05, px - 0.05, px
    return w


def test_k_zero_is_liq_map_1m_trade():
    rng = np.random.default_rng(3)
    n = 0
    for side, lvl in (("long", 99.0), ("short", 101.0)):
        for _ in range(30):
            c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, m1.WIN_MIN)))
            o = np.r_[100.0, c[:-1]]
            w = np.column_stack([o, np.maximum(o, c) * 1.002, np.minimum(o, c) * 0.998, c])
            a, b = m1.minute_trade(w, side, lvl), lp.past_trade(w, side, lvl, 0.0)
            assert (a is None) == (b is None)
            if a is not None:
                n += 1
                assert b["filled"] and b["m2"] == a["m"] and b["fill"] == a["fill"]
                for x in ("r5m", "r15m", "r60m", "rscalp", "mscalp"):
                    assert (np.isnan(a[x]) and np.isnan(b[x])) or a[x] == b[x], x
    assert n >= 20                                                                            # the paths do reach the levels


def test_the_long_order_fills_through_its_own_level_after_the_cluster():
    w = _w(100.0)
    w[5, 2] = 98.9                                                                            # through 99 (the cluster), not 98.505
    deep = 99.0 * (1 - 0.005)
    w[9, 2] = deep * (1 - 0.0005) + 1e-9                                                      # touches its level, not through
    w[12, 2] = deep * 0.999                                                                   # through: fills here, at its level
    w[12 + 15, 3], w[12 + 60, 3] = 99.0, 98.0
    tr = lp.past_trade(w, "long", 99.0, 0.005)
    assert tr["filled"] and tr["m"] == 5 and tr["m2"] == 12 and abs(tr["fill"] - deep) < 1e-12
    assert abs(tr["r15m"] - (99.0 / deep - 1)) < 1e-12 and abs(tr["r60m"] - (98.0 / deep - 1)) < 1e-12


def test_it_can_fill_in_the_cluster_minute_and_at_the_open_on_a_gap():
    w = _w(100.0)
    w[5, 2] = 98.0                                                                            # one minute through both levels
    assert lp.past_trade(w, "long", 99.0, 0.005)["m2"] == 5
    w2 = _w(100.0)
    w2[5, 2] = 98.9
    w2[8, 0], w2[8, 2] = 97.0, 96.9                                                           # opens under its level
    assert lp.past_trade(w2, "long", 99.0, 0.005)["fill"] == 97.0


def test_the_cancel_window_counts_from_the_cluster_minute():
    deep = 99.0 * (1 - 0.01)
    for at, filled in ((5 + 59, True), (5 + 60, False)):
        w = _w(100.0)
        w[5, 2] = 98.9
        w[at, 2] = deep * 0.999
        assert lp.past_trade(w, "long", 99.0, 0.01)["filled"] is filled, at


def test_no_cluster_crossing_in_the_first_hour_is_dropped_and_no_deep_fill_is_unfilled():
    w = _w(100.0)
    w[70, 2] = 90.0                                                                           # only after the fill hour
    assert lp.past_trade(w, "long", 99.0, 0.005) is None
    w2 = _w(100.0)
    w2[5, 2] = 98.9                                                                           # the cluster, never 0.5% past it
    assert lp.past_trade(w2, "long", 99.0, 0.005) == dict(filled=False, m=5)


def test_the_short_side_mirrors():
    w = _w(100.0)
    w[3, 1] = 101.1                                                                           # through 101 upward
    deep = 101.0 * 1.005
    w[7, 1] = deep * 1.001
    w[7 + 15, 3] = 101.0
    tr = lp.past_trade(w, "short", 101.0, 0.005)
    assert tr["m2"] == 7 and abs(tr["fill"] - deep) < 1e-12 and abs(tr["r15m"] - (-(101.0 / deep - 1))) < 1e-12
    w2 = _w(100.0)
    w2[3, 1] = 101.1
    w2[7, 2] = 90.0                                                                           # down, not up: never fills
    assert not lp.past_trade(w2, "short", 101.0, 0.005)["filled"]


def _D():
    return pd.DataFrame([dict(eid="e0", coin="X", side="long", half="tu", dist=0.03, kind="cluster", level=99.0, hour=0),
                         dict(eid="e0", coin="X", side="long", half="tu", dist=0.03, kind="control", level=99.0, hour=1),
                         dict(eid="e1", coin="Y", side="long", half="ho", dist=0.03, kind="cluster", level=99.0, hour=2)])


def _W():
    a, b, c = _w(100.0), _w(100.0), _w(100.0)
    a[5, 2] = 98.4                                                                            # cluster and 0.5% past, above the stop
    b[5, 2] = 98.9                                                                            # control: the level only
    return {("X", 0): a, ("X", 1): b, ("Y", 2): c}                                           # Y: never through (dropped)


def test_score_rows_per_k_and_costs():
    S = lp.score(_D(), _W(), ks=(0.0, 0.005))
    assert len(S) == 6
    r = S[(S.eid == "e0") & (S.kind == "cluster") & (S.k == 0.005)].iloc[0]
    assert r.ok and r.filled
    tr = lp.past_trade(_W()[("X", 0)], "long", 99.0, 0.005)
    assert abs(r["60m"] - (tr["r60m"] - m1.lm.FEE - m1.lm.FUND_H * 61 / 60)) < 1e-15
    assert tr["mscalp"] > 1 and abs(r["scalp"] - (tr["rscalp"] - m1.lm.FEE - m1.lm.FUND_H * tr["mscalp"] / 60)) < 1e-15
    c = S[(S.kind == "control") & (S.k == 0.005)].iloc[0]
    assert c.ok and not c.filled and np.isnan(c["60m"])
    y = S[S.eid == "e1"]
    assert (~y.ok.astype(bool)).all() and (~y.filled.astype(bool)).all()


def test_score_reads_each_rows_side():
    w = _w(100.0)
    w[4, 1] = 102.0                                                                           # through 101 and 0.5% past it, upward
    w[4 + 60, 3] = 100.0
    D = pd.DataFrame([dict(eid="s0", coin="Z", side="short", half="tu", dist=0.01, kind="cluster", level=101.0, hour=0)])
    r = lp.score(D, {("Z", 0): w}, ks=(0.005,)).iloc[0]
    tr = lp.past_trade(w, "short", 101.0, 0.005)
    assert r.filled and r["60m"] > 0 and abs(r["60m"] - (tr["r60m"] - m1.lm.FEE - m1.lm.FUND_H * 61 / 60)) < 1e-15


def test_fill_rate_and_per_order_count_unfilled_as_zero():
    S = pd.DataFrame([dict(k=0.005, side="long", half="tu", kind="cluster", ok=True, filled=True, day="d1", **{"60m": 0.01}),
                      dict(k=0.005, side="long", half="tu", kind="cluster", ok=True, filled=False, day="d2", **{"60m": np.nan}),
                      dict(k=0.005, side="long", half="tu", kind="cluster", ok=True, filled=True, day="d3", **{"60m": -0.004}),
                      dict(k=0.005, side="long", half="tu", kind="cluster", ok=True, filled=True, day="d4", **{"60m": np.nan}),
                      dict(k=0.005, side="long", half="tu", kind="cluster", ok=False, filled=False, day="d5", **{"60m": np.nan}),
                      dict(k=0.005, side="long", half="tu", kind="control", ok=True, filled=False, day="d1", **{"60m": np.nan})])
    assert abs(lp.fill_rate(S, "long", 0.005, "cluster") - 3 / 4) < 1e-12 and lp.fill_rate(S, "long", 0.005, "control") == 0.0
    mean, _ = lp.per_order(S, "long", 0.005, "tu")
    assert abs(mean - (0.01 + 0.0 - 0.004) / 3) < 1e-15                                       # unfilled 0; no exit price dropped


def test_at_k_keeps_only_filled_rows_for_the_cell():
    S = lp.score(_D(), _W(), ks=(0.0, 0.005))
    d = lp.at_k(S, 0.005)
    assert d.ok.sum() == 1 and set(d.k) == {0.005}


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
