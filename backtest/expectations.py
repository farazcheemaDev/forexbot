"""IF I PUT IN $X AND LEAVE IT RUNNING FOR A MONTH, WHAT AM I LOOKING AT?

WHY THIS FILE EXISTS
    Every return figure in this repo is an AVERAGE, and this strategy's average is not
    something anyone experiences. 2021 alone made 40% of its lifetime profit. The median
    month is negative in every recent window. A person reading "+14.8%/month" and putting
    in $200 will be surprised, and the surprise is avoidable arithmetic.

    So this file answers the question that was actually asked - a DISTRIBUTION of dollar
    outcomes per starting capital - instead of a single number.

WHAT IT DOES
    1. Runs the deployed book at each starting capital WITH the venue minimum order
       enforced (small_capital.simulate), because a $10 account and a $500 account do not
       trade the same signals. That is the part every "just scale it down" answer misses.
    2. Turns each equity curve into overlapping 1 / 3 / 6 / 12-month windows and reports
       the MEDIAN and the QUARTILES, not the mean.
    3. Prints the same table twice: raw, and after the 3x hindsight haircut applied the
       way the rest of the repo applies it (annualised return divided by blend.HINDSIGHT).
       The haircut is monotonic, so P(losing month) is IDENTICAL in both - which makes it
       the one figure in here that no modelling choice can flatter.

    python -m backtest.expectations
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.small_capital import SEEDS, price_maps, simulate  # noqa: E402

CAPITALS = (10, 25, 50, 100, 200, 500, 1000, 5000)
WINDOWS = (1, 3, 6, 12)


def haircut(mult: float, months: int) -> float:
    """The repo's 3x hindsight convention, applied to a window of any length.

    Annualise the window, divide the annual rate by blend.HINDSIGHT, re-compound. This is
    the same operation small_capital.hpm performs, so the numbers here are comparable to
    every other 'per month' figure in the docs."""
    if mult <= 0:
        return 0.0
    yrs = months / 12.0
    cagr = mult ** (1 / yrs) - 1
    return float(max(1 + cagr / blend.HINDSIGHT, 0.0) ** yrs)


def month_ends(curve: pd.Series) -> pd.Series:
    """Equity at each month end - the only points a person actually checks."""
    return curve.resample("ME").last().ffill().dropna()


def windows(me: pd.Series, k: int) -> np.ndarray:
    """Every overlapping k-month multiple. Overlapping windows are correlated, so these
    are a description of history, not independent samples."""
    v = me.to_numpy(float)
    if len(v) <= k:
        return np.array([])
    a, b = v[:-k], v[k:]
    ok = a > 0
    return b[ok] / a[ok]


def curves(rows, bear, px, step, cap, risk=0.30, slots=12):
    """One equity curve per seed, plus the average rejection rate at this capital."""
    out = [simulate(rows, bear, px, step, cap, risk, slots, sd) for sd in SEEDS]
    rej = float(np.mean([o["skipped"] / max(o["skipped"] + o["taken"], 1) for o in out])) * 100
    return [o["curve"] for o in out], rej, float(np.mean([o["ruined"] for o in out])) * 100


def main():
    bear = regimes()[1000]
    px, step = price_maps()
    rows = rows_for(BASE_RULES)
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print(f"deployed book | {len(rows)} trades | {len(SEEDS)} orderings | "
          f"haircut {blend.HINDSIGHT:g}x | holdout from {cut:%Y-%m-%d}\n")

    # ---- 1. how the answer depends on capital -------------------------------------
    print("1. BY STARTING CAPITAL. Holdout columns are the ones to plan on.")
    print(f"  {'capital':>8}{'rejected':>9}{'DD':>6}  |{'  ALL med.mo':>12}"
          f"{'  HOLD med.mo':>13}{'  HOLD loses':>13}{'  HOLD 1mo $':>13}"
          f"{'  HOLD 12mo $':>14}")
    store = {}
    for cap in CAPITALS:
        cs, rej, ruin = curves(rows, bear, px, step, cap)
        m1 = np.concatenate([windows(month_ends(c), 1) for c in cs])
        if not len(m1):
            print(f"  ${cap:>7,}  no usable curve")
            continue
        store[cap] = (cs, m1)
        dd = float(np.mean([(1 - c / c.cummax()).max() * 100 for c in cs]))
        hs = [month_ends(c[c.index >= cut]) for c in cs]
        k1 = np.concatenate([windows(x, 1) for x in hs])
        k12 = np.concatenate([windows(x, 12) for x in hs])
        h1 = np.array([haircut(x, 1) for x in m1])
        g1 = np.array([haircut(x, 1) for x in k1])
        g12 = np.array([haircut(x, 12) for x in k12])
        print(f"  ${cap:>7,}{rej:>8.0f}%{dd:>5.0f}%  |{(np.median(h1)-1)*100:>+11.2f}%"
              f"{(np.median(g1)-1)*100:>+12.2f}%{(k1 < 1).mean()*100:>12.0f}%"
              f"{cap*np.median(g1):>13,.0f}{cap*np.median(g12):>14,.0f}")
    print("  'rejected' = signals skipped because one unit was below the venue minimum.")
    print("  'loses' is measured on the RAW curve; the haircut cannot change a sign.")
    print("  The percentage columns are FLAT above $25: capital buys dollars, not rate.")

    # ---- 2. how the answer depends on how long you leave it ----------------------
    print(f"\n2. HOW LONG YOU LEAVE IT RUNNING ($200 account, haircut)")
    print(f"  {'held for':>10}{'loses money':>13}{'25th':>9}{'median':>9}{'75th':>9}"
          f"{'95th':>9}{'   median $ from $200':>22}")
    cs = store[200][0]
    for k in WINDOWS:
        w = np.concatenate([windows(month_ends(c), k) for c in cs])
        h = np.array([haircut(x, k) for x in w])
        print(f"  {k:>7}mo{(w < 1).mean()*100:>12.0f}%{(np.percentile(h,25)-1)*100:>+8.0f}%"
              f"{(np.median(h)-1)*100:>+8.0f}%{(np.percentile(h,75)-1)*100:>+8.0f}%"
              f"{(np.percentile(h,95)-1)*100:>+8.0f}%{200*np.median(h):>21,.0f}")

    # ---- 3. the same table on the holdout only ----------------------------------
    print(f"\n3. THE SAME QUESTION ON THE HOLDOUT ONLY (from {cut:%Y-%m}, never tuned on)")
    print(f"  {'capital':>8}{'held for':>10}{'loses money':>13}{'median':>9}"
          f"{'   median $ out':>16}")
    for cap in (200, 1000):
        cs, _rej, _r = curves(rows, bear, px, step, cap)
        for k in (1, 12):
            w = np.concatenate([windows(month_ends(c[c.index >= cut]), k) for c in cs])
            if not len(w):
                continue
            h = np.array([haircut(x, k) for x in w])
            print(f"  ${cap:>7,}{k:>7}mo{(w < 1).mean()*100:>12.0f}%"
                  f"{(np.median(h)-1)*100:>+8.0f}%{cap*np.median(h):>15,.0f}")

    print("\n  Two sentences to carry away: the median MONTH is near zero at every")
    print("  capital, and the 12-month median is large only because a few months are.")


if __name__ == "__main__":
    main()
