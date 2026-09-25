"""CAN THE MARKET-NEUTRAL BOOK BE MADE SCALABLE? - a stop on the short leg.

WHY THIS, AND WHY IT IS THE ONLY LEVER LEFT FOR CHOP
    The product earns in rising markets (+71%/mo) and falling ones (+7.6%), and approximately
    nothing in SIDEWAYS: +0.2% average, -4.5% typical, 32% of months up (logs/machine.txt).
    Sideways is 25 of 79 months, so "gains in every market" is decided here and nowhere else.

    The chop arithmetic, per month (logs/final_regimes.txt):
        trend -5.2%   market-neutral +4.3%   bear sleeve -0.7%   crash bids +1.4%  =  +0.2%

    Two of those four cannot move.
      * The TREND book cannot be cut in chop. dd_fixes.py already tested it - chop 1h x0.5 is
        -0.46 tune / -0.48 holdout %/mo, chop all x0 is -3.59 / -4.48, and the win counts are
        0-2 of 10. The book has to be IN the market during chop to catch the turn into bull;
        its chop losses are the premium for the bull payoff.
      * The SLEEVE only trades in bears by construction.

    That leaves the market-neutral book, the one book that earns in every regime (+1.394%/wk in
    chop, +2.198% bull, +1.731% bear, logs/carry_check.txt). It is held at 1x. Not because 1x is
    optimal - because of ONE number: its worst week is -24.2% of the whole account. At 2x that is
    -48%, at 3x -73%. max_mix.py's header says the falls it reports are "slightly too shallow for
    large MN shares", so the model understates the danger exactly where the size question lives.

THE MECHANISM THIS ATTACKS
    The book is long the top momentum decile and SHORT THE BOTTOM decile - beaten-down coins,
    which are exactly the ones that squeeze. With 60 names and frac 0.1 there are 6 per side, so
    ONE short at +1137% (MYX, 2025-09-05) moves the basket mean by +190% and the account by -95%.
    Every one of the five worst weeks in logs/carry_check.txt names a single exploding short, and
    the short leg has no stop of any kind - grep market_neutral.py for one.

    So this is not a search for an edge. It is a tail cut on a book whose mean is already
    established, and its purpose is to buy back the size that the tail is charging for.

METHOD
    Per short name, walk the DAILY closes across the hold. The first close at or beyond the stop
    exits that name there - not at the stop level, at the close that breached it, so a gap
    through the stop is paid in full. The freed capital sits in cash for the rest of the week.
    One extra round trip of fees is charged on every stopped name.
    A real bot checking intraday would stop MORE often (whipsaw) and exit EARLIER (less gap):
    those pull in opposite directions, so daily closes are a middle, not a best case.

REGISTERED PREDICTIONS (before running, 2026-09-26)
    1. A stop at +100% cuts the worst week from -24.2% to about -15%, and the drawdown from 37%
       to under 30%.
    2. The MEAN return FALLS, by 0.1-0.2 %/wk. Stops cost money on average: you exit at the worst
       moment and beaten-down coins mean-revert. If the mean RISES instead, look for the bug
       before believing it.
    3. Chop stays clearly positive, +1.0 to +1.4 %/wk.
    4. Sharpe improves anyway, because the tail shrinks faster than the mean.
    5. There is an interior optimum around +75% to +150%. Tighter and the stop fires on ordinary
       volatility; looser and it never binds.
    6. Fewer than 3% of short positions are stopped at +100%.

    python -m backtest.mn_stop
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.market_neutral import (FEE, btc_regime, drop_non_crypto,  # noqa: E402
                                     load_panel)
from backtest.wide_book import MIN_AGE_D, eligibility  # noqa: E402

LOOK, HOLD, FRAC, MIN_NAMES = 30, 7, 0.1, 20
STOPS = (0.50, 0.75, 1.00, 1.50, 2.00, 3.00, None)
CUT = "2024-08-29"


def run_stop(C, F, first, elig, short_stop=None, long_stop=None):
    """market_neutral.run, with an optional per-name stop checked on daily closes."""
    idx = C.index
    rows, prev_long, prev_short = [], set(), set()
    n_short = n_stopped = 0
    for i in range(LOOK + 1, len(idx) - HOLD, HOLD):
        t0 = idx[i]
        month = t0.strftime("%Y-%m")
        ok = [s for s in C.columns
              if month in elig.get(s, ()) and (t0 - first[s]).days >= MIN_AGE_D
              and np.isfinite(C[s].iat[i]) and np.isfinite(C[s].iat[i - LOOK])]
        if len(ok) < MIN_NAMES:
            continue
        past = pd.Series({s: C[s].iat[i] / C[s].iat[i - LOOK] - 1 for s in ok})
        k = max(int(len(past) * FRAC), 3)
        order = past.sort_values().index
        shorts, longs = list(order[:k]), list(order[-k:])

        def path_exit(s, stop, sign):
            """sign=+1: we are SHORT, so a RISE hurts. sign=-1: we are LONG, a FALL hurts.
            Returns (forward return of the COIN, whether it was stopped)."""
            e = C[s].iat[i]
            v = C[s].iloc[i:i + HOLD + 1].dropna()
            if len(v) == 0:
                return 0.0, False
            if stop is not None:
                r = v.to_numpy(float) / e - 1.0
                hit = np.nonzero(sign * r >= stop)[0]
                if len(hit):
                    return float(r[hit[0]]), True          # the close that BREACHED it
            return float(v.iloc[-1]) / e - 1.0, False

        sret, lret, stopped = [], [], 0
        for s in shorts:
            r, st = path_exit(s, short_stop, +1)
            sret.append(r)
            stopped += st
        for s in longs:
            r, st = path_exit(s, long_stop, -1)
            lret.append(r)
            stopped += st
        n_short += len(shorts)
        n_stopped += stopped
        fnd = {s: float(F[s].iloc[i:i + HOLD].sum()) if s in F else 0.0 for s in ok}
        lr, sr = float(np.mean(lret)), float(np.mean(sret))
        lf = float(np.mean([fnd[s] for s in longs]))
        sf = float(np.mean([fnd[s] for s in shorts]))
        gross = 0.5 * lr - 0.5 * sr
        carry = 0.5 * (-lf) + 0.5 * sf
        turn = (len(set(longs) ^ prev_long) + len(set(shorts) ^ prev_short)) / (2 * k * 2)
        cost = FEE * min(turn, 1.0) + FEE * stopped / (2 * k)      # stops pay an extra trip
        prev_long, prev_short = set(longs), set(shorts)
        rows.append(dict(t=t0, net=gross + carry - cost, gross=gross, carry=carry))
    df = pd.DataFrame(rows)
    df.attrs["stop_rate"] = n_stopped / max(n_short, 1) * 100
    return df


def stats(df, reg, t_from=None, t_to=None):
    d = df
    if t_from is not None:
        d = d[d.t >= t_from]
    if t_to is not None:
        d = d[d.t < t_to]
    n = d["net"].to_numpy(float)
    if len(n) < 10:
        return None
    cur = np.cumprod(1 + n)
    dd = float((1 - cur / np.maximum.accumulate(cur)).max() * 100)
    lab = np.array([reg.asof(t) if t >= reg.index[0] else "chop" for t in pd.DatetimeIndex(d.t)])
    out = dict(mean=n.mean() * 100, dd=dd, worst=n.min() * 100,
               shrp=n.mean() / n.std(ddof=1) * np.sqrt(52) if n.std(ddof=1) else np.nan,
               stop=df.attrs["stop_rate"], n=len(n))
    for r in ("bull", "bear", "chop"):
        out[r] = n[lab == r].mean() * 100 if (lab == r).any() else np.nan
    return out


def main():
    print("loading the point-in-time panel (this takes a moment)...")
    C, F, first = load_panel()
    elig = drop_non_crypto(eligibility(60))
    reg = btc_regime(C)
    print(f"PIT top-60 | {LOOK}d momentum | weekly | long top decile, SHORT BOTTOM decile")
    print("the stop is on the SHORT leg, checked on daily closes, exiting at the close that "
          "breached it")
    print()
    print("1. THE SWEEP - full history")
    print(f"  {'short stop':>11}{'%/wk':>8}{'bull':>8}{'bear':>8}{'CHOP':>8}{'Sharpe':>8}"
          f"{'DD':>7}{'worst wk':>10}{'stopped':>9}")
    keep = {}
    for s in STOPS:
        df = run_stop(C, F, first, elig, short_stop=s)
        keep[s] = df
        st = stats(df, reg)
        lab = "none" if s is None else f"+{s:.0%}"
        flag = "  <- TODAY" if s is None else ""
        print(f"  {lab:>11}{st['mean']:>+7.3f}%{st['bull']:>+7.3f}%{st['bear']:>+7.3f}%"
              f"{st['chop']:>+7.3f}%{st['shrp']:>8.2f}{st['dd']:>6.0f}%{st['worst']:>+9.1f}%"
              f"{st['stop']:>8.1f}%{flag}")

    print()
    print(f"2. BOTH HALVES - tune < {CUT} <= holdout. A tail cut must hold on both.")
    print(f"  {'short stop':>11}{'TUNE/wk':>10}{'DD':>6}{'worst':>9}{'HOLD/wk':>10}{'DD':>6}"
          f"{'worst':>9}{'HOLD chop':>11}")
    cut = pd.Timestamp(CUT)
    for s in STOPS:
        t = stats(keep[s], reg, t_to=cut)
        h = stats(keep[s], reg, t_from=cut)
        if not t or not h:
            continue
        lab = "none" if s is None else f"+{s:.0%}"
        print(f"  {lab:>11}{t['mean']:>+9.3f}%{t['dd']:>5.0f}%{t['worst']:>+8.1f}%"
              f"{h['mean']:>+9.3f}%{h['dd']:>5.0f}%{h['worst']:>+8.1f}%{h['chop']:>+10.3f}%")

    print()
    print("3. WHAT SIZE THE TAIL BUYS - worst week of the MN book alone, at each multiplier")
    print(f"  {'short stop':>11}{'1.0x':>9}{'1.5x':>9}{'2.0x':>9}{'2.5x':>9}{'3.0x':>9}")
    for s in STOPS:
        st = stats(keep[s], reg)
        lab = "none" if s is None else f"+{s:.0%}"
        cells = "".join(f"{st['worst'] * m:>+8.1f}%" for m in (1.0, 1.5, 2.0, 2.5, 3.0))
        print(f"  {lab:>11}{cells}")
    print()
    print("  A multiplier is usable only while the worst week stays survivable ALONGSIDE the")
    print("  trend book's own fall. That is the number that decides the chop months.")


if __name__ == "__main__":
    main()
