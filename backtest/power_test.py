"""IS OUR TESTING BROKEN? A power analysis of the gate battery.

THE CHALLENGE THAT PROMPTED THIS
--------------------------------
Four candidates passed most gates and died at one (gold: holdout; intramarket:
MCPT; level_fade and meta-labeling and VSA: cross-asset). Every single time I
concluded THE STRATEGY was bad. I never tested the alternative: that the FAILING
GATE is too harsh and has been discarding real edges.

That assumption is load-bearing under every negative result in this project, and
it is testable.

THE METHOD
----------
Inject an edge that is REAL BY CONSTRUCTION, at the effect size we actually care
about, then run the full battery and see whether it survives.

    1. take real OHLC for all 9 coins
    2. pick a signal from our OWN family set (bb_break 30/1.5), computed causally
    3. add a drift of  k * ATR[i-1] * signal[i]  to bar i's return
       -> the signal now genuinely predicts, by construction
    4. rebuild prices from the modified returns
    5. run: holdout test, cross-asset gate, MCPT

If the battery FINDS the injected edge      -> the gates are calibrated, and the
                                               four failures were real.
If the battery MISSES it                    -> the gates are too harsh, every
                                               negative result is suspect, and
                                               the testing needs rebuilding.

This is a power analysis: the probability of detecting a true effect. A test with
no power is worse than no test, because it manufactures confident negatives.

CALIBRATION MATTERS. k is swept so we can find the smallest real edge the battery
can still see. If the detection floor is well ABOVE +0.05R, then our gates were
never capable of resolving the edge we have been hunting - which would mean the
whole search was mis-specified rather than the strategies being worthless.

    python -m backtest.power_test
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.holdout_sweep import USED_DAYS, signals_for  # noqa: E402
from backtest.mass_search import FILTERS, fetch  # noqa: E402
from backtest.permute import get_permutation  # noqa: E402
from backtest.rtest import run_r  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
          "AVAXUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]
FRESH = ["LTCUSDT", "DOTUSDT", "ATOMUSDT", "FILUSDT"]
PRIMARY = ("bb_break", (30, 1.5))
SL, TP, FEE_BP = 2.0, 3.0, 10.0
OHLC = ["open", "high", "low", "close"]


def inject_edge(df: pd.DataFrame, k: float) -> pd.DataFrame:
    """Add a genuine, causal edge of scale k*ATR aligned with the primary signal.

    The signal is computed on the ORIGINAL data and is already shifted, so it
    depends only on bars up to i-1. We then nudge bar i's close-to-close return in
    the signal's direction. That makes the signal truly predictive - no look-ahead,
    just a real relationship we put there on purpose.
    """
    if k == 0.0:
        return df
    sig = FILTERS["none"](df, signals_for(df, *PRIMARY)).to_numpy()
    a = atr_ind(df, 14).to_numpy(float)
    c = df["close"].to_numpy(float)

    d = np.zeros(len(df))
    live = (sig != Action.HOLD) & np.isfinite(a)
    d[live] = np.where(sig[live] == Action.BUY, 1.0, -1.0) * k * a[live] / c[live]
    d = np.nan_to_num(d)

    # apply as a multiplicative drift on the return path, then rebuild OHLC so the
    # bar shapes stay intact (high/low keep their offsets from the close)
    logc = np.log(c)
    ret = np.diff(logc, prepend=logc[0]) + d
    new_c = np.exp(logc[0] + np.cumsum(ret))
    scale = new_c / c
    out = df.copy()
    for col in OHLC:
        out[col] = df[col].to_numpy(float) * scale
    return out


def measure(df: pd.DataFrame) -> tuple[float, int]:
    sig = FILTERS["none"](df, signals_for(df, *PRIMARY))
    R, _ = run_r(df, sig, SL, TP, FEE_BP)
    return (float(R.mean()), len(R)) if len(R) >= 30 else (float("nan"), len(R))


def segments(sym):
    try:
        d = fetch(sym, "1h", 2400)
    except Exception:
        return None
    cut = d.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
    hold = d[d.time < cut].reset_index(drop=True)
    used = d[d.time >= cut].reset_index(drop=True)
    return (hold, used) if len(hold) >= 3000 else None


def main():
    print("POWER ANALYSIS — can our gate battery detect an edge we KNOW is real?\n")
    base = {a: segments(a) for a in ASSETS}
    base = {a: v for a, v in base.items() if v}
    fresh = {a: segments(a) for a in FRESH}
    fresh = {a: v for a, v in fresh.items() if v}
    print(f"{len(base)} original coins, {len(fresh)} fresh coins\n")

    print("=" * 80)
    print("STEP 1 — calibrate: what per-trade edge does each injection size give?")
    print("=" * 80)
    print(f"{'k':>6} {'holdout meanR':>15} {'dev meanR':>12} {'coins+':>9}")
    KS = [0.0, 0.005, 0.01, 0.02, 0.04, 0.08]
    table = {}
    for k in KS:
        res = {}
        for wi, wn in ((0, "hold"), (1, "dev")):
            ms, ns, pos = [], [], 0
            for a, segs in base.items():
                inj = inject_edge(segs[wi], k)
                m, n = measure(inj)
                if np.isfinite(m):
                    ms.append(m); ns.append(n); pos += m > 0
            res[wn] = (sum(m * n for m, n in zip(ms, ns)) / sum(ns), pos, len(ms))
        table[k] = res
        print(f"{k:>6.3f} {res['hold'][0]:>+15.4f} {res['dev'][0]:>+12.4f} "
              f"{res['hold'][1]:>4}/{res['hold'][2]:<4}")

    # pick the injection whose holdout edge is closest to the +0.05R we chase
    target = 0.05
    k_star = min((k for k in KS if k > 0),
                 key=lambda k: abs(table[k]["hold"][0] - target))
    print(f"\n  -> k={k_star} gives holdout {table[k_star]['hold'][0]:+.4f}R, "
          f"closest to the +{target:.2f}R effect we have been hunting")

    print("\n" + "=" * 80)
    print(f"STEP 2 — run the CROSS-ASSET GATE on the injected edge (k={k_star})")
    print("   this is the gate that killed level_fade, meta-labeling and VSA")
    print("=" * 80)
    print(f"  {'coin':10} {'window':8} {'meanR':>9} {'positive?':>10}")
    w = t = 0
    for a, segs in fresh.items():
        for wi, wn in ((0, "holdout"), (1, "dev")):
            m, n = measure(inject_edge(segs[wi], k_star))
            if not np.isfinite(m):
                continue
            t += 1; w += m > 0
            print(f"  {a:10} {wn:8} {m:>+9.4f} {'YES' if m > 0 else 'no':>10}")
    print(f"\n  positive on {w}/{t} FRESH coin-windows "
          f"({'PASSES' if t and w/t >= 0.7 else 'FAILS'} the cross-asset gate)")

    print("\n" + "=" * 80)
    print(f"STEP 3 — run MCPT on the injected edge (k={k_star})")
    print("   this is the gate that killed intramarket difference")
    print("=" * 80)
    inj = {a: inject_edge(segs[0], k_star) for a, segs in base.items()}
    ms, ns = [], []
    for a, d in inj.items():
        m, n = measure(d)
        if np.isfinite(m):
            ms.append(m); ns.append(n)
    real = sum(m * n for m, n in zip(ms, ns)) / sum(ns)
    print(f"  real (injected) pooled meanR = {real:+.4f}")
    perms, better = [], 0
    N = 60
    for i in range(N):
        pm, pn = [], []
        for a, d in inj.items():
            p = get_permutation(d, seed=77000 + i * 13 + hash(a) % 97)
            m, n = measure(p)
            if np.isfinite(m):
                pm.append(m); pn.append(n)
        v = sum(m * n for m, n in zip(pm, pn)) / sum(pn)
        perms.append(v)
        if v >= real:
            better += 1
        if (i + 1) % 20 == 0:
            print(f"    {i+1}/{N} | permuted median {np.median(perms):+.4f} "
                  f"max {np.max(perms):+.4f} | better={better}", flush=True)
    p = (1 + better) / (1 + N)
    print(f"\n  permuted: median {np.median(perms):+.4f}  max {np.max(perms):+.4f}")
    print(f"  p-value {p:.4f}  ({'DETECTED' if p <= 0.05 else 'MISSED'})")

    print("\n" + "=" * 80)
    print("VERDICT ON OUR OWN TESTING")
    print("=" * 80)
    xa = "PASSES" if t and w / t >= 0.7 else "FAILS"
    mc = "DETECTED" if p <= 0.05 else "MISSED"
    print(f"  injected edge size      {table[k_star]['hold'][0]:+.4f}R "
          f"(target {target:+.2f}R)")
    print(f"  cross-asset gate        {xa}")
    print(f"  MCPT                    {mc}")
    if xa == "PASSES" and mc == "DETECTED":
        print("\n  -> The battery CAN see a real edge of the size we are hunting.")
        print("     So the four failures were the strategies, not the tests.")
    else:
        print("\n  -> The battery CANNOT reliably see a real edge of this size.")
        print("     Every negative result in this project is then suspect, and the")
        print("     gates need rebuilding before any strategy is dismissed again.")


if __name__ == "__main__":
    main()
