"""LONG + REGIME-GATED SHORT — the first complementary pair in this project.

THE FINDING THIS BUILDS ON
    Measured in backtest/shortside.py, 9 coins, 1h:

                          bull regime   bear regime
        long  trail 12x      +259.0%       +79.8%
        short trail  5x       -15.0%        +5.3%

        short by year:  2021 -38.7% | 2022 +91.8% (DD 40.3%) | 2023 -57.1%
                        2024  -7.1% | 2025 +79.4% (DD 53.6%)

    Shorts are weak standalone (+0.056R against the long side's +0.674R) but they
    earn in precisely the regimes where the long book bleeds. That anti-correlation
    is the point, not the return.

    The long-only system needs crypto to rise - the objection raised repeatedly and
    correctly. A short sleeve that pays during declines is the only thing tested
    here that addresses it.

ASYMMETRIC EXITS ARE REQUIRED, NOT OPTIONAL
    Longs improve monotonically out to a 20xATR trail (+0.023 at 3x -> +0.897 at
    20x). Shorts do the OPPOSITE: best at 3-5x (+0.025/+0.028) and NEGATIVE at 20x
    (-0.023). Up-moves grind, crashes are fast, so a trail tuned for one gives back
    the other. Every earlier test used one trail for both and buried this.

WHAT IS MEASURED
    Three books sharing ONE position cap, so shorts compete for the same slots and
    the comparison is not secretly running twice the exposure:
        A  long only                          the control
        B  long + shorts, ungated             does adding shorts help at all?
        C  long + shorts gated below 200h MA  does the regime filter matter?

    The headline is not CAGR. It is whether DRAWDOWN falls, because drawdown is what
    sets the minimum viable capital and it is the binding constraint on a small
    account.

    python -m backtest.twoside
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import fetch  # noqa: E402
from backtest.convex import run_uncapped  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
         "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0          # asymmetric, per the sweep
SLOTS = 8
_D: dict = {}


def load(c, days=2400):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", days)
        except Exception:
            _D[c] = None
    return _D[c]


def short_trades(df, regime, trail):
    """Shorts via run_uncapped's NATIVE short handling (d = -1).

    BROKEN VERSION REMOVED 2026-09-12. The first implementation mirrored the price
    series around twice its FIRST close and traded the mirror as a long. That is
    only valid if the price never doubles. SOLUSDT rose 97x, so 92% of its mirrored
    bars were NEGATIVE prices (mirrored min -280 against a real max of 286), and
    since run_uncapped charges the fee as `fee * entry_price`, the fee came out with
    the wrong sign and magnitude. It flattered shorts roughly 4x - reporting
    +0.117R where the native path gives +0.028R - and it invalidated every
    two-sided result derived from it.

    Caught because two of my own tests disagreed on identical trade counts. The
    lesson: never transform the price series to reuse an engine. run_uncapped
    already handles d = -1 correctly - stop above entry, trail above the low water
    mark ratcheting down, R = (exit - entry) * d / risk, fee on the REAL price.

    Verified against backtest/shortside.py, which always used the native path.
    """
    sig = signals(df, "short", regime)
    R, idx, bars, _d = run_uncapped(df, sig, sl_mult=2.0, fee_bp=FEE_BP,
                                    mode="trail_atr", trail=trail)
    t = df["time"].to_numpy()
    return [(t[max(int(i) - int(b), 0)], t[int(i)], float(r), "S")
            for r, i, b in zip(R, idx, bars)]


def long_trades(df, trail, units):
    sig = signals(df, "long", "all")
    R, idx, _u, held = run_pyramid(df, sig, sl_mult=2.0, trail=trail,
                                   max_units=units, add_every=2.0, fee_bp=FEE_BP)
    t = df["time"].to_numpy()
    return [(t[max(int(i) - int(h), 0)], t[int(i)], float(r), "L")
            for r, i, h in zip(R, idx, held)]


def book(include_short, regime, risk, units=5):
    tr = []
    for c in COINS:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        tr += long_trades(df, LONG_TRAIL, units)
        if include_short:
            tr += short_trades(df, regime, SHORT_TRAIL)
    if not tr:
        return None
    tr.sort(key=lambda x: x[0])
    eq, curve, times, opens = 1.0, [], [], []
    taken = {"L": 0, "S": 0}
    ruined = False
    f = risk / 100.0
    for a, b, r, side in tr:
        opens = [u for u in opens if u > a]
        if len(opens) >= SLOTS:
            continue
        opens.append(b)
        taken[side] += 1
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 0.01:
                eq, ruined = 0.0, True
        curve.append(eq); times.append(b)
    if sum(taken.values()) < 30:
        return None
    cur = np.asarray(curve)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    mo = pd.Series(cur, index=ts).resample("30D").last().pct_change().dropna() * 100
    if ruined:
        mo = mo.iloc[:0]
    # per-year, to see whether the bear years stop hurting
    yr = {}
    s = pd.Series(cur, index=ts)
    for y, g in s.groupby(s.index.year):
        if len(g) > 5:
            yr[y] = (g.iloc[-1] / g.iloc[0] - 1) * 100
    return dict(L=taken["L"], S=taken["S"], cagr=cagr, dd=dd, ruined=ruined,
                mar=cagr / dd if dd > 0.5 else 0.0,
                mo_med=float(mo.median()) if len(mo) else float("nan"),
                pm=((1 + cagr / 100) ** (1 / 12) - 1) * 100 if cagr > -100 else -100,
                yr=yr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risk", type=float, default=0.1,
                    help="per unit; 0.1 x 5 units = 0.5%% total, the matched case")
    args = ap.parse_args()
    print(f"LONG + REGIME-GATED SHORT   {len(COINS)} coins, 1h, {SLOTS} shared "
          f"slots, {args.risk}%/unit")
    print(f"  asymmetric exits: long trail {LONG_TRAIL:.0f}xATR, "
          f"short trail {SHORT_TRAIL:.0f}xATR")
    print("  the headline is DRAWDOWN, not CAGR - drawdown sets the minimum "
          "viable capital\n")
    print("=" * 100)
    print(f"{'book':<30} {'longs':>6} {'shorts':>7} {'CAGR':>10} {'DD':>7} "
          f"{'MAR':>6} {'/month':>8}")
    res = {}
    for tag, inc, rg in (("A  long only", False, "all"),
                         ("B  long + short, ungated", True, "all"),
                         ("C  long + short, bear-gated", True, "bear")):
        d = book(inc, rg, args.risk)
        if not d:
            print(f"{tag:<30} (no result)")
            continue
        res[tag] = d
        ru = " RUIN" if d["ruined"] else ""
        print(f"{tag:<30} {d['L']:>6} {d['S']:>7} {d['cagr']:>+9.1f}% "
              f"{d['dd']:>6.1f}% {d['mar']:>+6.2f} {d['pm']:>+7.2f}%{ru}",
              flush=True)

    if len(res) < 2:
        return
    print("\n" + "=" * 100)
    print("BY YEAR — does the short sleeve stop the bear years hurting?")
    print("=" * 100)
    years = sorted({y for d in res.values() for y in d["yr"]})
    print(f"{'book':<30} " + " ".join(f"{y:>9}" for y in years))
    for tag, d in res.items():
        print(f"{tag:<30} " +
              " ".join(f"{d['yr'].get(y, float('nan')):>+8.1f}%" for y in years))
    a = res.get("A  long only")
    for tag in ("B  long + short, ungated", "C  long + short, bear-gated"):
        d = res.get(tag)
        if a and d:
            print(f"\n{tag}: drawdown {a['dd']:.1f}% -> {d['dd']:.1f}% "
                  f"({d['dd']-a['dd']:+.1f}pp), CAGR {a['cagr']:+.1f}% -> "
                  f"{d['cagr']:+.1f}%, MAR {a['mar']:+.2f} -> {d['mar']:+.2f}")
    print("\nA short sleeve earns its place by cutting DRAWDOWN even if it costs "
          "CAGR - lower\ndrawdown lowers the capital floor, and that floor is what "
          "has blocked every\nsmall-account configuration measured today.")


if __name__ == "__main__":
    main()
