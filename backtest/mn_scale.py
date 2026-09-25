"""HOW BIG CAN THE MARKET-NEUTRAL BOOK BE? - basket width, and the size the tail buys.

THE GOAL THIS SERVES
    "Crazy gains in every market, not just a bull." The product earns +71%/mo in rising markets
    and +7.6% in falling ones, and +0.2% average / -4.5% typical in SIDEWAYS, with only 32% of
    sideways months up (logs/machine.txt). 25 of 79 months are sideways. That one cell is the
    whole gap between what the book is and what it is supposed to be.

    The chop arithmetic per month (logs/final_regimes.txt):
        trend -5.2%   market-neutral +4.3%   bear sleeve -0.7%   crash bids +1.4%  =  +0.2%

    Three of those four are fixed:
      * TREND cannot be cut in chop - dd_fixes.py measured -0.46 to -4.48 %/mo for every chop
        gate, 0-2 wins of 10. It must be in the market to catch the turn into bull.
      * SLEEVE only trades in bears by construction.
      * CRASH BIDS are already in at 1x and doc 16 caps them for a reason.
    So the sideways cell is decided by how big the MARKET-NEUTRAL book can safely be.

WHY BASKET WIDTH, AND WHY A STOP WAS THE WRONG ANSWER
    The book is capped at 1x by a single number - a -24.2% worst week on the whole account.
    mn_stop.py tried to cut that with a per-name stop on the short leg and FAILED: the stop fires
    on 0.3% of positions at +100% and makes the worst week WORSE (-26.3%), because it books the
    bottom of a squeeze that reverts inside the week. That test also corrected its own premise -
    the single-name blow-ups in logs/carry_check.txt (MYX +1137%) belong to the FUNDING CARRY
    variant, not to the momentum book that is actually deployed.

    Concentration is the part that was never tested. `frac=0.1` is hard-coded as the default in
    market_neutral.run, bear_chop.fast_run, crash_days.mn_basket and bear_shorts.weakest, and it
    is not swept anywhere in the repo. On the PIT top-60 a decile is SIX names a side - doc 10
    section 174 notices this and leaves it. One name is a sixth of a leg; at frac 0.25 it is a
    fifteenth. If the tail is concentration rather than a single blow-up, width cuts it and a
    stop does not, which is exactly the pattern mn_stop.py found.

WHAT DECIDES IT
    Not return, and not the tail - the ratio. A wider basket that earns less per unit but carries
    a smaller tail can be run BIGGER, and what reaches the chop months is (return x multiplier)
    at an unchanged worst week. That comparison is the last table.

REGISTERED PREDICTIONS (before running, 2026-09-26)
    1. The mean FALLS monotonically as frac rises - cross-sectional momentum is strongest at the
       extremes, so widening dilutes the signal.
    2. The worst week improves from -24.2% to about -15% by frac 0.25, but NOT as fast as 1/k,
       because the names that hurt move together.
    3. Sharpe peaks at an interior frac between 0.15 and 0.25.
    4. Chop falls with frac but stays above +1.0%/wk at 0.25.
    5. THE ONE THAT MATTERS: at a FIXED worst week, a wider basket delivers more chop return than
       frac 0.10 does. If this is wrong, the book is stuck at 1x and the sideways cell cannot be
       fixed from this direction.
    6. Both halves agree on the direction of 1-4, even though the holdout is mined out - this is
       a risk measurement, not a tuned parameter.

    python -m backtest.mn_scale
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

LOOK, HOLD, MIN_NAMES = 30, 7, 20
FRACS = (0.10, 0.15, 0.20, 0.25, 0.33, 0.50)
CUT = pd.Timestamp("2024-08-29")


def run_frac(C, F, first, elig, frac):
    idx = C.index
    rows, prev_long, prev_short, ks = [], set(), set(), []
    for i in range(LOOK + 1, len(idx) - HOLD, HOLD):
        t0 = idx[i]
        month = t0.strftime("%Y-%m")
        ok = [s for s in C.columns
              if month in elig.get(s, ()) and (t0 - first[s]).days >= MIN_AGE_D
              and np.isfinite(C[s].iat[i]) and np.isfinite(C[s].iat[i - LOOK])]
        if len(ok) < MIN_NAMES:
            continue
        past = pd.Series({s: C[s].iat[i] / C[s].iat[i - LOOK] - 1 for s in ok})
        k = max(int(len(past) * frac), 3)
        order = past.sort_values().index
        shorts, longs = list(order[:k]), list(order[-k:])
        ks.append(k)

        def exit_px(s):
            v = C[s].iloc[i:i + HOLD + 1].dropna()
            return float(v.iloc[-1]) if len(v) else float(C[s].iat[i])

        fwd = {s: exit_px(s) / C[s].iat[i] - 1 for s in ok}
        fnd = {s: float(F[s].iloc[i:i + HOLD].sum()) if s in F else 0.0 for s in ok}
        lr = float(np.mean([fwd[s] for s in longs]))
        sr = float(np.mean([fwd[s] for s in shorts]))
        lf = float(np.mean([fnd[s] for s in longs]))
        sf = float(np.mean([fnd[s] for s in shorts]))
        gross = 0.5 * lr - 0.5 * sr
        carry = 0.5 * (-lf) + 0.5 * sf
        turn = (len(set(longs) ^ prev_long) + len(set(shorts) ^ prev_short)) / (2 * k * 2)
        cost = FEE * min(turn, 1.0)
        prev_long, prev_short = set(longs), set(shorts)
        rows.append(dict(t=t0, net=gross + carry - cost))
    df = pd.DataFrame(rows)
    df.attrs["k"] = float(np.mean(ks)) if ks else 0.0
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
    lab = np.array([reg.asof(t) if t >= reg.index[0] else "chop" for t in pd.DatetimeIndex(d.t)])
    out = dict(mean=n.mean() * 100, worst=n.min() * 100, k=df.attrs["k"],
               dd=float((1 - cur / np.maximum.accumulate(cur)).max() * 100),
               shrp=n.mean() / n.std(ddof=1) * np.sqrt(52) if n.std(ddof=1) else np.nan)
    for r in ("bull", "bear", "chop"):
        out[r] = n[lab == r].mean() * 100 if (lab == r).any() else np.nan
    return out


def main():
    print("loading the point-in-time panel...")
    C, F, first = load_panel()
    elig = drop_non_crypto(eligibility(60))
    reg = btc_regime(C)
    print(f"PIT top-60 | {LOOK}d momentum | weekly | long top frac / short bottom frac")
    print()
    print("1. BASKET WIDTH, full history")
    print(f"  {'frac':>6}{'names/side':>12}{'%/wk':>8}{'bull':>8}{'bear':>8}{'CHOP':>8}"
          f"{'Sharpe':>8}{'DD':>7}{'worst wk':>10}")
    keep = {}
    for f in FRACS:
        df = run_frac(C, F, first, elig, f)
        keep[f] = df
        s = stats(df, reg)
        flag = "  <- TODAY" if abs(f - 0.10) < 1e-9 else ""
        print(f"  {f:>6.2f}{s['k']:>12.0f}{s['mean']:>+7.3f}%{s['bull']:>+7.3f}%"
              f"{s['bear']:>+7.3f}%{s['chop']:>+7.3f}%{s['shrp']:>8.2f}{s['dd']:>6.0f}%"
              f"{s['worst']:>+9.1f}%{flag}")

    print()
    print(f"2. BOTH HALVES - tune < {CUT:%Y-%m-%d} <= holdout")
    print(f"  {'frac':>6}{'TUNE/wk':>10}{'DD':>6}{'worst':>9}{'HOLD/wk':>10}{'DD':>6}"
          f"{'worst':>9}{'HOLD chop':>11}")
    for f in FRACS:
        t, h = stats(keep[f], reg, t_to=CUT), stats(keep[f], reg, t_from=CUT)
        if not t or not h:
            continue
        print(f"  {f:>6.2f}{t['mean']:>+9.3f}%{t['dd']:>5.0f}%{t['worst']:>+8.1f}%"
              f"{h['mean']:>+9.3f}%{h['dd']:>5.0f}%{h['worst']:>+8.1f}%{h['chop']:>+10.3f}%")

    print()
    print("3. THE TEST THAT DECIDES IT - each width scaled to the SAME worst week as frac 0.10")
    print("   (that is the constraint that holds the book at 1x; equalise it and compare)")
    base = stats(keep[0.10], reg)
    tgt = abs(base["worst"])
    print(f"  target worst week = {base['worst']:+.1f}% (frac 0.10 at 1x)")
    print(f"  {'frac':>6}{'mult':>8}{'%/wk':>9}{'CHOP/wk':>10}{'CHOP/mo':>10}{'DD':>7}"
          f"{'vs today':>11}")
    best = None
    for f in FRACS:
        s = stats(keep[f], reg)
        m = tgt / abs(s["worst"]) if s["worst"] else 0.0
        chop_mo = ((1 + s["chop"] * m / 100) ** (365.25 / 12 / 7) - 1) * 100
        base_mo = ((1 + base["chop"] / 100) ** (365.25 / 12 / 7) - 1) * 100
        d = chop_mo - base_mo
        if best is None or chop_mo > best[1]:
            best = (f, chop_mo, m, s)
        print(f"  {f:>6.2f}{m:>8.2f}x{s['mean'] * m:>+8.3f}%{s['chop'] * m:>+9.3f}%"
              f"{chop_mo:>+9.2f}%{s['dd'] * m:>6.0f}%{d:>+10.2f}%")
    print()
    f, chop_mo, m, s = best
    print(f"  BEST AT EQUAL TAIL RISK: frac {f:.2f} at {m:.2f}x -> {chop_mo:+.2f}%/mo in chop")
    print(f"  against frac 0.10 at 1.00x -> {base_mo:+.2f}%/mo.")
    print()
    print("  Feed that into the sideways cell: trend -5.2, sleeve -0.7, bids +1.4, MN as above.")
    print(f"    today   -5.2 - 0.7 + 1.4 + {base_mo:.1f} = {-5.2 - 0.7 + 1.4 + base_mo:+.1f}%/mo")
    print(f"    this    -5.2 - 0.7 + 1.4 + {chop_mo:.1f} = {-5.2 - 0.7 + 1.4 + chop_mo:+.1f}%/mo")
    print("  (a first-order sum, not a simulation - the mix has to confirm it)")


if __name__ == "__main__":
    main()
