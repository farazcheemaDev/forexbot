"""TRYING TO BREAK THE 16-MARKET TREND RESULT (fx_tsmom.py, logs/fx_tsmom.txt).

fx_tsmom.py: 12-month time-series momentum on 16 markets, monthly, equal risk, ~10% volatility:
+5.5%/yr swap-free after spread (Sharpe 0.56; tune 0.52 / holdout 0.62, split 2017-09), max fall 23%;
WITH Exness swap -1.6%/yr. 6- and 3-month lookbacks were weaker (6-month holdout negative). Before
believing any of it:
  1. WHERE it comes from: FX only, commodities only (gold, silver, oil), equity indices only, bond.
  2. ONE MARKET: drop each market in turn - the range of the result.
  3. ONE YEAR: without its best year.
  4. SIZE: swap-free at 15% and 20% volatility - return and biggest fall.
  5. SMALL CAPITAL: the notional each market needs on $300 at 10% volatility, against Exness's
     minimum position (Standard 0.01 lot, and Standard Cent, 100x smaller).

REGISTERED PREDICTION (2026-09-25, before running): the result leans on commodities and bonds (the
2022 and 2025 trends) more than FX; no single market's removal takes it below +3.5%/yr; without its
best year (2013) it is ~+4.5%/yr; at 20% volatility ~+11%/yr with a ~45% fall; on $300 the FX legs need
~$40-80 of notional each, far under the Standard 0.01 lot ($1,000+) and above the Cent minimum (~$10)
- so it is tradable at $300 only on a Cent account.

    python -m backtest.fx_tsmom_check
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.fx_anomalies import yf_daily  # noqa: E402
from backtest.fx_tsmom import MARKETS, START, VOL_T  # noqa: E402

CLASS = {"EURUSD=X": "FX", "GBPUSD=X": "FX", "JPY=X": "FX", "AUDUSD=X": "FX", "CAD=X": "FX", "CHF=X": "FX",
         "NZDUSD=X": "FX", "GC=F": "commodities", "SI=F": "commodities", "CL=F": "commodities",
         "^GSPC": "indices", "^NDX": "indices", "^DJI": "indices", "^GDAXI": "indices", "^N225": "indices",
         "ZN=F": "bond"}
CUT_DATE = pd.Timestamp("2017-09-01")


def book(C, R, vol, markets, L=12, swap=False):
    """Daily net return of the 12-month TSMOM book on `markets`, before the portfolio scale."""
    past = C / C.shift(21 * L) - 1
    me = C.resample("ME").last().index
    me = me[me >= START]
    days = R.index
    n = len(markets)
    out, prev = [], pd.Series(0.0, index=markets)
    sp = pd.Series({tk: MARKETS[tk][1] for tk in markets}) / 1e4
    sw = pd.Series({tk: MARKETS[tk][2] for tk in markets}) / 1e4
    for a, b in zip(me[:-1], me[1:]):
        ia = days.searchsorted(a, side="right") - 1
        s, v = np.sign(past[markets].iloc[ia]), vol[markets].iloc[ia]
        w = (s * (VOL_T / v) / n).where(np.isfinite(s) & (v > 0), 0.0).fillna(0.0)
        seg = R[markets][(days > days[ia]) & (days <= b)].fillna(0.0)
        if not len(seg):
            continue
        g = seg.mul(w, axis=1).sum(axis=1)
        g.iloc[0] -= ((w - prev).abs() * sp).sum()
        if swap:
            g -= seg.index.to_series().diff().dt.days.fillna(1).to_numpy() * (w.abs() * sw).sum()
        out.append(g)
        prev = w
    return pd.concat(out)


def stats(x, k):
    x = x * k
    c = (1 + x).cumprod()
    return x.mean() * 252 * 100, x.mean() / x.std() * np.sqrt(252), (1 - c / c.cummax()).max() * 100


def main():
    warnings.filterwarnings("ignore")
    C = pd.DataFrame({tk: yf_daily(tk, start="2003-01-01").Close for tk in MARKETS}).sort_index()
    C = C[C.index >= "2003-01-01"].ffill(limit=5)
    R = C.pct_change()
    R = R.where(R.abs() < 0.25)
    vol = R.rolling(60, min_periods=40).std() * np.sqrt(252)
    allm = list(MARKETS)
    base = book(C, R, vol, allm)
    k = VOL_T / (base[base.index < CUT_DATE].std() * np.sqrt(252))
    a, s, dd = stats(base, k)
    print(f"BASE (12-month, 16 markets, swap-free, ~10% vol): {a:+.1f}%/yr, Sharpe {s:.2f}, fall {dd:.0f}%\n")

    print("1. WHERE IT COMES FROM (each class alone, scaled to 10% on its own tune half)")
    for cl in ("FX", "commodities", "indices", "bond"):
        ms = [m for m in allm if CLASS[m] == cl]
        x = book(C, R, vol, ms)
        kk = VOL_T / (x[x.index < CUT_DATE].std() * np.sqrt(252))
        a1, s1, d1 = stats(x, kk)
        _, st, _ = stats(x[x.index < CUT_DATE], kk)
        _, sh, _ = stats(x[x.index >= CUT_DATE], kk)
        print(f"   {cl:<12} {len(ms):>2} markets: {a1:+5.1f}%/yr  Sharpe {s1:+.2f} (tune {st:+.2f} / holdout {sh:+.2f})  fall {d1:.0f}%")

    print("\n2. DROP ONE MARKET AT A TIME (same scale as the base)")
    res = []
    for m in allm:
        x = book(C, R, vol, [z for z in allm if z != m])
        res.append((stats(x, k)[0], stats(x, k)[1], MARKETS[m][0]))
    res.sort()
    lo, hi = res[0], res[-1]
    print(f"   lowest  {lo[0]:+.1f}%/yr (Sharpe {lo[1]:.2f}) without {lo[2]}")
    print(f"   highest {hi[0]:+.1f}%/yr (Sharpe {hi[1]:.2f}) without {hi[2]}")

    print("\n3. WITHOUT ITS BEST YEAR")
    yr = base.groupby(base.index.year).apply(lambda g: (1 + g * k).prod() - 1)
    best = yr.idxmax()
    x = base[base.index.year != best]
    print(f"   best year {best} ({yr[best]*100:+.0f}%); without it {stats(x, k)[0]:+.1f}%/yr, Sharpe {stats(x, k)[1]:.2f}")

    print("\n4. SIZE (swap-free)")
    for vt in (0.10, 0.15, 0.20, 0.30):
        a2, s2, d2 = stats(base, k * vt / VOL_T)
        print(f"   {vt*100:.0f}% volatility: {a2:+.1f}%/yr, fall {d2:.0f}%")

    print("\n5. SMALL CAPITAL: notional per market on $300 at 10% volatility (median month), vs Exness minimums")
    past = C / C.shift(252) - 1
    me = C.resample("ME").last().index
    me = me[me >= "2020-01-01"]
    W = []
    for a_ in me:
        ia = R.index.searchsorted(a_, side="right") - 1
        v = vol.iloc[ia]
        W.append((VOL_T / v / len(allm)).abs() * k)
    W = pd.DataFrame(W).median()
    px = C.iloc[-1]
    # Standard account: FX 0.01 lot = 1,000 base units; gold 0.01 lot = 1 oz; silver 0.01 = 50 oz;
    # oil 0.01 = 1 bbl; indices 0.01 lot = 0.01 x index (USTEC/US500/US30/DE30/JP225, contract 1);
    # 10y note taken as an index-style CFD (0.01 x price). Cent account: 100x smaller.
    std_min = {}
    for tk in allm:
        if CLASS[tk] == "FX":
            base_ccy_usd = 1.0 if tk in ("JPY=X", "CAD=X", "CHF=X") else px[tk]
            std_min[tk] = 1000 * base_ccy_usd
        elif tk == "GC=F":
            std_min[tk] = 1 * px[tk]
        elif tk == "SI=F":
            std_min[tk] = 50 * px[tk]
        elif tk == "CL=F":
            std_min[tk] = 1 * px[tk]
        elif tk == "^N225":
            std_min[tk] = 0.01 * px[tk] / 150
        else:
            std_min[tk] = 0.01 * px[tk]
    print(f"   {'market':<14}{'needs on $300':>14}{'Standard min':>14}{'Cent min':>10}")
    for tk in allm:
        need = W[tk] * 300
        print(f"   {MARKETS[tk][0]:<14}{need:>13.0f}${std_min[tk]:>12,.0f}${std_min[tk]/100:>9,.2f}")


if __name__ == "__main__":
    main()
