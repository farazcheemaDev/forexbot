"""IS THE 3x HINDSIGHT PENALTY THE SAME IN EVERY YEAR? IT IS APPLIED AS IF IT IS.

    python -m backtest.hindsight

THE ASSUMPTION UNDER ATTACK
    Every honest figure in this project divides by HINDSIGHT = 3.0. That number was
    measured ONCE over the whole history, two ways that agreed:
        pit_universe.py   point-in-time universe vs today's top coins -> 3.03-3.05x
        small_book.py     719.8%/yr fixed book vs 240.1%/yr point-in-time -> 3.00x
    Two independent measurements agreeing is why it was trusted, and it is still the
    right correction for a LIFETIME figure.

    But it is then applied FLAT to every sub-period, including "2026 onward". Nobody
    ever checked whether the premium is constant in time, and there is a strong reason
    to think it is not:

        The premium is the value of KNOWING WHICH COINS WOULD MATTER. In 2020-2021 that
        knowledge was worth a fortune - today's names were tiny or did not exist, and
        the coins that were actually liquid then have largely died. By 2025-2026 the
        universe is settled: the coins in the book were already liquid, already ranked
        where they rank now. There is much less to know in advance.

    If that is right, a flat 3.0x over-penalises recent performance - which is exactly
    the window used to set the forward expectation. Every recent number in this project
    would be too low, by up to 3x.

    The opposite is also possible and would make things WORSE: if the premium is LARGER
    recently - because the book's cheap alts are the survivors of a cohort that mostly
    died in 2022-2024 - then the honest recent figure is lower still.

HOW IT IS MEASURED
    Two books, one engine, split by year.

      FIXED  the 12 coins actually deployed in blend_paper.py. Chosen in 2026 with full
             knowledge of what survived. This is the book whose numbers get quoted.
      PIT    top 12 by realised dollar volume in the PRIOR month, drawn from every coin
             available including the 202 DELISTED ones. This is what a person could
             actually have picked at the time, with no knowledge of the future.

    premium_year = fixed mean R / PIT mean R

    Mean R per trade is the ratio statistic rather than annual return, because a ratio
    of returns is meaningless the moment one side is negative, and in 2025 both sides
    are near zero. Sign disagreements are reported rather than divided through.

REGISTERED PREDICTION (2026-09-14, before running)
    The premium SHRINKS over time: well above 3x in 2020-2021, near 1x by 2025-2026.
    Therefore the flat 3.0x over-penalises the recent window and the honest recent
    expectation is HIGHER than the ~2%/month previously reported - though not by the
    full 3x, and not enough to reach 10%/month.

    If instead the premium is flat or rising, the flat divisor stands, recent numbers
    are right or generous, and this line of argument is closed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.blend import BOOK as DEPLOYED                       # noqa: E402
from backtest.pit_universe import (load_all, monthly_volume,      # noqa: E402
                                   trades_for)

TOP = 12            # match the deployed book size exactly


def all_trades(frames, symbols=None):
    out = []
    for s, df in frames.items():
        if symbols is not None and s not in symbols:
            continue
        for t_in, t_out, r in trades_for(df):
            out.append((pd.Timestamp(t_in), pd.Timestamp(t_out), float(r), s))
    out.sort(key=lambda x: x[0])
    return out


def by_year(trades, allowed=None, slots=12):
    """Per-year mean R and trade count, with the slot cap applied chronologically.

    The slot cap has to be applied over the WHOLE stream and the results bucketed
    afterwards - not applied inside each year - otherwise every year starts with an
    empty book and takes trades the real bot could not have taken.
    """
    rows = []
    open_until: list = []
    for t_in, t_out, r, s in trades:
        if allowed is not None:
            ok = allowed.get(pd.Timestamp(t_in).to_period("M"))
            if ok is None or s not in ok:
                continue
        open_until = [u for u in open_until if u > t_in]
        if len(open_until) >= slots:
            continue
        open_until.append(t_out)
        rows.append((t_in.year, r))
    if not rows:
        return {}
    d = pd.DataFrame(rows, columns=["year", "R"])
    return {int(y): (float(g["R"].mean()), len(g), float(g["R"].sum()))
            for y, g in d.groupby("year")}


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: the premium SHRINKS over time - well above 3x in")
    print("2020-21, near 1x by 2025-26 - so the flat 3.0x over-penalises the recent")
    print("window. If it is flat or rising, this argument is closed.\n")

    print("loading every coin, alive and delisted...", flush=True)
    frames = load_all(verbose=False)
    print(f"  {len(frames)} coins loaded")
    have = [c for c in DEPLOYED if c in frames]
    missing = [c for c in DEPLOYED if c not in frames]
    if missing:
        print(f"  ! deployed coins absent from this universe: {missing}")
    print(f"  deployed book: {len(have)} of {len(DEPLOYED)} coins usable")

    vol = monthly_volume(frames)
    allowed = {}
    for per, rowv in vol.iterrows():
        top = rowv.dropna().sort_values(ascending=False).head(TOP)
        # ranked on the PRIOR month, so the universe never reads its own month
        allowed[per + 1] = set(top.index)
    print(f"  point-in-time universe built for {len(allowed)} months\n")

    fixed = by_year(all_trades(frames, set(have)), allowed=None, slots=TOP)
    pit = by_year(all_trades(frames), allowed=allowed, slots=TOP)

    print("=" * 92)
    print("THE HINDSIGHT PREMIUM, YEAR BY YEAR")
    print("=" * 92)
    print(f"  {'year':<7}{'FIXED meanR':>13}{'n':>7}{'PIT meanR':>12}{'n':>7}"
          f"{'premium':>10}   note")
    prem = {}
    for y in sorted(set(fixed) | set(pit)):
        f = fixed.get(y)
        p = pit.get(y)
        if not f or not p:
            print(f"  {y:<7}{'(one side missing)':>30}")
            continue
        fm, fn, _fs = f
        pm, pn, _ps = p
        if pm > 0 and fm > 0:
            r = fm / pm
            prem[y] = r
            note = ""
        elif fm > 0 >= pm:
            r = float("inf")
            note = "PIT <= 0: hindsight is the WHOLE edge"
        elif pm > 0 >= fm:
            r = 0.0
            note = "FIXED <= 0: the chosen book was WORSE"
        else:
            r = float("nan")
            note = "both <= 0"
        rs = "   inf" if r == float("inf") else ("   n/a" if r != r else f"{r:>6.2f}x")
        print(f"  {y:<7}{fm:>13.3f}{fn:>7}{pm:>12.3f}{pn:>7}{rs:>10}   {note}")

    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92)
    if len(prem) < 3:
        print("  too few comparable years to judge the trend")
        return
    ys = sorted(prem)
    early = [prem[y] for y in ys if y <= 2022]
    late = [prem[y] for y in ys if y >= 2024]
    print(f"  premium by year: " + "  ".join(f"{y}:{prem[y]:.2f}x" for y in ys))
    if early and late:
        e, l = float(np.mean(early)), float(np.mean(late))
        print(f"\n  2020-2022 mean {e:.2f}x     2024-2026 mean {l:.2f}x")
        if l < e * 0.7:
            print(f"\n  THE PREMIUM SHRINKS. A flat 3.0x OVER-penalises the recent")
            print(f"  window. The right recent divisor is nearer {l:.2f}x, which raises")
            print(f"  every recent figure by {3.0 / max(l, 0.01):.2f}x.")
        elif l > e * 1.3:
            print("\n  THE PREMIUM GROWS. The flat 3.0x UNDER-penalises recent results,")
            print("  and the honest recent expectation is LOWER than reported.")
        else:
            print("\n  THE PREMIUM IS FLAT. The 3.0x divisor stands as applied, recent")
            print("  figures are right, and this line of argument is closed.")
    print("\n  One universe, one engine, ~6 years. Yearly mean R on a fat-tailed")
    print("  distribution is noisy, so read the DIRECTION across years, not any")
    print("  single year's ratio.")


if __name__ == "__main__":
    main()
