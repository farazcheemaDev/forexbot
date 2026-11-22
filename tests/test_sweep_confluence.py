"""sweep_confluence.py offline: planted sweeps with hand-computed factors, a look-ahead (causality) check, the trade rules, the statistics.
Run as a script: python tests/test_sweep_confluence.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import sweep_confluence as sc  # noqa: E402

N = 420


def flat_market():
    """Every bar: open 100, high 101, low 99, close 100, quote volume 1000 (ATR 2, 168-bar mean 100)."""
    t = pd.date_range("2024-01-01", periods=N, freq="h").to_numpy("datetime64[ns]")
    o, h, l, c, q = (np.full(N, v, float) for v in (100.0, 101.0, 99.0, 100.0, 1000.0))
    return t, o, h, l, c, q, np.zeros(N)


def planted():
    t, o, h, l, c, q, rate = flat_market()
    l[228:276] = np.where(np.arange(228, 276) % 5 == 0, 97.0, 99.0)             # 10 of those 48 bars have a far-away low (outside the touch band)
    # long sweep at 300: the 24 bars before have low 99; this one goes to 98, closes 99.6 (above the level 99 and above its open 99.2)
    o[300], h[300], l[300], c[300], q[300] = 99.2, 99.9, 98.0, 99.6, 9000.0
    # short sweep at 350: the 24 bars before have high 101; this one goes to 102, closes 100.4 (below 101 and below its open 100.8)
    o[350], h[350], l[350], c[350], q[350] = 100.8, 102.0, 100.1, 100.4, 3000.0
    q[288:300], q[338:350] = 5000.0, 4000.0                                     # uneven volume before each sweep: half the prior 24 bars are busy
    rate[:] = 0.0004
    return t, o, h, l, c, q, rate


def test_a_planted_long_sweep_has_the_hand_computed_factors():
    t, o, h, l, c, q, rate = planted()
    F = sc.features(t, o, h, l, c, q, rate)[1]
    assert list(np.flatnonzero(F["ev"])) == [300], np.flatnonzero(F["ev"])                      # exactly one long event
    assert abs(F["depth"][300] - (99.0 - 98.0) / 2.0) < 1e-12                                   # (level - low) / ATR = 0.5
    assert abs(F["vol"][300] - 9000.0 / np.median(q[276:300])) < 1e-12 and abs(np.median(q[276:300]) - 3000.0) < 1e-12   # 12 bars at 1000 and 12 at 5000: 3000
    assert abs(F["loc"][300] - (99.6 - 98.0) / (99.9 - 98.0)) < 1e-12
    sma = (167 * 100.0 + 99.6) / 168
    assert abs(F["trend"][300] - (99.6 / sma - 1)) < 1e-12
    assert F["touch"][300] == sum(1 for i in range(228, 300) if abs(l[i] - 99.0) <= 0.5) - 1 == 61   # 72 prior bars, 10 far away, minus the bar that set the level
    assert abs(F["fund"][300] + 0.0004) < 1e-15                                                 # long: -rate
    assert abs(F["r24"][300] - (99.6 / 100.0 - 1)) < 1e-12


def test_a_planted_short_sweep_mirrors_it():
    t, o, h, l, c, q, rate = planted()
    F = sc.features(t, o, h, l, c, q, rate)[-1]
    assert list(np.flatnonzero(F["ev"])) == [350]
    assert abs(F["depth"][350] - (102.0 - 101.0) / 2.0) < 1e-12
    assert abs(F["vol"][350] - 3000.0 / np.median(q[326:350])) < 1e-12 and abs(np.median(q[326:350]) - 2500.0) < 1e-12
    assert abs(F["loc"][350] - (102.0 - 100.4) / (102.0 - 100.1)) < 1e-12
    sma = (166 * 100.0 + 99.6 + 100.4) / 168                                                    # the 168 bars also hold the long sweep's bar 300 (close 99.6)
    assert abs(F["trend"][350] - (-(100.4 / sma - 1))) < 1e-12                                  # short: side x (c / mean - 1)
    assert abs(F["fund"][350] - 0.0004) < 1e-15                                                 # short: -(-1) x rate


def test_no_feature_at_a_bar_reads_a_later_bar():
    """Recompute on data cut right after bar i, and on data whose FUTURE is scrambled: every factor at i must be identical."""
    t, o, h, l, c, q, rate = planted()
    full = sc.features(t, o, h, l, c, q, rate)
    rng = np.random.default_rng(5)
    for i in [200, 260, 300, 301, 350, 351, 400] + list(rng.integers(200, N - 1, 12)):
        i = int(i)
        cut = sc.features(t[:i + 1], o[:i + 1], h[:i + 1], l[:i + 1], c[:i + 1], q[:i + 1], rate[:i + 1])
        o2, h2, l2, c2, q2 = (a.copy() for a in (o, h, l, c, q))
        for a in (o2, h2, l2, c2, q2):
            a[i + 1:] = a[i + 1:] * rng.uniform(0.5, 2.0, len(a) - i - 1)                       # the future, scrambled
        wild = sc.features(t, o2, np.maximum(h2, np.maximum(o2, c2)), np.minimum(l2, np.minimum(o2, c2)), c2, q2, rate)
        for side in (1, -1):
            for k, v in cut[side].items():
                for other in (v[i], wild[side][k][i]):
                    assert (np.isnan(full[side][k][i]) and np.isnan(other)) or full[side][k][i] == other, (side, k, i, full[side][k][i], other)


def test_a_gap_in_the_bars_blocks_an_event():
    t, o, h, l, c, q, rate = planted()
    t = t.copy()
    t[150:] = t[150:] + np.timedelta64(5, "h")                                                  # a 5-hour hole inside the 168 bars before bar 300
    assert not sc.features(t, o, h, l, c, q, rate)[1]["ev"][300]


def test_the_trade_rules_stop_target_gap_and_expiry():
    n = 40
    o, h, l, c = (np.full(n, 100.0) for _ in range(4))
    h[:], l[:] = 100.5, 99.5
    fc = np.zeros(n)
    i = 5
    # long, stopped: bar 6 trades down to 98.5 with a stop at 99 -> exits at the stop, -1.00% gross
    l2 = l.copy(); l2[6] = 98.5
    net, gross = sc.trade(i, 1, 99.0, None, o, h, l2, c, fc)
    assert abs(gross + 0.01) < 1e-12 and abs(net - (-0.01 - sc.FEE)) < 1e-12
    # entered at 100 on bar 6, then bar 7 gaps open at 98.0, under the stop -> exits at the open, -2.00%
    o3, l3 = o.copy(), l.copy(); o3[7], l3[7] = 98.0, 97.5
    assert abs(sc.trade(i, 1, 99.0, None, o3, h, l3, c, fc)[1] + 0.02) < 1e-12
    # the entry bar itself opens under the stop: there is no trade
    o3b = o.copy(); o3b[6] = 98.0
    assert sc.trade(i, 1, 99.0, None, o3b, h, l, c, fc) is None
    # a target: +2% reached on bar 7 -> exactly +2% (stop untouched)
    h4 = h.copy(); h4[7] = 102.5
    assert abs(sc.trade(i, 1, 99.0, 0.02, o, h4, l, c, fc)[1] - 0.02) < 1e-12
    assert abs(sc.trade(i, 1, 99.0, None, o, h4, l, c, fc)[1]) < 1e-12                          # no target in T24: the move is ignored, exit at the close (100) after 24 bars
    # expiry: nothing touched -> the close HOLD bars after the signal bar
    c5 = c.copy(); c5[i + sc.HOLD] = 101.0
    assert abs(sc.trade(i, 1, 99.0, None, o, h, l, c5, fc)[1] - 0.01) < 1e-12
    # a stop at or above the entry (the open gapped through it) is no trade; the short mirror
    assert sc.trade(i, 1, 100.0, None, o, h, l, c, fc) is None
    assert sc.trade(i, -1, 100.0, None, o, h, l, c, fc) is None
    h6 = h.copy(); h6[6] = 101.5
    assert abs(sc.trade(i, -1, 101.0, None, o, h6, l, c, fc)[1] + 0.01) < 1e-12
    # funding is charged to the side that pays: fc rises 0.5 over the hold on a price of 100 -> longs pay 0.5%, shorts receive
    fc7 = np.zeros(n); fc7[i + 2:] = 0.5
    assert abs(sc.trade(i, 1, 99.0, None, o, h, l, c, fc7)[1] + 0.005) < 1e-12
    assert abs(sc.trade(i, -1, 101.0, None, o, h, l, c, fc7)[1] - 0.005) < 1e-12
    # the same on the stop path and the target path (funding accrued from the entry to the exit bar), and the fee on all three exits
    fc8 = np.zeros(n); fc8[7:] = 0.5
    l8 = l.copy(); l8[7] = 98.5
    net, gross = sc.trade(i, 1, 99.0, None, o, h, l8, c, fc8)
    assert abs(gross - (-0.01 - 0.005)) < 1e-12 and abs(net - (gross - sc.FEE)) < 1e-12
    net, gross = sc.trade(i, 1, 99.0, 0.02, o, h4, l, c, fc8)
    assert abs(gross - (0.02 - 0.005)) < 1e-12 and abs(net - (gross - sc.FEE)) < 1e-12
    net, gross = sc.trade(i, 1, 99.0, None, o, h, l, c5, fc8)
    assert abs(gross - (0.01 - 0.005)) < 1e-12 and abs(net - (gross - sc.FEE)) < 1e-12


def test_cluster_robust_spread_matches_an_independent_calculation():
    rng = np.random.default_rng(2)
    day = np.repeat(np.arange(8), 6)
    flag = rng.random(len(day)) < 0.5
    y = 0.01 * flag + rng.normal(0, 0.02, len(day)) + np.repeat(rng.normal(0, 0.02, 8), 6)
    b, t = sc.spread_t(y, flag, day)
    X = np.c_[np.ones(len(y)), flag.astype(float)]
    beta = np.linalg.solve(X.T @ X, X.T @ y)
    e = y - X @ beta
    meat = np.zeros((2, 2))
    for g in range(8):
        s = (X[day == g] * e[day == g, None]).sum(0)
        meat += np.outer(s, s)
    bread = np.linalg.inv(X.T @ X)
    V = bread @ meat @ bread * (8 / 7)
    assert abs(b - beta[1]) < 1e-12 and abs(t - beta[1] / np.sqrt(V[1, 1])) < 1e-9
    # a planted effect is found and a null one is not
    big = 0.02 * flag + rng.normal(0, 0.005, len(day))
    assert sc.spread_t(big, flag, day)[1] > 4
    assert abs(sc.spread_t(rng.normal(0, 0.02, len(day)), flag, day)[1]) < 3


def test_holm_and_the_day_t():
    adj = sc.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert abs(adj["a"] - 0.03) < 1e-12 and abs(adj["c"] - 0.06) < 1e-12 and abs(adj["b"] - 0.06) < 1e-12      # 3x.01, max(2x.03, .03), max(1x.04, .06)
    x = pd.Series([1.0, 1.0, 1.0, 1.0, 5.0, 3.0])                                             # one busy day (4 trades) and two single-trade days
    d = pd.Series([0, 0, 0, 0, 1, 2])
    y, m = x.to_numpy(), x.mean()
    S = [(y[:4] - m).sum(), (y[4:5] - m).sum(), (y[5:] - m).sum()]
    expect = m / (np.sqrt(3 / 2 * sum(v * v for v in S)) / 6)
    assert abs(sc.t_by_day(x, d) - expect) < 1e-12 and m > 0                                    # the per-TRADE mean with day-clustered errors (the day-mean t would be 3.0/1.15)
    assert sc.t_by_day(pd.Series([-1.0, -1.0, -1.0, -1.0, 1.0, 0.0]), d) < 0                    # the sign of the t is the sign of the printed mean
    assert abs(sc.t_by_day(x, d) - 3.0 / (2.0 / np.sqrt(3))) > 0.1                              # and it is not the average-of-day-means t
    assert abs(sc.p_one_sided(0.0) - 0.5) < 1e-12 and sc.p_one_sided(4.0) < 1e-4


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
