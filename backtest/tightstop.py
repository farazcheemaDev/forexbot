"""STOP WIDTH — the one parameter this project has NEVER swept.

THE IDEA BEING TESTED (user's, 2026-09-13)
    On a small account, use much more leverage with a very tight stop: cut the trade
    the moment it is down ~$0.50 on a $20 account, but size big so that a winner
    pays properly.

WHAT LEVERAGE ACTUALLY IS HERE
    Leverage is not an input to this system. It is an output:

        notional = risk_dollars / stop_fraction
        leverage = notional / equity = risk_fraction / stop_fraction

    So "more leverage" and "tighter stop" are the SAME knob, not two. Tightening the
    stop while holding dollar risk constant automatically enlarges the position -
    that is where the leverage comes from - and it does not by itself change what the
    strategy earns.

    Two things DO change, and they pull opposite ways:
      * a tighter stop is hit by noise more often            (worse)
      * a tighter stop means a given price move is worth more R   (better)
    Which wins is empirical, and it has never been measured here: every test in this
    project hardcoded sl_mult = 2.0.

    A third effect is not ambiguous at all:
        fee toll in R = fee_fraction x price / stop_distance
    Cut the stop 10x and the fee cost per trade multiplies by 10. At 12bp round trip
    against a 2.43% stop the toll is ~0.049R; against a 0.243% stop it is ~0.49R,
    which would erase the entire measured edge of +0.10R on its own.

WHY MEAN R IS COMPARABLE ACROSS STOP WIDTHS HERE
    R is defined against the stop, so a narrower stop mechanically inflates both the
    wins and the losses - the numbers are NOT comparable in the abstract. They become
    comparable once the RISK FRACTION is held constant, because then

        equity change per trade = R x risk_fraction

    and risk_fraction is the same in every row. So with risk fixed, higher mean R
    means faster growth, whatever the stop width. That is the only reading under
    which this table means anything, and it is why risk is held at one value.

THE SECOND HALF OF THE IDEA, WHICH IS SEPARATE
    "$0.50 loss on a $20 account" is 2.5% risk per trade. That is not a stop-width
    choice, it is a risk choice, and it was already measured: 2.5% total exposure
    produced a 99.9% drawdown - ruin. The table reports the implied leverage and the
    dollar risk at $20 so the two halves of the idea can be judged separately.

REGISTERED PREDICTION (2026-09-13, before running)
    Mean R falls as the stop tightens, and falls off a cliff below ~1xATR, because
    the fee toll rises as 1/stop while the noise stop-outs rise too. The best stop is
    at or WIDER than the 2.0 currently used - possibly 3x. If a tight stop wins I
    will suspect the fee model before believing it.

    python -m backtest.tightstop
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import run_uncapped  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

FEE_BP = 12.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MAX_UNITS, ADD_EVERY = 5, 2.0
BOOK = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
        "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
SLOTS = 8
HINDSIGHT = 3.0
_D: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def atr_pct(df):
    a = (atr_ind(df, 14) / df["close"]).replace([np.inf, -np.inf], np.nan).dropna()
    return float(a.median()) if len(a) else float("nan")


def run_sl(sl_mult, risk, be=3.0):
    """Whole book at one stop width. Trail stays in ATR units, because the trail is
    an exit-distance rule and not a multiple of the stop - scaling it with sl_mult
    would change two variables at once."""
    tr = []
    for c in BOOK:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        t = df["time"].to_numpy()
        R, idx, _u, held = run_pyramid(df, signals(df, "long", "all"),
                                       sl_mult=sl_mult, trail=LONG_TRAIL,
                                       max_units=MAX_UNITS, add_every=ADD_EVERY,
                                       fee_bp=FEE_BP, breakeven_at=be)
        tr += [(t[max(int(i) - int(h), 0)], t[int(i)], float(r))
               for r, i, h in zip(R, idx, held)]
        R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"),
                                        sl_mult=sl_mult, fee_bp=FEE_BP,
                                        mode="trail_atr", trail=SHORT_TRAIL,
                                        be_at=be)
        tr += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r))
               for r, i, b in zip(R, idx, bars)]
    if len(tr) < 30:
        return None
    tr.sort(key=lambda x: x[0])
    f = risk / 100.0
    eq, curve, times, opens = 1.0, [], [], []
    Rs = []
    ruined = False
    for a, b, r in tr:
        opens = [u for u in opens if u > a]
        if len(opens) >= SLOTS:
            continue
        opens.append(b)
        Rs.append(r)
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 0.01:
                eq, ruined = 0.0, True
        curve.append(eq); times.append(b)
    if len(Rs) < 30:
        return None
    R = np.asarray(Rs)
    cur = np.asarray(curve)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    hc = cagr / HINDSIGHT if cagr > -100 else -100.0
    return dict(n=len(R), mean=float(R.mean()), win=float((R > 0).mean() * 100),
                med=float(np.median(R)), mx=float(R.max()),
                dd=dd, ruined=ruined, cagr=cagr,
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risk", type=float, default=0.13,
                    help="held CONSTANT across rows - see docstring")
    args = ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: mean R falls as the stop tightens and collapses")
    print("below ~1xATR. Best stop at or wider than 2.0. A tight-stop win would make")
    print("me check the fee model first.\n")

    ap_med = float(np.median([atr_pct(load(c)) for c in BOOK
                              if load(c) is not None]))
    print(f"median ATR(14) = {ap_med*100:.2f}% of price across {len(BOOK)} coins")
    print(f"risk held at {args.risk}%/unit in every row, so mean R is comparable\n")
    print("=" * 118)
    print(f"{'stop':>6} {'stop %':>7} {'fee toll R':>10} {'lev @$20':>9} "
          f"{'$risk@20':>9} {'n':>6} {'meanR':>8} {'win%':>6} {'maxR':>8} "
          f"{'HONEST /mo':>11} {'DD':>7}")
    print("=" * 118)
    rows = []
    for sl in (0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0):
        d = run_sl(sl, args.risk)
        stop_frac = sl * ap_med
        toll = (FEE_BP / 1e4) / stop_frac
        lev = (args.risk / 100.0) / stop_frac
        drisk = 20.0 * args.risk / 100.0
        if not d:
            print(f"{sl:>6.2f} {stop_frac*100:>6.2f}% {toll:>10.3f} "
                  f"{lev:>8.2f}x {drisk:>9.3f} (no result)")
            continue
        rows.append((sl, d, toll, lev))
        ru = " RUIN" if d["ruined"] else ""
        print(f"{sl:>6.2f} {stop_frac*100:>6.2f}% {toll:>10.3f} {lev:>8.2f}x "
              f"{drisk:>9.3f} {d['n']:>6} {d['mean']:>+8.3f} {d['win']:>6.1f} "
              f"{d['mx']:>8.1f} {d['hpm']:>+10.2f}% {d['dd']:>6.1f}%{ru}",
              flush=True)

    if not rows:
        return
    best = max(rows, key=lambda r: r[1]["mean"])
    cur = next((r for r in rows if r[0] == 2.0), None)
    print("\n" + "=" * 118)
    print(f"BEST mean R at stop {best[0]:.2f}xATR ({best[1]['mean']:+.3f}), "
          f"currently running {cur[0]:.2f}x ({cur[1]['mean']:+.3f})"
          if cur else "")
    print("=" * 118)
    print("The 'fee toll R' column is the argument against a tight stop, and it is")
    print("arithmetic rather than a backtest result: cost in R = fee / stop distance,")
    print("so halving the stop doubles what every trade pays before it can win.")
    print("\nSEPARATELY, on the '$0.50 loss on a $20 account' half of the idea:")
    print("  $0.50 of 20 is 2.5% risk per trade. 2.5% total exposure was measured")
    print("  at 99.9% drawdown - ruin - and that is independent of stop width. The")
    print("  '$risk@20' column shows what THIS table's risk setting actually costs")
    print(f"  per trade on a $20 account: ${20.0*args.risk/100.0:.3f}.")
    print("\nAnd the leverage column shows the other half: at this risk setting even")
    print("the tightest stop here implies well under 1x leverage on $20. High")
    print("leverage does not arrive from a tight stop alone - it arrives from")
    print("raising RISK, which is the part already measured as ruinous.")


if __name__ == "__main__":
    main()
