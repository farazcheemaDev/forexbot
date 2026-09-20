"""HOW MUCH OF A WINNER DO WE ACTUALLY KEEP? — and can the giveback be fixed?

    python -m backtest.giveback

THE QUESTION, FROM THE LIVE BOOK
    2026-09-21: AVAX is +89.2R open with its stop still at the entry price, because a
    20xATR trail with expanded ATR sits ~32% below spot. NEAR is +64.3R. The whole book is
    +253.8R on paper against -146.3R if every stop fired.

    Nobody in this project has ever measured the obvious thing: **for a position that
    reaches a peak of +X R, what does it actually close at?** Every exit test so far
    (pyramid_exits.py) applied a UNIFORM rule and every one lost money, because a uniform
    rule taxes the 5,000 ordinary positions to protect the 50 that matter.

    So: measure the capture ratio by peak size first, then test a rule that only acts
    where the giveback actually is.

WHAT IS MEASURED
    Part 1  Every long pyramid position from the deployed config, recording the PEAK R the
            position ever showed (mark-to-market on bar highs, using the same unit
            structure the exit accounting uses) against the R it closed at. Bucketed by
            peak, so the capture ratio can be read by size instead of averaged into
            meaninglessness.

    Part 2  A HIGH-THRESHOLD trail: leave the 20xATR trail completely alone until a
            position's peak exceeds a threshold T, then tighten to a fraction of it.
            Thresholds of 20R, 40R and 80R are tested against tighten factors of 0.5 and
            0.25. Below T nothing changes at all - which is the difference from
            pyramid_exits.py's ratchet, which started tightening at +10R and taxed the
            whole distribution.

WHY THIS COULD STILL FAIL
    The giveback might BE the mechanism. A 20xATR trail is what lets a position run from
    +10R to +90R in the first place; tighten it and the same position stops at +25R and
    never reaches 90. The capture table in Part 1 cannot distinguish "gave back 60R" from
    "only got to 90R because it was allowed to breathe". Part 2 is the only test that can,
    because it re-runs the path under the tighter rule.

REGISTERED PREDICTION (2026-09-21, before running)
    Capture will be BAD and get worse with size - I expect positions peaking above +50R to
    close at under half their peak, and the very largest to give back more. The total R
    given back across the book will be comparable to the total R kept.

    And I still expect Part 2 to FAIL, for the reason above: the 20xATR trail is not
    protecting the winner, it is what creates the winner. But it should fail by LESS than
    the uniform ratchet did, and if any threshold survives it will be the highest one
    (80R), because that touches the fewest positions. If 80R/0.25 beats the baseline on
    both halves, it is the first exit improvement found here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

RULES = ["1h", "4h", "12h"]
BUCKETS = [(0, 2), (2, 5), (5, 10), (10, 20), (20, 50), (50, 100), (100, 1e9)]


def walk(df, sig, *, thresh=None, tighten=1.0, record=False):
    """The deployed long pyramid, with an optional HIGH-THRESHOLD trail tightening.

    thresh=None reproduces run_pyramid exactly. Otherwise, once the position's peak R
    exceeds `thresh`, the trail multiple is scaled by `tighten` - and below the
    threshold nothing changes, which is the whole point.
    """
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    fee = FEE_BP / 1e4
    out, pos = [], None
    for i in range(1, len(df)):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i-1]) and a[i-1] > 0:
            risk = blend.SL_MULT * a[i-1]
            pos = dict(risk=risk, stop=o[i]-risk, best=o[i], bar=i,
                       ents=[o[i]], nxt=1, peak=0.0)
        if pos is None:
            continue
        risk = pos["risk"]; e0 = pos["ents"][0]
        # peak R of the POSITION, marked on this bar's high, before any stop check
        mark = sum(h[i] - e_ for e_ in pos["ents"]) / risk
        pos["peak"] = max(pos["peak"], mark)
        if lo[i] <= pos["stop"]:
            px = pos["stop"]
            r = (sum(px - e_ for e_ in pos["ents"])
                 - sum(fee * e_ for e_ in pos["ents"])) / risk
            out.append((pos["peak"], r, len(pos["ents"]), i - pos["bar"]))
            pos = None
            continue
        if len(pos["ents"]) < blend.MAX_UNITS:
            if (h[i] - e0) / risk >= pos["nxt"] * blend.ADD_EVERY:
                pos["ents"].append(e0 + pos["nxt"] * blend.ADD_EVERY * risk)
                pos["nxt"] += 1
        pos["best"] = max(pos["best"], h[i])
        gain = (pos["best"] - e0) / risk
        tm = blend.LONG_TRAIL
        if thresh is not None and pos["peak"] >= thresh:
            tm = blend.LONG_TRAIL * tighten
        cand = pos["best"] - tm * a[i-1]
        if gain >= blend.BE_AT:
            cand = max(cand, e0)
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None:
        px = c[-1]
        r = (sum(px - e_ for e_ in pos["ents"])
             - sum(fee * e_ for e_ in pos["ents"])) / pos["risk"]
        out.append((pos["peak"], r, len(pos["ents"]), len(df)-1-pos["bar"]))
    return out


def collect(thresh=None, tighten=1.0):
    rows = []
    for c in blend.BOOK:
        d = blend.load(c)
        if d is None:
            continue
        for rule in RULES:
            df = resample(d, rule)
            if len(df) < 300:
                continue
            rows += walk(df, signals(df, "long", "all"),
                         thresh=thresh, tighten=tighten)
    return pd.DataFrame(rows, columns=["peak", "exit", "units", "bars"])


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: capture is bad and worsens with size; total given back ~ total")
    print("kept. Part 2 still fails, because the wide trail CREATES the winner rather")
    print("than failing to protect it - but if anything survives it is the 80R threshold.\n")

    base = collect()
    print("=" * 96)
    print("1. CAPTURE RATIO BY PEAK SIZE — deployed config, long side, all 3 sleeves")
    print("=" * 96)
    print(f"  {'peak bucket':<16}{'n':>7}{'med peak':>10}{'med exit':>10}"
          f"{'capture':>9}{'sum peak':>11}{'sum exit':>11}{'given back':>12}")
    for lo_, hi_ in BUCKETS:
        g = base[(base.peak >= lo_) & (base.peak < hi_)]
        if not len(g):
            continue
        cap = (g.exit.median() / g.peak.median() * 100) if g.peak.median() > 0 else 0.0
        lab = f"{lo_:g}-{hi_:g}R" if hi_ < 1e9 else f"{lo_:g}R+"
        print(f"  {lab:<16}{len(g):>7}{g.peak.median():>+10.1f}{g.exit.median():>+10.1f}"
              f"{cap:>8.0f}%{g.peak.sum():>+11.0f}{g.exit.sum():>+11.0f}"
              f"{g.peak.sum()-g.exit.sum():>+12.0f}")
    tot_p, tot_e = base.peak.sum(), base.exit.sum()
    print(f"\n  ALL {len(base):,} positions: peak sum {tot_p:+,.0f}R, "
          f"exit sum {tot_e:+,.0f}R  ->  kept {100*tot_e/tot_p:.0f}% of peak")
    print(f"  total given back: {tot_p-tot_e:+,.0f}R")
    big = base[base.peak >= 50]
    print(f"  positions peaking >= +50R: {len(big)} ({100*len(big)/len(base):.2f}%), "
          f"they hold {100*big.exit.sum()/tot_e:.0f}% of all realised R")

    print("\n" + "=" * 96)
    print("2. A TRAIL THAT ONLY TIGHTENS AT EXTREMES — does protecting the few work?")
    print("=" * 96)
    print(f"  {'rule':<30}{'n':>7}{'total R':>11}{'vs base':>10}"
          f"{'med exit >50R peak':>21}")
    b50 = base[base.peak >= 50]
    print(f"  {'deployed (no tightening)':<30}{len(base):>7}{tot_e:>+11.0f}"
          f"{'—':>10}{b50.exit.median():>+21.1f}")
    best = None
    for th in (20.0, 40.0, 80.0):
        for tg in (0.50, 0.25):
            v = collect(thresh=th, tighten=tg)
            d = v.exit.sum() - tot_e
            if best is None or v.exit.sum() > best[0]:
                best = (v.exit.sum(), th, tg)
            v50 = v[v.peak >= 50]
            print(f"  {'tighten above +' + f'{th:g}R to ' + f'{tg:g}x':<30}{len(v):>7}"
                  f"{v.exit.sum():>+11.0f}{d:>+10.0f}"
                  f"{(v50.exit.median() if len(v50) else float('nan')):>+21.1f}")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    if best and best[0] > tot_e:
        print(f"  BEST: tighten above +{best[1]:g}R to {best[2]:g}x  "
              f"-> {best[0]:+,.0f}R against the deployed {tot_e:+,.0f}R")
        print("  This is a total-R comparison on the long sleeve only, NOT a portfolio")
        print("  result - it ignores the slot cap, the regime gate and compounding. Run it")
        print("  through blend.run before believing any of it.")
    else:
        print(f"  NOTHING BEATS THE DEPLOYED TRAIL. Best was {best[0]:+,.0f}R against")
        print(f"  {tot_e:+,.0f}R. The giveback is not a leak to be plugged - the wide")
        print("  trail is what allows a position to reach +90R at all, and tightening it")
        print("  truncates the same positions it was meant to protect.")


if __name__ == "__main__":
    main()
