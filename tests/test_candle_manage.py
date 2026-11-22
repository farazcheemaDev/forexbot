"""Offline tests for backtest/candle_manage.py - the trade management (stops, gaps, targets, breakeven, trail, time cap), the
cost in R, the one-position rule, the baseline wiring. No network, no archive.

    python tests/test_candle_manage.py
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

TREND, SCALP = cm.MGMT["trend"], cm.MGMT["scalp"]


def flat(n=30, price=100.0):
    return [np.full(n, price), np.full(n, price + 0.5), np.full(n, price - 0.5), np.full(n, price)]     # o, h, l, c


def run(bars, m, side=1, E=0):
    o, h, l, c = bars
    atr = np.ones(len(o))
    rg, k, rf = cm.simulate(o, h, l, c, atr, [E], side, m)
    return float(rg[0]), int(k[0]), float(rf[0])


def test_atr_is_the_mean_true_range_of_the_14_bars_up_to_the_bar():
    h = np.array([2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 20.0])
    l = h - 2
    c = h - 1
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, 15)]
    a = cm.atr14(h, l, c)
    assert np.isnan(a[12])
    assert abs(a[13] - np.mean(tr[0:14])) < 1e-12 and abs(a[14] - np.mean(tr[1:15])) < 1e-12
    assert tr[1] == 3.0 and tr[14] == 5.0                                       # the test data has gaps, so true range > high - low


def test_a_stop_fills_at_the_stop_and_a_gap_through_it_at_the_open():
    o, h, l, c = flat()
    l[3] = 97.5                                                    # 1R = 2 (2 ATR): the stop is 98
    r, k, rf = run((o, h, l, c), TREND)
    assert abs(r + 1.0) < 1e-12 and k == 3 and abs(rf - 0.02) < 1e-12
    o2, h2, l2, c2 = flat()
    o2[3], h2[3], l2[3], c2[3] = 97.0, 97.5, 96.5, 97.2             # opens beyond the stop: filled at 97, -1.5R
    r, k, _ = run((o2, h2, l2, c2), TREND)
    assert abs(r + 1.5) < 1e-12 and k == 3


def test_target_stop_and_the_bar_that_touches_both():
    o, h, l, c = flat()
    h[2] = 102.4                                                   # scalp: 1R = 1, stop 99, target 102
    r, k, _ = run((o, h, l, c), SCALP)
    assert abs(r - 2.0) < 1e-12 and k == 2
    o, h, l, c = flat()
    h[2], l[2] = 102.4, 98.9                                       # both in one bar: the stop counts
    r, k, _ = run((o, h, l, c), SCALP)
    assert abs(r + 1.0) < 1e-12 and k == 2
    o, h, l, c = flat()
    o[2], h[2], l[2], c[2] = 103.0, 103.5, 102.8, 103.2            # a gap above the target fills at the open
    r, _, _ = run((o, h, l, c), SCALP)
    assert abs(r - 3.0) < 1e-12


def test_breakeven_applies_from_the_next_bar_and_not_inside_the_bar_that_reached_it():
    o, h, l, c = flat()
    h[1] = 106.5                                                   # trend: +3R is 106; reached on the entry bar (low stays above 98)
    l[2] = 99.8                                                    # next bar dips under the entry price: the breakeven stop at 100 is hit
    o[2] = 100.2
    r, k, _ = run((o, h, l, c), TREND)
    assert abs(r) < 1e-12 and k == 2
    o, h, l, c = flat()
    h[1], l[1] = 106.5, 97.9                                       # the same bar also pierces the ORIGINAL stop: -1R, no breakeven yet
    r, k, _ = run((o, h, l, c), TREND)
    assert abs(r + 1.0) < 1e-12 and k == 1


def test_the_trailing_stop_follows_the_best_price_from_the_next_bar():
    m = dict(stop=2.0, be=None, trail=2.0, target=None, cap=20)
    o, h, l, c = flat()
    h[1] = 110.0                                                   # best 110 -> trail 108 from the next bar; this bar's low is fine
    o[2], l[2] = 109.0, 107.5
    r, k, _ = run((o, h, l, c), m)
    assert abs(r - 4.0) < 1e-12 and k == 2                          # out at 108 = +4R


def test_the_time_cap_exits_at_the_close_of_the_last_bar():
    o, h, l, c = flat()
    h[:], l[:] = 100.3, 99.7
    c[:] = 100.1 + 0.01 * np.arange(30)
    r, k, _ = run((o, h, l, c), SCALP)
    assert k == 24 and abs(r - (c[24] - 100.0) / 1.0) < 1e-12


def test_a_short_is_the_mirror_of_a_long():
    rng = np.random.default_rng(7)
    n = 800
    cl = 100 * np.exp(np.cumsum(rng.normal(0.002, 0.012, n)))
    op = np.r_[cl[0], cl[:-1]] * np.exp(rng.normal(0, 0.006, n))
    hi = np.maximum(op, cl) * np.exp(np.abs(rng.normal(0, 0.006, n)))
    lo = np.minimum(op, cl) * np.exp(-np.abs(rng.normal(0, 0.006, n)))
    atr = cm.atr14(hi, lo, cl)
    for m in (TREND, SCALP):
        E = np.arange(20, n - m["cap"] - 2)
        a = cm.simulate(op, hi, lo, cl, atr, E, 1, m)
        K = 2 * 400.0
        b = cm.simulate(K - op, K - lo, K - hi, K - cl, atr, E, -1, m)        # prices reflected around a point
        assert np.allclose(a[0], b[0], atol=1e-9) and np.array_equal(a[1], b[1])
        assert len(set(np.round(a[0], 3).tolist())) > 50 and a[0].max() > 2 and a[0].min() < -0.9      # the comparison is not trivial


def test_costs_in_r_charge_funding_on_longs_only():
    k = np.array([10, 3])
    rf = np.array([0.004, 0.02])
    assert np.allclose(cm.cost_r(k, rf, 1, 4), (cs.FEE + cs.FUND_H * k * 4) / rf)
    assert np.allclose(cm.cost_r(k, rf, -1, 4), cs.FEE / rf)


def test_one_position_per_coin_by_exit_bar():
    ex = [0] * 12
    ex[2], ex[3], ex[4], ex[9] = 5, 6, 7, 10
    assert cm.pick_trades(np.array([2, 3, 4, 9]), ex).tolist() == [2, 9]
    assert cm.pick_trades(np.array([2, 5, 9]), ex).tolist() == [2, 5, 9]            # a signal ON the exit bar is allowed


def test_half_stats_measures_the_excess_at_the_trades_day_and_slot():
    days = np.arange(120)
    key = days * 2 + 1
    base = np.zeros(240)
    base[1::2] = 0.3                                              # slot 1 earns +0.3R more than slot 0
    net = 0.3 + np.random.default_rng(2).normal(0, 0.05, 120)
    s = cm.half_stats(days, net, key, base, np.ones(120, bool))
    assert abs(s["exc"]) < 0.03 and abs(s["t_exc"]) < 3 and abs(s["net"] - 0.3) < 0.03 and s["t"] > 20
    s2 = cm.half_stats(days, net - 1.0, key, base, np.ones(120, bool))
    assert s2["exc"] < -0.9 and s2["t_exc"] < -20 and s2["net"] < 0 and s2["t"] < 0       # the sign of t is the sign of the mean
    base2 = base.copy()
    base2[key[5]] = np.nan                                         # a day-slot with no random entries cannot be a control: the trade drops out
    s3 = cm.half_stats(days, net, key, base2, np.ones(120, bool))
    assert s3["n"] == 119 and np.isfinite(s3["exc"]) and np.isfinite(s3["t_exc"])


def plant(n=2000, rng_half=0.5):
    t = np.datetime64("2024-01-01T00", "ns") + np.arange(n) * np.timedelta64(1, "h")
    o, c = np.full(n, 100.0), np.full(n, 100.0)
    h, l = np.full(n, 100.0 + rng_half), np.full(n, 100.0 - rng_half)
    return t, o, h, l, c


def test_end_to_end_numbers_membership_baseline_and_the_minimum_risk_filter():
    t, o, h, l, c = plant()
    for k in (300, 1000):                                          # a bullish engulfing in January and one in February
        o[k - 1], h[k - 1], l[k - 1], c[k - 1] = 100.0, 100.1, 98.9, 99.0
        o[k], h[k], l[k], c[k] = 98.9, 100.3, 98.8, 100.2
        o[k + 1], h[k + 1], l[k + 1], c[k + 1] = 100.0, 102.2, 99.9, 102.0       # the next bar runs up through +2R
    d = pd.DataFrame(dict(time=t, o=o, h=h, l=l, c=c))
    cells, bs, bc = {}, {}, {}
    for tfh in cs.TFS.values():
        for mn in cm.MGMT:
            for sd in (1, -1):
                bs[(tfh, mn, sd)] = np.zeros(cs.ND * cs.n_slots(tfh))
                bc[(tfh, mn, sd)] = np.zeros(cs.ND * cs.n_slots(tfh))
    cm.process(d, np.array(["2024-02"], dtype="datetime64[M]"), 1, cells, bs, bc)
    # ATR at the signal bar = (12 flat ranges of 1.0 + 1.2 + 1.5) / 14 = 1.05, so 1R = 1.05 and the target is +2.1
    day, key, net = cells[(1, "scalp", 1, "BULL_ENGULF")][0]
    assert len(net) == 1                                           # the January pattern is not traded
    expect = 2.0 - (cs.FEE + cs.FUND_H * 1 * 1) / (1.05 / 100.0)
    assert abs(net[0] - expect) < 1e-9
    d_feb11 = int((np.datetime64("2024-02-11", "D") - cs.D0) / np.timedelta64(1, "D"))
    assert key[0] == d_feb11 * 24 + 17 and bc[(1, "scalp", 1)][key[0]] >= 1          # entered in slot 17, and the baseline is kept per slot
    short = cells[(1, "scalp", -1, "BULL_ENGULF")][0][2]
    assert abs(short[0] - (-1.0 - cs.FEE / (1.05 / 100.0))) < 1e-9              # the short is stopped in the same bar: -1R less the fee
    assert int(bc[(1, "scalp", 1)].sum()) == 29 * 24                          # exactly February's 696 bars are in the baseline
    first_feb = int((np.datetime64("2024-02-01", "D") - cs.D0) / np.timedelta64(1, "D"))
    assert bc[(1, "scalp", 1)].reshape(cs.ND, 24)[:first_feb].sum() == 0       # and nothing from January
    # a market too quiet to carry a 0.2% stop is skipped entirely
    t, o, h, l, c = plant(rng_half=0.01)
    cells2, bs2, bc2 = {}, {k: np.zeros_like(v) for k, v in bs.items()}, {k: np.zeros_like(v) for k, v in bc.items()}
    cm.process(pd.DataFrame(dict(time=t, o=o, h=h, l=l, c=c)), np.array(["2024-02"], dtype="datetime64[M]"), 1, cells2, bs2, bc2)
    assert all(v.sum() == 0 for v in bc2.values())


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
