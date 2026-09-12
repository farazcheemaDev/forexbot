"""MCPT for the VSA absorption filter.

WHAT IS BEING CORRECTED FOR
---------------------------
The filter sweep tried 6 rules and reported the best (dev < -0.5, +0.0378R on the
holdout vs -0.0069 unfiltered). Six rules is a search, so the winner is partly the
largest random deviation. Each permutation re-runs the WHOLE sweep and takes its
best, so the multiple-comparisons penalty is applied automatically.

THE NULL IS SPECIFIC HERE
-------------------------
VSA exploits the relationship between a candle's RANGE and its VOLUME. The
permutation therefore reorders volume with the same intrabar index as the range,
so each bar keeps its own volume: corr(range, volume) is preserved exactly
(0.8391 -> 0.8391, verified) while volume's serial structure dies (autocorr
0.655 -> 0.015). Leaving volume unshuffled would have destroyed the very
relationship under test and made the null trivially beatable.

    python -m backtest.vsa_mcpt --perms 100
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.holdout_sweep import USED_DAYS, signals_for  # noqa: E402
from backtest.mass_search import FILTERS, fetch  # noqa: E402
from backtest.permute import get_permutation  # noqa: E402
from backtest.rtest import run_r  # noqa: E402
from backtest.vsa import ASSETS, FEE_BP, SL, TP, vsa_indicator  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

RULES = {
    "unfiltered": None,
    "dev<-0.5": lambda s: s < -0.5,
    "dev<-1.0": lambda s: s < -1.0,
    "dev>0.5": lambda s: s > 0.5,
    "dev>1.0": lambda s: s > 1.0,
    "|dev|<0.25": lambda s: s.abs() < 0.25,
}


def best_rule(frames: list[pd.DataFrame]) -> tuple[float, str]:
    """Pooled mean R of the best of the 6 rules — the data-mined quantity."""
    base = {}
    devs = {}
    for k, df in enumerate(frames):
        base[k] = FILTERS["none"](df, signals_for(df, "bb_break", (30, 1.5)))
        devs[k] = vsa_indicator(df).shift(1)
    best, name = -1e9, ""
    for label, rule in RULES.items():
        tot_n, tot_s = 0, 0.0
        for k, df in enumerate(frames):
            sig = base[k] if rule is None else base[k].where(rule(devs[k]),
                                                            Action.HOLD)
            R, _ = run_r(df, sig, SL, TP, FEE_BP)
            if len(R) >= 30:
                tot_n += len(R); tot_s += R.sum()
        if tot_n >= 500:
            m = tot_s / tot_n
            if m > best:
                best, name = m, label
    return best, name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perms", type=int, default=100)
    args = ap.parse_args()

    frames = []
    for a in ASSETS:
        try:
            d = fetch(a, "1h", 2400)
        except Exception:
            continue
        cut = d.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
        hold = d[d.time < cut].reset_index(drop=True)
        if len(hold) >= 3000:
            frames.append(hold)
    print(f"{len(frames)} assets, holdout window only, {len(RULES)} rules, "
          f"cost {FEE_BP}bp")

    t0 = time.time()
    real, name = best_rule(frames)
    print(f"REAL best rule: {name}  -> {real:+.4f}R  "
          f"({time.time()-t0:.0f}s per pass)\n")

    perms, better = [], 0
    for i in range(args.perms):
        pf = [get_permutation(d, seed=9000 + i * 37 + k)
              for k, d in enumerate(frames)]
        b, _ = best_rule(pf)
        perms.append(b)
        if b >= real:
            better += 1
        if (i + 1) % 10 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{args.perms} | permuted best median "
                  f"{np.median(perms):+.4f} max {np.max(perms):+.4f} | "
                  f"better={better} | {el/(i+1):.0f}s/perm", flush=True)

    p = (1 + better) / (1 + args.perms)
    print(f"\npermuted best-of-rules: median {np.median(perms):+.4f}  "
          f"95th {np.percentile(perms,95):+.4f}  max {np.max(perms):+.4f}")
    print(f"permutations >= real: {better}/{args.perms}")
    print(f"p-value {p:.4f}")
    print("->", "not explainable by mining this data" if p <= 0.05
          else "INDISTINGUISHABLE FROM DATA MINING")


if __name__ == "__main__":
    main()
