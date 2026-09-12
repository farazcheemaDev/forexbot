"""VOLUME SPREAD ANALYSIS — the first use of VOLUME in this entire project.

WHY IT IS WORTH A LOOK
----------------------
All 393 configs across 18 families used PRICE ONLY. Volume is the most obvious
free non-price input available and we never touched it. When meta-labeling ran,
normalised volume came out as the #2 feature of 10 - not enough to save that
approach, but enough to justify testing volume directly.

THE INDICATOR (after neurotrader888/VSAIndicator)
-------------------------------------------------
    norm_range  = (high - low) / ATR(168)
    norm_volume = volume / median_volume(168)

Regress norm_range on norm_volume over a rolling 168-bar window. The indicator is
the RESIDUAL:

    dev = norm_range - (intercept + slope * norm_volume)

So it answers: "was this candle's range bigger or smaller than its volume
justifies?"

    dev << 0   lots of volume, little movement  -> ABSORPTION. Someone large is
               soaking up the flow without letting price run.
    dev >> 0   big move on thin volume          -> NO OPPOSITION, a move nobody
               is defending, often unsustainable.

If the regression is degenerate (slope <= 0 or weak fit, r < 0.2) the indicator
returns 0 rather than a meaningless residual.

IMPLEMENTATION NOTES
--------------------
  * VECTORISED. The reference runs scipy.linregress in a Python loop, one call
    per bar (~36,000 calls per asset). Rolling sums give identical slope /
    intercept / r in one pass, which makes a 9-asset x 2-window sweep feasible.
  * SHIFTED by 1. ATR(168), the median, the range and the regression window all
    include the current bar, so the raw indicator is only knowable at that bar's
    close. Trading on it unshifted is the exact look-ahead that has bitten this
    project three times today.

TESTED TWO WAYS
---------------
  1. as a FILTER on the momentum signals we already measured
  2. as a STANDALONE signal (fade a thin-volume move, follow absorption)
both on the development window AND the untouched holdout, per coin.

    python -m backtest.vsa
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.holdout_sweep import USED_DAYS, signals_for  # noqa: E402
from backtest.mass_search import FILTERS, fetch  # noqa: E402
from backtest.rtest import run_r, stats  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
          "AVAXUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]
NORM_LB = 168
SL, TP, FEE_BP = 2.0, 3.0, 10.0
MIN_R = 0.20          # regression must explain something, else dev = 0


def vsa_indicator(df: pd.DataFrame, norm_lookback: int = NORM_LB) -> pd.Series:
    """Vectorised rolling-regression residual. Shift before use — see docstring."""
    a = atr_ind(df, norm_lookback)
    vol_med = df["volume"].rolling(norm_lookback).median()
    y = ((df["high"] - df["low"]) / a).to_numpy(float)          # norm_range
    x = (df["volume"] / vol_med).to_numpy(float)                # norm_volume

    sx = pd.Series(x); sy = pd.Series(y)
    n = norm_lookback
    Sx = sx.rolling(n).sum(); Sy = sy.rolling(n).sum()
    Sxx = (sx * sx).rolling(n).sum(); Syy = (sy * sy).rolling(n).sum()
    Sxy = (sx * sy).rolling(n).sum()

    den = n * Sxx - Sx * Sx
    slope = (n * Sxy - Sx * Sy) / den.replace(0, np.nan)
    intercept = (Sy - slope * Sx) / n
    rnum = n * Sxy - Sx * Sy
    rden = np.sqrt((n * Sxx - Sx * Sx) * (n * Syy - Sy * Sy))
    r = rnum / rden.replace(0, np.nan)

    pred = intercept + slope * sx
    dev = sy - pred
    dev[(slope <= 0) | (r < MIN_R) | ~np.isfinite(dev)] = 0.0
    dev.iloc[: norm_lookback * 2] = np.nan          # match reference warm-up
    return pd.Series(dev.to_numpy(), index=df.index)


def summarise(R, label):
    st = stats(R)
    if st is None or st["n"] < 30:
        return None
    return dict(label=label, n=st["n"], meanR=st["meanR"], win=st["win"],
                pf=st["pf"])


def main():
    print("VSA — Volume Spread Analysis. First use of volume in this project.\n")
    data = {}
    for a in ASSETS:
        try:
            d = fetch(a, "1h", 2400)
        except Exception:
            continue
        cut = d.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
        hold = d[d.time < cut].reset_index(drop=True)
        used = d[d.time >= cut].reset_index(drop=True)
        if len(hold) < 3000:
            continue
        data[a] = (hold, used)
    print(f"{len(data)} assets | holdout + dev windows | cost {FEE_BP}bp\n")

    # sanity: what does the indicator actually look like?
    d0 = data["BTCUSDT"][0]
    dev0 = vsa_indicator(d0).dropna()
    print(f"indicator sanity (BTC holdout): n={len(dev0)} "
          f"mean={dev0.mean():+.4f} sd={dev0.std():.4f} "
          f"zeros={float((dev0 == 0).mean())*100:.1f}% "
          f"p5={dev0.quantile(0.05):+.3f} p95={dev0.quantile(0.95):+.3f}")

    # ---------- 1. VSA as a FILTER on momentum ----------
    print(f"\n{'='*80}")
    print("1. VSA AS A FILTER on momentum signals (bb_break 30/1.5)")
    print(f"{'='*80}")
    print(f"{'rule':34} {'window':8} {'trades':>7} {'meanR':>9} {'coins+':>8}")
    RULES = {
        "unfiltered": None,
        "dev < -0.5  (absorption)": lambda s: s < -0.5,
        "dev < -1.0  (strong absorption)": lambda s: s < -1.0,
        "dev >  0.5  (thin move)": lambda s: s > 0.5,
        "dev >  1.0  (very thin move)": lambda s: s > 1.0,
        "|dev| < 0.25 (normal candles)": lambda s: s.abs() < 0.25,
    }
    for label, rule in RULES.items():
        for wi, wname in ((0, "holdout"), (1, "dev")):
            allR, pos, tot = [], 0, 0
            for a, segs in data.items():
                df = segs[wi]
                sig = FILTERS["none"](df, signals_for(df, "bb_break", (30, 1.5)))
                if rule is not None:
                    dev = vsa_indicator(df).shift(1)      # causality
                    sig = sig.where(rule(dev), Action.HOLD)
                R, _ = run_r(df, sig, SL, TP, FEE_BP)
                if len(R) >= 30:
                    allR.append(R); tot += 1; pos += R.mean() > 0
            if not allR:
                continue
            R = np.concatenate(allR)
            print(f"{label:34} {wname:8} {len(R):>7} {R.mean():>+9.4f} "
                  f"{pos:>3}/{tot:<4}")

    # ---------- 2. VSA as a STANDALONE signal ----------
    print(f"\n{'='*80}")
    print("2. VSA AS A STANDALONE SIGNAL (no momentum involved)")
    print(f"{'='*80}")
    print(f"{'rule':34} {'window':8} {'trades':>7} {'meanR':>9} {'coins+':>8}")

    def standalone(df, mode, th):
        dev = vsa_indicator(df).shift(1)
        up = df["close"].shift(1) > df["close"].shift(2)
        sig = pd.Series(Action.HOLD, index=df.index, dtype=int)
        if mode == "fade_thin":          # thin wide move -> expect it to fail
            sig[(dev > th) & up] = Action.SELL
            sig[(dev > th) & ~up] = Action.BUY
        elif mode == "follow_thin":
            sig[(dev > th) & up] = Action.BUY
            sig[(dev > th) & ~up] = Action.SELL
        elif mode == "absorb_follow":    # absorption -> follow the prevailing move
            sig[(dev < -th) & up] = Action.BUY
            sig[(dev < -th) & ~up] = Action.SELL
        elif mode == "absorb_fade":
            sig[(dev < -th) & up] = Action.SELL
            sig[(dev < -th) & ~up] = Action.BUY
        return sig.astype(int)

    for mode in ("fade_thin", "follow_thin", "absorb_follow", "absorb_fade"):
        for th in (0.5, 1.0):
            for wi, wname in ((0, "holdout"), (1, "dev")):
                allR, pos, tot = [], 0, 0
                for a, segs in data.items():
                    df = segs[wi]
                    R, _ = run_r(df, standalone(df, mode, th), SL, TP, FEE_BP)
                    if len(R) >= 30:
                        allR.append(R); tot += 1; pos += R.mean() > 0
                if not allR:
                    continue
                R = np.concatenate(allR)
                print(f"{mode+' th='+str(th):34} {wname:8} {len(R):>7} "
                      f"{R.mean():>+9.4f} {pos:>3}/{tot:<4}")

    print(f"\nVerdict rule: a candidate must be positive on BOTH windows and on")
    print(f"most coins. Anything positive on one window only is noise — that is")
    print(f"exactly how gold and the volatility band died.")


if __name__ == "__main__":
    main()
