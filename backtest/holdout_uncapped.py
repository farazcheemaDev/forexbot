"""RE-RUN OF THE 18-FAMILY SWEEP, WITHOUT THE PROFIT CAP.

WHY THIS EXISTS
    holdout_sweep.py concluded "SURVIVORS: NONE" across 18 families x 393 configs
    x 9 assets. Every one of those evaluations called
        run_r(df, sig, SL=2.0, TP=3.0, FEE_BP=10)
    and a 3xATR target against a 2xATR stop caps a winner at +1.5R. Its own
    docstring even says "a win caps at +1.5R" - the cap was documented and its
    implication still missed for weeks.

    backtest/convex.py then showed that removing the cap flips three of those very
    families from mean R ~0 to +0.19..+0.21, monotonically as the trail widens, and
    backtest/convex_wide.py showed the effect holds 6/6 on coins that took no part
    in any choice, with a short side 74% the size of the long side (so it is not
    merely the 2020-26 crypto updraft).

    So "SURVIVORS: NONE" was, in part, a verdict on the exit rule. This re-runs the
    same families, same assets, same holdout split, with the cap removed.

WHAT I EXPECT, WRITTEN DOWN FIRST
    TREND / BREAKOUT / MOMENTUM families should improve a lot. Their edge lives in
    the tail and the cap deletes the tail.
    MEAN-REVERSION families (vwap_rev, stoch_rsi_rev, bollinger_rsi, level_fade)
    should NOT improve, because a small quick target IS their thesis - a wide trail
    just gives back the snap-back they were trying to capture.
    If mean-reversion improves as much as trend does, then something other than
    the cap is driving the change and this whole line needs re-examining.

HOLDOUT HONESTY — THIS IS LOOK #3 ON THIS DATA
    The crypto 1h holdout (older than USED_DAYS) is already marked PARTLY SPENT in
    the contamination ledger: one clean look for the original sweep, then its
    atr_pct decile structure was inspected during meta-labeling. This is a third
    look.
    Mitigating: the exit rule tested here was chosen on the RECENT (contaminated)
    window in convex.py, never on this holdout, so as a test OF THE EXIT RULE this
    is genuinely out-of-sample.
    But the stronger evidence is convex_wide.py's virgin-COIN result, which needed
    no fresh time period at all. Treat this file as confirmatory, not primary.

    python -m backtest.holdout_uncapped
    python -m backtest.holdout_uncapped --family rsi_mom
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import run_uncapped  # noqa: E402
from backtest.holdout_sweep import (ASSETS, DAYS, FEE_BP, SL, TP,  # noqa: E402
                                    USED_DAYS, full_space, signals_for)
from backtest.mass_search import fetch  # noqa: E402
from backtest.rtest import run_r  # noqa: E402

TRAILS = (3.0, 5.0, 8.0)
MEAN_REV = {"vwap_rev", "stoch_rsi_rev", "bollinger_rsi", "level_fade",
            "liquidity_sweep", "rsi_rev", "bb_rev"}


def pooled(exits: str, trail: float, fam: str, params: list,
           data: dict) -> dict | None:
    """Pool every config of one family across assets, on the HOLDOUT only."""
    Rs, Ds = [], []
    for p in params:
        for a, (hold, _used) in data.items():
            try:
                sig = signals_for(hold, fam, p)
            except Exception:
                continue
            if sig is None:
                continue
            if exits == "capped":
                R, _idx = run_r(hold, sig, SL, TP, FEE_BP)
                d = np.zeros(len(R), dtype=int)
            else:
                R, _idx, _b, d = run_uncapped(hold, sig, sl_mult=SL,
                                              fee_bp=FEE_BP, mode="trail_atr",
                                              trail=trail)
            if len(R):
                Rs.append(R); Ds.append(d)
    if not Rs:
        return None
    R = np.concatenate(Rs)
    D = np.concatenate(Ds)
    if len(R) < 100:
        return None
    sd = R.std(ddof=1)
    return dict(n=len(R), mean=float(R.mean()),
                t=float(R.mean() / (sd / np.sqrt(len(R)))) if sd > 0 else 0.0,
                pf=float(R[R > 0].sum() / -R[R < 0].sum()) if (R < 0).any() else np.inf,
                mx=float(R.max()),
                long_r=float(R[D > 0].mean()) if (D > 0).any() else float("nan"),
                short_r=float(R[D < 0].mean()) if (D < 0).any() else float("nan"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family")
    ap.add_argument("--days", type=int, default=DAYS)
    args = ap.parse_args()

    space = full_space()
    if args.family:
        space = {args.family: space[args.family]}

    data = {}
    for a in ASSETS:
        try:
            d = fetch(a, "1h", args.days)
        except Exception:
            continue
        cut = d.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
        hold = d[d.time < cut].reset_index(drop=True)
        used = d[d.time >= cut].reset_index(drop=True)
        if len(hold) < 3000:
            continue
        data[a] = (hold, used)

    print(f"18-FAMILY SWEEP, UNCAPPED   {len(data)} assets, HOLDOUT only "
          f"(older than {USED_DAYS}d)")
    print(f"  {len(space)} families | trails {TRAILS}xATR | fee {FEE_BP}bp")
    print(f"  'capped' column = the ORIGINAL rule (2xATR stop, 3xATR target "
          f"-> +1.5R max)\n")
    print("=" * 112)
    print(f"{'family':<17} {'MR?':>4} | {'capped meanR':>13} {'t':>6} | "
          f"{'trail3 meanR':>13} {'trail5 meanR':>13} {'trail8 meanR':>13} "
          f"{'t8':>6} {'best':>7}")
    rows = []
    for fam, params in space.items():
        base = pooled("capped", 0.0, fam, params, data)
        if not base:
            continue
        cells = {}
        for tr in TRAILS:
            cells[tr] = pooled("trail", tr, fam, params, data)
        got = [c for c in cells.values() if c]
        if not got:
            continue
        best = max(got, key=lambda c: c["mean"])
        tag = "MR" if fam in MEAN_REV else "trend"
        rows.append((fam, tag, base, cells, best))
        c8 = cells.get(8.0)
        print(f"{fam:<17} {tag:>4} | {base['mean']:>+13.4f} {base['t']:>+6.2f} | "
              + " ".join(f"{(cells[tr]['mean'] if cells.get(tr) else float('nan')):>+13.4f}"
                         for tr in TRAILS)
              + f" {(c8['t'] if c8 else float('nan')):>+6.2f} "
                f"{best['mean']:>+7.4f}", flush=True)

    print("\n" + "=" * 112)
    print("DID THE CAP HIDE AN EDGE?")
    print("=" * 112)
    for tag in ("trend", "MR"):
        sub = [r for r in rows if r[1] == tag]
        if not sub:
            continue
        cap_pos = sum(1 for _, _, b, _, _ in sub if b["mean"] > 0)
        unc_pos = sum(1 for _, _, _, _, bst in sub if bst["mean"] > 0)
        dmean = np.mean([bst["mean"] - b["mean"] for _, _, b, _, bst in sub])
        print(f"  {tag:<6} families: {len(sub):>2} | positive CAPPED "
              f"{cap_pos:>2}/{len(sub)} | positive UNCAPPED {unc_pos:>2}/{len(sub)}"
              f" | mean improvement {dmean:+.4f}R")
    print("\nPREDICTION MADE BEFORE RUNNING: trend families improve a lot, "
          "mean-reversion\nfamilies do not (a tight target IS their thesis). If MR "
          "improves as much as\ntrend, the cap is not what changed and this line "
          "needs re-examining.")

    surv = [(r[4]["mean"], r[0], r[4]) for r in rows
            if r[4]["mean"] > 0 and r[4]["t"] > 3.0]
    surv.sort(reverse=True)
    print(f"\nSURVIVORS (uncapped holdout meanR > 0 AND t > 3): {len(surv)}")
    for m, fam, c in surv:
        print(f"  {fam:<17} meanR {m:>+.4f}  t {c['t']:>+5.2f}  n {c['n']:>6}  "
              f"PF {c['pf']:>4.2f}  maxR {c['mx']:>6.1f}  "
              f"long {c['long_r']:>+.3f} short {c['short_r']:>+.3f}")
    if surv:
        print("\nA short side near zero means asset-class drift, not an edge. "
              "Check that column\nbefore believing any of these.")
    print("\nReminder: this is look #3 on this holdout. The primary evidence is "
          "the\nvirgin-COIN result in convex_wide.py, which needed no fresh time "
          "window.")


if __name__ == "__main__":
    main()
