"""TAKE PROFIT EARLY AND TRADE MORE OFTEN — mapping the frequency/capture surface.

    python -m backtest.freq_capture

THE HYPOTHESIS
    "Keep more per trade by taking profit early, and make up the lost upside by trading
    far more often." Every exit test so far held the entry fixed, so it only ever measured
    the capture side of that trade-off. This maps both axes at once.

    It is also the one version of the idea that is not obviously dead on costs.
    backtest/fee_sweep.py established that this strategy is almost fee-insensitive - a
    2xATR stop is 8-15% of price on these alts, so a 12bp round trip is about 0.012R
    against a +3.4R average position. **Trading ten times as often costs almost nothing in
    fees.** So if frequency can rescue an early exit, it is allowed to.

WHAT IS SWEPT
    ENTRY looseness   bb_break standard deviations: 1.0 (very loose, fires constantly)
                      through 2.5 (tight, rare). Lower k = more trades.
    EXIT              a fixed profit target in ATR: 2, 3, 5, 10 x ATR. NOTE run_r's tp_mult
                      is in ATR units and 1R = 2xATR (SL_MULT), so those are targets of
                      1.0R, 1.5R, 2.5R and 5.0R. An earlier version of this file labelled
                      them "+2R..+10R" in its output, which was wrong by 2x - against the deployed
                      alternative of no target at all, a 20xATR trail with a 5-unit
                      pyramid.

    Fixed-target rows are SINGLE UNIT, because a fixed target with a pyramid is
    incoherent - the target would fire before the second unit is added. So the comparison
    is honest about being a different strategy, not a tweak.

    Every row: same 2xATR stop, same 12bp round trip, same 12 coins, same three sleeves.

WHAT WOULD MAKE THE HYPOTHESIS WORK
    Total R is n x mean R. Capping the winner cuts mean R; the claim is that a looser
    entry raises n by more. That can only work if mean R stays POSITIVE after the cap -
    multiplying a negative mean by more trades makes it worse, not better. So the decisive
    column is mean R, and the question is whether any (looseness, target) pair keeps it
    above zero by enough.

REGISTERED PREDICTION (2026-09-21, before running)
    No cell beats the deployed config, and the reason will be visible in the win-rate
    column: a fixed +3R target against a 1R stop needs better than 25% wins to break even,
    and this strategy's win rate is ~23% with an UNCAPPED upside. Cap the upside and the
    win rate barely moves - the winners that hit +3R were going to +80R - so mean R goes
    negative and no amount of frequency rescues it.

    The looser entries should make it worse still, because k=1.0 fires on noise rather
    than on breakouts. If anything surprises me it will be a tight entry (k=2.5) with a
    large target (+10R), which is closest to the deployed rule and therefore least
    different from a config already validated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.mass_search import gen_signals  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.rtest import run_r  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

RULES = ["1h", "4h", "12h"]
KS = (1.0, 1.5, 2.0, 2.5)
TARGETS = (2.0, 3.0, 5.0, 10.0)
FEE = blend.FEE_BP


def frames():
    out = []
    for coin in blend.BOOK:
        d = blend.load(coin)
        if d is None:
            continue
        for rule in RULES:
            df = resample(d, rule)
            if len(df) >= 400:
                out.append(df)
    return out


def fixed(fr, k, tp):
    Rs = []
    for df in fr:
        sig = gen_signals(df, "bb_break", (30, k))
        r, _i = run_r(df, sig, sl_mult=blend.SL_MULT, tp_mult=tp, fee_bp=FEE)
        if len(r):
            Rs.append(np.asarray(r, float))
    r = np.concatenate(Rs) if Rs else np.array([])
    return r


def deployed(fr, k):
    Rs = []
    for df in fr:
        sig = gen_signals(df, "bb_break", (30, k))
        R, _i, _u, _h = run_pyramid(df, sig, sl_mult=blend.SL_MULT,
                                    trail=blend.LONG_TRAIL,
                                    max_units=blend.MAX_UNITS,
                                    add_every=blend.ADD_EVERY, fee_bp=FEE,
                                    breakeven_at=blend.BE_AT)
        if len(R):
            Rs.append(np.asarray(R, float))
    return np.concatenate(Rs) if Rs else np.array([])


def line(lab, r, base_n=None, width=30):
    if not len(r):
        return f"  {lab:<{width}}  no trades"
    freq = f"{len(r)/base_n:.1f}x" if base_n else "1.0x"
    return (f"  {lab:<{width}}{len(r):>9,}{freq:>7}{100*(r>0).mean():>7.0f}%"
            f"{r.mean():>+9.3f}{r.sum():>+11,.0f}{np.median(r):>+9.2f}")


HDR = (f"  {'configuration':<30}{'trades':>9}{'freq':>7}{'win%':>7}"
       f"{'mean R':>9}{'total R':>11}{'median':>9}")


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: no cell beats the deployed config. A +3R target against a 1R stop")
    print("needs >25% wins and this strategy wins ~23% with UNCAPPED upside; capping barely")
    print("moves the win rate because the winners that reach +3R were going to +80R.\n")

    fr = frames()
    print(f"  {len(fr)} coin/sleeve series, 2xATR stop, {FEE}bp round trip\n")

    print("=" * 96)
    print("1. THE DEPLOYED RULE AT EACH ENTRY LOOSENESS (no target, 20xATR trail, 5 units)")
    print("=" * 96)
    print(HDR)
    base = deployed(fr, 1.5)
    n15 = len(base)
    for k in KS:
        r = base if k == 1.5 else deployed(fr, k)
        tag = "  <- DEPLOYED" if k == 1.5 else ""
        print(line(f"bb_break(30, {k})  trail{tag}", r, n15))

    print("\n" + "=" * 96)
    print("2. FIXED TARGETS, SINGLE UNIT — take profit early, trade more often")
    print("=" * 96)
    print(HDR)
    best = None
    for k in KS:
        for tp in TARGETS:
            r = fixed(fr, k, tp)
            if not len(r):
                continue
            if best is None or r.sum() > best[0]:
                best = (r.sum(), k, tp, len(r), r.mean(), 100*(r > 0).mean())
            print(line(f"bb_break(30, {k})  target {tp:g}xATR = {tp/blend.SL_MULT:g}R", r, n15))
        print()

    print("=" * 96)
    print("VERDICT")
    print("=" * 96)
    print(f"  deployed (trail, k=1.5): {len(base):,} trades, mean {base.mean():+.3f}R, "
          f"total {base.sum():+,.0f}R")
    if best:
        print(f"  best fixed-target cell: k={best[1]}, {best[2]:g}xATR = {best[2]/blend.SL_MULT:g}R -> {best[3]:,} trades "
              f"({best[3]/n15:.1f}x the frequency), win {best[5]:.0f}%, "
              f"mean {best[4]:+.3f}R, total {best[0]:+,.0f}R")
        if best[0] > base.sum():
            print("\n  A FIXED TARGET WITH MORE TRADES BEATS THE TRAIL. That contradicts")
            print("  the profit-cap result in pyramid_exits.py and must be re-run through")
            print("  blend.run with the slot cap before it means anything - more trades")
            print("  compete for the same 12 slots, which this test does not model.")
        else:
            need = base.sum() / best[4] if best[4] > 0 else float("nan")
            print(f"\n  NO. The best cell reaches {best[0]:+,.0f}R against the deployed")
            print(f"  {base.sum():+,.0f}R.")
            if best[4] > 0:
                print(f"  To match the trail at that mean R you would need {need:,.0f}"
                      f" trades - {need/best[3]:.1f}x more than the loosest entry")
                print("  produces, and they would all compete for the same 12 slots.")
            else:
                print("  Its mean R is NEGATIVE, so frequency cannot help at all:")
                print("  more trades multiply a negative number.")


if __name__ == "__main__":
    main()
