"""CROSS-SECTIONAL FUNDING DISLOCATION — a strategy designed from our own results.

WHY THIS SHAPE, DERIVED FROM WHAT WE MEASURED
---------------------------------------------
  1. Directional prediction from price is dead here: 18 families, 9 coins, 4 years
     of untouched data, ~2.6M trades, nothing survived.
  2. Fees set the SIGN, not the size. Breakeven was 6-8.5bp round trip and Bitget
     taker is ~12bp. => turnover must be LOW.
  3. Correlation was the true ceiling. 20 crypto coins behaved like ~1.6
     independent bets, which is why 10%/month looked unreachable. The structural
     cure for correlation is MARKET NEUTRALITY: long one coin, short another, and
     the shared market factor cancels.
  4. The only thing that nearly survived was RELATIVE (intramarket difference:
     MAR 1.36, passed three gates, failed MCPT). That direction deserves a
     better-motivated instrument than a moving-average spread.
  5. Funding rates are data, not chart patterns - and we measured real
     dislocations (0.35-0.58% per 8h on small alts, vs <0.1% on majors).

THE IDEA
--------
A perp's funding rate is a direct readout of LEVERAGED CROWDING, published by the
exchange. Positive funding = longs are crowded and paying to stay there. It is not
a price prediction and not a pattern anyone draws on a candle chart.

Each settlement, rank the universe by funding:
    SHORT the most-positive-funding coins   (crowded longs pay us)
    LONG  the most-negative-funding coins   (crowded shorts pay us)
    equal dollar weight   -> market neutral

TWO INDEPENDENT RETURN SOURCES FROM ONE TRADE
    (a) CARRY: we receive funding on BOTH legs, by construction.
    (b) CONVERGENCE: if crowded positioning unwinds, the spread moves our way.
Neither requires forecasting the market's direction.

WHAT IS TESTED HERE
-------------------
  * raw funding rank vs Z-SCORED funding. Z-scoring matters because some coins sit
    persistently negative (APT -12.9%/yr, ATOM -10.4%/yr measured) - a raw rank
    would just pick the same coins forever, which is carry, not dislocation.
  * holding periods 8h / 24h / 72h, because fees are the known killer.
  * CORRELATION TO BTC of the resulting equity curve. This is the whole point: if
    it really is market neutral, several such strategies would be INDEPENDENT
    bets, which is exactly what our correlation math says we need.
  * split into two halves; a candidate must work in both.

    python -m backtest.funding_xs
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

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
CACHE.mkdir(parents=True, exist_ok=True)

UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
            "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT",
            "FILUSDT", "NEARUSDT", "ETCUSDT", "UNIUSDT", "AAVEUSDT", "ARBUSDT",
            "OPUSDT", "APTUSDT", "SUIUSDT", "XLMUSDT", "BCHUSDT", "TRXUSDT"]
FEE_BP = 12.0          # taker round trip per leg; maker would be ~4
Z_LOOKBACK = 90        # periods (8h each) for the funding z-score


def funding_history(sym: str) -> pd.DataFrame | None:
    f = CACHE / f"funding_{sym}.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["t"])
    out, end = [], int(time.time() * 1000)
    for _ in range(4):
        u = (f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}"
             f"&limit=1000&endTime={end}")
        try:
            r = json.load(urllib.request.urlopen(u, timeout=25))
        except Exception:
            return None
        if not r:
            break
        out = r + out
        end = int(r[0]["fundingTime"]) - 1
        time.sleep(0.25)
    if not out:
        return None
    d = pd.DataFrame(out)
    d["fundingRate"] = d["fundingRate"].astype(float)
    d["t"] = pd.to_datetime(d["fundingTime"], unit="ms")
    d = d[["t", "fundingRate"]].drop_duplicates("t").sort_values("t")
    d.to_csv(f, index=False)
    return d.reset_index(drop=True)


def mark_prices(sym: str) -> pd.DataFrame | None:
    """8h closes aligned to funding settlements."""
    f = CACHE / f"px8h_{sym}.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["t"])
    out, end = [], int(time.time() * 1000)
    for _ in range(3):
        u = (f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}"
             f"&interval=8h&limit=1000&endTime={end}")
        try:
            r = json.load(urllib.request.urlopen(u, timeout=25))
        except Exception:
            return None
        if not r:
            break
        out = r + out
        end = int(r[0][0]) - 1
        time.sleep(0.25)
    if not out:
        return None
    d = pd.DataFrame([{"t": pd.to_datetime(k[0], unit="ms"),
                       "close": float(k[4])} for k in out])
    d = d.drop_duplicates("t").sort_values("t")
    d.to_csv(f, index=False)
    return d.reset_index(drop=True)


def build_panels():
    fr, px = {}, {}
    for s in UNIVERSE:
        f = funding_history(s)
        p = mark_prices(s)
        if f is not None and p is not None and len(f) > 600 and len(p) > 600:
            fr[s] = f.set_index("t")["fundingRate"]
            px[s] = p.set_index("t")["close"]
    F = pd.DataFrame(fr).sort_index()
    P = pd.DataFrame(px).sort_index()
    common = F.index.intersection(P.index)
    return F.loc[common], P.loc[common]


def simulate(F: pd.DataFrame, P: pd.DataFrame, k: int, hold: int,
             use_z: bool, fee_bp: float = FEE_BP) -> dict | None:
    """Rank by funding each `hold` periods; short top-k, long bottom-k, equal $.

    Return per period = price move of the basket + funding received on both legs.
    Costs charged on every rebalance, on both legs.
    """
    ret = np.log(P).diff().shift(-1)        # period t -> t+1 return, per coin
    sig = (F - F.rolling(Z_LOOKBACK).mean()) / F.rolling(Z_LOOKBACK).std() \
        if use_z else F
    rows = []
    i = Z_LOOKBACK + 1 if use_z else 1
    n = len(F)
    while i < n - hold:
        s = sig.iloc[i].dropna()
        if len(s) < 2 * k + 2:
            i += hold
            continue
        shorts = s.nlargest(k).index      # crowded longs -> we short, we receive
        longs = s.nsmallest(k).index      # crowded shorts -> we long, we receive
        pnl = 0.0
        for h in range(hold):
            j = i + h
            if j >= n - 1:
                break
            rr = ret.iloc[j]
            ff = F.iloc[j]
            for c in longs:
                if pd.notna(rr.get(c)) and pd.notna(ff.get(c)):
                    pnl += (rr[c] - ff[c]) / (2 * k)     # long pays funding if +
            for c in shorts:
                if pd.notna(rr.get(c)) and pd.notna(ff.get(c)):
                    pnl += (-rr[c] + ff[c]) / (2 * k)    # short receives if +
        pnl -= 2 * fee_bp / 10000.0        # both legs, in and out
        rows.append((F.index[i], pnl))
        i += hold
    if len(rows) < 40:
        return None
    t = [r[0] for r in rows]
    r = np.array([r[1] for r in rows])
    yrs = (t[-1] - t[0]).days / 365.25
    eq = np.cumprod(1 + r)
    peak = np.maximum.accumulate(eq)
    dd = float(((peak - eq) / peak).max() * 100)
    cagr = float((eq[-1] ** (1 / yrs) - 1) * 100) if eq[-1] > 0 else -100
    return dict(n=len(r), mean_bp=float(r.mean() * 1e4), total=float(eq[-1]),
                cagr=cagr, dd=dd, mar=(cagr / dd if dd > 0 else np.inf),
                sharpe=float(r.mean() / r.std() * np.sqrt(len(r) / yrs))
                if r.std() > 0 else 0.0,
                win=float((r > 0).mean()), times=t, rets=r)


def main():
    print("Building funding + 8h price panels (cached after first run)...")
    F, P = build_panels()
    print(f"  {F.shape[1]} coins, {len(F)} 8h settlements "
          f"({F.index.min().date()} .. {F.index.max().date()})\n")
    mid = len(F) // 2
    halves = {"1st half": (F.iloc[:mid], P.iloc[:mid]),
              "2nd half": (F.iloc[mid:], P.iloc[mid:]),
              "FULL": (F, P)}

    print(f"{'signal':8} {'k':>3} {'hold':>5} | " +
          " | ".join(f"{h:>22}" for h in ("1st half", "2nd half")) +
          " | FULL")
    print(f"{'':8} {'':>3} {'':>5} | " +
          " | ".join(f"{'n':>5}{'meanbp':>8}{'CAGR%':>9}" for _ in range(2)) +
          " |  CAGR%   maxDD%   MAR  Sharpe")
    best = []
    for use_z in (False, True):
        for k in (2, 3, 5):
            for hold in (1, 3, 9):        # 8h, 24h, 72h
                cells = {}
                for label, (f, p) in halves.items():
                    cells[label] = simulate(f, p, k, hold, use_z)
                if not all(cells.values()):
                    continue
                a, b, full = cells["1st half"], cells["2nd half"], cells["FULL"]
                name = "zscore" if use_z else "raw"
                print(f"{name:8} {k:>3} {hold*8:>4}h | "
                      f"{a['n']:>5}{a['mean_bp']:>+8.1f}{a['cagr']:>+9.1f} | "
                      f"{b['n']:>5}{b['mean_bp']:>+8.1f}{b['cagr']:>+9.1f} | "
                      f"{full['cagr']:>+7.1f} {full['dd']:>7.1f} "
                      f"{full['mar']:>6.2f} {full['sharpe']:>6.2f}")
                if a["cagr"] > 0 and b["cagr"] > 0:
                    best.append((full["mar"], name, k, hold, full))

    if not best:
        print("\nNothing positive in BOTH halves. Strategy rejected on first look.")
        return
    best.sort(reverse=True, key=lambda x: x[0])
    mar, name, k, hold, full = best[0]
    print(f"\nBEST consistent config: {name} k={k} hold={hold*8}h")
    print(f"  CAGR {full['cagr']:+.1f}%  maxDD {full['dd']:.1f}%  MAR {mar:.2f}  "
          f"Sharpe {full['sharpe']:.2f}  win rate {full['win']*100:.1f}%")

    # THE decisive check: is it actually market neutral?
    btc = np.log(P["BTCUSDT"]).diff()
    ser = pd.Series(full["rets"], index=full["times"])
    btc_agg = btc.reindex(ser.index).fillna(0)
    win = max(1, hold)
    btc_h = np.log(P["BTCUSDT"]).diff(win).reindex(ser.index)
    c = float(ser.corr(btc_h))
    print(f"\n  correlation of strategy returns to BTC = {c:+.3f}")
    print(f"  -> {'MARKET NEUTRAL: this is an INDEPENDENT bet, which is what the' if abs(c) < 0.3 else 'NOT market neutral - it is a disguised directional bet'}")
    if abs(c) < 0.3:
        print(f"     correlation maths said we need. 20 coins gave ~1.6 effective")
        print(f"     bets; strategies like this one ADD effective bets instead.")


if __name__ == "__main__":
    main()
