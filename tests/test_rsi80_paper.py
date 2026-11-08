"""rsi80_paper.py offline: the plain-Python rule against the backtest's own code (rsi_ratio / candle_manage / rsi80_more) on real coin history, trade for
trade, and the book's mechanics on fakes (no network). Run as a script: python tests/test_rsi80_paper.py"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rsi80_paper as rp  # noqa: E402

try:                                    # the backtest's own code and history: on the research PC, not on the VM (those three tests then SKIP)
    import backtest.candle_manage as cm  # noqa: E402
    import backtest.capitulation_wide as cw  # noqa: E402
    import backtest.rsi80_more as rm  # noqa: E402
    import backtest.rsi_ratio as rr  # noqa: E402
    HAVE_BT = cw.hourly("SOLUSDT") is not None
except Exception:  # noqa: BLE001
    HAVE_BT = False

H4, MIN = rp.H4, rp.MIN
COINS = ("SOLUSDT", "DOGEUSDT", "LINKUSDT", "AVAXUSDT")


def patched():
    d = Path(tempfile.mkdtemp())
    rp.D, rp.STATE, rp.TRADES = d, d / "state.json", d / "trades.csv"
    return d


def real_4h(sym):
    d = rr.to_tf(cw.hourly(sym), 4)
    t = d.time.to_numpy("datetime64[ms]").astype("int64")
    bars = [(int(a), float(o), float(h), float(l), float(c), int(a) + H4 - 1) for a, o, h, l, c in zip(t, d.o, d.h, d.l, d.c)]
    return d, bars


def test_rsi_and_atr_are_the_backtests():
    if not HAVE_BT:
        print("SKIP (no backtest code / history here)")
        return
    d, bars = real_4h("SOLUSDT")
    c, h, l = d.c.to_numpy(), d.h.to_numpy(), d.l.to_numpy()  # noqa: E741
    assert np.allclose(rp.rsi14(list(c)), rr.rsi14(c), atol=1e-9)
    a = rp.atr14(list(h), list(l), list(c))
    b = cm.atr14(h, l, c)
    assert all(x is None for x in a[:13]) and np.isnan(b[:13]).all() and np.allclose(a[13:], b[13:], rtol=1e-12)


def test_step_is_candle_manage_simulate():
    if not HAVE_BT:
        print("SKIP (no backtest code / history here)")
        return
    rng = np.random.default_rng(3)
    for _ in range(300):
        n = 40
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, n)))
        o = np.r_[100.0, c[:-1]] * np.exp(rng.normal(0, 0.01, n))               # gaps at the opens
        h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.02, n)))
        l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.02, n)))  # noqa: E741
        atr = np.full(n, rng.uniform(0.5, 3.0))
        g, kx, rf = cm.simulate(o, h, l, c, atr, np.array([5]), 1, dict(stop=4.0, be=None, trail=None, target=4.0, cap=24))
        e, risk = o[6], 4.0 * atr[5]
        tr = dict(entry_ms=0, entry=e, stop=e - risk, target=e + 4 * risk, rf=risk / e, bars=0)
        ex = None
        for k in range(1, 25):
            ex = rp.step(tr, (0, o[5 + k], h[5 + k], l[5 + k], c[5 + k], 0))
            if ex:
                break
        assert ex["bars"] == kx[0] and abs((ex["exit"] - e) / risk - g[0]) < 1e-9


def replay(bars, coin):
    """The live loop over history: at every bar close (+5 minutes) the job sees the closed bars and the forming one."""
    st = dict(started_ms=0, equity=rp.START, peak=rp.START, universe={}, open={}, checked={}, free_from={})
    nofund = lambda path, params: []  # noqa: E731
    r = rp.rsi14([b[4] for b in bars])                                  # bar i's RSI / ATR read only bars <= i: the full-series values ARE the prefix values
    a = rp.atr14([b[2] for b in bars], [b[3] for b in bars], [b[4] for b in bars])
    W = rp.WARM + 4
    for j in range(len(bars) - 1):
        lo = max(0, j + 2 - W)
        vis = bars[lo:j + 2]                                            # the last W bars are all either function reads (60 behind + the forming bar)
        now = vis[-1][0] + 5 * MIN
        rp.manage(st, coin, vis, now, nofund)
        rp.try_entry(st, coin, vis, now, lambda m: [coin], ind=(r[lo:j + 2], a[lo:j + 2]))
    return st


def test_the_live_loop_reproduces_the_backtests_trades_on_real_coins():
    if not HAVE_BT:
        print("SKIP (no backtest code / history here)")
        return
    patched()
    checked = 0
    for coin in COINS:
        if rp.TRADES.exists():
            rp.TRADES.unlink()
        d, bars = real_4h(coin)
        em = np.array(sorted(set(d.time.dt.strftime("%Y-%m"))), dtype="datetime64[M]")
        bt = rm.lead_trades(d, em)
        replay(bars, coin)
        pt = pd.DataFrame(rp.read_trades())
        assert len(bt) > 5, coin
        pt["entry_ms"] = pt.entry_ms.astype("int64")
        bt_in = bt.t_in.to_numpy("datetime64[ms]").astype("int64")
        bt_out = bt.t_out.to_numpy("datetime64[ms]").astype("int64")
        # every backtest trade is a paper trade with the same exit and result (the backtest drops signals near holes / the data end; the paper book may have more)
        m = pt.set_index("entry_ms")
        for ti, to, net in zip(bt_in, bt_out, bt.net.to_numpy(float)):
            assert ti in m.index, (coin, ti)
            r = m.loc[ti]
            assert int(r.exit_ms) == to - 1 and abs(float(r.net_r_flat) - net) < 1e-6, (coin, ti, r.exit_ms, to, r.net_r_flat, net)   # the log keeps 6 decimals
            checked += 1
        # and a paper trade the backtest lacks is only one the backtest's own validity rule could not see (a hole within 24 bars ahead, or the data end)
        t = [b[0] for b in bars]
        pos = {b[0]: k for k, b in enumerate(bars)}
        for ti in set(m.index) - set(bt_in):
            i = pos[int(m.loc[ti].signal_ms)]
            ahead = t[i:i + 26]
            assert len(ahead) < 26 or any(ahead[k + 1] - ahead[k] != H4 for k in range(len(ahead) - 1)) or i < rr.WARM + 12, (coin, ti)
    assert checked > 100


def _bars(n, t0=1_700_006_400_000, p=100.0):
    return [(t0 + k * H4, p, p * 1.001, p * 0.999, p, t0 + k * H4 + H4 - 1) for k in range(n)]


def _crossing(n=80, t0=1_700_006_400_000, zig=0.005, rise=0.02, wick=0.001):
    """A coin that zig-zags +-zig (RSI near 50), then rises `rise` a bar from bar 66 until RSI crosses 80: returns (bars up to the forming one, the cross bar)."""
    cs, p = [], 100.0
    for k in range(n):
        p *= (1 + rise) if k >= 66 else ((1 + zig) if k % 2 else (1 - zig))
        cs.append(p)
    r = rp.rsi14(cs)
    k80 = next(k for k in range(61, n) if r[k - 1] <= 80 < r[k])
    bars = []
    for k in range(k80 + 2):
        o = cs[k - 1] if k else cs[0]
        bars.append((t0 + k * H4, o, max(o, cs[k]) * (1 + wick), min(o, cs[k]) * (1 - wick), cs[k], t0 + k * H4 + H4 - 1))
    return bars, k80


def test_a_signal_needs_60_contiguous_bars_behind_it_and_a_stop_of_at_least_0_2_percent():
    bars, k80 = _crossing()
    assert rp.signal(bars, k80) is not None
    hole = [(t - H4, o, h, l, c, ct - H4) if j < k80 - 30 else (t, o, h, l, c, ct) for j, (t, o, h, l, c, ct) in enumerate(bars)]   # the same closes, a 4h hole 30 bars back
    assert rp.rsi14([b[4] for b in hole]) == rp.rsi14([b[4] for b in bars]) and rp.signal(hole, k80) is None
    far = [(t - H4, o, h, l, c, ct - H4) if j < k80 - 70 else (t, o, h, l, c, ct) for j, (t, o, h, l, c, ct) in enumerate(bars)]    # a hole 70 bars back is fine
    assert rp.signal(far, k80) is not None
    tiny, k2 = _crossing(zig=0.00005, rise=0.0002, wick=0.0)                       # the same shape, moves 100x smaller: 4 ATR is ~0.1% of the price
    assert rp.signal(tiny, k2) is None


def test_a_gap_past_the_target_fills_at_the_open():
    tr = dict(entry_ms=0, entry=100.0, stop=90.0, target=140.0, rf=0.1, bars=0)
    ex = rp.step(tr, (0, 150.0, 155.0, 149.0, 152.0, 1))
    assert ex["kind"] == "target" and ex["exit"] == 150.0
    tr = dict(entry_ms=0, entry=100.0, stop=90.0, target=140.0, rf=0.1, bars=0)
    ex = rp.step(tr, (0, 85.0, 95.0, 84.0, 90.0, 1))
    assert ex["kind"] == "stop" and ex["exit"] == 85.0


def test_the_forming_bar_is_never_managed():
    patched()
    st = rp.load_state()
    t0 = 1_700_006_400_000
    st["open"]["AAAUSDT"] = dict(signal_ms=t0 - H4, entry_ms=t0, entry=100.0, seen_px=100.0, stop=90.0, target=140.0, rf=0.1, bars=0, risk_usd=3.0,
                                 notional=30.0, booked=True)
    bars = [(t0, 100, 101, 99, 100, t0 + H4 - 1), (t0 + H4, 100, 100, 80, 85, t0 + 2 * H4 - 1)]                  # bar 2 dips through the stop - so far
    rp.manage(st, "AAAUSDT", bars, t0 + H4 + 30 * MIN, lambda p, q: [])                                             # half an hour into bar 2
    assert "AAAUSDT" in st["open"] and st["open"]["AAAUSDT"]["bars"] == 1
    rp.manage(st, "AAAUSDT", bars, t0 + 2 * H4 + 5 * MIN, lambda p, q: [])                                          # after it closed
    assert "AAAUSDT" not in st["open"] and rp.read_trades()[0]["kind"] == "stop"


def test_a_trade_that_was_not_booked_never_moves_the_book():
    patched()
    st = rp.load_state()
    t0 = 1_700_006_400_000
    st["open"]["AAAUSDT"] = dict(signal_ms=t0 - H4, entry_ms=t0, entry=100.0, seen_px=100.0, stop=90.0, target=140.0, rf=0.1, bars=0, risk_usd=3.0,
                                 notional=3.0, booked=False)
    rp.manage(st, "AAAUSDT", [(t0, 100, 150, 99, 140, t0 + H4 - 1)], t0 + H4 + MIN, lambda p, q: [])
    row = rp.read_trades()[0]
    assert st["equity"] == rp.START and float(row["pnl_usd"]) == 0.0 and float(row["net_r"]) > 3.5          # scored as a prediction, no paper money


def test_one_entry_per_bar_and_no_stale_entries():
    patched()
    st = rp.load_state()
    vis, k80 = _crossing()
    now = vis[-1][0] + 5 * MIN
    rp.try_entry(st, "AAAUSDT", vis, now, lambda m: ["AAAUSDT"])
    assert "AAAUSDT" in st["open"] and st["open"]["AAAUSDT"]["entry_ms"] == vis[-1][0]
    first = dict(st["open"]["AAAUSDT"])
    rp.try_entry(st, "AAAUSDT", vis, now + MIN, lambda m: ["AAAUSDT"])                           # the same bar again: nothing changes
    assert st["open"]["AAAUSDT"] == first
    st2 = rp.load_state()
    rp.try_entry(st2, "AAAUSDT", vis, vis[-1][0] + 2 * rp.H1, lambda m: ["AAAUSDT"])                # two hours into the entry bar: too late
    assert "AAAUSDT" not in st2["open"] and st2["checked"]["AAAUSDT"] == vis[-2][0]
    st3 = rp.load_state()
    rp.try_entry(st3, "AAAUSDT", vis, now, lambda m: ["BBBUSDT"])                                   # not in the universe of the signal bar's month
    assert "AAAUSDT" not in st3["open"]
    st4 = rp.load_state()
    rp.try_entry(st4, "AAAUSDT", vis[:-1], vis[-2][5] + MIN, lambda m: ["AAAUSDT"])                  # no forming bar yet: the entry open is unknown
    assert "AAAUSDT" not in st4["open"] and "AAAUSDT" not in st4["checked"]


def test_sizing_minimum_and_the_gross_cap():
    patched()
    st = rp.load_state()
    bars = _bars(3)
    now = bars[-1][0] + 5 * MIN
    sig = lambda e, rf: dict(signal_ms=bars[-2][0], entry_ms=bars[-1][0], entry=e, stop=e * (1 - rf), target=e * (1 + 4 * rf), rf=rf, bars=0)  # noqa: E731
    old = rp.signal
    try:
        rp.signal = lambda bars, i, *a: sig(100.0, 0.1)
        rp.try_entry(st, "AAAUSDT", bars, now, lambda m: ["AAAUSDT"])
        tr = st["open"]["AAAUSDT"]
        assert tr["booked"] and abs(tr["risk_usd"] - 3.0) < 1e-9 and abs(tr["notional"] - 30.0) < 1e-9          # 1% of $300, over a 10% stop
        rp.signal = lambda bars, i, *a: sig(100.0, 0.7)                                                               # $3 / 70% = $4.29: under $5
        rp.try_entry(st, "BBBUSDT", bars, now, lambda m: ["BBBUSDT"])
        assert not st["open"]["BBBUSDT"]["booked"]
        rp.signal = lambda bars, i, *a: sig(100.0, 0.001)                                                             # $3 / 0.1% = $3,000 > 10x $300
        rp.try_entry(st, "CCCUSDT", bars, now, lambda m: ["CCCUSDT"])
        assert not st["open"]["CCCUSDT"]["booked"]
        st["equity"] = 500.0
        rp.signal = lambda bars, i, *a: sig(100.0, 0.1)
        rp.try_entry(st, "DDDUSDT", bars, now, lambda m: ["DDDUSDT"])
        assert abs(st["open"]["DDDUSDT"]["risk_usd"] - 5.0) < 1e-9                                                # 1% of the BOOKED equity at entry
    finally:
        rp.signal = old


def test_an_exit_is_booked_with_real_funding_and_frees_the_coin_on_its_exit_bar():
    patched()
    st = rp.load_state()
    t0 = 1_700_006_400_000
    tr = dict(signal_ms=t0 - H4, entry_ms=t0, entry=100.0, seen_px=100.1, stop=90.0, target=140.0, rf=0.1, bars=0, risk_usd=3.0, notional=30.0, booked=True)
    st["open"]["AAAUSDT"] = tr
    bars = [(t0, 100, 101, 99, 100, t0 + H4 - 1), (t0 + H4, 100, 145, 99, 140, t0 + 2 * H4 - 1), (t0 + 2 * H4, 140, 141, 139, 140, t0 + 3 * H4 - 1)]
    calls = []

    def fund(path, params):
        calls.append(params)
        return [dict(fundingRate="0.001", fundingTime=t0), dict(fundingRate="0.0005", fundingTime=t0 + H4), dict(fundingRate="0.002", fundingTime=t0 + 9 * H4)]
    rp.manage(st, "AAAUSDT", bars, t0 + 2 * H4 + 5 * MIN, fund)
    assert "AAAUSDT" not in st["open"] and calls[0]["startTime"] == t0 + 1 and calls[0]["endTime"] == t0 + 2 * H4 - 1
    row = rp.read_trades()[0]
    assert row["kind"] == "target" and int(row["bars"]) == 2 and abs(float(row["fund_real"]) - 0.0005) < 1e-12      # only the settlement inside (entry, exit end]
    assert abs(float(row["net_r"]) - (4.0 - (rp.FEE + 0.0005) / 0.1)) < 1e-9
    assert abs(float(row["net_r_flat"]) - (4.0 - (rp.FEE + rp.FUND_H * 8) / 0.1)) < 1e-9
    assert abs(st["equity"] - (300 + 3.0 * float(row["net_r"]))) < 1e-6
    assert st["free_from"]["AAAUSDT"] <= t0 + H4 < st["free_from"]["AAAUSDT"] + H4                                   # a signal on the exit bar is allowed


def test_a_hole_in_the_bars_holds_the_trade_rather_than_skipping_a_bar():
    patched()
    st = rp.load_state()
    t0 = 1_700_006_400_000
    st["open"]["AAAUSDT"] = dict(signal_ms=t0 - H4, entry_ms=t0, entry=100.0, seen_px=100.0, stop=90.0, target=140.0, rf=0.1, bars=0, risk_usd=3.0,
                                 notional=30.0, booked=True)
    bars = [(t0, 100, 101, 99, 100, t0 + H4 - 1), (t0 + 2 * H4, 100, 150, 99, 140, t0 + 3 * H4 - 1)]              # bar 2 is missing
    rp.manage(st, "AAAUSDT", bars, t0 + 3 * H4 + MIN, lambda p, q: [])
    assert st["open"]["AAAUSDT"]["bars"] == 1 and not rp.read_trades()


def test_the_universe_is_last_months_volume_with_the_age_rule():
    day = rp.DAY
    m0 = rp.month_start_ms("2026-11")
    old = [(m0 - 60 * day + k * day, 1.0) for k in range(70)]
    daily = {"AAAUSDT": [(t, 5.0 if rp.month_start_ms("2026-10") <= t < m0 else 999.0) for t, _ in old],
             "BBBUSDT": [(t, 9.0 if rp.month_start_ms("2026-10") <= t < m0 else 0.0) for t, _ in old],
             "NEWUSDT": [(m0 - 20 * day + k * day, 1e9) for k in range(25)]}                                    # listed 20 days before: too young
    assert rp.rank_universe(daily, "2026-11") == ["BBBUSDT", "AAAUSDT"]
    info = dict(symbols=[dict(symbol="AAAUSDT", quoteAsset="USDT", contractType="PERPETUAL", status="TRADING", underlyingType="COIN", baseAsset="AAA"),
                         dict(symbol="USDCUSDT", quoteAsset="USDT", contractType="PERPETUAL", status="TRADING", underlyingType="COIN", baseAsset="USDC"),
                         dict(symbol="XAUUSDT", quoteAsset="USDT", contractType="PERPETUAL", status="TRADING", underlyingType="TRADIFI", baseAsset="XAU"),
                         dict(symbol="BBBUSDT", quoteAsset="USDT", contractType="CURRENT_QUARTER", status="TRADING", baseAsset="BBB"),
                         dict(symbol="CCCUSDT", quoteAsset="USDT", contractType="PERPETUAL", status="SETTLING", baseAsset="CCC")])
    assert rp.candidates(lambda p, q: info) == ["AAAUSDT"]
    from backtest.market_neutral import NON_CRYPTO
    assert rp.NON_CRYPTO == NON_CRYPTO


def test_the_registered_lines():
    rows = lambda m, n: [dict(net_r=str(m))] * n  # noqa: E731
    assert rp.verdict(rows(-0.5, 40), 250, "2027-01-15").startswith("NOT YET")
    assert rp.verdict(rows(-0.30, 40), 250, "2027-02-01").startswith("DEAD - the kill line")
    assert rp.verdict(rows(-0.30, 20), 250, "2027-02-01").startswith("NOT YET")                          # under 30 trades: no kill
    assert rp.verdict(rows(-0.20, 40), 280, "2027-02-01").startswith("NOT YET")
    assert rp.verdict(rows(0.08, 150), 310, "2027-04-09").startswith("HELD UP")
    assert rp.verdict(rows(0.08, 150), 299, "2027-04-09").startswith("CANNOT TELL")                       # the account must be above $300 too
    assert rp.verdict(rows(-0.11, 150), 290, "2027-04-09").startswith("DEAD (")
    assert rp.verdict(rows(0.0, 150), 290, "2027-04-09").startswith("CANNOT TELL")


def test_the_record_line_with_resolved_trades():
    patched()
    rp.append_trade(dict(coin="A", net_r="0.5", net_r_flat="0.4", kind="stop", seen_px="101", entry="100"))
    rp.append_trade(dict(coin="B", net_r="-1", net_r_flat="-1", kind="time", seen_px="99", entry="100"))
    s = rp.status()
    assert "mean R a trade -0.250 (real funding) / -0.300" in s and "exits stop 1, target 0, time 1" in s and "1.00% apart" in s


def test_a_whole_run_on_fake_data():
    patched()
    t0 = rp.month_start_ms("2026-11") + 7 * rp.DAY
    daily = [[rp.month_start_ms("2026-11") - 60 * rp.DAY + k * rp.DAY, "1", "1", "1", "1", "1", 0, "1000", 0, 0, 0, 0] for k in range(70)]
    k4 = [[t0 + k * H4, "100", "100.1", "99.9", "100", "1", t0 + (k + 1) * H4 - 1, "1", 0, 0, 0, 0] for k in range(100)]
    info = dict(symbols=[dict(symbol="AAAUSDT", quoteAsset="USDT", contractType="PERPETUAL", status="TRADING", underlyingType="COIN", baseAsset="AAA")])

    def fetch(path, params):
        if path.endswith("exchangeInfo"):
            return info
        if path.endswith("fundingRate"):
            return []
        return daily if params["interval"] == "1d" else k4
    st = rp.run(now=t0 + 99 * H4 + 5 * MIN, fetch=fetch)
    assert st["universe"]["2026-11"] == ["AAAUSDT"] and st["checked"]["AAAUSDT"] == t0 + 98 * H4 and not st["open"]
    assert json.loads(rp.STATE.read_text())["equity"] == rp.START
    assert "NOT YET" in rp.status()


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
