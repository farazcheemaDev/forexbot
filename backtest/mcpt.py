"""Monte Carlo Permutation Tests — the four-step validation framework.

    Step 1  in-sample optimisation          (what we already did: mass_search)
    Step 2  IN-SAMPLE MCPT                  <- p-value that corrects for data mining
    Step 3  walk-forward                    (what we already did: walkforward.py)
    Step 4  WALK-FORWARD MCPT               <- p-value that the WF result isn't luck

Method credit: neurotrader888/mcpt; Timothy Masters, "Testing and Tuning Market
Trading Systems"; Good, "Permutation, Parametric and Bootstrap Tests".

WHY THIS IS DIFFERENT FROM WHAT WE HAD
--------------------------------------
Our previous defence against data mining was a train/validation/holdout split
plus walk-forward. Those are real, but they answer "does it still work on data
I didn't tune on?" - a yes/no that gets noisier the smaller the holdout.

MCPT answers a sharper question: "if there were NO edge whatsoever, how often
would my search process still produce a result this good?" That is a p-value,
and crucially it is computed by re-running THE ENTIRE SEARCH on each
permutation. So the more configs we search, the higher the permuted results
climb, and the harder our real result has to work to look special. The
multiple-comparisons penalty is applied automatically instead of by hand.

    p = (1 + #{permutations at least as good as real}) / (1 + N)

Low p = the result is unlikely to be luck. High p = it is exactly what a big
search finds in structureless data.

    python -m backtest.mcpt --step insample   --asset BTCUSDT --perms 200
    python -m backtest.mcpt --step walkforward --asset BTCUSDT --perms 100
    python -m backtest.mcpt --step calibrate                   --perms 30
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import FILTERS, fetch, gen_signals, pf_of  # noqa: E402
from backtest.permute import get_permutation  # noqa: E402
from bot.core.indicators import donchian, ema, macd  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "logs"
OUT.mkdir(exist_ok=True)

SL, TP = 2.0, 3.0          # the exits we actually trade
MIN_TRADES = 30            # a config with fewer trades is not evaluated

# The optimisation space. This must represent THE SEARCH WE ACTUALLY RAN -
# the p-value is only honest if the permutations get to mine as hard as we did.
# Restricted to the trend/momentum families we chose among, which makes the
# test MORE forgiving than our real 873-config search; a failure here is
# therefore conclusive, while a pass is only as strong as this space is wide.
GRID_FAMS = {
    "rsi_mom":  list(itertools.product([7, 14, 21], [30, 40], [60, 70])),
    "roc_mom":  list(itertools.product([5, 10, 20], [1.0, 2.0, 4.0])),
    "bb_break": list(itertools.product([14, 20, 30], [1.5, 2.0, 2.5])),
    "donchian": [(n,) for n in [10, 20, 30, 55, 80]],
    "ma_cross": list(itertools.product([5, 10, 20, 50], [50, 100, 200])),
    "macd":     list(itertools.product([8, 12], [21, 26], [7, 9])),
}
GRID_FILTERS = ["none", "er30"]

# negative control: mean reversion, which every honest test we ran rejected.
CONTROL_FAMS = {
    "bb_rev":     list(itertools.product([14, 20, 30], [1.5, 2.0, 2.5])),
    "rsi_rev":    list(itertools.product([7, 14, 21], [25, 30, 35], [65, 70, 75])),
    "zscore_rev": list(itertools.product([20, 50], [1.5, 2.0, 2.5])),
}

# What the LIVE FOREX BOT actually trades: long-only donchian breakout gated by
# a trend EMA (5 of its 6 sleeves), plus trend-filtered MACD (the 6th). Testing
# the generic long/short donchian instead would not be testing our bot.
FOREX_FAMS = {
    "donch_lo":   list(itertools.product([10, 20, 30, 55, 80], [100, 200])),
    "macd_trend": list(itertools.product([8, 12], [21, 26], [9], [200])),
}

GRIDS = {"momentum": GRID_FAMS, "control": CONTROL_FAMS, "forex": FOREX_FAMS}


def gen_signals_ext(df: pd.DataFrame, fam: str, p: tuple) -> pd.Series:
    """gen_signals plus the two families the forex bot really runs."""
    if fam == "donch_lo":                      # == bot.strategies.DonchianBreakout
        period, trend = p                      #    (use_trend=True, long_only=True)
        lower, upper = donchian(df, period)
        c = df["close"]
        sig = pd.Series(Action.HOLD, index=df.index, dtype=int)
        sig[(c > upper) & (c > ema(c, trend))] = Action.BUY
        return sig.shift(1).fillna(Action.HOLD).astype(int)
    if fam == "macd_trend":                    # == bot.strategies.MacdTrend
        f, s, g, trend = p
        line, sg, _ = macd(df["close"], f, s, g)
        et = ema(df["close"], trend)
        up = df["close"] > et
        sig = pd.Series(Action.HOLD, index=df.index, dtype=int)
        sig[(line > sg) & (line.shift(1) <= sg.shift(1)) & up] = Action.BUY
        sig[(line < sg) & (line.shift(1) >= sg.shift(1)) & ~up] = Action.SELL
        return sig.shift(1).fillna(Action.HOLD).astype(int)
    return gen_signals(df, fam, p)


def build_grid(fams: dict) -> list[tuple]:
    return [(f, p, filt) for f, ps in fams.items() for p in ps for filt in GRID_FILTERS]


@dataclass
class Best:
    fam: str
    p: tuple
    filt: str
    pf: float
    n: int


def optimize(df: pd.DataFrame, grid: list[tuple]) -> Best:
    """Best profit factor over the grid. This is the 'data mining' being tested."""
    best = Best("none", (), "none", -1.0, 0)
    for fam, p, filt in grid:
        try:
            sig = FILTERS[filt](df, gen_signals_ext(df, fam, p))
            pf, n = pf_of(df, sig, SL, TP)
        except Exception:
            continue
        if pf is None or n < MIN_TRADES:
            continue
        if pf > best.pf:
            best = Best(fam, p, filt, float(pf), int(n))
    return best


# --------------------------------------------------------------------------- #
# Step 2: in-sample MCPT
# --------------------------------------------------------------------------- #
def insample_mcpt(df: pd.DataFrame, grid: list[tuple], n_perm: int,
                  label: str, seed0: int = 1000) -> dict:
    t0 = time.time()
    real = optimize(df, grid)
    print(f"  REAL best: {real.fam}{real.p} filt={real.filt} "
          f"PF={real.pf:.4f} trades={real.n}")
    if real.pf <= 0:
        return dict(error="no valid config on real data")

    perm_pfs, n_better = [], 0
    for i in range(n_perm):
        perm = get_permutation(df, seed=seed0 + i)
        b = optimize(perm, grid)
        perm_pfs.append(b.pf)
        if b.pf >= real.pf:
            n_better += 1
        if (i + 1) % 10 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{n_perm} perms | permuted best PF median "
                  f"{np.median(perm_pfs):.3f} max {np.max(perm_pfs):.3f} "
                  f"| better={n_better} | {el/(i+1):.1f}s/perm", flush=True)

    pval = (1 + n_better) / (1 + n_perm)
    res = dict(test="insample_mcpt", label=label, real_pf=real.pf,
               real_cfg=f"{real.fam}{real.p}+{real.filt}", real_trades=real.n,
               n_perm=n_perm, n_better=n_better, pval=pval,
               perm_pf_mean=float(np.mean(perm_pfs)),
               perm_pf_median=float(np.median(perm_pfs)),
               perm_pf_p95=float(np.percentile(perm_pfs, 95)),
               perm_pf_max=float(np.max(perm_pfs)),
               grid_size=len(grid), secs=round(time.time() - t0, 1),
               perm_pfs=[round(x, 4) for x in perm_pfs])
    return res


# --------------------------------------------------------------------------- #
# Step 4: walk-forward MCPT
# --------------------------------------------------------------------------- #
def walkforward_signals(df: pd.DataFrame, grid: list[tuple],
                        train: int, step: int) -> pd.Series:
    """Re-optimise on a trailing window, trade the winner forward. No look-ahead:
    params for bars [s, s+step) come only from bars [s-train, s)."""
    sig = pd.Series(Action.HOLD, index=df.index, dtype=int)
    for s in range(train, len(df), step):
        tr = df.iloc[s - train:s].reset_index(drop=True)
        b = optimize(tr, grid)
        if b.pf <= 0:
            continue
        end = min(s + step, len(df))
        # signals generated on data up to `end` only; indicators are causal
        upto = df.iloc[:end]
        full = FILTERS[b.filt](upto, gen_signals_ext(upto, b.fam, b.p))
        sig.iloc[s:end] = full.iloc[s:end].to_numpy()
    return sig


def wf_pf(df: pd.DataFrame, sig: pd.Series, train: int) -> tuple[float, int]:
    s = sig.copy()
    s.iloc[:train] = Action.HOLD          # score out-of-sample only
    pf, n = pf_of(df, s, SL, TP)
    return (pf if pf is not None else 0.0), n


def walkforward_mcpt(df: pd.DataFrame, grid: list[tuple], n_perm: int,
                     train: int, step: int, label: str, seed0: int = 2000) -> dict:
    t0 = time.time()
    real_sig = walkforward_signals(df, grid, train, step)
    real_pf, real_n = wf_pf(df, real_sig, train)
    print(f"  REAL walk-forward PF={real_pf:.4f} trades={real_n} "
          f"(train={train} step={step}, {(len(df)-train)//step+1} refits)")
    if real_n < MIN_TRADES:
        return dict(error=f"only {real_n} OOS trades")

    perm_pfs, n_better = [], 0
    for i in range(n_perm):
        # permute ONLY out-of-sample: the strategy still trains on real data
        perm = get_permutation(df, start_index=train, seed=seed0 + i)
        ps = walkforward_signals(perm, grid, train, step)
        p_pf, _ = wf_pf(perm, ps, train)
        perm_pfs.append(p_pf)
        if p_pf >= real_pf:
            n_better += 1
        if (i + 1) % 5 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{n_perm} perms | permuted WF PF median "
                  f"{np.median(perm_pfs):.3f} max {np.max(perm_pfs):.3f} "
                  f"| better={n_better} | {el/(i+1):.0f}s/perm", flush=True)

    pval = (1 + n_better) / (1 + n_perm)
    return dict(test="walkforward_mcpt", label=label, real_pf=real_pf,
                real_trades=real_n, n_perm=n_perm, n_better=n_better, pval=pval,
                train=train, step=step,
                perm_pf_mean=float(np.mean(perm_pfs)),
                perm_pf_median=float(np.median(perm_pfs)),
                perm_pf_p95=float(np.percentile(perm_pfs, 95)),
                perm_pf_max=float(np.max(perm_pfs)),
                grid_size=len(grid), secs=round(time.time() - t0, 1),
                perm_pfs=[round(x, 4) for x in perm_pfs])


# --------------------------------------------------------------------------- #
# Calibration: is the TEST ITSELF unbiased?
# --------------------------------------------------------------------------- #
def calibrate(df: pd.DataFrame, grid: list[tuple], n_trials: int,
              n_perm: int) -> dict:
    """Feed the test data that provably has NO edge (a permutation) and check the
    p-values come out roughly UNIFORM. If they skew low, the test manufactures
    significance and every p-value it reports is worthless."""
    pvals = []
    for k in range(n_trials):
        fake_real = get_permutation(df, seed=90000 + k)
        real = optimize(fake_real, grid)
        n_better = 0
        for i in range(n_perm):
            b = optimize(get_permutation(df, seed=50000 + k * 500 + i), grid)
            if b.pf >= real.pf:
                n_better += 1
        p = (1 + n_better) / (1 + n_perm)
        pvals.append(p)
        print(f"    trial {k+1}/{n_trials}: fake-real PF={real.pf:.3f} p={p:.3f}",
              flush=True)
    return dict(test="calibration", n_trials=n_trials, n_perm=n_perm,
                pvals=pvals, mean_p=float(np.mean(pvals)),
                frac_below_05=float(np.mean(np.array(pvals) < 0.05)))


def verdict(p: float) -> str:
    """Deliberately narrow wording.

    On 2026-09-11 gold scored p=0.0050 here - 0 of 200 permutations beat it -
    and then LOST 12.6%/yr on a 2.54-year untouched holdout (backtest/final_oos).
    Both numbers were correct. Passing this test only rules out one specific
    failure: that the result came from mining THIS data with THIS declared
    search. It says nothing about choices made before the search was declared
    (family, filters, exits, which window to even load) or about regime
    dependence. This wording must never again imply 'a real edge'.
    """
    if p <= 0.01:
        return "not explainable by mining this data (still needs a holdout)"
    if p <= 0.05:
        return "clears the 5% bar on this data (still needs a holdout)"
    if p <= 0.10:
        return "WEAK / borderline - not tradeable on its own"
    return "INDISTINGUISHABLE FROM DATA MINING"


def save(res: dict, name: str) -> Path:
    f = OUT / f"mcpt_{name}.json"
    json.dump(res, open(f, "w"), indent=1)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True,
                    choices=["insample", "walkforward", "calibrate"])
    ap.add_argument("--asset", default="BTCUSDT")
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--days", type=int, default=900)
    ap.add_argument("--perms", type=int, default=200)
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--train", type=int, default=8760)     # ~1 year of 1h bars
    ap.add_argument("--step-bars", type=int, default=2160)  # refit ~quarterly
    ap.add_argument("--grid", default="momentum", choices=list(GRIDS),
                    help="momentum | control (mean reversion) | forex (what the "
                         "live forex bot trades)")
    ap.add_argument("--control", action="store_true",
                    help="alias for --grid control")
    args = ap.parse_args()

    gname = "control" if args.control else args.grid
    df = fetch(args.asset, args.tf, args.days)
    grid = build_grid(GRIDS[gname])
    tag = f"{args.asset}_{args.tf}" + ("" if gname == "momentum" else f"_{gname.upper()}")
    print(f"{args.asset} {args.tf}: {len(df)} bars "
          f"{df.time.iloc[0].date()}..{df.time.iloc[-1].date()}")
    print(f"grid: {len(grid)} configs ({gname}), "
          f"exits {SL}/{TP} ATR, fee 10bp round trip\n")

    if args.step == "insample":
        res = insample_mcpt(df, grid, args.perms, tag)
    elif args.step == "walkforward":
        res = walkforward_mcpt(df, grid, args.perms, args.train,
                               args.step_bars, tag)
    else:
        res = calibrate(df, grid, args.trials, args.perms)

    if "error" in res:
        print(f"\nERROR: {res['error']}")
        return

    if res["test"] == "calibration":
        print(f"\nmean p-value {res['mean_p']:.3f} (should be ~0.5), "
              f"fraction below 0.05: {res['frac_below_05']:.2f} (should be ~0.05)")
        print("VERDICT:", "test looks unbiased" if 0.3 < res["mean_p"] < 0.7
              else "TEST IS BIASED - do not trust its p-values")
    else:
        print(f"\n{'='*66}")
        print(f"real PF           {res['real_pf']:.4f}   ({res.get('real_cfg','walk-forward')})")
        print(f"permuted PF       median {res['perm_pf_median']:.4f}  "
              f"95th {res['perm_pf_p95']:.4f}  max {res['perm_pf_max']:.4f}")
        print(f"permutations >= real:  {res['n_better']} / {res['n_perm']}")
        print(f"p-value           {res['pval']:.4f}")
        print(f"VERDICT: {verdict(res['pval'])}")
        print(f"{'='*66}")

    f = save(res, f"{res['test']}_{tag}" if res["test"] != "calibration"
             else f"calibration_{tag}")
    print(f"saved -> {f}")


if __name__ == "__main__":
    main()
