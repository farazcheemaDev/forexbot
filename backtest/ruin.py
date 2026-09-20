"""RISK OF RUIN AND THE GROWTH-OPTIMAL BET SIZE — trading as the gamble it is.

    python -m backtest.ruin

THE QUESTION THIS PROJECT NEVER ASKED
    Every capital floor here was derived from MAX DRAWDOWN - one historical worst case,
    padded by 1/(1-DD). That is not a probability of anything. The gambling framing asks
    the sharper question:

        given the ACTUAL distribution of this strategy's trade outcomes, what is the
        chance the account degrades past the point where it can keep trading, and what
        bet size maximises growth without crossing that line?

    That inverts the capital question in the direction of the stated goal. Instead of
    "what drawdown does 0.30% risk produce", it asks "what is the largest risk $221 can
    carry", which is the maximum-return-at-minimum-capital question stated properly.

THE ABSORBING BARRIER IS NOT ONE LINE, IT IS TWELVE
    Ruin here is not equity reaching zero. Each coin needs
    `min_order x stop_fraction / risk_fraction` of equity before its position can be
    sized at all, and those thresholds differ by 500x across the book (SHIB $0.005
    minimum against NEAR $2.28). So as equity falls the book does not die - it loses
    coins one at a time, and with them the diversification that produced the edge.

    Three lines are therefore tracked, not one:
        CRIPPLED   fewer than 6 of the 12 coins fundable - the book stops being a book
        NEAR-DEAD  fewer than 2 coins fundable
        HALVED     equity below half its starting value

WHAT IS SIMULATED
    Block bootstrap of the strategy's own 5,503 realised trade Rs, in contiguous blocks
    of 25 so that losing streaks and the clustering of winners survive resampling - an
    i.i.d. shuffle would destroy exactly the structure that causes ruin.

    Two edge scenarios, because the R distribution comes from a FIXED book and this
    project measured a 3.0x hindsight premium on fixed books (pit_universe.py):
        as measured    the raw Rs
        PIT haircut    every R shifted down by a constant so the MEAN is one third of
                       the original, leaving the shape and the variance intact

    The live bot also quarter-sizes while BTC is below its 1000h average, which this
    does not model. So every number here is slightly PESSIMISTIC about the live config.

REGISTERED PREDICTION (2026-09-20, before running)
    0.30% per unit will look survivable on the raw Rs and dangerous under the PIT
    haircut, because ruin probability is driven by the mean-to-variance ratio and the
    haircut cuts the mean by two thirds while leaving the variance alone. I expect the
    growth-optimal risk on the raw distribution to be far ABOVE 0.30% - Kelly on a
    +2.6R average trade is enormous - and the risk that keeps P(crippled) under 5%
    under the haircut to be BELOW 0.30%. If those two disagree, the honest answer is
    the smaller one, because the haircut is the honest edge.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.timeframes import MIN_ORDER  # noqa: E402

RULES, SLOTS = ["1h", "4h", "12h"], 12
START = 221.0
BLOCK = 25
PATHS = 20000
HORIZONS = (200, 600)
RISKS = (0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 0.75, 1.00)
rng = np.random.default_rng(1729)


def thresholds():
    """min_order x stop_fraction for each coin - the numerator of its funding line."""
    blend._S.clear()
    stops = {}
    for r in RULES:
        _, s = blend.sleeve(r)
        for k, v in s.items():
            stops[k] = max(stops.get(k, 0.0), v)
    # only coins with a known minimum order; a PIT run leaves a much wider
    # universe in the sleeve cache than MIN_ORDER covers
    return np.array(sorted(MIN_ORDER[c] * stops[c]
                           for c in stops if c in MIN_ORDER))


def paths(R, f, n, m=PATHS):
    """m block-bootstrapped equity paths of n trades at risk fraction f.

    Returns the final equity and the running MINIMUM of each path - ruin is about the
    worst point reached, not the endpoint.
    """
    nb = int(np.ceil(n / BLOCK))
    starts = rng.integers(0, len(R) - BLOCK, size=(m, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(m, -1)[:, :n]
    step = 1.0 + R[idx] * f
    np.maximum(step, 1e-9, out=step)          # a -20R trade at 1% is -20%, never < 0
    eq = START * np.cumprod(step, axis=1)
    return eq[:, -1], eq.min(axis=1)


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: 0.30% survivable on raw Rs, dangerous under the PIT haircut.")
    print("Growth-optimal risk far above 0.30% on raw; the risk keeping P(crippled)")
    print("under 5% under the haircut below 0.30%. If they disagree, take the smaller.\n")

    d = blend.run(RULES, SLOTS)
    R_raw = np.asarray(d["R"], dtype=float)
    thr = thresholds()
    print(f"  {len(R_raw):,} realised trades, mean {R_raw.mean():+.3f}R, "
          f"sd {R_raw.std():.2f}, worst {R_raw.min():+.1f}R, best {R_raw.max():+.1f}R")
    print(f"  starting equity ${START:,.0f}, block bootstrap in blocks of {BLOCK}, "
          f"{PATHS:,} paths per cell")
    print(f"  funding lines (min_order x stop): cheapest {thr[0]:.4f}, "
          f"6th cheapest {thr[5]:.4f}, dearest {thr[-1]:.4f}\n")

    scen = {"as measured": R_raw,
            "PIT haircut (mean/3)": R_raw - (2.0 / 3.0) * R_raw.mean()}
    for name, R in scen.items():
        print("=" * 104)
        print(f"{name.upper()}  —  mean {R.mean():+.3f}R")
        print("=" * 104)
        for n in HORIZONS:
            print(f"\n  after {n} trades")
            print(f"  {'risk/unit':>10}{'cripple line':>14}{'median eq':>12}"
                  f"{'5th pct':>10}{'P(crippled)':>13}{'P(near-dead)':>14}"
                  f"{'P(halved)':>11}{'P(2x+)':>9}")
            best = None
            for f_pct in RISKS:
                f = f_pct / 100.0
                fin, low = paths(R, f, n)
                crip = thr[5] / f          # equity below this -> fewer than 6 coins
                dead = thr[1] / f          # below this -> fewer than 2 coins
                med = float(np.median(fin))
                if best is None or med > best[0]:
                    best = (med, f_pct)
                print(f"  {f_pct:>9.2f}%{crip:>13,.0f}${med:>11,.0f}"
                      f"{np.percentile(fin, 5):>10,.0f}"
                      f"{100*(low < crip).mean():>12.1f}%"
                      f"{100*(low < dead).mean():>13.1f}%"
                      f"{100*(fin < START/2).mean():>10.1f}%"
                      f"{100*(fin > 2*START).mean():>8.1f}%")
            print(f"    growth-optimal risk at this horizon: {best[1]:.2f}% "
                  f"(median ${best[0]:,.0f})")
        print()

    print("=" * 104)
    print("WHAT RISK IS SAFE? — largest risk keeping P(crippled) under 5% over 600 trades")
    print("=" * 104)
    print(f"  {'scenario':<24}{'safe risk':>11}{'median eq':>12}{'/month equiv':>14}")
    for name, R in scen.items():
        pick = None
        for f_pct in RISKS:
            f = f_pct / 100.0
            fin, low = paths(R, f, 600)
            if 100 * (low < thr[5] / f).mean() < 5.0:
                pick = (f_pct, float(np.median(fin)))
        if pick is None:
            print(f"  {name:<24}{'none':>11}   every risk level crosses 5%")
            continue
        # 600 trades at the live rate of ~8 closed/day is ~75 days ~ 2.5 months
        mult = pick[1] / START
        mo = (mult ** (1 / 2.5) - 1) * 100
        print(f"  {name:<24}{pick[0]:>10.2f}%{pick[1]:>11,.0f}${mo:>+13.1f}%")
    print("\n  '/month equiv' converts the median 600-trade outcome to a monthly rate at")
    print("  the live bot's observed ~8 closed trades per day (600 trades ~ 2.5 months).")
    print("  The deployed config runs 0.30% per unit. Compare it to the safe column.")


if __name__ == "__main__":
    main()
