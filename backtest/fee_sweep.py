"""WHAT THE DEPLOYED BLEND IS WORTH AT EACH VENUE'S FEES.

    python -m backtest.fee_sweep

WHY THIS IS THE CHEAPEST TEST IN THE PROJECT
    Every strategy here was tested at 12bp round trip - Bitget's TAKER rate - and
    this project's own measured breakeven for the momentum families is 6-8.5bp. So
    every test has been run on the wrong side of breakeven, and `backtest/maker_r.py`
    already showed what happens when that is fixed: bb_break goes from -3.32 sumR/yr
    at taker to +21.81 at maker, with an 86.5% fill rate and both non-fill and
    adverse selection modelled.

    Hyperliquid, verified from its API on 2026-09-20: 234 perp markets, maker
    0.015% / taker 0.045%, ZERO gas on every trade, cancel and modify, up to 40x
    leverage, no KYC. That is 3bp round trip maker-maker against Bitget's 12bp
    taker - a 4x reduction on a strategy whose breakeven is 6-8.5bp.

    Nothing about the signal changes. Only `FEE_BP`.

THE FEE LADDER, AND WHAT EACH ROW REQUIRES OF YOU
    12bp  Bitget taker, both sides. What every test and all three live bots used.
     9bp  Hyperliquid TAKER both sides (4.5bp x 2). Needs nothing but the venue -
          market orders, same behaviour as today. This row is free.
     6bp  one side maker, one side taker, mixed venue.
     4bp  Bitget maker both sides.
     3bp  Hyperliquid MAKER both sides. Needs resting limit orders that actually
          fill - see the honesty note below.
     2bp  high-volume tier, where Hyperliquid's maker fee goes toward zero.

    THE 3bp ROW IS NOT FREE. It assumes entries and exits fill as resting limit
    orders. maker_r.py measured that properly for these same families - 82-94% fill
    at a 0.10-0.25 ATR offset, with the missed trades and the adverse selection both
    counted - and maker still won by a wide margin. But a stop-loss is always a
    taker, so a losing trade really pays maker+taker, and this sweep charges one flat
    rate to both. Read 3bp as the optimistic end of a range whose pessimistic end is
    the 6bp row.

WHAT IS MEASURED
    The deployed configuration exactly: 1h+4h+12h sleeves, 12 shared slots, 0.30%
    per unit, quarter risk in a BTC bear, breakeven at 3R, 20xATR long trail with a
    5-unit pyramid, 5xATR short trail. Same 60/40 split as backtest/blend.py. The
    8-slot column is included because that is the live capital question.

REGISTERED PREDICTION (2026-09-20, before running)
    Return roughly doubles between 12bp and 3bp, because the project's own breakeven
    is 6-8.5bp and both ends of the ladder sit far from it - 12bp is well past it and
    3bp is well inside it. Drawdown should get slightly WORSE, not better: cheaper
    fees keep marginal trades alive, so the book carries more exposure. The capital
    floor is the interesting column - it moves with drawdown, so it may not improve
    even though the return does.

    The honest bar the user set is 10%/month. The holdout already clears it at 12bp
    (+13.17%), so the question is not whether 3bp crosses 10% - it is how much room
    it buys above it once the hindsight divisor and the point-in-time universe take
    their cut. Anything that looks like a 3x jump is a bug, not a venue.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402

RULES = ["1h", "4h", "12h"]
LADDER = [(12.0, "Bitget taker (every test so far)"),
          (9.0, "Hyperliquid TAKER - venue change only"),
          (6.0, "one side maker, one side taker"),
          (4.0, "Bitget maker both sides"),
          (3.0, "Hyperliquid MAKER both sides"),
          (2.0, "high-volume maker tier")]


def at_fee(fee, slots, **kw):
    blend.FEE_BP = fee
    blend._S.clear()
    assert blend.FEE_BP == fee, "fee injection did not take"
    return blend.run(RULES, slots, **kw)


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: return roughly doubles from 12bp to 3bp (breakeven is 6-8.5bp);")
    print("drawdown gets slightly WORSE because cheap fees keep marginal trades alive;")
    print("the floor may not improve. A 3x jump would be a bug, not a venue.\n")

    orig = blend.FEE_BP
    try:
        at_fee(12.0, 12)
        ts = pd.DatetimeIndex(sorted(x[0] for x in blend.sleeve("1h")[0]))
        cut = ts[int(len(ts) * 0.6)]
        print(f"  deployed config: {'+'.join(RULES)}, 0.30%/unit, split {cut.date()}\n")

        print("=" * 108)
        print("1. THE FEE LADDER AT THE DEPLOYED 12 SLOTS")
        print("=" * 108)
        print(f"  {'fee':>5}  {'what it needs':<34}|{'TUNE /mo':>10}{'DD':>7}{'floor':>7}"
              f"|{'HOLD /mo':>10}{'DD':>7}{'floor':>7}{'n':>6}{'meanR':>8}")
        rows = {}
        for fee, what in LADDER:
            a = at_fee(fee, 12, t_to=cut)
            b = at_fee(fee, 12, t_from=cut)
            rows[fee] = (a, b)
            print(f"  {fee:>4.1f}b  {what:<34}|{a['hpm']:>+9.2f}%{a['dd']:>6.1f}%"
                  f"{a['floor']:>7.0f}|{b['hpm']:>+9.2f}%{b['dd']:>6.1f}%"
                  f"{b['floor']:>7.0f}{b['n']:>6}{b['mean']:>+8.3f}")

        print("\n" + "=" * 108)
        print("2. THE SAME LADDER AT 8 SLOTS — the configuration that fits $221")
        print("=" * 108)
        print(f"  {'fee':>5}  |{'TUNE /mo':>10}{'DD':>7}{'floor':>7}"
              f"|{'HOLD /mo':>10}{'DD':>7}{'floor':>7}{'n':>6}")
        for fee, _ in LADDER:
            a = at_fee(fee, 8, t_to=cut)
            b = at_fee(fee, 8, t_from=cut)
            print(f"  {fee:>4.1f}b  |{a['hpm']:>+9.2f}%{a['dd']:>6.1f}%{a['floor']:>7.0f}"
                  f"|{b['hpm']:>+9.2f}%{b['dd']:>6.1f}%{b['floor']:>7.0f}{b['n']:>6}")

        print("\n" + "=" * 108)
        print("3. WHAT THE VENUE IS WORTH, IN THE ONLY TERMS THAT MATTER")
        print("=" * 108)
        base = rows[12.0][1]
        for fee in (9.0, 6.0, 3.0):
            h = rows[fee][1]
            d = h["hpm"] - base["hpm"]
            print(f"  12bp -> {fee:>4.1f}bp   holdout {base['hpm']:+.2f}%/mo -> "
                  f"{h['hpm']:+.2f}%/mo  ({d:+.2f} points, "
                  f"{h['hpm']/base['hpm'] if base['hpm'] else float('nan'):.2f}x)"
                  f"   DD {base['dd']:.1f}% -> {h['dd']:.1f}%"
                  f"   floor ${base['floor']:.0f} -> ${h['floor']:.0f}")
        print("\n  These are hindsight-divided monthly figures on a fixed book. The")
        print("  point-in-time universe took a further 3.0x off the raw number when it")
        print("  was measured (pit_universe.py), and nothing here re-measures that. So")
        print("  read the RATIO between rows, and treat the levels as upper bounds.")
    finally:
        blend.FEE_BP = orig
        blend._S.clear()


if __name__ == "__main__":
    main()
