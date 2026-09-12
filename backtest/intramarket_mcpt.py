"""MCPT for the intramarket-difference strategy, with the correct null.

WHY A SPECIAL NULL IS NEEDED
----------------------------
This strategy trades the SPREAD between two coins. If we permuted each coin
independently we would destroy their contemporaneous correlation too (0.82 -> 0.00
for ETH/BTC, measured), producing a permuted world with no co-movement at all -
far easier to beat than reality, and a hopelessly optimistic p-value.

The hypothesis under test is "the spread has no exploitable SERIAL structure",
so the null must keep the co-movement and destroy only the ordering. One SHARED
permutation index across all markets does exactly that: verified corr(ETH,BTC)
0.8218 -> 0.8218 while autocorrelation collapses.

WHAT IS BEING CORRECTED FOR
---------------------------
We searched 9 configs (3 lookbacks x 3 thresholds) and reported the best on the
holdout (+19.16bp/trade). Each permutation re-runs THAT WHOLE SEARCH, so the
multiple-comparisons penalty is applied automatically.

    python -m backtest.intramarket_mcpt --perms 100
"""
from __future__ import annotations

import argparse
import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.intramarket import (ASSETS, LOOKBACKS, THRESHOLDS,  # noqa: E402
                                  USED_DAYS, cmma, threshold_revert_signal,
                                  trades_from_signal)
from backtest.mass_search import fetch  # noqa: E402
from backtest.permute import get_permutation_multi  # noqa: E402

REF = "BTCUSDT"


def best_config(frames: dict[str, pd.DataFrame], fee_bp: float) -> float:
    """Pooled mean bp of the best of the 9 configs — the data-mined quantity."""
    best = -1e9
    ref = frames[REF]
    for lb, th in itertools.product(LOOKBACKS, THRESHOLDS):
        cr = cmma(ref, lb).shift(1).to_numpy(float)
        tot_n, tot_s = 0, 0.0
        for a, df in frames.items():
            if a == REF:
                continue
            ct = cmma(df, lb).shift(1).to_numpy(float)
            sig = threshold_revert_signal(ct - cr, th)
            R = trades_from_signal(df, sig, fee_bp)
            if len(R) >= 25:
                tot_n += len(R); tot_s += R.sum()
        if tot_n >= 200:
            m = tot_s / tot_n
            if m > best:
                best = m
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perms", type=int, default=100)
    ap.add_argument("--fee", type=float, default=12.0)
    args = ap.parse_args()

    # align every asset onto one common timestamp index, holdout period only
    raw = {}
    for a in ASSETS:
        try:
            raw[a] = fetch(a, "1h", 2400).set_index("time")
        except Exception:
            pass
    common = None
    for d in raw.values():
        common = d.index if common is None else common.intersection(d.index)
    cut = common.max() - pd.Timedelta(days=USED_DAYS)
    common = common[common < cut]                      # HOLDOUT only
    frames = {a: raw[a].loc[common].reset_index() for a in raw}
    print(f"{len(frames)} assets aligned on {len(common)} common holdout bars "
          f"({common.min().date()}..{common.max().date()})")
    print(f"cost {args.fee}bp | grid {len(LOOKBACKS)*len(THRESHOLDS)} configs\n")

    t0 = time.time()
    real = best_config(frames, args.fee)
    print(f"REAL best-of-grid: {real:+.2f}bp/trade   ({time.time()-t0:.0f}s per pass)")

    order = list(frames)
    perms, better = [], 0
    for i in range(args.perms):
        pl = get_permutation_multi([frames[a] for a in order], seed=4000 + i)
        pf = {a: d for a, d in zip(order, pl)}
        b = best_config(pf, args.fee)
        perms.append(b)
        if b >= real:
            better += 1
        if (i + 1) % 10 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{args.perms} | permuted best median {np.median(perms):+.2f} "
                  f"max {np.max(perms):+.2f} | better={better} | "
                  f"{el/(i+1):.0f}s/perm", flush=True)

    p = (1 + better) / (1 + args.perms)
    print(f"\npermuted best-of-grid: median {np.median(perms):+.2f}bp  "
          f"95th {np.percentile(perms,95):+.2f}bp  max {np.max(perms):+.2f}bp")
    print(f"permutations >= real: {better}/{args.perms}")
    print(f"p-value {p:.4f}")
    print("->", "not explainable by mining this data" if p <= 0.05
          else "INDISTINGUISHABLE FROM DATA MINING")


if __name__ == "__main__":
    main()
