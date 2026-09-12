"""VIRGIN-COIN GATE on the uncapped-trailing result.

WHAT IS BEING TESTED
    backtest/convex.py found that removing the profit cap flips three signal
    families from mean R ~0 to +0.19..+0.21 (t ~ +5), monotonically as the trail
    widens. Sized at 0.5%/trade that is +174%/yr at the same ~79% drawdown
    equal-weight buy-and-hold produced, i.e. ~4x the return for the same pain.

    But it was the best of 18 cells on the 9 coins this project has stared at all
    day. This morning an apparently 1.7x-better ranking rule died 6/6 on coins it
    had not been searched on. Same gate, same frozen parameters, applied here.

THE DECOMPOSITION MATTERS MORE THAN THE HEADLINE
    xs_wide.py showed that lumping all unused coins together HID a survivorship
    effect: the whole apparent edge lived in 2023-25 new listings (WIF, BONK,
    PENGU, TRUMP...), which are in today's top-120 by volume precisely BECAUSE
    they pumped, while the ones that died were never downloaded. On established
    never-used coins the edge was zero.

    So the groups are kept separate again:
        USED              9-27 coins, every parameter chosen on them
        VIRGIN established never used AND listed before 2022-08 -> the real test
        VIRGIN recent     never used but listed later -> survivorship-contaminated

    If the uncapped edge is real it must appear in VIRGIN ESTABLISHED. If it
    appears only in VIRGIN RECENT, it is the same illusion again.

ALSO REPORTED, because the earlier run showed the long leg doing ~88% of the work
    long-side and short-side mean R separately. An edge that is all long side in
    a period when the asset class rose 40%/yr compounded is beta, not skill, and
    would not survive a bear market. The short side is the honest half.

    python -m backtest.convex_wide
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import FEE_BP, describe, run_uncapped  # noqa: E402
from backtest.mass_search import DATA, fetch, gen_signals  # noqa: E402
from backtest.xs_momentum import UNIVERSE  # noqa: E402

# FROZEN, exactly as convex.py left them. No re-tuning on virgin coins.
FAMS = [("bb_break", (30, 1.5)), ("roc_mom", (24, 0.0)), ("rsi_mom", (7, 40, 60))]
TRAILS = (5.0, 8.0)
RISK = 0.5          # the sizing that matched buy-and-hold's drawdown
FULL_HISTORY_BARS = 34000


def group_pool(coins: list[str], fam: str, p, trail: float, days: int):
    allR, allT, allD = [], [], []
    for c in coins:
        try:
            df = fetch(c, "1h", days)
        except Exception:
            continue
        if len(df) < 9000:
            continue
        sig = gen_signals(df, fam, p)
        if sig is None:
            continue
        R, idx, _b, d = run_uncapped(df, sig, sl_mult=2.0, fee_bp=FEE_BP,
                                     mode="trail_atr", trail=trail)
        if len(R):
            allR.append(R); allT.append(df["time"].iloc[idx]); allD.append(d)
    if not allR:
        return None
    o = np.argsort(np.concatenate([t.values for t in allT]))
    R = np.concatenate(allR)[o]
    D = np.concatenate(allD)[o]
    T = pd.Series(np.concatenate([t.values for t in allT])[o])
    return describe(R, T, RISK, dirs=D)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1500)
    args = ap.parse_args()

    wide = json.load(open(DATA / "wide_universe.json"))
    used = [s for s in wide if s in UNIVERSE]
    virgin = [s for s in wide if s not in UNIVERSE]
    vfull, vlate = [], []
    for s in virgin:
        try:
            d = fetch(s, "1h", args.days)
        except Exception:
            continue
        (vfull if len(d) >= FULL_HISTORY_BARS else vlate).append(s)

    groups = [("USED (tuned on)", used),
              ("VIRGIN established", vfull),
              ("VIRGIN recent", vlate)]
    print(f"VIRGIN-COIN GATE on uncapped trailing exits   risk {RISK}%/trade  "
          f"fee {FEE_BP}bp")
    for tag, g in groups:
        print(f"  {tag:<20} {len(g):>3} coins")
    print("\nThe test is VIRGIN ESTABLISHED. VIRGIN RECENT carries survivorship "
          "bias (see docstring).\n")

    print("=" * 118)
    print(f"{'family':<18} {'trail':>6} {'group':<20} {'n':>6} {'meanR':>8} "
          f"{'t':>7} {'longR':>8} {'shortR':>8} {'CAGR':>9} {'DD':>7} "
          f"{'mo>10%':>7}")
    verdict = {}
    for fam, p in FAMS:
        for tr in TRAILS:
            for tag, g in groups:
                d = group_pool(g, fam, p, tr, args.days)
                if not d:
                    continue
                verdict[(fam, tr, tag)] = d
                ru = " RUIN" if d["ruined"] else ""
                print(f"{fam+str(p):<18} {tr:>5.0f}x {tag:<20} {d['n']:>6} "
                      f"{d['mean']:>+8.3f} {d['t']:>+7.2f} {d['long_r']:>+8.3f} "
                      f"{d['short_r']:>+8.3f} {d['cagr']:>+8.1f}% {d['dd']:>6.1f}%"
                      f"{d['mo_over10']:>7.1f}%{ru}", flush=True)
            print()

    print("=" * 118)
    print("VERDICT")
    print("=" * 118)
    est = [(k, v) for k, v in verdict.items() if k[2] == "VIRGIN established"]
    rec = [(k, v) for k, v in verdict.items() if k[2] == "VIRGIN recent"]
    if est:
        pe = sum(1 for _, v in est if v["mean"] > 0)
        print(f"VIRGIN ESTABLISHED: mean R positive in {pe}/{len(est)} cells, "
              f"average meanR {np.mean([v['mean'] for _, v in est]):+.3f}")
    if rec:
        pr = sum(1 for _, v in rec if v["mean"] > 0)
        print(f"VIRGIN RECENT:      mean R positive in {pr}/{len(rec)} cells, "
              f"average meanR {np.mean([v['mean'] for _, v in rec]):+.3f}")
    if est:
        ls = [v["long_r"] for _, v in est if np.isfinite(v["long_r"])]
        ss = [v["short_r"] for _, v in est if np.isfinite(v["short_r"])]
        if ls and ss:
            print(f"\non VIRGIN ESTABLISHED: long {np.mean(ls):+.3f}R vs "
                  f"short {np.mean(ss):+.3f}R")
            print("  a short side near zero means the result is asset-class drift, "
                  "not an edge —\n  it would not survive a sustained bear market")
    print("\nPASS requires: positive on VIRGIN ESTABLISHED in most cells, with a "
          "short side\nthat is not ~zero. Positive ONLY on VIRGIN RECENT is the "
          "survivorship illusion again.")


if __name__ == "__main__":
    main()
