"""THE REGIME FILTER IS LOOKING THROUGH THE WRONG END OF THE TELESCOPE.

    python -m backtest.regime

WHAT IS IN FRONT OF US
    The deployed book's whole history is two years carrying six:

        2020    2021     2022    2023    2024    2025    2026
        +276%  +1213%   -167%   +639%   +906%    -10%    +48%

    2021 and 2024 made everything. 2025 lost. And 2025-2026 produced 2.5% of lifetime
    profit on 30% of the trades. Those are MULTI-YEAR regimes.

    The gate that is supposed to handle this scales risk to x0.25 while BTC sits below
    its 200-HOUR average. 200 hours is EIGHT AND A HALF DAYS. It is being asked to
    separate a two-year bull market from a two-year bleed, with an eight-day lookback.

    backtest/opt200.py swept the gate in 3 cells - off, x0.5, x0.25 - all of which vary
    the MULTIPLIER. The LOOKBACK was never varied, and `btc_bear()` hardcodes
    rolling(200). So the one dimension that decides whether the filter can see the thing
    it exists for has never been tested.

    Second gap: `regime=0.0` currently means "gate disabled", so there has never been a
    GO FLAT option. Only "trade smaller in a bear", never "do not trade in a bear" -
    even though the bear years are where the losses are.

WHY DRAWDOWN IS THE REAL PRIZE, NOT RETURN
    From this project's own capital-floor formula:

        floor = min_order x stop_fraction / risk_fraction / (1 - maxDD)

    Drawdown enters as 1/(1 - maxDD). At 57.7% that multiplier is 2.36x; at 40% it is
    1.67x. So cutting drawdown lowers the capital floor AND frees risk budget: less
    drawdown for the same return means you can spend the difference on position size.
    DRAWDOWN IS THE BUDGET AND RETURN IS WHAT YOU BUY WITH IT. Every lever in this file
    is therefore judged on return-per-unit-drawdown (MAR), not on return.

THE STATISTICAL TRAP, STATED BEFORE THE RESULTS
    A 200-day moving average over 6.6 years produces only a HANDFUL of regime switches.
    A long lookback that wins may have won on three lucky calls, and there is no way to
    fix that with this much data. So:
      * the 60/40 time holdout is reported for every cell, not just the winner
      * a cell that wins in-sample and dies out-of-sample is called out as such
      * MAR is the ranking statistic, because return alone rewards luck on a few calls
    Read a long-lookback win as a hypothesis, not a result.

REGISTERED PREDICTION (2026-09-14, before running)
    Longer lookbacks BEAT 200h on MAR, because the thing being detected is slow. The
    best cell is somewhere between 1,000h (~6 weeks) and 3,000h (~4 months) - long
    enough to see a cycle, short enough to still switch a few times in 6 years. GO FLAT
    beats x0.25 on drawdown and loses on return. And the very longest lookbacks
    (4,800h) will look great and fail the holdout, having made only 2-3 calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.opt200 import (BASE, coin_trades, floor_for,  # noqa: E402
                             load, split_times)

LOOKBACKS = [200, 500, 1000, 2000, 3000, 4800]      # hours
ACTIONS = [("x0.50", 0.50), ("x0.25", 0.25), ("FLAT", 0.0)]
_BEAR: dict = {}


def bear_series(lookback: int) -> pd.Series:
    """BTC below its own N-hour average, shifted one bar so a decision never reads
    the bar it is deciding on. Same convention as opt200.btc_bear, lookback opened up."""
    if lookback not in _BEAR:
        d = load("BTCUSDT")
        ma = d["close"].rolling(lookback).mean()
        b = (d["close"] < ma).shift(1).fillna(False).to_numpy(bool)
        _BEAR[lookback] = pd.Series(b, index=pd.DatetimeIndex(d["time"]))
    return _BEAR[lookback]


def book(lookback, mult, t_from=None, t_to=None):
    """Portfolio pass with a parameterised regime lookback and a real FLAT option.

    mult == 0.0 means SKIP THE TRADE, which is not what opt200's regime=0.0 meant
    (there it disabled the gate). A trade skipped in a bear also frees its slot, which
    is part of the mechanism and not a side effect: capital not risked on a bear-market
    entry is available for the next non-bear signal.
    """
    tr = coin_trades(BASE["trail_l"], BASE["trail_s"], BASE["add_every"], BASE["be"])
    bear = bear_series(lookback)
    f0 = BASE["risk"] / 100.0
    eq, peak, dd = 1.0, 1.0, 0.0
    opens: list[tuple] = []
    Rs, sides, skipped, declined = [], [], 0, 0
    day_pnl: dict = {}
    for a, b, r, side in tr:
        if t_from is not None and a < t_from:
            continue
        if t_to is not None and a >= t_to:
            continue
        opens = [u for u in opens if u[0] > a]
        if len(opens) >= BASE["slots"]:
            declined += 1
            continue
        try:
            is_bear = bool(bear.asof(a))
        except Exception:
            is_bear = False
        f = f0 * (mult if is_bear else 1.0)
        if f <= 0.0:
            skipped += 1
            continue
        opens.append((b, side))
        Rs.append(r); sides.append(side)
        # Compound BY DATE, not by trade. Compounding trade-by-trade was mistake #6 -
        # it invented sequencing that never happened and drove equity to 1e-9.
        # `b` arrives as numpy.datetime64 from coin_trades, which has no .date()
        ed = pd.Timestamp(b).date()
        day_pnl.setdefault(ed, 0.0)
        day_pnl[ed] += r * f
    if not Rs:
        return None
    for d in sorted(day_pnl):
        eq *= (1.0 + day_pnl[d])
        if eq <= 0:
            eq = 1e-9
        peak = max(peak, eq)
        dd = max(dd, (peak - eq) / peak * 100.0)
    days = (max(day_pnl) - min(day_pnl)).days or 1
    months = days / 30.44
    hpm = ((eq ** (1.0 / months)) - 1.0) * 100.0 if eq > 0 and months > 0 else -100.0
    mar = (hpm * 12.0 / dd) if dd > 0 else float("nan")
    return dict(n=len(Rs), skipped=skipped, declined=declined, hpm=hpm, dd=dd,
                mar=mar, floor=floor_for(BASE["risk"], dd), eq=eq)


HDR = (f"  {'lookback':<20}{'n':>6}{'skip':>6}{'/mo':>9}{'DD':>8}{'MAR':>7}"
       f"{'floor $':>10}")


def row(tag, d):
    if not d:
        return f"  {tag:<20}{'(no trades)':>20}"
    return (f"  {tag:<20}{d['n']:>6}{d['skipped']:>6}{d['hpm']:>+8.2f}%"
            f"{d['dd']:>7.1f}%{d['mar']:>7.2f}{d['floor']:>10,.0f}")


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: longer beats 200h on MAR; best between 1,000h and")
    print("3,000h; FLAT beats x0.25 on drawdown and loses on return; 4,800h looks")
    print("great and fails the holdout on 2-3 calls.\n")

    cut = split_times()
    print(f"holdout split at {cut:%Y-%m-%d}\n")

    base = book(200, 1.0)          # gate effectively off: mult 1.0 in bear = no change
    print("=" * 92)
    print("0. NO GATE AT ALL (the reference)")
    print("=" * 92)
    print(HDR)
    print(row("none", base))

    best = []
    for name, mult in ACTIONS:
        print("\n" + "=" * 92)
        print(f"{name}  — risk multiplier while BTC is below its N-hour average"
              + ("   (FLAT = skip the trade entirely)" if mult == 0 else ""))
        print("=" * 92)
        print(HDR)
        for lb in LOOKBACKS:
            d = book(lb, mult)
            print(row(f"{lb}h ({lb/24:.0f}d)", d))
            if d:
                best.append((d["mar"], name, lb, d))

    print("\n" + "=" * 92)
    print("HOLDOUT — every cell, not just the winner. IS = first 60%, OOS = last 40%.")
    print("=" * 92)
    print(f"  {'cell':<22}{'IS /mo':>10}{'OOS /mo':>10}{'IS DD':>8}{'OOS DD':>8}"
          f"{'verdict':>13}")
    for _m, name, lb, _d in sorted(best, reverse=True)[:8]:
        mult = dict(ACTIONS)[name]
        i = book(lb, mult, t_to=cut)
        o = book(lb, mult, t_from=cut)
        if not i or not o:
            print(f"  {name + ' ' + str(lb) + 'h':<22}{'one half empty':>30}")
            continue
        a, b = i["hpm"], o["hpm"]
        if a > 0 and b > 0:
            v = "HOLDS"
        elif a > 0 >= b:
            v = "dies OOS"
        elif b > 0 >= a:
            v = "ONE REGIME"
        else:
            v = "dead both"
        print(f"  {name + ' ' + str(lb) + 'h':<22}{a:>+9.2f}%{b:>+9.2f}%"
              f"{i['dd']:>7.1f}%{o['dd']:>7.1f}%{v:>13}")

    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92)
    if not best:
        print("  nothing ran")
        return
    best.sort(reverse=True)
    m, name, lb, d = best[0]
    bl = next((x for x in best if x[1] == "x0.25" and x[2] == 200), None)
    print(f"  best by MAR: {name} at {lb}h ({lb/24:.0f} days) — "
          f"{d['hpm']:+.2f}%/mo at {d['dd']:.1f}% DD, MAR {m:.2f}")
    if bl:
        print(f"  deployed   : x0.25 at 200h (8 days)    — "
              f"{bl[3]['hpm']:+.2f}%/mo at {bl[3]['dd']:.1f}% DD, MAR {bl[0]:.2f}")
    if base:
        print(f"  no gate    :                            "
              f"{base['hpm']:+.2f}%/mo at {base['dd']:.1f}% DD, "
              f"MAR {base['mar']:.2f}")
    print("\n  Judge on MAR and on the holdout, not on /mo. A long lookback makes few")
    print("  calls, so a high return can be three lucky ones - which is exactly why")
    print("  every cell's holdout is printed above rather than only the winner's.")


if __name__ == "__main__":
    main()
