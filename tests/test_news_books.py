"""Offline tests for news_books.py - the news book and the NASDAQ-dip book of the final machine. No network: the channel
page and the 1h bars are fakes, funding a function. Each rule is tested where it must fire and where it must not.

    python tests/test_news_books.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = [sys.argv[0]]
import combo_paper as cp  # noqa: E402
import final_books as fb  # noqa: E402
import news_books as nb  # noqa: E402

cp.set_dir(Path(tempfile.mkdtemp()))
NOFUND = lambda s, a, b: 0.0  # noqa: E731
FEE = 6.0 / 1e4
T0 = 1_790_000_000                                           # seconds
PX = {"BTCUSDT": 100_000.0, "ARBUSDT": 1.0, "ATAUSDT": 0.10, "A2ZUSDT": 0.01, "FIOUSDT": 0.02, "GTCUSDT": 0.5,
      "ETHUSDT": 3000.0}
ADD = "Binance Will Add Arbitrum (ARB) on Earn, Buy Crypto, Convert, Margin & Futures\nhttps://www.binance.com/x"
TAG = "Binance Will Extend the Monitoring Tag to Include ATA, A2Z, FIO & GTC on 2026-03-13"
PROMO = "Binance Earn: Enjoy up to 4.5% APR with SOL Simple Earn Flexible Products!"


def account(eq=300.0):
    st = dict(equity=eq, cum={}, fin=fb.fresh())
    nb.ensure(st)
    return st


def reader(msgs):
    return lambda: list(msgs)


def ms(sec):
    return int(sec * 1000)


def armed(st, msgs_before=((1, T0 - 600, PROMO),)):
    """The first read only records the newest id."""
    nb.news_poll(st, PX, ms(T0), fund=NOFUND, read=reader(msgs_before))


def test_first_read_trades_nothing_old():
    st = account()
    nb.news_poll(st, PX, ms(T0), fund=NOFUND, read=reader([(5, T0 - 60, ADD)]))
    n = st["fin"]["news"]
    assert n["last_id"] == 5 and not n["pending"] and not n["open"]


def test_add_products_shorts_the_coin_vs_btc_15_minutes_later():
    st = account()
    armed(st)
    eq0 = st["equity"]
    nb.news_poll(st, PX, ms(T0), fund=NOFUND, read=reader([(2, T0, ADD)]))
    n = st["fin"]["news"]
    assert list(n["pending"]) == ["2:ARBUSDT"] and not n["open"]
    nb.news_poll(st, PX, ms(T0 + 14 * 60), fund=NOFUND, read=reader([(2, T0, ADD)]))
    assert not n["open"], "opened before the 15-minute delay"
    nb.news_poll(st, PX, ms(T0 + 15 * 60), fund=NOFUND, read=reader([(2, T0, ADD)]))
    p = n["open"]["2:ARBUSDT"]
    usd = nb.K_NEWS * eq0 / nb.NEWS_SLOTS
    assert abs(p["q_coin"] + usd / 1.0) < 1e-9 and abs(p["q_btc"] - usd / 100_000.0) < 1e-12
    assert abs(st["equity"] - (eq0 - 2 * usd * FEE)) < 1e-9
    t = nb.targets(st)
    assert t["ARBUSDT"] < 0 < t["BTCUSDT"]
    assert fb.targets(st)["ARBUSDT"] == t["ARBUSDT"], "final_books.targets must carry the news book"


def opened(coin_px=1.0):
    st = account()
    armed(st)
    nb.news_poll(st, PX, ms(T0), fund=NOFUND, read=reader([(2, T0, ADD)]))
    nb.news_poll(st, PX, ms(T0 + 900), fund=NOFUND, read=reader([(2, T0, ADD)]))
    return st, st["fin"]["news"]["open"]["2:ARBUSDT"]


def test_stop_take_profit_and_time_exit():
    for px, when, why_left in ((1.24, 3600, True), (1.25, 3600, False), (0.81, 3600, True), (0.80, 3600, False),
                               (1.0, 72 * 3600 - 120, True), (1.0, 72 * 3600 + 60, False)):
        st, p = opened()
        eq = st["equity"]
        prices = dict(PX, ARBUSDT=px)
        nb.news_poll(st, prices, ms(T0 + 900 + when), fund=NOFUND, read=reader([]))
        still = "2:ARBUSDT" in st["fin"]["news"]["open"]
        assert still == why_left, (px, when)
        if not still:
            pnl = p["q_coin"] * (px - 1.0)                       # BTC unchanged
            fee = (abs(p["q_coin"]) * px + abs(p["q_btc"]) * 100_000.0) * FEE
            assert abs(st["equity"] - (eq + pnl - fee)) < 1e-9, (px, st["equity"], eq + pnl - fee)


def test_short_receives_funding_the_long_btc_leg_pays():
    st, p = opened()
    eq = st["equity"]
    fund = lambda s, a, b: 0.001 if s != "BTCUSDT" else 0.0005  # noqa: E731
    nb.news_poll(st, dict(PX, ARBUSDT=0.80), ms(T0 + 7200), fund=fund, read=reader([]))
    pnl = p["q_coin"] * (0.80 - 1.0) - p["q_coin"] * 1.0 * 0.001 - p["q_btc"] * 100_000.0 * 0.0005
    fee = (abs(p["q_coin"]) * 0.80 + abs(p["q_btc"]) * 100_000.0) * FEE
    assert abs(st["equity"] - (eq + pnl - fee)) < 1e-9
    assert -p["q_coin"] * 1.0 * 0.001 > 0, "a short must RECEIVE positive funding"


def test_monitoring_tag_takes_its_first_three_coins_and_promos_are_ignored():
    st = account()
    armed(st)
    nb.news_poll(st, PX, ms(T0), fund=NOFUND, read=reader([(2, T0, TAG), (3, T0, PROMO)]))
    pend = st["fin"]["news"]["pending"]
    assert sorted(k.split(":")[1] for k in pend) == ["A2ZUSDT", "ATAUSDT", "FIOUSDT"], pend
    assert st["fin"]["news"]["seen"] == 2


def test_slots_one_per_coin_and_stale_signals():
    st = account()
    armed(st)
    syms = [f"C{i:02d}" for i in range(12)]
    prices = dict(PX, **{f"{s}USDT": 1.0 for s in syms})
    msgs = [(10 + i, T0, f"Binance Will Add Coin{i} ({s}) on Earn, Convert, Margin & Futures") for i, s in enumerate(syms)]
    msgs.append((40, T0, "Binance Will Add Coin0 again (C00) on Earn, Convert, Margin & Futures"))
    nb.news_poll(st, prices, ms(T0), fund=NOFUND, read=reader(msgs))
    nb.news_poll(st, prices, ms(T0 + 900), fund=NOFUND, read=reader([]))
    n = st["fin"]["news"]
    assert len(n["open"]) == nb.NEWS_SLOTS
    assert len({p["coin"] for p in n["open"].values()}) == nb.NEWS_SLOTS, "two trades in one coin"
    nb.news_poll(st, prices, ms(T0 + 900 + 3601), fund=NOFUND, read=reader([]))
    assert not n["pending"] and n["dropped"] >= 2, "full slots for an hour must drop the waiting signals"


def test_no_price_means_wait_then_drop():
    st = account()
    armed(st)
    msg = (2, T0, "Binance Will Add Nocoin (NOC) on Earn, Convert, Margin & Futures")
    prices = dict(PX, NOCUSDT=1.0)
    nb.news_poll(st, prices, ms(T0), fund=NOFUND, read=reader([msg]))
    assert "2:NOCUSDT" in st["fin"]["news"]["pending"]
    nb.news_poll(st, PX, ms(T0 + 900), fund=NOFUND, read=reader([]))          # no NOC price now
    assert not st["fin"]["news"]["open"] and "2:NOCUSDT" in st["fin"]["news"]["pending"]
    nb.news_poll(st, PX, ms(T0 + 900 + 3601), fund=NOFUND, read=reader([]))
    assert not st["fin"]["news"]["pending"]


def test_old_state_gets_the_new_books():
    st = dict(equity=300.0, fin=fb.fresh())
    del st["fin"]["daily"]["taken"]
    nb.ensure(st)
    assert "news" in st["fin"] and "ndx" in st["fin"] and st["fin"]["news"]["last_id"] is None


# ------------------------------------------------------------------ the NASDAQ dip book

def ny_bars(closes, start="2026-09-01"):
    """1h bars whose 16:00 New York close each weekday is the given close; flat in between."""
    rows, k = [], 0
    for d in pd.bdate_range(start, periods=len(closes)):
        end = pd.Timestamp(d.strftime("%Y-%m-%d") + " 16:00", tz="America/New_York")
        for h in range(-3, 1):
            t = end + pd.Timedelta(hours=h) - pd.Timedelta(hours=1)
            rows.append((int(t.tz_convert("UTC").timestamp() * 1000), closes[k]))
        k += 1
    return pd.DataFrame(rows, columns=["t", "c"])


def run_days(st, closes, upto):
    h = ny_bars(closes)
    for i in range(1, upto + 1):
        sub = ny_bars(closes[:i])
        now = int(sub.t.iloc[-1]) + 3_600_000 + 60_000
        nb.ndx_poll(st, {nb.NDX_SYM: closes[i - 1]}, now, fund=NOFUND, get1h=lambda s, sub=sub: sub)
    return h


def test_ndx_buys_a_sharp_dip_and_sells_above_the_5_day_average():
    base = list(100 + np.arange(20) * 0.5)
    closes = base + [base[-1] * 0.97, base[-1] * 0.95]                 # two sharp down closes: RSI(2) < 10
    st = account()
    run_days(st, closes, len(closes))
    o = st["fin"]["ndx"]["open"]
    assert o is not None and abs(o["entry"] - closes[-1]) < 1e-9 and o["rsi"] < 10
    eq = st["equity"]
    closes2 = closes + [closes[-1] * 1.001, closes[-1] * 1.08]          # first close above the 5-day average exits
    run_days(st, closes2, len(closes2))
    assert st["fin"]["ndx"]["open"] is None and st["cum"]["ndx"] > 0 and st["equity"] > eq


def test_ndx_ignores_a_calm_market_and_acts_once_per_close():
    closes = list(100 + np.arange(25) * 0.5)
    st = account()
    run_days(st, closes, len(closes))
    assert st["fin"]["ndx"]["open"] is None and st["fin"]["ndx"]["taken"] == 0
    day = st["fin"]["ndx"]["last_close_day"]
    sub = ny_bars(closes)
    nb.ndx_poll(st, {nb.NDX_SYM: 1.0}, int(sub.t.iloc[-1]) + 3_600_000 + 120_000, fund=NOFUND, get1h=lambda s: sub)
    assert st["fin"]["ndx"]["last_close_day"] == day


def test_ndx_does_not_buy_a_stale_signal():
    base = list(100 + np.arange(20) * 0.5)
    closes = base + [base[-1] * 0.97, base[-1] * 0.95]
    sub = ny_bars(closes)
    st = account()
    late = int(sub.t.iloc[-1]) + 3_600_000 + 4 * 3_600_000                      # 4 hours after the close (a literal:
                                                                                  # reading NDX_LATE_MS made the test move with the rule)
    nb.ndx_poll(st, {nb.NDX_SYM: closes[-1]}, late, fund=NOFUND, get1h=lambda s: sub)
    assert st["fin"]["ndx"]["open"] is None and st["fin"]["ndx"]["taken"] == 0
    st = account()
    early = int(sub.t.iloc[-1]) + 3_600_000 + 60_000
    nb.ndx_poll(st, {nb.NDX_SYM: closes[-1]}, early, fund=NOFUND, get1h=lambda s: sub)
    assert st["fin"]["ndx"]["open"] is not None


def test_ndx_max_days_exit():
    base = list(100 + np.arange(20) * 0.5)
    closes = base + [base[-1] * 0.97, base[-1] * 0.95] + [base[-1] * 0.95 * (0.995 ** k) for k in range(1, 12)]
    st = account()
    run_days(st, closes, len(closes))
    assert st["fin"]["ndx"]["taken"] >= 1
    assert st["fin"]["ndx"]["open"] is None or st["fin"]["ndx"]["open"]["days"] < nb.NDX_MAX_DAYS


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
