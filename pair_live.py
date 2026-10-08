"""THE PAIR, LIVE - read-only signals and a paper book for the daily Bollinger trend book + the capitulation book.

What it is (doc 02, 2026-10-08; backtest/pair_books.py): two simple, point-in-time rules that earn in opposite markets.
    DAILY TREND  a daily close above Bollinger(30, 1.5)        -> BUY at the next open
                 a daily close under the 30-day mean            -> SELL at the next open (30-day cap)
    CAPITULATION a 4h close where RSI(14) crosses under 20 with quote volume > 2x its 20-bar average, once >= 5 coins
                 have done so within 24 hours                   -> BUY at the next open
                 +5% (a limit), or SELL at the next open once 24 bars (4 days) have passed with the close not in
                 profit; 7-day cap
    Universe: the 40 Bitget USDT perps with the most quote volume over the last 30 days (the backtest used the prior
    calendar month on Binance - close, not identical).
    Backtest, 1x, half the account per book, 8 slots each: +47..+59%/yr, worst fall 25-34%, half of months flat or down.
    NOT proven forward - this file is the forward test.

What it does: PUBLIC Bitget market data only (ccxt, no keys, no orders). It prints plain-English signals and keeps a
paper account (10,000 PKR at 280 PKR/$, half per book, a position = that book's equity / 8) in logs/pair_paper_state.json,
every trade in logs/pair_paper_trades.csv. Funding is not charged on paper (the backtest charged it; ~0.03%/day).

    python pair_live.py --scan        what fires right now (no state change)
    python pair_live.py --paper       update the paper book once (run hourly)
    python pair_live.py --loop        --paper every hour at :02
    python pair_live.py --status      the paper book
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "logs" / "pair_paper_state.json"
TRADES = ROOT / "logs" / "pair_paper_trades.csv"
TOP_N, SLOTS, START_PKR, PKR = 40, 8, 10_000.0, 280.0
FEE = 0.0012
BOOKS = ("daily", "capit")


def now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def rsi14(c):
    d = np.r_[0.0, np.diff(c)]
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dn > 0, 100 - 100 / (1 + up / dn), 100.0)


class Market:
    """Everything that touches the exchange (a ccxt bitget instance, or a fake in tests)."""

    def __init__(self, ex):
        self.ex = ex

    def crypto(self, s):
        """Crypto perps only, like the backtest: no Bitget real-world-asset contracts (isRwa - stock tokens such as
        SPCX), no gold-backed or stable/fiat perps (market_neutral.NON_CRYPTO)."""
        from backtest.market_neutral import NON_CRYPTO
        m = (getattr(self.ex, "markets", None) or {}).get(s, {})
        if str((m.get("info") or {}).get("isRwa", "")).upper() == "YES":
            return False
        return s.split("/")[0] not in NON_CRYPTO

    def universe(self):
        tick = self.ex.fetch_tickers()
        cand = sorted(((s, (t.get("quoteVolume") or 0.0)) for s, t in tick.items()
                       if s.endswith("/USDT:USDT") and self.crypto(s)), key=lambda x: -x[1])[:120]
        vol30 = {}
        for s, _ in cand:
            d = self.closed(s, "1d", 40)
            if len(d) >= 30:
                vol30[s] = float((d.v * d.c).iloc[-30:].sum())
        return [s for s, _ in sorted(vol30.items(), key=lambda x: -x[1])[:TOP_N]]

    def closed(self, sym, tf, n):
        ms = {"1d": 86_400_000, "4h": 14_400_000}[tf]
        raw = self.ex.fetch_ohlcv(sym, tf, limit=n + 1)
        d = pd.DataFrame(raw, columns=["t", "o", "h", "l", "c", "v"])
        return d[d.t + ms <= now_ms()].reset_index(drop=True)          # closed bars only

    def price(self, sym):
        return float(self.ex.fetch_ticker(sym)["last"])


# ---------------------------------------------------------------- the two rules (on CLOSED bars)

def daily_signal(d):
    """('buy' | 'sell' | None, mean) from the last closed daily bar."""
    if len(d) < 31:
        return None, None
    c = d.c.to_numpy(float)
    mid = pd.Series(c).rolling(30).mean().to_numpy()
    sd = pd.Series(c).rolling(30).std(ddof=0).to_numpy()
    if c[-1] > mid[-1] + 1.5 * sd[-1]:
        return "buy", mid[-1]
    if c[-1] < mid[-1]:
        return "sell", mid[-1]
    return None, mid[-1]


def capit_hits(d):
    """Times (ms) of the 4h bars among the last 6 closed ones where RSI crossed under 20 with quote volume > 2x."""
    if len(d) < 60:
        return []
    c, v = d.c.to_numpy(float), (d.v * d.c).to_numpy(float)
    r = rsi14(c)
    vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
    hit = np.r_[False, (r[:-1] >= 20) & (r[1:] < 20)] & (v > 2 * vavg)
    idx = np.flatnonzero(hit)
    return [int(d.t.iloc[i]) for i in idx if i >= len(d) - 6]


# ---------------------------------------------------------------- paper book

def fresh():
    half = START_PKR / PKR / 2
    return dict(cash={b: half for b in BOOKS}, open={b: {} for b in BOOKS}, started=datetime.now(timezone.utc).isoformat(),
                signals=0, last_daily=None, last_4h=None)


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else fresh()


def save(st):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1))


def book_equity(st, b, prices):
    return st["cash"][b] + sum(p["size"] * prices.get(s, p["entry"]) for s, p in st["open"][b].items())


def record(row):
    new = not TRADES.exists()
    pd.DataFrame([row]).to_csv(TRADES, mode="a", header=new, index=False)


def close_pos(st, b, sym, px, why):
    p = st["open"][b].pop(sym)
    st["cash"][b] += p["size"] * px * (1 - FEE / 2)
    ret = px / p["entry"] - 1 - FEE
    record(dict(book=b, coin=sym, opened=p["t"], closed=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                entry=p["entry"], exit=px, ret_pct=round(ret * 100, 3), why=why))
    return ret


def open_pos(st, b, sym, px, extra):
    eq = st["cash"][b] + sum(p["size"] * p["entry"] for p in st["open"][b].values())
    usd = eq / SLOTS
    if len(st["open"][b]) >= SLOTS or sym in st["open"][b] or usd > st["cash"][b]:
        return False
    st["open"][b][sym] = dict(entry=px, size=usd * (1 - FEE / 2) / px, t=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              **extra)
    st["cash"][b] -= usd
    return True


def cycle(mk, st, say=print, trade=True):
    """One pass: read the market, print what fires, and (trade=True) move the paper book."""
    uni = mk.universe()
    lines = []
    # DAILY book: decided on the last CLOSED daily bar, once per day
    dd = {s: mk.closed(s, "1d", 70) for s in set(uni) | set(st["open"]["daily"])}
    last_day = max((int(d.t.iloc[-1]) for d in dd.values() if len(d)), default=None)
    if last_day is not None and last_day != st.get("last_daily"):
        for s in list(st["open"]["daily"]):
            sig, mean = daily_signal(dd[s])
            age_days = (now_ms() - pd.Timestamp(st["open"]["daily"][s]["t"]).value // 10 ** 6) / 86_400_000
            if sig == "sell" or age_days >= 30:
                px = mk.price(s)
                lines.append(f"DAILY  SELL {s} ~{px:g} ({'close under the 30-day mean' if sig == 'sell' else '30-day cap'})")
                if trade:
                    close_pos(st, "daily", s, px, "mean" if sig == "sell" else "cap")
        for s in uni:
            sig, mean = daily_signal(dd[s])
            if sig == "buy" and s not in st["open"]["daily"]:
                px = mk.price(s)
                lines.append(f"DAILY  BUY  {s} ~{px:g} - exit after a daily close under the 30-day mean (now {mean:g})")
                if trade and open_pos(st, "daily", s, px, {}):
                    st["signals"] += 1
        if trade:
            st["last_daily"] = last_day
    # CAPITULATION book: exits every pass, entries on a new closed 4h bar
    for s, p in list(st["open"]["capit"].items()):
        d4 = mk.closed(s, "4h", 60)
        since = d4[d4.t >= pd.Timestamp(p["t"]).value // 10 ** 6]
        px = mk.price(s)
        age_bars = len(since)
        if len(since) and since.h.max() >= p["entry"] * 1.05:
            lines.append(f"CAPIT  TARGET {s} +5% hit")
            if trade:
                close_pos(st, "capit", s, p["entry"] * 1.05, "target")
        elif (age_bars >= 24 and since.c.iloc[-1] <= p["entry"]) or age_bars >= 42:
            lines.append(f"CAPIT  SELL {s} ~{px:g} ({'not working after 4 days' if age_bars < 42 else '7-day cap'})")
            if trade:
                close_pos(st, "capit", s, px, "not_working" if age_bars < 42 else "cap")
    d4s = {s: mk.closed(s, "4h", 120) for s in uni}
    last_4h = max((int(d.t.iloc[-1]) for d in d4s.values() if len(d)), default=None)
    hits = {s: capit_hits(d) for s, d in d4s.items()}
    cutoff = (last_4h or 0) - 24 * 3_600_000 + 14_400_000            # the 6 closed 4h bars up to the last
    breadth = sorted(s for s, h in hits.items() if any(t >= cutoff for t in h))
    if last_4h is not None and last_4h != st.get("last_4h"):
        fresh_hits = [s for s, h in hits.items() if last_4h in h]
        if fresh_hits and len(breadth) >= 5:
            for s in fresh_hits:
                if s in st["open"]["capit"]:
                    continue
                px = mk.price(s)
                lines.append(f"CAPIT  BUY  {s} ~{px:g} - {len(breadth)} coins capitulated in 24h; target {px * 1.05:g} (+5%); "
                             f"if not in profit after 4 days, sell")
                if trade and open_pos(st, "capit", s, px, {}):
                    st["signals"] += 1
        if trade:
            st["last_4h"] = last_4h
    lines.append(f"(capitulation breadth now: {len(breadth)} coins in 24h; needs 5)")
    for ln in lines:
        say(ln)
    return lines


def status(st, mk=None):
    prices = {}
    if mk is not None:
        for b in BOOKS:
            for s in st["open"][b]:
                prices[s] = mk.price(s)
    tot = sum(book_equity(st, b, prices) for b in BOOKS)
    print(f"PAIR PAPER BOOK since {st['started'][:16]} UTC: {tot * PKR:,.0f} PKR ({(tot * PKR / START_PKR - 1) * 100:+.1f}%), "
          f"signals taken {st['signals']}")
    for b in BOOKS:
        print(f"  {b:6}: equity {book_equity(st, b, prices) * PKR:,.0f} PKR, open {len(st['open'][b])}: "
              + ", ".join(f"{s.split('/')[0]} {(prices.get(s, p['entry']) / p['entry'] - 1) * 100:+.1f}%" for s, p in st["open"][b].items()))
    if TRADES.exists():
        t = pd.read_csv(TRADES)
        for b, g in t.groupby("book"):
            print(f"  closed {b}: {len(g)} trades, win {np.mean(g.ret_pct > 0):.0%}, avg {g.ret_pct.mean():+.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--paper", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    import ccxt
    mk = Market(ccxt.bitget({"enableRateLimit": True, "options": {"defaultType": "swap"}}))
    mk.ex.load_markets()
    if a.status:
        return status(load(), mk)
    if a.scan:
        return cycle(mk, load(), trade=False)
    if a.paper or a.loop:
        while True:
            st = load()
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            cycle(mk, st, say=lambda m: print(f"{stamp} | {m}", flush=True))
            save(st)
            if not a.loop:
                break
            nxt = (time.time() // 3600 + 1) * 3600 + 120
            time.sleep(max(60, nxt - time.time()))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
