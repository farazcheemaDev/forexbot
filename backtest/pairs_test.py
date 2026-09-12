"""Test the NASDAQ <-> GOLD/SILVER pair relationship (the thing he actually trades).

1) How correlated are they (risk-on/risk-off)?
2) Does a spread/z-score mean-reversion pair trade have an edge?
   (long NQ + short gold when the spread is stretched one way, and vice versa)
Uses yfinance so both legs share identical timestamps: NQ=F, GC=F, SI=F.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load(sym, interval, period):
    d = yf.download(sym, interval=interval, period=period, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.reset_index()
    tcol = "Datetime" if "Datetime" in d.columns else "Date"
    return pd.DataFrame({"time": pd.to_datetime(d[tcol]).dt.tz_localize(None),
                         "close": d["Close"].astype(float)}).dropna()


def zscore_pair(a, b, lookback=60, entry_z=2.0, exit_z=0.5, cost_bp=3.0):
    """Trade the spread of log-prices (a - hedge*b). Returns per-trade pnl in
    spread units (bps of notional), net of round-trip cost."""
    df = pd.merge(a.rename(columns={"close": "a"}), b.rename(columns={"close": "b"}), on="time")
    if len(df) < lookback * 3:
        return None, df
    la, lb = np.log(df.a), np.log(df.b)
    # rolling hedge ratio via covariance/variance
    cov = la.rolling(lookback).cov(lb)
    var = lb.rolling(lookback).var()
    hedge = (cov / var).clip(-3, 3)
    spread = la - hedge * lb
    m = spread.rolling(lookback).mean()
    s = spread.rolling(lookback).std()
    z = (spread - m) / s

    pos, entry, pnl = 0, 0.0, []
    for i in range(len(df)):
        if not np.isfinite(z.iloc[i]):
            continue
        if pos == 0:
            if z.iloc[i] > entry_z:
                pos, entry = -1, spread.iloc[i]      # spread too high -> short spread
            elif z.iloc[i] < -entry_z:
                pos, entry = 1, spread.iloc[i]
        else:
            if abs(z.iloc[i]) < exit_z or (pos == 1 and z.iloc[i] > entry_z) or (pos == -1 and z.iloc[i] < -entry_z):
                ret = (spread.iloc[i] - entry) * pos * 10000        # bps
                pnl.append(ret - cost_bp * 2)
                pos = 0
    return np.array(pnl), df


def report(name, pnl):
    if pnl is None or len(pnl) < 15:
        print(f"  {name:28} too few trades ({0 if pnl is None else len(pnl)})"); return
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    pf = gw / gl if gl > 0 else 99
    # split-half robustness
    h = len(pnl) // 2
    pf1 = (lambda x: x[x > 0].sum() / max(-x[x < 0].sum(), 1e-9))(pnl[:h])
    pf2 = (lambda x: x[x > 0].sum() / max(-x[x < 0].sum(), 1e-9))(pnl[h:])
    print(f"  {name:28} n={len(pnl):>4} pf={pf:>5.2f} win={(pnl>0).mean()*100:>5.1f}% "
          f"exp={pnl.mean():>7.2f}bp | half1_pf={pf1:.2f} half2_pf={pf2:.2f} "
          f"{'<< ROBUST' if pf > 1.1 and pf1 > 1 and pf2 > 1 else ''}")


def main():
    print("=== NASDAQ vs GOLD/SILVER: correlation ===")
    for interval, period in [("1h", "730d"), ("1d", "5y")]:
        nq = load("NQ=F", interval, period)
        gc = load("GC=F", interval, period)
        si = load("SI=F", interval, period)
        m = nq.rename(columns={"close": "nq"}).merge(
            gc.rename(columns={"close": "gc"}), on="time").merge(
            si.rename(columns={"close": "si"}), on="time")
        r = m[["nq", "gc", "si"]].pct_change().dropna()
        c = r.corr()
        print(f"  {interval} ({len(m)} bars): corr(NQ,GOLD)={c.loc['nq','gc']:+.3f}  "
              f"corr(NQ,SILVER)={c.loc['nq','si']:+.3f}  corr(GOLD,SILVER)={c.loc['gc','si']:+.3f}")

    print("\n=== PAIR SPREAD mean-reversion (z-score), net of cost ===")
    for interval, period, lb in [("1h", "730d", 60), ("1h", "730d", 120), ("1d", "5y", 40)]:
        nq = load("NQ=F", interval, period)
        gc = load("GC=F", interval, period)
        si = load("SI=F", interval, period)
        for nm, other in (("NQ~GOLD", gc), ("NQ~SILVER", si)):
            for ez in (1.5, 2.0, 2.5):
                pnl, _ = zscore_pair(nq, other, lookback=lb, entry_z=ez)
                report(f"{interval} lb={lb} {nm} z={ez}", pnl)


if __name__ == "__main__":
    main()
