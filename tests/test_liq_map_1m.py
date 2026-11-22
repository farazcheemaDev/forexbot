"""Offline tests for backtest/liq_map_1m.py - the minute window from daily files, the fill minute, the four exits and the overshoot on
both sides, costs, the per-event control mean, the deep subset and the pass rule. Synthetic data only.

    python tests/test_liq_map_1m.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import liq_map_1m as m1  # noqa: E402

M = m1.M


def _w(px=100.0, n=m1.WIN_MIN):
    w = np.zeros((n, 4))
    w[:, 0], w[:, 1], w[:, 2], w[:, 3] = px, px + 0.05, px - 0.05, px
    return w


def test_the_window_stitches_two_days_and_leaves_missing_minutes_empty():
    start = 1_000 * M
    t1 = start + np.arange(0, 100) * M
    t2 = start + np.arange(100, 180) * M
    a1 = (t1, np.full(100, 1.0), np.full(100, 2.0), np.full(100, 0.5), np.full(100, 1.5))
    a2 = (np.delete(t2, 5), *(np.full(79, v) for v in (3.0, 4.0, 2.5, 3.5)))
    w = m1.window([a1, a2, None], start)
    assert w.shape == (180, 4) and w[0, 0] == 1.0 and w[150, 3] == 3.5 and np.isnan(w[105]).all()


def test_a_long_fills_in_the_first_minute_through_the_level():
    w = _w(100.0)
    w[7, 2] = 99.0 * (1 - 0.0005) + 1e-9                                                    # touched, not through
    w[9, 2] = 98.9                                                                           # through 99
    w[9 + 5, 3], w[9 + 15, 3], w[9 + 60, 3] = 99.5, 100.2, 98.0
    tr = m1.minute_trade(w, "long", 99.0)
    assert tr["m"] == 9 and tr["fill"] == 99.0
    assert abs(tr["r5m"] - (99.5 / 99 - 1)) < 1e-12 and abs(tr["r15m"] - (100.2 / 99 - 1)) < 1e-12 and abs(tr["r60m"] - (98.0 / 99 - 1)) < 1e-12
    w2 = _w(100.0)
    w2[70, 2] = 90.0                                                                         # only after the fill hour: not this trade
    assert m1.minute_trade(w2, "long", 99.0) is None
    w3 = _w(100.0)
    w3[4, 0], w3[4, 2] = 98.0, 97.9                                                          # opens under the level: filled at the open
    assert m1.minute_trade(w3, "long", 99.0)["fill"] == 98.0


def test_the_scalp_bracket_and_its_tie_rules():
    w = _w(99.2)
    w[3, 2] = 98.9                                                                           # fill at 99
    w[10, 1] = 99.0 * 1.010 + 0.001                                                          # target first
    tr = m1.minute_trade(w, "long", 99.0)
    assert abs(tr["rscalp"] - 0.010) < 1e-12 and tr["mscalp"] == 8
    w2 = _w(99.2)
    w2[3, 2] = 99.0 * 0.995 - 0.01                                                           # the fill minute reaches the stop
    tr2 = m1.minute_trade(w2, "long", 99.0)
    assert abs(tr2["rscalp"] + 0.005) < 1e-12 and tr2["mscalp"] == 1
    w3 = _w(99.2)
    w3[3, 2] = 98.9
    w3[6, 1], w3[6, 2] = 101.0, 98.0                                                         # both in one minute: the stop
    assert abs(m1.minute_trade(w3, "long", 99.0)["rscalp"] + 0.005) < 1e-12
    w4 = _w(99.2)
    w4[3, 2] = 98.9
    w4[6, 0], w4[6, 2] = 98.0, 97.9                                                          # gaps through the stop: out at the open
    assert abs(m1.minute_trade(w4, "long", 99.0)["rscalp"] - (98.0 / 99 - 1)) < 1e-12
    w5 = _w(99.2)
    w5[3, 2] = 98.9
    w5[3 + 60, 3] = 99.3                                                                     # neither: out at the close 60 minutes on
    assert abs(m1.minute_trade(w5, "long", 99.0)["rscalp"] - (99.3 / 99 - 1)) < 1e-12


def test_the_short_side_mirrors():
    w = _w(100.8)
    w[2, 1] = 101.1                                                                          # through 101 upward
    w[2 + 5, 3] = 100.5
    w[12, 2] = 101.0 * 0.99 - 0.001                                                          # short target
    tr = m1.minute_trade(w, "short", 101.0)
    assert tr["m"] == 2 and abs(tr["r5m"] - (-(100.5 / 101 - 1))) < 1e-12 and abs(tr["rscalp"] - 0.010) < 1e-12


def test_the_overshoot_is_how_far_past_the_level_in_five_minutes():
    w = _w(100.0)
    w[9, 2] = 98.9
    w[12, 2] = 98.0                                                                          # deepest within 5 minutes after the fill
    w[20, 2] = 90.0                                                                          # later: not counted
    assert abs(m1.minute_trade(w, "long", 99.0)["over"] - (99 - 98) / 99) < 1e-12


def test_costs_pro_rata():
    assert abs(m1.net(0.01, 60) - (0.01 - 12e-4 - 1e-4 / 8)) < 1e-15


def _S():
    rows = []
    for k, (half, day) in enumerate([("tu", "d1"), ("tu", "d2"), ("tu", "d3"), ("ho", "d4")]):
        rows.append(dict(eid=f"e{k}", side="long", half=half, dist=0.09 if k < 2 else 0.03, kind="cluster", ok=True, day=day, **{"5m": 0.01 * (k + 1)}))
        rows.append(dict(eid=f"e{k}", side="long", half=half, dist=0.09, kind="control", ok=True, day=day, **{"5m": 0.0}))
        rows.append(dict(eid=f"e{k}", side="long", half=half, dist=0.09, kind="control", ok=True, day=day, **{"5m": 0.02}))
    rows.append(dict(eid="e9", side="long", half="tu", dist=0.09, kind="cluster", ok=False, day="d5", **{"5m": np.nan}))
    return pd.DataFrame(rows)


def test_cell_uses_the_mean_of_each_events_controls_and_the_deep_subset():
    st = m1.cell(_S(), "long", "5m", "tu")
    assert st["n"] == 3 and abs(st["net"] - 0.02) < 1e-12 and abs(st["ex"] - (0.02 - 0.01)) < 1e-12
    deep = m1.cell(_S(), "long", "5m", "tu", sub=lambda d: d.dist >= m1.DEEP)
    assert deep["n"] == 2 and np.isnan(deep["net"])                                        # two deep events: too few to score


def test_the_pass_rule():
    def half(net=1e-3, t=2.5, ex=1e-3, ext=2.5):
        return dict(net=net, t=t, ex=ex, ex_t=ext)
    assert m1.passes(dict(tu=half(), ho=half()), 0.01) and not m1.passes(dict(tu=half(), ho=half()), 0.06)
    for kw in (dict(net=-1e-4), dict(t=1.9), dict(ex=-1e-4), dict(ext=1.9)):
        assert not m1.passes(dict(tu=half(**kw), ho=half()), 0.01) and not m1.passes(dict(tu=half(), ho=half(**kw)), 0.01), kw


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
