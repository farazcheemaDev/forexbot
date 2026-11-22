"""Offline tests for backtest/rsi_ratio.py - the RSI recursion, the signal flags (and their causality), the volume rule, the warm-up mask,
the break-even arithmetic, one planted trade through process() and the summary helpers. Synthetic data only.

    python tests/test_rsi_ratio.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import candle_manage as cm  # noqa: E402
from backtest import candle_scan as cs  # noqa: E402
from backtest import rsi_ratio as rr  # noqa: E402


def wilder_rsi_loop(c):
    """The textbook recursion written out by hand."""
    n = len(c)
    up = dn = 0.0
    out = np.full(n, 100.0)
    for i in range(1, n):
        d = c[i] - c[i - 1]
        up = (1 / 14) * max(d, 0.0) + (13 / 14) * up
        dn = (1 / 14) * max(-d, 0.0) + (13 / 14) * dn
        out[i] = 100 - 100 / (1 + up / dn) if dn > 0 else 100.0
    return out


def cost_of(k, rf, side):
    """cm.cost_r for one trade (it returns a scalar on the short side)."""
    return float(np.atleast_1d(cm.cost_r(np.array([k]), rf, side, 1))[0])


def planted_path(n=320, fall_bars=14, seed=0):
    """Flat oscillation, then a steady fall that pushes RSI under 30 once, then flat again. ATR comes out as exactly 1.0 on every bar
    before the planted future: every bar is 1.0 wide, opens at the previous close and keeps its open and close inside its range."""
    step = np.tile([0.3, -0.3], n)[:n]                                               # RSI sits near 50 (seed kept for a stable signature)
    step[120:120 + fall_bars] = -0.35
    step[120 + fall_bars:] = np.tile([0.3, -0.3], n)[: n - 120 - fall_bars]
    c = 100.0 + np.cumsum(step)
    o = np.r_[c[0], c[:-1]]
    lo = np.minimum(o, c) - 0.1
    hi = lo + 1.0
    t = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame({"time": t, "o": o, "h": hi, "l": lo, "c": c, "v": np.full(n, 1000.0)})


def test_rsi_matches_the_hand_written_recursion():
    rng = np.random.default_rng(3)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 400)))
    assert np.allclose(rr.rsi14(c), wilder_rsi_loop(c), atol=1e-9)
    assert abs(rr.rsi14(np.arange(1.0, 60.0))[-1] - 100.0) < 1e-9                  # only gains: 100
    assert 40 < rr.rsi14(100 + np.tile([0.5, -0.5], 100))[-1] < 60               # alternating: about 50


def test_cross_flags_fire_on_the_crossing_bar_only():
    r = np.array([50, 40, 31, 29, 28, 35, 29, 60, 71, 72, 69, 71, 76, 79, 81.0])
    f = rr.rsi_flags(r, np.ones(len(r)))
    assert np.flatnonzero(f["lo30"]).tolist() == [3, 6]                              # 31 -> 29 and 35 -> 29; staying under is not a new cross
    assert np.flatnonzero(f["lo25"]).tolist() == [] and np.flatnonzero(f["lo20"]).tolist() == []
    assert np.flatnonzero(f["hi70"]).tolist() == [8, 11]                             # 60 -> 71, 69 -> 71
    assert np.flatnonzero(f["hi75"]).tolist() == [12] and np.flatnonzero(f["hi80"]).tolist() == [14]
    e = rr.rsi_flags(np.array([30.0, 30.0, 29.9]), np.ones(3))                       # exactly 30 then under: crosses; exactly 30 stays
    assert np.flatnonzero(e["lo30"]).tolist() == [2]
    assert np.flatnonzero(rr.rsi_flags(np.array([70.0, 70.0, 70.1]), np.ones(3))["hi70"]).tolist() == [2]


def test_flags_are_causal():
    d = planted_path(seed=4)
    r_full = rr.rsi14(d["c"].to_numpy())
    full = rr.rsi_flags(r_full, d["v"].to_numpy())
    for cut in (130, 140, 200):
        part = rr.rsi_flags(rr.rsi14(d["c"].to_numpy()[:cut]), d["v"].to_numpy()[:cut])
        for k in full:
            assert np.array_equal(full[k][:cut], part[k]), (k, cut)                  # later bars never change an earlier flag


def test_the_volume_rule_uses_the_twenty_bars_before_and_a_strict_threshold():
    n = 60
    r = np.full(n, 50.0)
    r[40] = 25.0
    r[41] = 15.0                                                                     # crosses lo20 at bar 41
    v = np.full(n, 100.0)
    v[41] = 301.0                                                                    # just over 3x the mean of the 20 before
    assert rr.rsi_flags(r, v)["cap20"][41]
    v[41] = 300.0                                                                    # exactly 3x: not over
    assert not rr.rsi_flags(r, v)["cap20"][41]
    v[41] = 301.0
    v[21:41] = 101.0                                                                 # a higher volume history raises the bar to 303
    assert not rr.rsi_flags(r, v)["cap20"][41]
    v[41] = 400.0
    assert rr.rsi_flags(r, v)["cap20"][41]


def test_warm_mask_needs_w_contiguous_bars_behind():
    t = pd.date_range("2024-01-01", periods=100, freq="h").to_numpy("datetime64[ns]")
    step = 3600 * 10 ** 9
    w = rr.warm_mask(t, step, 10)
    assert not w[:10].any() and w[10:].all()
    t2 = np.r_[t[:50], t[60:]]                                                      # a hole of ten hours after bar 49
    w2 = rr.warm_mask(t2, step, 10)
    assert w2[49] and not w2[50] and not w2[59] and w2[60]


def test_break_even_share_is_the_arithmetic_of_the_bracket():
    assert abs(rr.breakeven(2.0, 0.0) - 1 / 3) < 1e-12 and abs(rr.breakeven(1.0, 0.0) - 0.5) < 1e-12
    assert abs(rr.breakeven(1.0, 0.12) - 0.56) < 1e-12 and abs(rr.breakeven(0.5, 0.0) - 2 / 3) < 1e-12
    p = rr.breakeven(2.0, 0.12)
    assert abs(p * 2.0 - (1 - p) - 0.12) < 1e-12                                    # expectancy is exactly the cost at that share


def test_one_planted_trade_goes_through_process_with_the_right_net_r():
    d = planted_path(seed=5)
    r = rr.rsi14(d["c"].to_numpy())
    fl = rr.rsi_flags(r, d["v"].to_numpy())
    warm = rr.warm_mask(d["time"].to_numpy("datetime64[ns]"), 3600 * 10 ** 9, rr.WARM)
    idx = np.flatnonzero(fl["lo30"] & warm)
    assert len(idx) >= 1 and not (fl["hi70"] & warm).any() and 119 < idx[0] < 135     # the wiggle back up re-crosses later; the planted future removes it
    E = int(idx[0])
    atr = cm.atr14(d["h"].to_numpy(), d["l"].to_numpy(), d["c"].to_numpy())
    assert abs(atr[E] - 1.0) < 1e-9
    e = d["c"].iloc[E]
    o2, h2, l2, c2 = (d[k].to_numpy().copy() for k in ("o", "h", "l", "c"))
    # E+1: inside; E+2: up to e+1.2 (a short's 1-ATR stop at e+1 is hit, a long's target at e+2 is not); E+3: spike to e+2.5 (long target hit)
    plan = {E + 1: (e, e + 0.8, e - 0.3, e + 0.2), E + 2: (e + 0.2, e + 1.2, e + 0.1, e + 0.9), E + 3: (e + 1.0, e + 2.5, e + 0.9, e + 2.2)}
    for j, (oo, hh, ll, cc) in plan.items():
        o2[j], h2[j], l2[j], c2[j] = oo, hh, ll, cc
    o2[E + 4:] = e + 2.2
    c2[E + 4:] = e + 2.2
    h2[E + 4:] = e + 2.7
    l2[E + 4:] = e + 1.7
    d2 = pd.DataFrame({"time": d["time"], "o": o2, "h": h2, "l": l2, "c": c2, "v": d["v"]})
    bi = rr.BRACKETS.index((1.0, 2.0))
    cells, acc = {}, rr.new_acc()
    rr.process(d2, np.array(["2024-01", "2024-02"], dtype="datetime64[M]"), 1, cells, acc)
    risk_frac = 1.0 / e
    long_net = cells[(1, bi, 1, "lo30")][0][2]
    assert len(long_net) == 1
    assert abs(long_net[0] - (2.0 - cost_of(3, risk_frac, 1))) < 1e-9          # target at +2R in the third bar
    short_net = cells[(1, bi, -1, "lo30")][0][2]
    assert len(short_net) == 1
    assert abs(short_net[0] - (-1.0 - cost_of(2, risk_frac, -1))) < 1e-9       # stop at +1 ATR in the second bar
    wide = rr.BRACKETS.index((4.0, 0.5))                                                           # a 4-ATR stop is never touched; +0.5R target = e+2
    assert abs(cells[(1, wide, 1, "lo30")][0][2][0] - (0.5 - cost_of(3, 4.0 / e, 1))) < 1e-9
    assert not any(k[3] == "hi70" for k in cells)
    # the control accumulators saw every valid entry at this bracket and counted the planted long as a win
    assert acc["cnt"][(1, bi, 1)].sum() > 100 and acc["win"][(1, bi, 1)].sum() >= 1
    assert acc["sum"][(1, bi, 1)].sum() != 0.0


def test_the_non_textbook_side_is_labelled_a_mirror():
    d = planted_path(seed=6)
    cells, acc = {}, rr.new_acc()
    rr.process(d, np.array(["2024-01", "2024-02"], dtype="datetime64[M]"), 1, cells, acc)
    sides = {(k[3], k[2]) for k in cells}
    assert ("lo30", 1) in sides and ("lo30", -1) in sides                           # both sides are simulated for every flag
    assert rr.TEXT["lo30"] == 1 and rr.TEXT["hi75"] == -1 and rr.TEXT["cap20"] == 1


def test_summary_counts_and_excess():
    def r(bi, side, tun, hon, xt, xh, win=0.4, bw=0.38, flag="lo30", tf=1, n=200):
        mk = lambda net, x: dict(n=n, days=60, net=net, t=1.0, exc=x, t_exc=0.5, win=win, bw=bw, pt=net - 0.2)
        stp, tgt = rr.BRACKETS[bi]
        return dict(tf=tf, bi=bi, stop=stp, tgt=tgt, flag=flag, side=side, text=rr.TEXT[flag] == side, tu=mk(tun, xt), ho=mk(hon, xh))
    rows = [r(0, 1, 0.1, 0.2, 0.01, 0.03), r(0, 1, -0.1, 0.2, -0.03, 0.01, flag="lo25"), r(0, 1, 0.5, 0.5, 0.2, 0.2, flag="cap20"),
            r(0, -1, 0.3, 0.3, 0.1, 0.1, flag="lo30"), r(1, 1, 0.1, 0.1, 0.0, 0.0)]
    ctrl = {(1, bi, sd): dict(cost=0.1 * (bi + 1), tu=0, ho=0, win=0, n=1) for bi in range(len(rr.BRACKETS)) for sd in (1, -1)}
    bs = rr.bracket_summary(rows, ctrl)
    v = bs[(0, 1)]
    assert v["cells"] == 2 and v["both"] == 1                                       # cap20 excluded; one of the two is positive on both halves
    assert abs(v["tu"] - 0.0) < 1e-12 and abs(v["ho"] - 0.2) < 1e-12 and abs(v["xtu"] + 0.01) < 1e-12 and abs(v["xho"] - 0.02) < 1e-12
    assert abs(v["ptu"] + 0.2) < 1e-12 and abs(v["pho"] - 0.0) < 1e-12                  # per-trade means are carried through (net - 0.2 in this fixture)
    assert abs(v["need"] - rr.breakeven(rr.BRACKETS[0][1], 0.1)) < 1e-12 and abs(v["win"] - 0.4) < 1e-12 and abs(v["bw"] - 0.38) < 1e-12
    assert (0, -1) not in bs                                                       # lo30 SHORT is the mirror side: no textbook cells for it here


def test_the_control_accumulators_equal_an_independent_recount():
    d = planted_path(seed=7)
    em = np.array(["2024-01", "2024-02"], dtype="datetime64[M]")
    cells, acc = {}, rr.new_acc()
    rr.process(d, em, 1, cells, acc)
    t = d["time"].to_numpy("datetime64[ns]")
    o, h, l, c = (d[k].to_numpy(float) for k in ("o", "h", "l", "c"))
    atr = cm.atr14(h, l, c)
    step = 3600 * 10 ** 9
    ok = (cs.valid_mask(t, step, rr.CAP) & rr.warm_mask(t, step, rr.WARM) & np.isin(t.astype("datetime64[M]"), em)
          & (o > 0) & (c > 0) & np.isfinite(atr) & (atr > 0))
    wins, small_wins = 0, 0
    for stp, tgt in ((1.0, 2.0), (4.0, 0.5)):
        bi = rr.BRACKETS.index((stp, tgt))
        E = np.flatnonzero(ok)
        E = E[~(stp * atr[E] / o[E + 1] < cm.MIN_RISK)]
        for side in (1, -1):
            rg, kx, rf = cm.simulate(o, h, l, c, atr, E, side, dict(stop=stp, be=None, trail=None, target=tgt, cap=rr.CAP))
            cost = np.broadcast_to(cm.cost_r(kx, rf, side, 1), rg.shape)
            net = rg - cost
            kk = (1, bi, side)
            assert acc["cnt"][kk].sum() == len(E)
            assert abs(acc["sum"][kk].sum() - net.sum()) < 1e-9
            assert acc["win"][kk].sum() == (net > 0).sum()
            assert abs(acc["cost"][kk].sum() - cost.sum()) < 1e-9
            wins += int((net > 0).sum())
            small_wins += int(((net > 0) & (net <= 0.5)).sum())
    assert len(E) > 100 and wins > 0 and small_wins > 0                               # a win worth less than half an R exists, so a wrong win rule changes the count


def test_a_second_signal_inside_an_open_trade_is_not_taken():
    d = planted_path(seed=8)
    r = rr.rsi14(d["c"].to_numpy())
    f = rr.rsi_flags(r, d["v"].to_numpy())["lo30"]
    warm = rr.warm_mask(d["time"].to_numpy("datetime64[ns]"), 3600 * 10 ** 9, rr.WARM)
    sig = np.flatnonzero(f & warm)
    assert len(sig) >= 2 and sig[1] - sig[0] < rr.CAP                              # two signals closer than the 24-bar holding limit
    cells, acc = {}, rr.new_acc()
    rr.process(d, np.array(["2024-01", "2024-02"], dtype="datetime64[M]"), 1, cells, acc)
    bi = rr.BRACKETS.index((4.0, 4.0))                                              # neither the stop nor the target is touched: the trade runs to the cap
    n_first = sum(len(p[2]) for p in cells[(1, bi, 1, "lo30")])
    assert n_first == 1, n_first


def test_the_minimum_risk_filter_drops_entries_with_a_tiny_stop():
    d = planted_path(seed=9)
    d2 = d.copy()
    for k in ("o", "h", "l", "c"):
        d2[k] = d[k] + 900.0                                                          # price near 1000, ATR still 1.0: 0.5 ATR is 0.05% of price
    em = np.array(["2024-01", "2024-02"], dtype="datetime64[M]")
    cells, acc = {}, rr.new_acc()
    rr.process(d2, em, 1, cells, acc)
    b_small, b_ok = rr.BRACKETS.index((0.5, 1.0)), rr.BRACKETS.index((4.0, 1.0))
    assert acc["cnt"][(1, b_small, 1)].sum() == 0 and not any(k[1] == b_small for k in cells)    # 0.05% < 0.2%
    assert acc["cnt"][(1, b_ok, 1)].sum() > 100                                                   # 4 ATR = 0.4% is kept


def test_the_control_win_share_is_taken_only_over_keys_the_trade_set_can_compare():
    day = np.array([1, 2, 3, 4])
    key = np.array([0, 1, 2, 3])
    net = np.array([0.5, -1.0, 0.5, -1.0])
    base = np.array([0.0, 0.1, np.nan, 0.2])
    bwr = np.array([0.3, 0.4, np.nan, 0.5])
    s = rr.half(day, net, key, base, bwr, np.ones(4, bool))
    assert s is not None and s["n"] == 3 and abs(s["bw"] - np.mean([0.3, 0.4, 0.5])) < 1e-12
    assert abs(s["pt"] - np.mean([0.5, -1.0, -1.0])) < 1e-12                          # the per-trade mean covers the same three trades, one vote each trade


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
