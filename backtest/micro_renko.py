"""DOES RENKO RAISE THE $10 ACCOUNT'S ODDS? — better bets vs fewer bets.

THE SETUP
    backtest/barsampling.py found that Renko bricks more than DOUBLE mean R per trade
    (+0.517 at a 2xATR brick against the 1h time-bar control's +0.229) while keeping
    the fat tail (maxR 193 vs 221) - so it is a genuine filter, not a profit cap. It
    still LOSES for the $221 book, because it trades a third as often and trade count
    is what compounds.

    The micro account is a different objective. Its enemy is RUIN, not slow
    compounding: 70.3% of paths from $10 die before reaching $50. A better edge per
    bet with fewer bets could cut that, because every trade is a chance for a losing
    streak to finish the account.

    So the question is narrow and worth asking: does the Renko signal raise
    P(reach $50 from $10)?

WHAT IS HELD IDENTICAL
    Same coins, same 2xATR stop, same 20x/5x trails, same BE@3R, same $5 Bitget floor,
    same block bootstrap, same 3x hindsight deflation, same 6,000 paths. ONLY the
    signal's bar construction changes. Execution is on real 1h OHLC in both cases, so
    a Renko advantage cannot come from synthetic fill prices.

THE CATCH TO WATCH FOR
    Fewer trades per year also means the target takes LONGER in wall-clock time, and
    the simulation caps a path at MAX_TRADES. A bar type that needs the same number of
    trades but each trade takes three times as long is not equivalent - so elapsed
    days is reported alongside, computed from each bar type's real trade rate.

REGISTERED PREDICTION (2026-09-14, before running)
    Renko RAISES P(reach $50) - somewhere in the 32-40% range against the time-bar
    29.7% - because on a floor-bound account the edge per bet dominates and the trade
    count only sets how long it takes. If it does NOT raise it, the honest conclusion
    is that 29.7% is close to the ceiling for $10 and no amount of signal work moves
    it much.

    python -m backtest.micro_renko
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.barsampling import (BOOK, bars_renko, bars_time,  # noqa: E402
                                  bars_activity, load, signals_on)
from backtest.convex import run_uncapped  # noqa: E402
from backtest.microacct import MIN_ORDER, simulate  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
SL_MULT, BE_AT = 2.0, 3.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
HINDSIGHT = 3.0


def seq_for(builder):
    """Pooled R in time order, the median stop fraction, and the real trade rate."""
    Rs, Ts, sfs = [], [], []
    for c in BOOK:
        real = load(c)
        if real is None or len(real) < 3000:
            continue
        a = (atr_ind(real, 14) / real["close"]).replace([np.inf, -np.inf],
                                                        np.nan).dropna()
        if len(a):
            sfs.append(float(a.median()) * SL_MULT)
        bars = builder(real)
        if bars is None or len(bars) < 60:
            continue
        sl, ss = signals_on(bars, len(real))
        for sig, trail in ((sl, LONG_TRAIL), (ss, SHORT_TRAIL)):
            if int((sig != Action.HOLD).sum()) == 0:
                continue
            R, idx, _b, _d = run_uncapped(real, sig, sl_mult=SL_MULT,
                                          fee_bp=FEE_BP, mode="trail_atr",
                                          trail=trail, be_at=BE_AT)
            if len(R):
                Rs.append(R); Ts.append(real["time"].iloc[idx].to_numpy())
    if not Rs:
        return None, None, None
    o = np.argsort(np.concatenate(Ts))
    R = np.concatenate(Rs)[o]
    T = pd.DatetimeIndex(np.concatenate(Ts)[o])
    days = max((T[-1] - T[0]).days, 1)
    return R, float(np.median(sfs)), len(R) / days      # trades per day


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: Renko raises P(reach $50) to 32-40%. If it does")
    print("not, 29.7% is near the ceiling for $10 and signal work will not move it.\n")

    variants = [
        ("TIME 1h (the current bot)", lambda d: bars_time(d, 1)),
        ("RENKO brick 1xATR", lambda d: bars_renko(d, 1.0)),
        ("RENKO brick 2xATR", lambda d: bars_renko(d, 2.0)),
        ("RENKO brick 3xATR", lambda d: bars_renko(d, 3.0)),
        ("TIME 4h", lambda d: bars_time(d, 4)),
    ]
    rng = np.random.default_rng(20260914)
    print("=" * 118)
    print("$10 -> $50 (5x), risk 4%/trade, Bitget $5 floor, honest edge, "
          "6,000 paths")
    print("=" * 118)
    print(f"{'signal bars':<26} {'meanR':>8} {'honest':>8} {'trades/day':>11} "
          f"{'P($50)':>8} {'P(ruin)':>9} {'med trades':>11} {'elapsed':>10}")
    rows = []
    for label, b in variants:
        R, sf, tpd = seq_for(b)
        if R is None or len(R) < 200:
            print(f"{label:<26} (insufficient)")
            continue
        defl = R - (2.0 / 3.0) * R.mean()
        d = simulate(defl, sf, 10.0, 4.0, 5.0, rng)
        days = d["med"] / tpd if tpd and np.isfinite(d["med"]) else float("nan")
        rows.append((label, R.mean(), defl.mean(), tpd, d, days))
        print(f"{label:<26} {R.mean():>+8.3f} {defl.mean():>+8.3f} "
              f"{tpd:>11.2f} {d['p']:>7.1f}% {d['ruin']:>8.1f}% "
              f"{d['med']:>11.0f} {days:>9.0f}d", flush=True)

    if not rows:
        return
    base = next((r for r in rows if r[0].startswith("TIME 1h")), None)
    best = max(rows, key=lambda r: r[4]["p"])
    print("\n" + "=" * 118)
    print("VERDICT")
    print("=" * 118)
    if base:
        print(f"  current bot (1h bars): {base[4]['p']:.1f}% chance of $50, "
              f"{base[4]['ruin']:.1f}% ruin, ~{base[5]:.0f} days")
    print(f"  best of {len(rows)}:        {best[0]} — {best[4]['p']:.1f}% chance, "
          f"{best[4]['ruin']:.1f}% ruin, ~{best[5]:.0f} days")
    if base and best[4]["p"] - base[4]["p"] > 2.0:
        print(f"\n  Renko-style sampling is worth {best[4]['p']-base[4]['p']:+.1f} "
              f"points of win probability on a micro account, while being WORSE for")
        print("  the $221 book. The two objectives genuinely want different bars.")
    elif base:
        print(f"\n  Nothing moved it by more than 2 points. {base[4]['p']:.1f}% is")
        print("  close to the ceiling for $10 on Bitget, and the binding constraint")
        print("  is the $5 minimum order, not the signal. More signal work on this")
        print("  account is wasted effort.")
    print("\n  'elapsed' is the median wall-clock wait, from each bar type's own real")
    print("  trade rate. A variant with the same trade count but a third of the rate")
    print("  takes three times as long to find out.")


if __name__ == "__main__":
    main()
