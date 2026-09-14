"""DOES THE 1,000-HOUR REGIME GATE SURVIVE ON THE ACTUALLY DEPLOYED BOOK?

    python -m backtest.regime_blend

WHAT THIS SETTLES
    backtest/regime.py found that the deployed regime gate uses a 200-HOUR (8.5 day)
    lookback to detect multi-year regimes, that the lookback had never been swept, and
    that 1,000h beat it: MAR 3.62 -> 4.10, drawdown 64.0% -> 58.3%.

    That was measured on the 1h-ONLY book. The thing actually running on the VM is
    blend_paper.py: 12 coins x 1h + 4h + 12h sharing 8 slots. A lever measured on one
    sleeve is not a lever on three - the sleeves fire at different times, so a gate that
    helps the fast sleeve can be neutral or harmful once slow sleeves compete for the
    same slots.

    So this re-runs the sweep through blend.run(), the same harness that produced the
    deployed configuration, and therefore:
      * the HINDSIGHT divisor (3.0) is applied, so `hpm` is comparable to the ~+8%/month
        expectation rather than to regime.py's raw figures
      * the per-coin MEXC minimums and the real capital floor come out of it
      * slots are shared across sleeves exactly as the live bot shares them

HOW THE LOOKBACK IS INJECTED
    blend.btc_bear() hardcodes rolling(200) and caches into the module global _BTC,
    returning the cache when it is not None. So the lookback is changed by WRITING that
    cache, not by editing the validated harness:

        blend._BTC = <bear series at the lookback under test>

    Nothing in blend.py is modified. If that caching behaviour ever changes, this file
    breaks loudly rather than silently testing 200h while printing another number - which
    is why the injection is asserted below before any cell runs.

REGISTERED PREDICTION (2026-09-14, before running)
    The 1,000h advantage SHRINKS on the blend and may vanish. Reason: the gate reduces
    risk during bears, and the 12h sleeve already holds through them - the blend's
    drawdown is 57.7% against the 1h book's 64%, so a third of the problem the gate
    solves has already been solved by the timeframe mix. Overlapping fixes do not add.
    I expect 1,000h still >= 200h on MAR, by less than the 13% seen on the 1h book.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402

LOOKBACKS = [200, 500, 1000, 2000, 3000]
RULES = ("1h", "4h", "12h")
SLOTS = 8


def bear_at(lookback: int) -> pd.Series:
    d = blend.load("BTCUSDT")
    ma = d["close"].rolling(lookback).mean()
    return pd.Series((d["close"] < ma).shift(1).fillna(False).to_numpy(bool),
                     index=pd.DatetimeIndex(d["time"]))


def set_lookback(lookback: int):
    """Install the bear series for `lookback` into blend's cache, and PROVE it took.

    Without the assertion a change to blend.btc_bear's caching would make every cell
    silently test 200h while this file printed different labels - the same class of
    failure as the endDate and copy_rates_range errors: a wrong answer that looks like
    a right one.
    """
    want = bear_at(lookback)
    blend._BTC = want
    got = blend.btc_bear()
    assert got is want, ("blend.btc_bear() no longer returns its _BTC cache - this "
                         "file can no longer set the lookback and must be rewritten")
    return want


def mar(d):
    return (d["hpm"] * 12.0 / d["dd"]) if d and d["dd"] > 0 else float("nan")


def row(tag, d):
    if not d:
        return f"  {tag:<18}{'(no result)':>22}"
    return (f"  {tag:<18}{d['n']:>7}{d['hpm']:>+9.2f}%{d['dd']:>8.1f}%"
            f"{mar(d):>7.2f}{d['floor']:>10,.0f}{d['mean']:>9.3f}"
            + ("  RUIN" if d["ruined"] else ""))


HDR = (f"  {'lookback':<18}{'n':>7}{'/mo':>10}{'DD':>9}{'MAR':>7}{'floor $':>10}"
       f"{'meanR':>9}")


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: the 1,000h edge SHRINKS on the blend and may vanish,")
    print("because the 12h sleeve already absorbs part of what the gate fixes (blend DD")
    print("57.7% vs 1h-book 64%). Overlapping fixes do not add.\n")

    cut = blend.split_times() if hasattr(blend, "split_times") else None
    if cut is None:
        # blend.py computes its split inline in main(); reproduce it the same way
        d0 = blend.run(RULES, SLOTS)
        cut = d0["times"][int(len(d0["times"]) * 0.6)] if d0 else None
    print(f"deployed config: 12 coins x {' + '.join(RULES)}, {SLOTS} shared slots, "
          f"risk {blend.RISK}%/unit, BE@{blend.BE_AT}R")
    print(f"hindsight divisor {blend.HINDSIGHT}x applied, so /mo is comparable to the")
    print(f"~+8%/month expectation. holdout split {cut:%Y-%m-%d}\n")

    print("=" * 96)
    print("FULL SAMPLE — gate multiplier x0.25, lookback swept")
    print("=" * 96)
    print(HDR)
    cells = []
    for lb in LOOKBACKS:
        set_lookback(lb)
        d = blend.run(RULES, SLOTS, regime=blend.REGIME_MULT)
        print(row(f"{lb}h ({lb/24:.0f}d)", d))
        if d:
            cells.append((lb, d))
    set_lookback(200)
    nog = blend.run(RULES, SLOTS, regime=0.0)
    print(row("no gate", nog))

    print("\n" + "=" * 96)
    print("HOLDOUT — every lookback, IS = first 60%, OOS = last 40%")
    print("=" * 96)
    print(f"  {'lookback':<18}{'IS /mo':>10}{'OOS /mo':>10}{'IS DD':>8}{'OOS DD':>8}"
          f"{'OOS MAR':>9}{'verdict':>13}")
    hold = []
    for lb, _d in cells:
        set_lookback(lb)
        a = blend.run(RULES, SLOTS, t_to=cut, regime=blend.REGIME_MULT)
        b = blend.run(RULES, SLOTS, t_from=cut, regime=blend.REGIME_MULT)
        if not (a and b):
            print(f"  {str(lb) + 'h':<18}{'one half too small':>30}")
            continue
        x, y = a["hpm"], b["hpm"]
        if x > 0 and y > 0:
            v = "HOLDS"
        elif x > 0 >= y:
            v = "dies OOS"
        elif y > 0 >= x:
            v = "ONE REGIME"
        else:
            v = "dead both"
        hold.append((lb, a, b, v))
        print(f"  {str(lb) + 'h (' + f'{lb/24:.0f}' + 'd)':<18}{x:>+9.2f}%{y:>+9.2f}%"
              f"{a['dd']:>7.1f}%{b['dd']:>7.1f}%{mar(b):>9.2f}{v:>13}")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    if not cells:
        print("  nothing ran")
        return
    dep = next((d for lb, d in cells if lb == 200), None)
    # RANK ON OUT-OF-SAMPLE MAR, NOT FULL-SAMPLE MAR.
    #
    # The first version of this verdict ranked on the full sample and named 2000h,
    # while the holdout table printed directly above it showed 1000h winning OOS
    # return, OOS drawdown AND OOS MAR. Ranking on a window that includes the
    # in-sample period rewards exactly the overfitting the holdout exists to expose -
    # the third verdict rule today that reached for the wrong statistic.
    oos = {lb: b for lb, _a, b, _v in hold}
    ranked = [(lb, d) for lb, d in cells if lb in oos]
    if ranked:
        best_lb, best_d = max(ranked, key=lambda t: mar(oos[t[0]]))
    else:
        best_lb, best_d = max(cells, key=lambda t: mar(t[1]))
    print(f"  deployed 200h : {dep['hpm']:+.2f}%/mo  DD {dep['dd']:.1f}%  "
          f"MAR {mar(dep):.2f}  floor ${dep['floor']:,.0f}")
    print(f"  best {best_lb}h    : {best_d['hpm']:+.2f}%/mo  DD {best_d['dd']:.1f}%  "
          f"MAR {mar(best_d):.2f}  floor ${best_d['floor']:,.0f}")
    if nog:
        print(f"  no gate       : {nog['hpm']:+.2f}%/mo  DD {nog['dd']:.1f}%  "
              f"MAR {mar(nog):.2f}  floor ${nog['floor']:,.0f}")
    if best_lb in oos and 200 in oos:
        print(f"  OUT OF SAMPLE   200h MAR {mar(oos[200]):.2f}  vs  "
              f"{best_lb}h MAR {mar(oos[best_lb]):.2f}   <- the criterion")
    gain = (mar(oos[best_lb]) - mar(oos[200])) if (best_lb in oos and 200 in oos)         else mar(best_d) - mar(dep)
    print()
    if best_lb == 200:
        print("  THE 1h-BOOK FINDING DOES NOT TRANSFER. 200h is already the best")
        print("  lookback on the deployed blend, so nothing should change.")
    elif gain <= 0.10:
        print(f"  {best_lb}h wins by only {gain:+.2f} MAR on the blend, against +0.48 on")
        print("  the 1h book. Inside the noise of one sample - NOT a reason to change a")
        print("  live configuration.")
    else:
        print(f"  {best_lb}h beats the deployed 200h by {gain:+.2f} MAR "
              f"({mar(dep):.2f} -> {mar(best_d):.2f}),")
        print(f"  drawdown {dep['dd']:.1f}% -> {best_d['dd']:.1f}%, floor "
              f"${dep['floor']:,.0f} -> ${best_d['floor']:,.0f}.")
        print("  Change it ONLY if the holdout row for that lookback says HOLDS.")
    print("\n  One sample, one universe, 6.6 years. A MAR gain under ~0.5 here is not")
    print("  distinguishable from luck, whatever the table says.")


if __name__ == "__main__":
    main()
