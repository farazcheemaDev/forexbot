"""MCPT for CROSS-SECTIONAL momentum — the shared-index null.

WHY THE NULL HAS TO BE SHARED-INDEX
-----------------------------------
A ranking strategy asks: does RELATIVE past strength predict RELATIVE future
strength? The matching null is "it does not" - NOT "these coins are unrelated".

If each coin were permuted with its own index, contemporaneous correlation would
be destroyed too. The permuted world would then be a diversifier's paradise that
any market-neutral book beats easily, and the p-value would be meaninglessly
optimistic. get_permutation_multi reuses ONE shuffle index across every coin, so:

    corr(coin_i, coin_j) at the same timestamp   -> PRESERVED
    "last week's winners keep winning"           -> DESTROYED

That isolates exactly the claim being made.

FUNDING IS TURNED OFF ON BOTH SIDES. Real funding timestamps have no meaning in a
permuted price path, so charging them to the real run and not the permuted one
would bias the test. Measured funding on this book is ~+0.1%/yr, so this changes
nothing material.

    python -m backtest.xs_mcpt --n 200
    python -m backtest.xs_mcpt --n 200 --window holdout
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import DATA, fetch  # noqa: E402
from backtest.permute import get_permutation_multi  # noqa: E402
from backtest.xs_momentum import (CENTRAL, HOLDOUT_DAYS, LONG_UNIVERSE,  # noqa: E402
                                  TAKER_BP, UNIVERSE, simulate)


def load_frames(days: int, universe: list[str] | None = None,
                min_bars: int = 8000):
    """Per-coin OHLCV frames on one common index — required for permutation.

    Use LONG_UNIVERSE. Intersecting the full 28-coin universe leaves 4,577 bars
    because TONUSDT was listed 2024-08, and an MCPT on that stub cannot resolve
    any Sharpe below ~2.2 (see LONG_UNIVERSE in xs_momentum).
    """
    frames = {}
    for s in (universe or LONG_UNIVERSE):
        try:
            d = fetch(s, "1h", days)
        except Exception:
            continue
        d = d.drop_duplicates("time").sort_values("time").set_index("time")
        need = ["open", "high", "low", "close"]
        if not all(c in d.columns for c in need):
            continue
        if d["close"].notna().sum() < min_bars:
            continue
        frames[s] = d[need + (["volume"] if "volume" in d.columns else [])]
    common = None
    for d in frames.values():
        common = d.index if common is None else common.intersection(d.index)
    if common is None or len(common) == 0:
        raise SystemExit(
            f"EMPTY COMMON INDEX across {len(frames)} coins. The shared-index "
            f"permutation needs every coin on one index, so a single late listing "
            f"empties the intersection. Raise --min-bars to keep only coins with "
            f"long history.")
    return {s: d.loc[common].astype(float) for s, d in frames.items()}, common


def panels(frames: dict[str, pd.DataFrame]):
    O = pd.DataFrame({s: d["open"] for s, d in frames.items()})
    C = pd.DataFrame({s: d["close"] for s, d in frames.items()})
    return O, C


def metric(O, C, Z, cfg, fee) -> tuple[float, float]:
    s = simulate(O, C, Z, **cfg, fee_bp=fee, charge_funding=False)
    return s["sharpe"], s["cagr"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--days", type=int, default=2400)
    ap.add_argument("--fee", type=float, default=TAKER_BP)
    ap.add_argument("--window", default="dev", choices=["dev", "holdout", "all"])
    ap.add_argument("--all-coins", action="store_true",
                    help="use the full 28-coin universe (collapses the common "
                         "index to ~190 days — almost never what you want)")
    ap.add_argument("--virgin", action="store_true",
                    help="use only wide-universe coins that are NOT in UNIVERSE, "
                         "i.e. coins that took no part in any parameter choice")
    ap.add_argument("--lb", type=int, help="override lookback")
    ap.add_argument("--k", type=int, help="override k")
    ap.add_argument("--min-bars", type=int, default=8000,
                    help="drop coins with less history than this BEFORE "
                         "intersecting; one late listing empties the index")
    args = ap.parse_args()

    if args.virgin:
        wide = json.load(open(DATA / "wide_universe.json"))
        uni = [s for s in wide if s not in UNIVERSE]
    elif args.all_coins:
        uni = UNIVERSE
    else:
        uni = LONG_UNIVERSE
    if args.lb:
        CENTRAL["lb"] = args.lb
    if args.k:
        CENTRAL["k"] = args.k
    frames, common = load_frames(args.days, uni, args.min_bars)
    cut = common[-1] - pd.Timedelta(days=HOLDOUT_DAYS)
    if args.window == "dev":
        frames = {s: d.loc[:cut] for s, d in frames.items()}
    elif args.window == "holdout":
        frames = {s: d.loc[cut:] for s, d in frames.items()}
    keys = list(frames)
    n = len(next(iter(frames.values())))
    Z = pd.DataFrame(0.0, index=next(iter(frames.values())).index, columns=keys)

    start = max(CENTRAL["lb"], 48) + 2
    print(f"MCPT cross-sectional momentum  window={args.window}  "
          f"{len(keys)} coins x {n:,} bars")
    print(f"  config {CENTRAL}  fee {args.fee}bp/side")
    print(f"  shared-index permutation from bar {start} "
          f"(warmup stays real), funding off both sides")
    print(f"  {args.n} permutations\n")

    O, C = panels(frames)
    r_sh, r_cagr = metric(O, C, Z, CENTRAL, args.fee)
    print(f"REAL:  Sharpe {r_sh:+.3f}   CAGR {r_cagr:+.1f}%/yr\n")
    if r_sh <= 0:
        print("Real Sharpe is not positive — nothing to test. Stopping.")
        return

    dfs = [frames[s] for s in keys]
    perm_sh, perm_cagr = [], []
    beat = 0
    for i in range(args.n):
        pf = get_permutation_multi(dfs, start_index=start, seed=1000 + i)
        pm = {s: d for s, d in zip(keys, pf)}
        Op, Cp = panels(pm)
        sh, cg = metric(Op, Cp, Z, CENTRAL, args.fee)
        perm_sh.append(sh); perm_cagr.append(cg)
        beat += sh >= r_sh
        if (i + 1) % 10 == 0:
            p = (1 + beat) / (i + 2)
            print(f"  {i+1:>4}/{args.n}  beaten {beat:>3}x  running p={p:.4f}",
                  flush=True)

    ps = np.asarray(perm_sh)
    p_val = (1 + beat) / (args.n + 1)
    print(f"\npermuted Sharpe: mean {ps.mean():+.3f}  sd {ps.std(ddof=1):.3f}  "
          f"p95 {np.percentile(ps,95):+.3f}  max {ps.max():+.3f}")
    print(f"real {r_sh:+.3f} sits at the {(ps < r_sh).mean()*100:.1f}th percentile "
          f"of the permuted distribution")
    print(f"\np = {p_val:.4f}   ({beat}/{args.n} permutations matched or beat real)")
    if p_val <= 0.01:
        v = "not explainable by mining this data (a holdout is still required)"
    elif p_val <= 0.05:
        v = "weak — survives, but this is the band where gold also passed"
    else:
        v = "INDISTINGUISHABLE from shuffled data"
    print(f"verdict: {v}")


if __name__ == "__main__":
    main()
