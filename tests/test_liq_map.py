"""Offline tests for backtest/liq_map.py - the price grid, the map's three steps (liquidate, shrink, book) and their order, the cluster
search, the limit order's fill and the three exits on both sides, costs, the 4-hour grid, an event's causality / cooldown / eligibility,
the map reset across an open-interest gap, the controls (same distance, same half), the statistics and the pass rule. Synthetic data only.

    python tests/test_liq_map.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import liq_map as lm  # noqa: E402

H = lm.H


def test_the_grid_round_trips_within_a_bin():
    g = lm.Grid(1.0, 1000.0)
    for p in (1.5, 37.2, 99.9, 512.0):
        assert abs(g.price(g.idx(p)) / p - 1) < 0.0025
    assert g.idx(0.5) == 0 and g.idx(5000.0) == g.n - 1                                   # clipped at the edges


def test_a_rise_in_open_interest_books_longs_below_and_shorts_above():
    g = lm.Grid(10.0, 1000.0)
    lo_m, sh_m = np.zeros(g.n), np.zeros(g.n)
    P = lm.map_step(lo_m, sh_m, g, 100.0, 110.0, 101.0, 99.0, 100.0)
    assert P == 100.0
    v = 10 * 100.0 / 4
    for L in lm.LEVS:
        assert lo_m[g.idx(100 * (1 - 1 / L))] == v and sh_m[g.idx(100 * (1 + 1 / L))] == v
    assert abs(lo_m.sum() - 1000.0) < 1e-9 and abs(sh_m.sum() - 1000.0) < 1e-9


def test_a_fall_shrinks_everything_in_proportion_and_nothing_is_booked():
    g = lm.Grid(10.0, 1000.0)
    lo_m, sh_m = np.zeros(g.n), np.zeros(g.n)
    lo_m[g.idx(90.0)], sh_m[g.idx(110.0)] = 100.0, 50.0
    lm.map_step(lo_m, sh_m, g, 100.0, 80.0, 100.5, 99.5, 100.0)
    assert abs(lo_m.sum() - 80.0) < 1e-9 and abs(sh_m.sum() - 40.0) < 1e-9


def test_the_hours_range_liquidates_old_positions_before_new_ones_are_booked():
    g = lm.Grid(10.0, 1000.0)
    lo_m, sh_m = np.zeros(g.n), np.zeros(g.n)
    lo_m[g.idx(95.0)], lo_m[g.idx(90.0)] = 7.0, 3.0
    sh_m[g.idx(105.0)], sh_m[g.idx(108.0)] = 5.0, 2.0
    lm.map_step(lo_m, sh_m, g, 100.0, 100.0, 105.5, 94.0, 100.0)                         # low 94 takes the 95 longs; high 105.5 the 105 shorts
    assert lo_m[g.idx(95.0)] == 0 and lo_m[g.idx(90.0)] == 3.0
    assert sh_m[g.idx(105.0)] == 0 and sh_m[g.idx(108.0)] == 2.0
    lo2, sh2 = np.zeros(g.n), np.zeros(g.n)
    lm.map_step(lo2, sh2, g, 100.0, 104.0, 100.5, 98.0, 100.0)                           # a 100x long is booked at 99.15, under the low: survives this hour
    assert lo2[g.idx(((100.5 + 98 + 100) / 3) * 0.99)] > 0


def test_a_bin_holding_the_hours_extreme_is_liquidated_too():
    g = lm.Grid(10.0, 1000.0)
    lo_m, sh_m = np.zeros(g.n), np.zeros(g.n)
    bl, bs = g.idx(95.0), g.idx(105.0)
    lo_m[bl], sh_m[bs] = 4.0, 6.0
    lm.map_step(lo_m, sh_m, g, 100.0, 100.0, g.price(bs), g.price(bl), 100.0)          # the low / high sit INSIDE those bins
    assert lo_m[bl] == 0 and sh_m[bs] == 0


def test_big_needs_sixty_earlier_readings_and_the_80th_percentile():
    hist = list(np.arange(100.0))
    q = np.quantile(hist, 0.8)
    assert lm.is_big(hist, q, 1.0) and not lm.is_big(hist, q - 0.01, 1.0)
    assert not lm.is_big(hist[:59], 1e9, 1.0) and lm.is_big(hist[:60], 1e9, 1.0)
    assert not lm.is_big(hist, 1e9, float("nan")) and not lm.is_big(hist, 0.0, 1.0)


def _capture(monkey_ret=False):
    seen = []

    def fake(hist, ratio, lv):
        seen.append((list(hist), ratio))
        return monkey_ret if not callable(monkey_ret) else monkey_ret(hist, ratio, lv)
    return seen, fake


def test_the_big_test_never_sees_the_reading_it_judges():
    t, o, h, l, c, oi, months = _coin()  # noqa: E741
    seen, fake = _capture(False)
    old = lm.is_big
    lm.is_big = fake
    try:
        lm.coin_events(t, o, h, l, c, oi, months, np.random.default_rng(1), int(t[-1]))
    finally:
        lm.is_big = old
    longs = seen[0::2]
    for k, (hist, _) in enumerate(longs[:600]):
        assert len(hist) == min(k, lm.LOOKBACK)                                               # only EARLIER readings


def test_eligibility_is_judged_at_the_close_of_the_reference_bar():
    t, o, h, l, c, oi, months = _coin()  # noqa: E741
    old = lm.is_big
    lm.is_big = lambda hist, ratio, lv: True
    try:
        ev = lm.coin_events(t, o, h, l, c, oi, {"2022-03"}, np.random.default_rng(1), int(t[-1]))
    finally:
        lm.is_big = old
    first = min(e["i"] for e in ev)
    assert pd.Timestamp(t[first], unit="ms") == pd.Timestamp("2022-02-28 23:00")           # closes 2022-03-01 00:00


def test_the_map_is_empty_right_after_an_open_interest_gap():
    t, o, h, l, c, oi, months = _coin()  # noqa: E741
    oi2 = oi.copy()
    oi2[1000:1100] = np.nan
    oi2[1100:] *= 5.0
    seen, fake = _capture(False)
    old = lm.is_big
    lm.is_big = fake
    try:
        lm.coin_events(t, o, h, l, c, oi2, months, np.random.default_rng(1), int(t[-1]))
    finally:
        lm.is_big = old
    refs = [i for i in range(len(t)) if lm.is_ref(t[i]) and pd.Timestamp(t[i] + H, unit="ms") >= lm.START]
    k = next(n for n, i in enumerate(refs) if i >= 1100)
    assert seen[2 * k][1] < 0.05                                                              # the 5x jump was not booked


def test_the_cluster_is_the_strongest_three_bins_inside_one_to_ten_percent():
    g = lm.Grid(10.0, 1000.0)
    m = np.zeros(g.n)
    m[g.idx(95.0)] = 5.0
    m[g.idx(95.0) + 1] = 5.0
    m[g.idx(97.0)] = 8.0
    m[g.idx(99.5)] = 100.0                                                                  # inside 1% of the close: not a cluster
    m[g.idx(85.0)] = 100.0                                                                  # beyond 10%: not a cluster
    p, v = lm.cluster(m, g, 100.0, "long")
    assert v == 10.0 and p == g.price(g.idx(95.0))                                           # the middle bin of the best window
    s = np.zeros(g.n)
    s[g.idx(104.0)] = 3.0
    p2, v2 = lm.cluster(s, g, 100.0, "short")
    assert v2 == 3.0 and abs(p2 / 104.0 - 1) < 0.006
    assert np.isnan(lm.cluster(np.zeros(g.n), g, 100.0, "long")[0])


def _bars(n=120, px=100.0):
    o = np.full(n, px)
    return o.copy(), o.copy() + 0.5, o.copy() - 0.5, o.copy()


def test_a_long_limit_fills_on_a_trade_through_and_takes_its_exits():
    o, h, l, c = _bars()  # noqa: E741
    l[5] = 94.9                                                                             # 95 traded through by 0.1%
    c[5 + 4], c[5 + 24] = 97.0, 101.0
    tr = lm.trade(o, h, l, c, 2, "long", 95.0, 1.0)
    assert tr["j"] == 5 and tr["fill"] == 95.0
    assert abs(tr["r4h"] - (97 / 95 - 1)) < 1e-12 and abs(tr["r24h"] - (101 / 95 - 1)) < 1e-12
    o2, h2, l2, c2 = _bars()
    l2[5] = 95.0 * (1 - lm.THROUGH) + 1e-9                                                 # touched but not through: no fill
    assert lm.trade(o2, h2, l2, c2, 2, "long", 95.0, 1.0) is None
    o3, h3, l3, c3 = _bars()
    o3[4], l3[4] = 93.0, 92.8                                                               # gaps under the level: filled at the open
    assert lm.trade(o3, h3, l3, c3, 2, "long", 95.0, 1.0)["fill"] == 93.0
    o6, h6, l6, c6 = _bars()
    l6[2], l6[6] = 90.0, 94.9                                                               # the reference bar itself traded through: not a fill
    assert lm.trade(o6, h6, l6, c6, 2, "long", 95.0, 1.0)["j"] == 6
    o4, h4, l4, c4 = _bars()
    l4[2 + lm.LIVE + 1] = 90.0                                                              # only after the order expired
    assert lm.trade(o4, h4, l4, c4, 2, "long", 95.0, 1.0) is None
    o5, h5, l5, c5 = _bars(n=40)
    l5[5] = 94.0
    assert lm.trade(o5, h5, l5, c5, 2, "long", 95.0, 1.0) is None                          # the data ends before the 48h bracket


def test_the_bracket_long_and_short():
    o, h, l, c = _bars(px=95.5)  # noqa: E741                                              # price sits just above the level (95.0 .. 96.0)
    l[5] = 94.9
    h[8] = 95.0 + 2 * 1.5 * 1.0 + 0.01                                                     # target 98.0 reached 3 hours later
    tr = lm.trade(o, h, l, c, 2, "long", 95.0, 1.0)
    assert abs(tr["rbr"] - (98.0 / 95 - 1)) < 1e-12 and tr["hbr"] == 4
    o2, h2, l2, c2 = _bars(px=95.5)
    l2[5] = 93.4                                                                            # the fill hour reaches the stop (93.5): stopped
    tr2 = lm.trade(o2, h2, l2, c2, 2, "long", 95.0, 1.0)
    assert abs(tr2["rbr"] - (93.5 / 95 - 1)) < 1e-12 and tr2["hbr"] == 1
    o3, h3, l3, c3 = _bars(px=95.5)
    l3[5] = 94.9
    l3[7], h3[7] = 93.0, 99.0                                                               # both in one hour: the stop
    assert abs(lm.trade(o3, h3, l3, c3, 2, "long", 95.0, 1.0)["rbr"] - (93.5 / 95 - 1)) < 1e-12
    o4, h4, l4, c4 = _bars(px=104.5)
    h4[5] = 105.1                                                                           # a short limit at 105
    l4[9] = 105.0 - 3.0 - 0.01
    tr4 = lm.trade(o4, h4, l4, c4, 2, "short", 105.0, 1.0)
    assert tr4["fill"] == 105.0 and abs(tr4["rbr"] - (102.0 / 105 - 1) * -1) < 1e-12
    o5, h5, l5, c5 = _bars(px=104.5)
    h5[5] = 105.1
    o5[8], h5[8] = 108.0, 108.5                                                             # gaps through the stop (106.5): out at the open
    assert abs(lm.trade(o5, h5, l5, c5, 2, "short", 105.0, 1.0)["rbr"] - (-(108.0 / 105 - 1))) < 1e-12


def test_costs_by_hours_held():
    tr = dict(r4h=0.01, r24h=0.02, rbr=-0.01, hbr=7)
    n = lm.nets(tr)
    assert abs(n["4h"] - (0.01 - 12e-4 - 5e-4 / 8)) < 1e-15 and abs(n["24h"] - (0.02 - 12e-4 - 25e-4 / 8)) < 1e-15
    assert abs(n["bracket"] - (-0.01 - 12e-4 - 7e-4 / 8)) < 1e-15


def test_the_four_hour_closes():
    base = int(pd.Timestamp("2024-03-05", tz="UTC").value // 10**6)
    assert lm.is_ref(base + 3 * H) and lm.is_ref(base + 23 * H) and not lm.is_ref(base + 4 * H) and not lm.is_ref(base)


def _coin(n=2600, seed=3):
    rng = np.random.default_rng(seed)
    t = int(pd.Timestamp("2022-01-01", tz="UTC").value // 10**6) + np.arange(n, dtype=np.int64) * H
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.004, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.004, n)))  # noqa: E741
    oi = 1000 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    months = {"2022-01", "2022-02", "2022-03", "2022-04"}
    return t, o, h, l, c, oi, months


def test_events_are_causal_and_one_per_day_per_side():
    t, o, h, l, c, oi, months = _coin()  # noqa: E741
    cut = int(t[1800])
    ev = lm.coin_events(t, o, h, l, c, oi, months, np.random.default_rng(1), cut)
    assert len(ev) > 10
    for side in ("long", "short"):
        ii = [e["i"] for e in ev if e["side"] == side]
        assert all(b - a >= lm.COOLDOWN for a, b in zip(ii, ii[1:]))
    assert all(pd.Timestamp(t[e["i"]] + H, unit="ms") >= lm.START for e in ev)
    k = ev[len(ev) // 2]["i"]
    h2, l2, c2, oi2 = h.copy(), l.copy(), c.copy(), oi.copy()
    h2[k + 1:] *= 1.3
    l2[k + 1:] *= 0.7
    c2[k + 1:] *= 1.1
    oi2[k + 1:] *= 3.0
    ev2 = lm.coin_events(t, o, h2, l2, c2, oi2, months, np.random.default_rng(1), cut)
    a = [(e["i"], e["side"], e["level"], e["ratio"]) for e in ev if e["i"] <= k]
    b = [(e["i"], e["side"], e["level"], e["ratio"]) for e in ev2 if e["i"] <= k]
    assert a == b                                                                           # nothing after an event changes it


def test_eligibility_is_read_at_the_reference_close():
    t, o, h, l, c, oi, months = _coin()  # noqa: E741
    ev = lm.coin_events(t, o, h, l, c, oi, {"2022-03"}, np.random.default_rng(1), int(t[-1]))
    assert ev and all(pd.Timestamp(t[e["i"]] + H, unit="ms").strftime("%Y-%m") == "2022-03" for e in ev)


def test_controls_use_the_same_distance_and_stay_in_the_same_half():
    t, o, h, l, c, oi, months = _coin()  # noqa: E741
    cut = int(t[1800])
    ev = lm.coin_events(t, o, h, l, c, oi, months, np.random.default_rng(1), cut)
    for e in ev:
        assert 0 < len(e["ctrl"]) <= lm.N_CTRL
        for x in e["ctrl"]:
            assert (t[x["i"]] + H < cut) == (t[e["i"]] + H < cut) and x["i"] != e["i"]
            assert abs(x["i"] - e["i"]) <= lm.CTRL_SPAN * 4
            if x["tr"] is not None:
                sg = 1 if e["side"] == "long" else -1
                lv = c[x["i"]] * (1 - sg * e["dist"])
                assert (l[x["tr"]["j"]] <= lv * (1 - lm.THROUGH)) if sg > 0 else (h[x["tr"]["j"]] >= lv * (1 + lm.THROUGH))


def test_a_gap_in_open_interest_resets_the_map_instead_of_booking_the_jump():
    t, o, h, l, c, oi, months = _coin()  # noqa: E741
    oi2 = oi.copy()
    oi2[1000:1100] = np.nan                                                                  # 100 hours missing
    oi2[1100:] *= 5.0                                                                        # and back five times bigger
    ev = lm.coin_events(t, o, h, l, c, oi2, months, np.random.default_rng(1), int(t[-1]))
    big_after = [e for e in ev if 1100 <= e["i"] < 1200]
    assert all(e["ratio"] < 2.0 for e in big_after)                                          # no phantom 4x position stack


def test_cell_statistics_and_the_pass_rule():
    D = pd.DataFrame({"side": ["long"] * 6, "half": ["tu"] * 6, "filled": [True] * 5 + [False],
                      "n_ctrl": [5] * 6, "ctrl_filled": [2] * 6, "day": ["d1", "d1", "d2", "d3", "d4", None],
                      "4h": [0.01, 0.02, 0.0, 0.03, -0.01, np.nan], "c_4h": [0.0, 0.01, 0.0, np.nan, 0.0, np.nan]})
    st = lm.cell_stats(D, "long", "4h", "tu")
    assert st["n_ev"] == 6 and st["n"] == 5 and abs(st["fill"] - 5 / 6) < 1e-12 and abs(st["cfill"] - 12 / 30) < 1e-12
    assert abs(st["net"] - 0.01) < 1e-12 and abs(st["ex"] - np.mean([0.01, 0.01, 0.0, -0.01])) < 1e-12

    def half(net=1e-3, t=2.5, ex=1e-3, ext=2.5):
        return dict(net=net, t=t, ex=ex, ex_t=ext)
    assert lm.passes(dict(tu=half(), ho=half()), 0.01) and not lm.passes(dict(tu=half(), ho=half()), 0.06)
    for kw in (dict(net=-1e-4), dict(t=1.9), dict(ex=-1e-4), dict(ext=1.9)):
        assert not lm.passes(dict(tu=half(**kw), ho=half()), 0.01) and not lm.passes(dict(tu=half(), ho=half(**kw)), 0.01), kw


def test_rows_split_the_halves_at_the_cut_and_average_filled_controls():
    t = np.arange(200, dtype=np.int64) * H
    tr = dict(j=10, fill=1.0, r4h=0.01, r24h=0.0, rbr=0.0, hbr=3)
    ev = [dict(i=5, side="long", dist=0.03, ratio=0.1, tr=tr, ctrl=[dict(i=50, tr=dict(tr, r4h=0.03)), dict(i=60, tr=None)]),
          dict(i=150, side="long", dist=0.03, ratio=0.1, tr=None, ctrl=[])]
    D = lm.rows_from({"X": ev}, {"X": t}, int(t[100]))
    assert D.half.tolist() == ["tu", "ho"] and D.filled.tolist() == [True, False]
    assert abs(D.loc[0, "c_4h"] - lm.nets(dict(tr, r4h=0.03))["4h"]) < 1e-15 and D.loc[0, "ctrl_filled"] == 1


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
