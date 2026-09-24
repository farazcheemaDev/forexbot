"""TRYING TO BREAK THE WICK-BID RESULT (crash_buy.py, logs/crash_buy.txt).

crash_buy.py: a resting buy k% below the previous hour's close, sold at the fill hour's close, made
+2.2% / +4.8% / +7.1% per fill (k 10 / 15 / 20%), positive in EVERY year 2020-2026, holdout +1.2 /
+2.1 / +2.5%; as a portfolio ~+60%/yr at k 15%, 5% a fill. Four ways it could be flattering:

  1. CAPACITY. The portfolio skipped fills once exposure hit 100%, but a crash fills EVERY resting
     bid in the book at once - you cannot choose. Honest version: bids on the top-N coins, each 1/N
     of equity, so total resting size is 100% by construction and nothing is skipped (N = 10/20/40).
  2. EXIT SLIPPAGE. Selling in a crash hour costs more than a quiet market: extra 30 / 60 / 100bp.
  3. A FEW DAYS. Remove the three biggest days, then every day in 2021.
  4. THE VENUE. The wicks are Binance's; the account trades on Bitget. Bitget's own 1h candles for
     its most liquid USDT perps (public history endpoint, as far back as it serves) get the same test,
     and the same coins on Binance over the same dates are shown beside it.

REGISTERED PREDICTION (2026-09-24, before running): 1 keeps it positive on both halves at N = 20/40,
lower than the skipping version; 2 at 60bp still positive for k 15-20%; 3 positive without the top days
and without 2021; 4 Bitget's wicks are shallower (fewer fills) and the per-fill return is positive but
smaller than Binance's on the same dates.

    python -m backtest.crash_buy_check
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.crash_buy import CUT, PEN, fills_for, load_1h  # noqa: E402
from backtest.market_neutral import drop_non_crypto  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

FEE = 8e-4


def honest(F, k, f, extra=0.0, drop_days=()):
    """Every fill taken at f of equity (entry-sized), no cap needed: N coins x f = 100% at most.
    P&L booked at the fill hour's close. Returns the daily curve."""
    x = F[(F.k == k) & (F.side == "buy")].copy()
    if drop_days:
        x = x[~x.t.dt.normalize().isin(pd.DatetimeIndex(drop_days))]
    x = x.sort_values("t")
    eq, pts = 1.0, []
    for t, g in x.groupby("t"):                      # all bids that filled in the same hour
        eq *= 1 + f * (g["close"] - FEE - extra).sum()
        eq = max(eq, 0.0)
        pts.append((t, eq))
    if not pts:
        return None
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    return s.resample("D").last().ffill()


def rate(c):
    if c is None or len(c) < 2:
        return np.nan
    y = (c.index[-1] - c.index[0]).days / 365.25
    return ((c.iloc[-1] / c.iloc[0]) ** (1 / max(y, 0.1)) - 1) * 100


def top_by_volume(elig, n):
    """{sym: months} keeping, for each month, only the top-n of the PIT top-40 by the prior month's
    volume - eligibility(n) exactly, intersected with the crypto filter."""
    return drop_non_crypto(eligibility(n))


def bitget_1h(sym, pages=40):
    """Bitget USDT-M 1h candles, newest backwards, as far as the public history endpoint serves."""
    out, end = [], None
    for _ in range(pages):
        u = (f"https://api.bitget.com/api/v2/mix/market/history-candles?symbol={sym}&productType=USDT-FUTURES"
             f"&granularity=1H&limit=200" + (f"&endTime={end}" if end else ""))
        try:
            d = json.load(urllib.request.urlopen(u, timeout=20)).get("data") or []
        except Exception:
            break
        if not d:
            break
        out += d
        end = int(min(int(r[0]) for r in d)) - 1
        time.sleep(0.15)
    if not out:
        return None
    df = pd.DataFrame(out, columns=["ts", "open", "high", "low", "close", "vol", "qvol"][:len(out[0])])
    df["time"] = pd.to_datetime(df.ts.astype("int64"), unit="ms").astype("datetime64[ns]")
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    return df.drop_duplicates("time").sort_values("time")[["time", "open", "high", "low", "close"]].reset_index(drop=True)


def main():
    rows = {}
    for n in (10, 20, 40):
        el = top_by_volume(None, n)
        r = []
        for s in sorted(x for x, ms in el.items() if ms):
            d = load_1h(s)
            if d is not None:
                r += fills_for(s, d, el[s], d.time.iloc[0], "buy")
        rows[n] = pd.DataFrame(r)

    print("1. CAPACITY: bids on the top-N coins, each 1/N of equity, every fill taken, sold at the fill hour's close")
    print(f"   {'N':>4}{'k':>5}{'fills/yr':>10}{'CAGR':>9}{'TUNE':>9}{'HOLD':>9}{'worst day':>11}{'max DD':>8}")
    for n, F in rows.items():
        yrs = (F.t.max() - F.t.min()).days / 365.25
        for k in (0.10, 0.15, 0.20):
            c = honest(F, k, 1 / n)
            print(f"   {n:>4}{k*100:>4.0f}%{len(F[F.k == k]) / yrs:>10.0f}{rate(c):>+8.1f}%{rate(c[c.index < CUT]):>+8.1f}%"
                  f"{rate(c[c.index >= CUT]):>+8.1f}%{c.pct_change().min()*100:>+10.1f}%{(1 - c / c.cummax()).max()*100:>7.0f}%")

    F = rows[20]
    print("\n2. EXIT SLIPPAGE in the crash hour (N 20, on top of 8bp fees): CAGR, TUNE / HOLD")
    for k in (0.10, 0.15, 0.20):
        cells = []
        for ex in (0.0, 0.003, 0.006, 0.010):
            c = honest(F, k, 1 / 20, extra=ex)
            cells.append(f"+{ex*1e4:>3.0f}bp: {rate(c):+6.1f}% ({rate(c[c.index < CUT]):+.1f} / {rate(c[c.index >= CUT]):+.1f})")
        print(f"   k {k*100:.0f}%  " + " | ".join(cells))

    print("\n3. WITHOUT THE BIG DAYS (N 20)")
    for k in (0.10, 0.15, 0.20):
        x = F[F.k == k]
        day = x.groupby(x.t.dt.normalize())["close"].sum().sort_values(ascending=False)
        top3 = list(day.index[:3])
        no21 = list(x[x.t.dt.year == 2021].t.dt.normalize().unique())
        print(f"   k {k*100:.0f}%: all {rate(honest(F, k, 0.05)):+.1f}%/yr | without top-3 days ({', '.join(f'{d:%Y-%m-%d}' for d in top3)}) "
              f"{rate(honest(F, k, 0.05, drop_days=top3)):+.1f}%/yr | without every 2021 fill {rate(honest(F, k, 0.05, drop_days=no21)):+.1f}%/yr")

    print("\n4. THE VENUE: Bitget's own 1h candles vs Binance's, same coins, same dates, sold at the fill hour's close")
    coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "SUIUSDT",
             "LTCUSDT", "DOTUSDT", "NEARUSDT", "ARBUSDT", "WLDUSDT", "ENAUSDT", "BNBUSDT", "TRXUSDT", "UNIUSDT",
             "AAVEUSDT", "PEPEUSDT"]
    bg, bn = [], []
    span = None
    for s in coins:
        b = bitget_1h(s)
        a = load_1h(s)
        if b is None or a is None or len(b) < 500:
            continue
        lo, hi = max(b.time.iloc[0], a.time.iloc[0]), min(b.time.iloc[-1], a.time.iloc[-1])
        b = b[(b.time >= lo) & (b.time <= hi)].reset_index(drop=True)
        a = a[(a.time >= lo) & (a.time <= hi)].reset_index(drop=True)
        span = (lo, hi) if span is None else (min(span[0], lo), max(span[1], hi))
        months = set(pd.DatetimeIndex(b.time).strftime("%Y-%m"))
        early = b.time.iloc[0] - pd.Timedelta(days=60)            # the age rule is irrelevant here
        bg += fills_for(s, b, months, early, "buy")
        bn += fills_for(s, a, months, early, "buy")
    G, N = pd.DataFrame(bg), pd.DataFrame(bn)
    print(f"   {len(coins)} coins requested; Bitget history served {span[0]:%Y-%m-%d} .. {span[1]:%Y-%m-%d}" if span else "   no Bitget data")
    for k in (0.05, 0.075, 0.10, 0.15):
        pass
    for k in (0.10, 0.15, 0.20):
        g, n = G[G.k == k] if len(G) else G, N[N.k == k] if len(N) else N
        gm = g["close"].mean() * 100 if len(g) else float("nan")
        nm = n["close"].mean() * 100 if len(n) else float("nan")
        print(f"   k {k*100:.0f}%: Bitget {len(g):>4} fills, mean {gm:+.2f}% per fill | Binance {len(n):>4} fills, mean {nm:+.2f}%")


if __name__ == "__main__":
    main()
