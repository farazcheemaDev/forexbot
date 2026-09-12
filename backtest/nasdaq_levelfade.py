"""The human scalper's strategy, tested on NASDAQ — the market he actually traded.

BACKGROUND. We reverse-engineered this from a screen recording plus 55
screenshots of a real trader running someone else's ~$1,800 account on NASDAQ,
reportedly ~10%/month over ~7 months. What we extracted: fades at round-number
levels roughly 25 index points apart and at prior-day high/low, with an RSI
filter, holding 4 to 36 SECONDS.

WHY THE EARLIER TEST WAS INVALID. The crypto holdout sweep scored level_fade at
-0.1004R and called it dead. That test was wrong on two counts: wrong market
(BTC/ETH, not an index) and wrong timeframe (1-hour bars for a strategy that
holds seconds). This file fixes the market and gets as close on timeframe as
free data allows.

DATA. NQ=F (Nasdaq-100 futures) via yfinance, which caps intraday history:
    5m  -> 60 days   (closest to his holding period we can reach)
    1h  -> 730 days  (long enough to split into two eras)
None of this data has EVER been loaded by this project before, so all of it is
virgin. Each timeframe is still split in half and a config must work on BOTH
halves - the fake cross-window consistency produced by the ATR look-ahead is
exactly what that check is for.

THE TIMEFRAME GAP IS NOT CLOSABLE HERE. He held 4-36 seconds; the finest bar we
can get is 5 minutes - 8 to 75 times his holding period. If his edge lives in
sub-minute order-flow, no free data can test it and this file cannot refute him.
What it CAN test is whether round-number levels carry predictive information on
NASDAQ at the timeframes we can see.

COSTS. Index spreads are quoted in points, not basis points, so they are charged
via fee_abs. Exness USTEC sits around 1-2 points; NQ futures are tighter. We
sweep 0 / 1 / 2 / 4 points because for a scalper the spread IS the thesis - his
own reported edge only reconciled after execution costs.

    python -m backtest.nasdaq_levelfade
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import FILTERS, gen_signals  # noqa: E402
from backtest.rtest import run_r, stats  # noqa: E402
from bot.strategies.level_fade import LevelFade  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
CACHE.mkdir(parents=True, exist_ok=True)
SL, TP = 2.0, 3.0
SPREADS = [0.0, 1.0, 2.0, 4.0]          # index points, round trip

# his levels were ~25 points apart; neighbours included to test robustness
ROUND_STEPS = [10.0, 25.0, 50.0, 100.0]
PROX = [3.0, 6.0, 10.0]
RSI_BANDS = [(32.0, 68.0), (25.0, 75.0)]

# comparison families, to see whether ANYTHING works on NASDAQ
OTHERS = {
    "rsi_mom":  [(7, 40, 60), (14, 40, 60)],
    "bb_break": [(20, 2.0), (30, 1.5)],
    "donchian": [(20,), (55,)],
    "bb_rev":   [(20, 2.0)],
    "rsi_rev":  [(14, 30, 70)],
}


def fetch_nq(interval: str, period: str) -> pd.DataFrame:
    f = CACHE / f"NQ_{interval}_{period}.csv"
    if f.exists():
        d = pd.read_csv(f, parse_dates=["time"])
        return d
    import yfinance as yf
    d = yf.download("NQ=F", interval=interval, period=period,
                    progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.rename(columns={"Open": "open", "High": "high", "Low": "low",
                          "Close": "close", "Volume": "volume"})
    d = d[["open", "high", "low", "close", "volume"]].dropna()
    d.index = pd.to_datetime(d.index).tz_localize(None)
    d = d.reset_index().rename(columns={d.index.name or "index": "time",
                                        "Datetime": "time", "Date": "time"})
    if "time" not in d.columns:
        d = d.rename(columns={d.columns[0]: "time"})
    d.to_csv(f, index=False)
    return d


def lf_signals(df, round_step, prox, band):
    lo, hi = band
    return LevelFade(round_step=round_step, prox=prox, rsi_lo=lo, rsi_hi=hi,
                     use_prior_day=True).signals(df)


def run_one(df, sig, spread):
    R, idx = run_r(df, sig, SL, TP, fee_bp=0.0, fee_abs=spread)
    if len(R) < 25:
        return None
    return stats(R, df["time"].iloc[idx])


def halves(df):
    m = len(df) // 2
    return df.iloc[:m].reset_index(drop=True), df.iloc[m:].reset_index(drop=True)


def section(tf, df):
    print(f"\n{'='*94}")
    print(f"NASDAQ (NQ=F) {tf} — {len(df)} bars  "
          f"{df.time.iloc[0]} -> {df.time.iloc[-1]}")
    a = float((df["high"] - df["low"]).mean())
    print(f"mean bar range {a:.1f} pts | a 25-pt level is "
          f"{25/float(df['close'].mean())*10000:.1f}bp of price")
    print(f"{'='*94}")
    h1, h2 = halves(df)

    print(f"\nLEVEL FADE (his strategy). Both halves must work.")
    print(f"{'step':>6} {'prox':>5} {'rsi':>9} {'sprd':>5} "
          f"{'n1':>5} {'meanR1':>8} {'n2':>5} {'meanR2':>8} {'win%':>6}  consistent?")
    best = None
    for rs, px, band in itertools.product(ROUND_STEPS, PROX, RSI_BANDS):
        for sp in SPREADS:
            s1 = run_one(h1, lf_signals(h1, rs, px, band), sp)
            s2 = run_one(h2, lf_signals(h2, rs, px, band), sp)
            if not s1 or not s2:
                continue
            both = s1["meanR"] > 0 and s2["meanR"] > 0
            if sp in (0.0, 2.0):        # print only the endpoints to stay readable
                print(f"{rs:>6.0f} {px:>5.0f} {str(band):>9} {sp:>5.1f} "
                      f"{s1['n']:>5} {s1['meanR']:>+8.4f} {s2['n']:>5} "
                      f"{s2['meanR']:>+8.4f} {s2['win']*100:>6.1f}  "
                      f"{'YES' if both else 'no'}")
            if both and (best is None or min(s1["meanR"], s2["meanR"]) > best[0]):
                best = (min(s1["meanR"], s2["meanR"]), rs, px, band, sp)

    print(f"\n  best level_fade config working on BOTH halves: "
          f"{'NONE' if best is None else f'step={best[1]:.0f} prox={best[2]:.0f} band={best[3]} spread={best[4]} -> worst-half meanR {best[0]:+.4f}'}")

    print(f"\nOTHER FAMILIES on NASDAQ {tf} (spread 2.0 pts, both halves):")
    print(f"{'family':10} {'params':14} {'n1':>5} {'meanR1':>8} {'n2':>5} "
          f"{'meanR2':>8}  consistent?")
    for fam, plist in OTHERS.items():
        for p in plist:
            s1 = run_one(h1, FILTERS["none"](h1, gen_signals(h1, fam, p)), 2.0)
            s2 = run_one(h2, FILTERS["none"](h2, gen_signals(h2, fam, p)), 2.0)
            if not s1 or not s2:
                continue
            both = s1["meanR"] > 0 and s2["meanR"] > 0
            print(f"{fam:10} {str(p):14} {s1['n']:>5} {s1['meanR']:>+8.4f} "
                  f"{s2['n']:>5} {s2['meanR']:>+8.4f}  {'YES' if both else 'no'}")


def main():
    for tf, per in (("5m", "60d"), ("1h", "730d")):
        try:
            df = fetch_nq(tf, per)
        except Exception as e:
            print(f"{tf}: fetch failed {type(e).__name__}: {e}")
            continue
        if len(df) < 2000:
            print(f"{tf}: only {len(df)} bars - skipped")
            continue
        section(tf, df)

    print(f"\n{'='*94}")
    print("READ THIS BEFORE CONCLUDING ANYTHING ABOUT HIS TRADING")
    print(f"{'='*94}")
    print("He held 4-36 SECONDS. The finest bar available free is 5 minutes.")
    print("A negative result here means round-number levels carry no edge at")
    print("5-minute-and-slower resolution. It does NOT refute his execution,")
    print("which lived in a timeframe this data cannot see.")


if __name__ == "__main__":
    main()
