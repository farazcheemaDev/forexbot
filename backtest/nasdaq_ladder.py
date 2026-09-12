"""Is the NASDAQ level-fade edge real, or 26 configs' worth of luck?

Two independent challenges to the 5-minute result.

1. TIMEFRAME LADDER. A genuine short-horizon mean-reversion effect (liquidity
   provision / overshoot at levels) should FADE SMOOTHLY as bars get coarser:
   strong at 5m, weaker at 15m, weaker at 30m, gone or negative at 1h. Noise has
   no reason to be ordered. We already know the endpoints (5m positive, 1h
   negative) - the question is whether the middle interpolates.

2. MCPT. We tested 26 level_fade configs on 60 days. That is a search, so the
   best result is partly the largest random deviation. Permutation re-runs the
   WHOLE search on shuffled bars and prices the multiple comparisons in.
   Note the permutation is valid here: shuffling returns still produces a price
   path that crosses round numbers, so a level-fade strategy remains testable.

    python -m backtest.nasdaq_ladder
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.nasdaq_levelfade import (PROX, ROUND_STEPS, RSI_BANDS,  # noqa: E402
                                       SL, TP, fetch_nq, lf_signals)
from backtest.permute import get_permutation  # noqa: E402
from backtest.rtest import run_r, stats  # noqa: E402

SPREAD = 2.0              # index points round trip — Exness USTEC ballpark
MIN_TRADES = 40
N_PERM = 300


def grid():
    return list(itertools.product(ROUND_STEPS, PROX, RSI_BANDS))


def best_meanR(df) -> tuple[float, tuple | None, int]:
    """Best mean R over the level_fade grid — the quantity being data-mined."""
    best, cfg, nn = -9.0, None, 0
    for rs, px, band in grid():
        R, _ = run_r(df, lf_signals(df, rs, px, band), SL, TP,
                     fee_bp=0.0, fee_abs=SPREAD)
        if len(R) < MIN_TRADES:
            continue
        m = float(R.mean())
        if m > best:
            best, cfg, nn = m, (rs, px, band), len(R)
    return best, cfg, nn


def ladder():
    print("=" * 88)
    print("1. TIMEFRAME LADDER — a real microstructure effect should decay in order")
    print("=" * 88)
    print(f"{'tf':>5} {'bars':>7} {'meanBar':>8} {'cfgs+':>7} {'medianR':>9} "
          f"{'bestR':>9} {'n@best':>7}")
    out = {}
    for tf, per in (("5m", "60d"), ("15m", "60d"), ("30m", "60d"),
                    ("60m", "60d"), ("1h", "730d")):
        try:
            df = fetch_nq(tf, per)
        except Exception as e:
            print(f"{tf:>5} fetch failed: {type(e).__name__}")
            continue
        if len(df) < 1500:
            print(f"{tf:>5} only {len(df)} bars — skipped")
            continue
        ms = []
        for rs, px, band in grid():
            R, _ = run_r(df, lf_signals(df, rs, px, band), SL, TP,
                         fee_bp=0.0, fee_abs=SPREAD)
            if len(R) >= MIN_TRADES:
                ms.append(float(R.mean()))
        if not ms:
            print(f"{tf:>5} no config reached {MIN_TRADES} trades")
            continue
        b, cfg, nn = best_meanR(df)
        rng = float((df["high"] - df["low"]).mean())
        pos = sum(1 for m in ms if m > 0)
        print(f"{tf:>5} {len(df):>7} {rng:>8.1f} {pos:>3}/{len(ms):<3} "
              f"{np.median(ms):>+9.4f} {b:>+9.4f} {nn:>7}")
        out[tf] = np.median(ms)
    # is it monotone from fine to coarse?
    order = [t for t in ("5m", "15m", "30m", "60m") if t in out]
    vals = [out[t] for t in order]
    mono = all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))
    print(f"\n  medians fine->coarse: "
          f"{', '.join(f'{t}={out[t]:+.4f}' for t in order)}")
    print(f"  monotone decay: {'YES — consistent with a real horizon effect' if mono else 'NO — pattern is not ordered, looks like noise'}")
    return out


def mcpt_5m():
    print("\n" + "=" * 88)
    print(f"2. MCPT on NASDAQ 5m — {len(grid())} configs, {N_PERM} permutations")
    print("=" * 88)
    df = fetch_nq("5m", "60d")
    real, cfg, nn = best_meanR(df)
    print(f"  REAL best: step={cfg[0]:.0f} prox={cfg[1]:.0f} band={cfg[2]} "
          f"meanR={real:+.4f} on {nn} trades")
    perm, better = [], 0
    for i in range(N_PERM):
        p = get_permutation(df, seed=7000 + i)
        b, _, _ = best_meanR(p)
        perm.append(b)
        if b >= real:
            better += 1
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{N_PERM} | permuted best median "
                  f"{np.median(perm):+.4f} max {np.max(perm):+.4f} | "
                  f"better={better}", flush=True)
    pv = (1 + better) / (1 + N_PERM)
    print(f"\n  permuted best meanR: median {np.median(perm):+.4f}  "
          f"95th {np.percentile(perm,95):+.4f}  max {np.max(perm):+.4f}")
    print(f"  permutations >= real: {better}/{N_PERM}")
    print(f"  p-value {pv:.4f}")
    print("  ->", "not explainable by mining this data (still needs more data)"
          if pv <= 0.05 else "INDISTINGUISHABLE FROM DATA MINING")
    return pv


if __name__ == "__main__":
    ladder()
    mcpt_5m()
    print("\nReminder: he held 4-36 SECONDS. 5m is the finest free bar. A pass "
          "here is evidence about 5-minute levels, not about his execution.")


# --------------------------------------------------------------------------- #
# The right null for the BREADTH claim, plus two artifact checks
# --------------------------------------------------------------------------- #
def median_meanR(df, spread=SPREAD, rth_only=False) -> tuple[float, int, int]:
    """Median mean-R ACROSS the whole grid — not a selection statistic, so the
    data-mining penalty largely vanishes and it tests what we actually claim:
    that the family as a whole is positive at this horizon."""
    d = df
    if rth_only:                      # 09:30-16:00 New York cash session
        t = pd.to_datetime(d["time"])
        mins = t.dt.hour * 60 + t.dt.minute
        d = d[(mins >= 570) & (mins <= 960)].reset_index(drop=True)
    ms = []
    for rs, px, band in grid():
        R, _ = run_r(d, lf_signals(d, rs, px, band), SL, TP,
                     fee_bp=0.0, fee_abs=spread)
        if len(R) >= MIN_TRADES:
            ms.append(float(R.mean()))
    if not ms:
        return float("nan"), 0, len(d)
    return float(np.median(ms)), sum(1 for m in ms if m > 0), len(d)


def mcpt_median(n_perm=300):
    print("\n" + "=" * 88)
    print(f"3. MCPT on the MEDIAN across configs (tests BREADTH, not best-of-N)")
    print("=" * 88)
    df = fetch_nq("5m", "60d")
    real, pos, _ = median_meanR(df)
    print(f"  REAL median meanR across {len(grid())} configs: {real:+.4f} "
          f"({pos}/{len(grid())} positive)")
    perm, better = [], 0
    for i in range(n_perm):
        m, _, _ = median_meanR(get_permutation(df, seed=31000 + i))
        if not np.isfinite(m):
            continue
        perm.append(m)
        if m >= real:
            better += 1
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{n_perm} | permuted median of medians "
                  f"{np.median(perm):+.4f} max {np.max(perm):+.4f} | "
                  f"better={better}", flush=True)
    pv = (1 + better) / (1 + len(perm))
    print(f"\n  permuted: median {np.median(perm):+.4f}  "
          f"95th {np.percentile(perm,95):+.4f}  max {np.max(perm):+.4f}")
    print(f"  better: {better}/{len(perm)}   p-value {pv:.4f}")
    print("  ->", "breadth NOT explainable by mining this data"
          if pv <= 0.05 else "breadth is within what mining produces")
    return pv


def artifact_checks():
    print("\n" + "=" * 88)
    print("4. ARTIFACT CHECKS — cost sensitivity and session")
    print("=" * 88)
    df = fetch_nq("5m", "60d")
    print(f"  {'spread(pts)':>12} {'medianR':>9} {'cfgs+':>8}   (all hours)")
    for sp in (0.0, 1.0, 2.0, 4.0, 6.0, 8.0):
        m, pos, _ = median_meanR(df, spread=sp)
        print(f"  {sp:>12.1f} {m:>+9.4f} {pos:>4}/{len(grid()):<3}")
    print(f"\n  Regular-trading-hours ONLY (09:30-16:00 ET) — overnight futures")
    print(f"  liquidity is thin, so a 2pt spread there may be fiction:")
    print(f"  {'spread(pts)':>12} {'medianR':>9} {'cfgs+':>8} {'bars':>7}")
    for sp in (2.0, 4.0):
        m, pos, nb = median_meanR(df, spread=sp, rth_only=True)
        print(f"  {sp:>12.1f} {m:>+9.4f} {pos:>4}/{len(grid()):<3} {nb:>7}")
