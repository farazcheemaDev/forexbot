"""Tests for backtest/rsi80_more.py: the moved day counter, the lead cell against rsi_ratio.process, the pooled control, the verdict and the small
account. Offline (synthetic candles). Run as a script: python tests/test_rsi80_more.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.candle_scan as cs  # noqa: E402
import backtest.rsi80_more as m  # noqa: E402
import backtest.rsi_ratio as rr  # noqa: E402

D0, CUT, ND = cs.D0, cs.CUT_DAY, cs.ND


def _restore():
    cs.D0, cs.CUT_DAY, cs.ND = D0, CUT, ND


def test_the_day_counter_moves_back_and_the_split_date_stays():
    try:
        m.move_day_origin()
        assert cs.D0 == np.datetime64("2017-01-01", "D") and cs.day_index(np.array(["2017-01-01T05:00"], "datetime64[ns]"))[0] == 0
        assert cs.D0 + np.timedelta64(cs.CUT_DAY, "D") == np.datetime64("2024-08-29", "D")
        assert cs.D0 + np.timedelta64(cs.ND, "D") == np.datetime64("2027-01-01", "D")
    finally:
        _restore()


def _coin(n=900, seed=0):
    """4h bars: a noisy walk with strong up-runs (RSI crosses 80) every ~120 bars."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, n)
    for s in range(150, n - 40, 120):
        r[s:s + 8] += 0.02 * rng.uniform(0.5, 1.5)
    c = 100 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.004, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.004, n)))  # noqa: E741
    t = pd.date_range("2021-01-01", periods=n, freq="4h")
    return pd.DataFrame(dict(time=t, o=o, h=h, l=l, c=c, v=rng.uniform(1, 2, n) * 1e6))


def test_the_lead_trades_are_rsi_ratio_s_own():
    try:
        m.move_day_origin()
        d = _coin()
        em = np.array(sorted({str(x)[:7] for x in d.time.dt.strftime("%Y-%m")}), dtype="datetime64[M]")
        cells, acc = {}, rr.new_acc()
        rr.process(d, em, 4, cells, acc)
        T = m.lead_trades(d, em)
        assert len(T) >= 3 and m.same_as_process(T, cells)
        assert (T.t_out > T.t_in).all() and (T.rf > 0).all()
        assert (T.t_in.to_numpy()[1:] >= T.t_out.to_numpy()[:-1] - np.timedelta64(4, "h")).all()      # one position per coin
        bad = T.copy()
        bad.loc[0, "net"] += 0.5
        assert not m.same_as_process(bad, cells)
        half = np.array(sorted({str(x)[:7] for x in d.time.dt.strftime("%Y-%m")})[:3], dtype="datetime64[M]")   # only 3 eligible months
        assert m.lead_trades(d, half).t_in.max() < np.datetime64("2021-04-02")
    finally:
        _restore()


def _coin2(n=900, seed=1):
    """A coin built so the risk floor and the one-position rule must bind: a double surge (two RSI crosses inside one 24-bar hold) at bar 300,
    and from bar 500 a 200-bar dead-flat stretch (so RSI's averages fade out) followed by tiny steady rises (RSI crosses 80 while 4 ATR is far under 0.2% of the price)."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, n)
    r[300:306] += 0.03
    r[306:309] -= 0.025
    r[309:315] += 0.03
    r[500:700] = 0.0
    r[700:760] = 1e-6
    c = 100 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    wig = np.abs(rng.normal(0, 0.004, n))
    wig[500:760] = 0.0
    h, l = np.maximum(o, c) * (1 + wig), np.minimum(o, c) * (1 - wig)  # noqa: E741
    t = pd.date_range("2021-01-01", periods=n, freq="4h")
    return pd.DataFrame(dict(time=t, o=o, h=h, l=l, c=c, v=np.full(n, 1e6)))


def test_the_risk_floor_the_one_position_rule_and_the_exit_time_bind():
    try:
        m.move_day_origin()
        d = _coin2()
        em = np.array(sorted(set(d.time.dt.strftime("%Y-%m"))), dtype="datetime64[M]")
        cells, acc = {}, rr.new_acc()
        rr.process(d, em, 4, cells, acc)
        T = m.lead_trades(d, em)
        assert m.same_as_process(T, cells)
        fl = rr.rsi_flags(rr.rsi14(d.c.to_numpy()), d.v.to_numpy())["hi80"]
        t = d.time.to_numpy("datetime64[ns]")
        assert fl[700:760].any() and not ((T.t_in > t[700]) & (T.t_in <= t[761])).any()      # crosses in the flat-and-tiny stretch: refused by the floor
        assert fl[300:316].sum() >= 2 and ((T.t_in > t[300]) & (T.t_in <= t[316])).sum() == 1   # two crosses inside one hold: one trade
        held = (T.t_out - T.t_in) / pd.Timedelta(hours=4)
        assert held.min() >= 1 and held.max() <= rr.CAP and (held == rr.CAP).any()              # t_out = the exit bar's END; a time exit = 24 bars
    finally:
        _restore()


def test_pooling_keeps_each_universe_on_its_own_control():
    S = cs.n_slots(4)
    b1, w1 = np.full(cs.ND * S, 0.1), np.full(cs.ND * S, 0.4)
    b2, w2 = np.full(cs.ND * S, -0.3), np.full(cs.ND * S, 0.2)
    d1, k1, n1 = np.array([10, 11]), np.array([60, 66]), np.array([1.0, -1.0])
    d2, k2, n2 = np.array([5]), np.array([30]), np.array([2.0])
    day, key, net, base, bw = m.pooled(((d1, k1, n1), (b1, w1)), ((d2, k2, n2), (b2, w2)))
    assert list(day) == [10, 11, 5] and list(net) == [1.0, -1.0, 2.0]
    assert list(base[key]) == [0.1, 0.1, -0.3] and list(bw[key]) == [0.4, 0.4, 0.2]


def _days(n, mu, first=None, noise=0.6, base=-0.1, seed=0):
    rng = np.random.default_rng(seed)
    day = np.arange(n)
    net = mu + rng.normal(0, noise, n)
    if first is not None:
        net[: n // 2] = first + rng.normal(0, noise, n // 2)
    key = day * 6
    b = np.full(n * 6 + 6, base)
    return day, key, net, b, np.full(n * 6 + 6, 0.3)


def test_the_verdict_needs_every_part_of_the_bar():
    assert m.verdict(*_days(400, 0.4))["ok"]
    assert not m.verdict(*_days(80, 0.6))["ok"]                                     # under 100 trades
    assert not m.verdict(*_days(400, 0.6, first=-0.2))["ok"]                         # the first half loses per trade
    assert not m.verdict(*_days(400, 0.4, base=0.9))["ok"]                           # the control does better
    assert not m.verdict(*_days(400, 0.03))["ok"]                                    # too small to reach t 2
    v = m.verdict(*_days(400, 0.4))
    assert abs(v["mde"] - 2.84 * v["whole"]["net"] / v["whole"]["t"]) < 1e-9


def _T(rows):
    return pd.DataFrame([dict(t_in=np.datetime64(a), t_out=np.datetime64(b), net=r, rf=f) for a, b, r, f in rows])


def test_the_account_takes_one_position_at_a_time_and_compounds():
    T = _T([("2021-01-01T00", "2021-01-03T00", 2.0, 0.05),        # +10%
            ("2021-01-02T00", "2021-01-04T00", -1.0, 0.05),       # open while the first is: skipped
            ("2021-01-05T00", "2021-01-06T00", -1.0, 0.05)])      # -5%
    a = m.account(T, 1.0)
    assert a["n"] == 2 and abs(a["end"] - 20 * 1.10 * 0.95) < 1e-9 and abs(a["dd"] - 0.05) < 1e-9 and abs(a["worst"] + 0.05) < 1e-12
    b = m.account(T, 2.0)
    assert abs(b["end"] - 20 * 1.20 * 0.90) < 1e-9
    wipe = _T([("2021-01-01T00", "2021-01-02T00", -1.0, 0.8), ("2021-01-03T00", "2021-01-04T00", 3.0, 0.05)])
    w = m.account(wipe, 2.0)                                       # -160% floors at -100%: nothing left, stuck
    assert w["end"] == 0 and w["stuck"] and w["n"] == 1


def test_the_account_stops_under_the_venue_minimum():
    T = _T([("2021-01-01T00", "2021-01-02T00", -1.0, 0.8), ("2021-01-03T00", "2021-01-04T00", 3.0, 0.05)])
    a = m.account(T, 1.0)                                          # $20 -> $4: under $5, the second signal cannot be traded
    assert abs(a["end"] - 4.0) < 1e-9 and a["n"] == 1 and a["stuck"]


def test_the_sized_account_takes_every_signal_sized_on_booked_equity():
    T = _T([("2021-01-01T00", "2021-01-03T00", 2.0, 0.05),        # risk $1 (1% of $100), notional $20: +$2 at its close
            ("2021-01-02T00", "2021-01-04T00", -1.0, 0.05),       # opens while the first is open: still sized on the BOOKED $100 -> -$1
            ("2021-01-03T00", "2021-01-05T00", 1.0, 0.05)])       # enters the instant the first closes: the exit is booked first -> risk $1.02
    a = m.sized_account(T, 100.0, 0.01)
    assert a["taken"] == 3 and a["skipped"] == 0
    assert abs(a["end"] - (100 + 2 - 1 + 1.02)) < 1e-9
    assert abs(a["gross"] - 40 / 100) < 1e-9                         # two $20 positions open on $100 booked (later $40.40 on $102 is less)
    assert abs(a["dd"] - (1 - 101 / 102)) < 1e-9                     # the fall is measured on the booked equity, from its peak
    small = m.sized_account(T, 20.0, 0.01)                           # $0.20 risk / 5% = $4 a position: under $5, nothing can be traded
    assert small["taken"] == 0 and small["skipped"] == 3 and small["end"] == 20.0


def test_funding_is_converted_to_r_over_the_hours_held():
    T = pd.DataFrame(dict(coin=["AAAUSDT"], t_in=[np.datetime64("2021-01-01T04:00")], t_out=[np.datetime64("2021-01-02T04:00")], rf=[0.1]))
    assert abs(m.flat_funding_r(T)[0] - (1e-4 / 8 * 24) / 0.1) < 1e-12                       # 24 hours at 1bp / 8h, over a 10% stop
    hh = pd.DataFrame(dict(time=pd.date_range("2021-01-01", periods=72, freq="h"), open=100.0, high=100.0, low=100.0, close=100.0, qvol=1.0))
    old_h, old_fc = m.cw.hourly, m.cw.funding_cum
    try:
        m.cw.hourly = lambda s: hh
        m.cw.funding_cum = lambda s, t, h: np.arange(len(t)) * 0.01                           # 0.01 of price units paid every hour
        r = m.real_funding_r(T)
        assert abs(r[0] - (24 * 0.01 / 100) / 0.1) < 1e-12                                    # 24 hours x 0.01 / price 100 / the 10% stop
    finally:
        m.cw.hourly, m.cw.funding_cum = old_h, old_fc


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
