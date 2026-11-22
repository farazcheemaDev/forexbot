"""Offline tests for backtest/candle_scan.py - the pattern definitions, the trade timing, the one-position rule, the date-matched
control, the cluster statistics and the pass rule. No network, no archive.

    python tests/test_candle_scan.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import candle_scan as cs  # noqa: E402


def bars(rows, warm=15):
    """Flat warm-up bars (o = c = 100) followed by the given (o, h, l, c) rows."""
    flat = [(100.0, 100.5, 99.5, 100.0)] * warm
    a = np.array(flat + list(rows), float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def hits(fl, name):
    return np.flatnonzero(fl[name]).tolist()


def test_bullish_engulfing_needs_a_red_bar_before_it():
    o, h, l, c = bars([(100.0, 100.1, 98.9, 99.0), (98.9, 100.3, 98.8, 100.2)])
    assert hits(cs.pattern_flags(o, h, l, c), "BULL_ENGULF") == [16]
    o, h, l, c = bars([(100.0, 100.6, 99.9, 100.5), (99.9, 101.1, 99.8, 101.0)])      # a bigger green bar after a GREEN one
    assert hits(cs.pattern_flags(o, h, l, c), "BULL_ENGULF") == []
    o, h, l, c = bars([(100.0, 100.6, 99.9, 100.5), (100.6, 100.7, 98.9, 99.0)])      # and the bearish mirror
    assert hits(cs.pattern_flags(o, h, l, c), "BEAR_ENGULF") == [16]


def test_hammer_needs_a_decline_and_hanging_man_a_rise():
    i = np.arange(15)
    cd = 120 - 1.5 * i
    down = [(x + 1.0, x + 1.1, x - 0.1, x) for x in cd] + [(98.9, 99.2, 95.0, 99.1)]
    o, h, l, c = (np.array(v, float) for v in zip(*down))
    fl = cs.pattern_flags(o, h, l, c)
    assert hits(fl, "HAMMER") == [15] and hits(fl, "HANGING_MAN") == []
    cu = 100 + 1.5 * i
    upr = [(x - 1.0, x + 0.1, x - 1.1, x) for x in cu] + [(121.1, 121.4, 117.0, 121.3)]
    o, h, l, c = (np.array(v, float) for v in zip(*upr))
    fl = cs.pattern_flags(o, h, l, c)
    assert hits(fl, "HANGING_MAN") == [15] and hits(fl, "HAMMER") == []


def test_morning_star_and_three_white_soldiers_need_every_leg():
    o, h, l, c = bars([(100.0, 100.1, 97.9, 98.0), (97.8, 98.0, 97.5, 97.7), (97.8, 100.1, 97.7, 100.0)])
    assert hits(cs.pattern_flags(o, h, l, c), "MORNING_STAR") == [17]
    o, h, l, c = bars([(100.0, 100.1, 97.9, 98.0), (98.4, 98.6, 98.2, 98.5), (97.8, 100.1, 97.7, 100.0)])   # the star sits above the first close
    assert hits(cs.pattern_flags(o, h, l, c), "MORNING_STAR") == []
    o, h, l, c = bars([(100.0, 101.1, 99.9, 101.0), (100.5, 102.1, 100.4, 102.0), (101.5, 103.1, 101.4, 103.0)])
    assert hits(cs.pattern_flags(o, h, l, c), "THREE_WHITE") == [17]
    o, h, l, c = bars([(100.0, 101.1, 99.9, 101.0), (100.0, 101.0, 99.95, 100.9), (100.5, 103.1, 100.4, 103.0)])   # the middle bar closes below the first
    assert hits(cs.pattern_flags(o, h, l, c), "THREE_WHITE") == []


def test_flags_read_only_the_bars_up_to_the_signal():
    rng = np.random.default_rng(3)
    n = 400
    cl = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    op = np.r_[cl[0], cl[:-1]] * np.exp(rng.normal(0, 0.003, n))
    hi = np.maximum(op, cl) * np.exp(np.abs(rng.normal(0, 0.004, n)))
    lo = np.minimum(op, cl) * np.exp(-np.abs(rng.normal(0, 0.004, n)))
    full = cs.pattern_flags(op, hi, lo, cl)
    assert sum(int(f.sum()) for f in full.values()) > 50                       # the test has something to compare
    for k in (80, 150, 301):
        part = cs.pattern_flags(op[:k], hi[:k], lo[:k], cl[:k])
        for name in full:
            assert np.array_equal(part[name], full[name][:k]), (name, k)


def test_a_trade_enters_at_the_next_open_and_leaves_at_the_close_h_bars_after_the_signal():
    o = np.array([10, 11, 12, 13, 14, 15, 16, 17.0])
    c = np.array([10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5])
    assert abs(cs.trade_returns(o, c, [3], 2)[0] - (c[5] / o[4] - 1)) < 1e-12
    assert abs(cs.trade_returns(o, c, [3], 1)[0] - (c[4] / o[4] - 1)) < 1e-12


def test_one_position_per_coin_at_a_time():
    flag = np.zeros(12, bool)
    flag[[2, 3, 4, 8]] = True
    ok = np.ones(12, bool)
    assert cs.pick_trades(flag, ok, 3).tolist() == [2, 8]          # 3 and 4 fall inside the trade from 2 (bars 3..5); 5 would be free
    assert cs.pick_trades(flag, ok, 1).tolist() == [2, 3, 4, 8]
    flag[5] = True
    assert cs.pick_trades(flag, ok, 3).tolist() == [2, 5, 8]
    ok[5] = False
    assert cs.pick_trades(flag, ok, 3).tolist() == [2, 8]


def test_a_hole_in_the_bars_blocks_every_trade_window_that_spans_it():
    t = np.arange(np.datetime64("2024-01-01T00", "ns"), np.datetime64("2024-01-05T05", "ns"), np.timedelta64(1, "h"))
    t = np.delete(t, np.arange(40, 45))                              # five missing hours before row 40
    v = cs.valid_mask(t, 3600 * 10 ** 9, 3)
    assert v[36] and not v[37:52].any() and v[52]                    # windows [i-12, i+3] that contain the break are 37 .. 51
    assert not v[-3:].any()                                          # no room for the exit


def test_day_mean_t_known_value_sign_and_no_infinity():
    m, t, g = cs.day_mean_t([1, 2, 3, 4], [0, 1, 2, 3])
    assert g == 4 and abs(m - 2.5) < 1e-12 and abs(t - 2.5 / (np.std([1, 2, 3, 4], ddof=1) / 2)) < 1e-9
    m2, t2, _ = cs.day_mean_t([-1, -2, -3, -4], [0, 1, 2, 3])
    assert m2 < 0 and t2 < 0 and abs(t2 + t) < 1e-9                   # the sign of t is the sign of the printed mean
    _, t3, _ = cs.day_mean_t([1, 1, 1, 1], [0, 0, 1, 1])         # no spread between days: undefined, not infinite
    assert not np.isfinite(t3)
    # many trades on one day are one bet: 50 copies of the same day do not make a significant mean
    _, t4, _ = cs.day_mean_t([0.05] * 50 + [-0.01, 0.0, 0.01], [0] * 50 + [1, 2, 3])
    assert t4 < 3


def test_the_control_removes_market_drift_costs_are_charged_and_shorts_flip():
    days = np.arange(120)
    rng = np.random.default_rng(1)
    drift = 0.01 * np.sin(days / 6.0)                                 # a market-wide wave the signal knows nothing about
    base = drift.copy()
    day = np.repeat(days, 3)
    noise = rng.normal(0, 0.002, len(day))
    mask = np.ones(len(day), bool)
    s0 = cs.cell_stats(day, drift[day] + noise, base, 1, 5, mask)
    assert abs(s0["exc"]) < 0.0005 and abs(s0["t_exc"]) < 3          # no edge over the day's baseline
    s1 = cs.cell_stats(day, drift[day] + 0.01 + noise, base, 1, 5, mask)
    assert abs(s1["exc"] - 0.01) < 0.0005 and s1["t_exc"] > 20
    assert abs(s1["net"] - (np.mean(drift[day] + 0.01 + noise) - cs.FEE - cs.FUND_H * 5)) < 1e-9
    s2 = cs.cell_stats(day, drift[day] + 0.01 + noise, base, -1, 5, mask)
    assert abs(s2["exc"] + 0.01) < 0.0005 and s2["t_exc"] < -20
    assert abs(s2["net"] - (-np.mean(drift[day] + 0.01 + noise) - cs.FEE)) < 1e-9          # shorts pay the fee but no funding
    base2 = base.copy()
    base2[10] = np.nan                                                # a day with no baseline observations drops out
    s3 = cs.cell_stats(day, drift[day] + noise, base2, 1, 5, mask)
    assert s3["n"] == len(day) - 3


def test_the_control_matches_the_entry_slot_too():
    # two slots a day; slot 1 always drifts +1% more than slot 0. Signals sit only in slot 1 and earn exactly their slot's return.
    days = np.arange(100)
    S = 2
    base_key = np.zeros(len(days) * S)
    base_key[1::2] = 0.01
    day = days.copy()
    key = days * S + 1
    gross = base_key[key]
    mask = np.ones(len(day), bool)
    by_slot = cs.cell_stats(day, gross + np.random.default_rng(0).normal(0, 0.002, len(day)), base_key, 1, 4, mask, key)
    assert abs(by_slot["exc"]) < 0.0006 and abs(by_slot["t_exc"]) < 3
    day_base = base_key.reshape(-1, S).mean(1)                           # the day-only control would call that drift a +0.5% edge
    by_day = cs.cell_stats(day, gross + np.random.default_rng(0).normal(0, 0.002, len(day)), day_base, 1, 4, mask)
    assert by_day["exc"] > 0.0045 and by_day["t_exc"] > 20


def test_evaluate_uses_the_slot_baseline_end_to_end():
    S, d0 = 6, 2000                                                      # days 2000 .. 2199: 67 before the cut, 133 after
    cells = {1: {}, 4: {}, 24: {}}
    bs = {(tfh, H): np.zeros(cs.ND * cs.n_slots(tfh)) for tfh in cs.TFS.values() for H in cs.HORIZONS}
    bc = {k: np.zeros_like(v) for k, v in bs.items()}
    for d in range(d0, d0 + 200):
        for sl in range(S):
            bs[(4, 1)][d * S + sl] = 40 * (0.01 if sl == 3 else 0.0)     # slot 3 always earns +1% more than the others
            bc[(4, 1)][d * S + sl] = 40
    rng = np.random.default_rng(5)
    day = np.repeat(np.arange(d0, d0 + 200), 2)
    gross = 0.01 + rng.normal(0, 0.002, len(day))                        # the pattern earns exactly its slot's +1%
    cells[4][(4, 1, "BULL_ENGULF")] = [(day, day * S + 3, gross)]
    rows = cs.evaluate(cells, bs, bc)
    long_ = [r for r in rows if r["side"] == 1 and r["pat"] == "BULL_ENGULF"][0]
    assert cs.sized(long_["tu"]) and cs.sized(long_["ho"])
    assert abs(long_["tu"]["exc"]) < 0.0006 and abs(long_["ho"]["exc"]) < 0.0006 and not long_["info"] and not long_["pass"]


def test_slot_of_counts_the_bar_of_the_utc_day():
    t = np.array(["2024-02-11T00:00", "2024-02-11T03:00", "2024-02-11T04:00", "2024-02-11T23:00"], dtype="datetime64[ns]")
    assert cs.slot_of(t, 4).tolist() == [0, 0, 1, 5] and cs.slot_of(t, 1).tolist() == [0, 3, 4, 23] and cs.slot_of(t, 24).tolist() == [0, 0, 0, 0]


def test_holm_and_the_pass_rule_need_every_condition():
    assert np.allclose(cs.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
    good = dict(n=500, days=200, net=0.004, t=3.0, exc=0.004, t_exc=3.0, win=0.5)
    assert cs.passes(good, dict(good), 0.01)
    for key, bad in (("net", -0.001), ("t", 1.5), ("exc", -0.001), ("t_exc", 1.9), ("n", 50), ("days", 10)):
        assert not cs.passes(dict(good, **{key: bad}), dict(good), 0.01), key
        assert not cs.passes(dict(good), dict(good, **{key: bad}), 0.01), key
    assert not cs.passes(good, dict(good), 0.06)                      # the multiple-testing line
    assert cs.information(good, dict(good)) and not cs.information(dict(good, t_exc=1.0), dict(good))


def test_only_point_in_time_months_trade_and_enter_the_baseline():
    n = 2000
    t0 = np.datetime64("2024-01-01T00", "ns")
    t = t0 + np.arange(n) * np.timedelta64(1, "h")
    o = np.full(n, 100.0)
    c = np.full(n, 100.0)
    h = np.full(n, 100.5)
    l = np.full(n, 99.5)
    for k in (300, 1000):                                             # a bullish engulfing in January and one in February
        o[k - 1], h[k - 1], l[k - 1], c[k - 1] = 100.0, 100.1, 98.9, 99.0
        o[k], h[k], l[k], c[k] = 98.9, 100.3, 98.8, 100.2
        o[k + 1], h[k + 1], l[k + 1], c[k + 1] = 100.0, 102.1, 99.9, 102.0    # the next bar rises 2% from its open
    d = pd.DataFrame(dict(time=t, o=o, h=h, l=l, c=c))
    cells, bs, bc, counts = {}, {(1, H): np.zeros(cs.ND * 24) for H in cs.HORIZONS}, {(1, H): np.zeros(cs.ND * 24) for H in cs.HORIZONS}, {}
    cs.process(d, np.array(["2024-02"], dtype="datetime64[M]"), 1, cells, bs, bc, counts)
    feb_hours = 29 * 24
    assert int(bc[(1, 1)].sum()) == feb_hours                         # only February's bars are in the baseline
    day, key, gross = cells[(1, 1, "BULL_ENGULF")][0]
    assert len(gross) == 1 and abs(gross[0] - 0.02) < 1e-9            # the January pattern is not traded
    d_feb11 = int((np.datetime64("2024-02-11", "D") - cs.D0) / np.timedelta64(1, "D"))
    assert day[0] == d_feb11 and key[0] == d_feb11 * 24 + 17          # bar 1001 is 17:00 on 11 February: entered in slot 17
    assert bc[(1, 1)][d_feb11 * 24 + 17] == 1 and bc[(1, 1)].reshape(cs.ND, 24)[d_feb11].sum() == 24      # the baseline is kept per slot
    assert counts[(1, "BULL_ENGULF")] == 1


def test_four_hour_bars_need_all_four_hours():
    t = pd.date_range("2024-01-01", periods=12, freq="h")
    h = pd.DataFrame(dict(time=t, open=np.arange(12) + 1.0, high=np.arange(12) + 2.0, low=np.arange(12) + 0.5,
                          close=np.arange(12) + 1.5, qvol=1.0)).drop(index=5).reset_index(drop=True)      # the 05:00 hour is missing
    d = cs.to_tf(h, 4)
    assert len(d) == 2 and d.o.tolist() == [1.0, 9.0] and d.c.tolist() == [4.5, 12.5] and d.h.tolist() == [5.0, 13.0]


def test_the_textbook_table_covers_every_pattern():
    fl = cs.pattern_flags(*bars([]))
    assert set(fl) == set(cs.TEXTBOOK) and len(fl) == 17
    assert sorted(cs.TEXTBOOK.values()) == [-1] * 8 + [0] + [1] * 8


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
