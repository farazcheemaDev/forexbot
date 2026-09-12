"""Does the 5-minute level-fade effect exist on instruments we never looked at?

This is the strongest test available right now. Yahoo caps 5-minute history at
60 days, so we cannot get more TIME - but we can get more INSTRUMENTS, and none
of these have ever been loaded by this project. If fading round-number levels
carries information at 5-minute resolution, it should show up on other index
futures too. If it is NQ-only, it was noise.

Levels and costs are scaled to each instrument's price so the test is
comparable: a 25-point level on NQ at 29,458 is 8.5bp, so we use 8.5bp-equivalent
steps everywhere, and charge a round-trip cost of 0.7bp of price (NQ's ~2 points).

    python -m backtest.nasdaq_cross
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.nasdaq_levelfade import (PROX, ROUND_STEPS, RSI_BANDS,  # noqa: E402
                                       SL, TP, lf_signals)
from backtest.rtest import run_r  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
NQ_REF = 29458.0                 # price NQ sat at when we calibrated the levels
COST_FRAC = 0.00007              # ~2 points on NQ, as a fraction of price
MIN_TRADES = 40

SYMBOLS = {
    "NQ=F":  "Nasdaq-100 fut (the original)",
    "ES=F":  "S&P 500 futures",
    "YM=F":  "Dow futures",
    "RTY=F": "Russell 2000 futures",
    "GC=F":  "Gold futures",
    "CL=F":  "Crude oil futures",
    "6E=F":  "EUR/USD futures",
}
GRID = list(itertools.product(ROUND_STEPS, PROX, RSI_BANDS))


def get(sym: str) -> pd.DataFrame:
    f = CACHE / f"{sym.replace('=','')}_5m_60d.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["time"])
    import yfinance as yf
    d = yf.download(sym, interval="5m", period="60d",
                    progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.rename(columns={"Open": "open", "High": "high", "Low": "low",
                          "Close": "close", "Volume": "volume"})
    d = d[["open", "high", "low", "close", "volume"]].dropna()
    d.index = pd.to_datetime(d.index).tz_localize(None)
    d = d.reset_index()
    d.columns = ["time"] + list(d.columns[1:])
    d.to_csv(f, index=False)
    return d


def median_meanR(df: pd.DataFrame) -> tuple[float, int, int]:
    """Median mean-R across the grid, levels/costs scaled to this instrument."""
    price = float(df["close"].mean())
    scale = price / NQ_REF
    cost = price * COST_FRAC
    ms = []
    for step, prox, band in GRID:
        R, _ = run_r(df, lf_signals(df, step * scale, prox * scale, band),
                     SL, TP, fee_bp=0.0, fee_abs=cost)
        if len(R) >= MIN_TRADES:
            ms.append(float(R.mean()))
    if not ms:
        return float("nan"), 0, 0
    return float(np.median(ms)), sum(1 for m in ms if m > 0), len(ms)


def main():
    print("CROSS-INSTRUMENT: level_fade @5m, 60 days, levels+costs scaled to price")
    print(f"{'symbol':7} {'bars':>6} {'price':>9} {'cost':>6} {'medianR':>9} "
          f"{'cfgs+':>8}  instrument")
    res = {}
    for sym, desc in SYMBOLS.items():
        try:
            d = get(sym)
        except Exception as e:
            print(f"{sym:7} fetch failed: {type(e).__name__}")
            continue
        if len(d) < 3000:
            print(f"{sym:7} {len(d):>6} bars — too few, skipped")
            continue
        med, pos, ncfg = median_meanR(d)
        if not np.isfinite(med):
            print(f"{sym:7} no config reached {MIN_TRADES} trades")
            continue
        price = float(d["close"].mean())
        res[sym] = med
        print(f"{sym:7} {len(d):>6} {price:>9.1f} {price*COST_FRAC:>6.2f} "
              f"{med:>+9.4f} {pos:>4}/{ncfg:<3}  {desc}")

    if not res:
        print("\nno instruments returned usable data")
        return
    pos = sum(1 for v in res.values() if v > 0)
    others = {k: v for k, v in res.items() if k != "NQ=F"}
    pos_o = sum(1 for v in others.values() if v > 0)
    print(f"\n  positive overall:            {pos}/{len(res)}")
    print(f"  positive EXCLUDING NQ:       {pos_o}/{len(others)}  "
          f"<- this is the out-of-sample number")
    print("  ->", "effect generalises — worth pursuing"
          if pos_o >= max(2, len(others) * 0.6)
          else "NQ-specific: the 5m result was almost certainly noise")


if __name__ == "__main__":
    main()
