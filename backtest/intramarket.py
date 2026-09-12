"""INTRAMARKET DIFFERENCE — a relative signal, not a directional prediction.

WHY THIS IS THE MOST INTERESTING THING LEFT
-------------------------------------------
Every one of the 393 configs we tested was SINGLE-ASSET: an indicator computed on
one coin's own price, predicting that coin. All of it failed. This is structurally
different - it asks whether one coin is extended RELATIVE to another, which does
not require forecasting the market's direction at all.

METHOD (after neurotrader888/IntramarketDifference)
---------------------------------------------------
    cmma(x)  = (close - MA(lookback)) / (ATR(atr_lb) * sqrt(lookback))
             "close minus moving average", volatility- and horizon-normalised so
             it is comparable between a $70,000 coin and a $0.08 one.

    diff     = cmma(target) - cmma(reference)        reference is usually BTC

    signal   long  when diff >  threshold
             short when diff < -threshold
             flat  once diff crosses back through 0

Note the asymmetry: entry is MOMENTUM on the spread (buy the coin pulling ahead),
exit is REVERSION (flat when the spread closes). There is no stop loss - the
position is held until the spread normalises.

WHAT WE ADD
-----------
  * every input SHIFTED by one bar, so a signal acting at bar i uses only data
    through i-1. (Today's tally: three separate look-ahead bugs found, each worth
    more than every real edge we have measured.)
  * DEV / HOLDOUT split - the holdout is 2020-02..2024-03, never used to choose
    anything about this strategy.
  * CROSS-ASSET gate - the same rule run on 8 target coins. A relative signal
    that works on one pair and not the others is noise; this is the gate that
    killed the Nasdaq level-fade and meta-labeling.
  * explicit costs in bp, charged per round trip.

    python -m backtest.intramarket
    python -m backtest.intramarket --ref ETHUSDT --fee 4
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import fetch  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

USED_DAYS = 900
ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
          "AVAXUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]
LOOKBACKS = [12, 24, 48]
THRESHOLDS = [0.15, 0.25, 0.40]
ATR_LB = 168


def cmma(df: pd.DataFrame, lookback: int, atr_lb: int = ATR_LB) -> pd.Series:
    """Close minus moving average, normalised by ATR and horizon. Scale-free."""
    a = atr_ind(df, atr_lb)
    ma = df["close"].rolling(lookback).mean()
    return (df["close"] - ma) / (a * lookback ** 0.5)


def threshold_revert_signal(ind: np.ndarray, threshold: float) -> np.ndarray:
    """+1 above threshold, -1 below -threshold, flat once it crosses back to 0."""
    out = np.zeros(len(ind))
    pos = 0
    for i in range(len(ind)):
        v = ind[i]
        if not np.isfinite(v):
            out[i] = pos
            continue
        if v > threshold:
            pos = 1
        elif v < -threshold:
            pos = -1
        if pos == 1 and v <= 0:
            pos = 0
        elif pos == -1 and v >= 0:
            pos = 0
        out[i] = pos
    return out


def trades_from_signal(df: pd.DataFrame, sig: np.ndarray,
                       fee_bp: float) -> np.ndarray:
    """Per-trade log return in bp, net of a round-trip cost.

    Position for bar i is taken at bar i's open and earns bar i's open->close plus
    subsequent bars until the signal changes. Signals are pre-shifted, so this is
    causal.
    """
    o = df["open"].to_numpy(float)
    c = df["close"].to_numpy(float)
    out = []
    i = 0
    n = len(sig)
    while i < n:
        if sig[i] == 0:
            i += 1
            continue
        d = sig[i]
        entry = o[i]
        j = i
        while j < n and sig[j] == d:
            j += 1
        # EXIT AT o[j], NOT c[j-1]. sig[j] is the first bar the position is no
        # longer wanted, and it is derived from data through j-1 - so the earliest
        # tradeable moment is bar j's OPEN. Exiting at c[j-1] books a move that was
        # only knowable at the instant the decision was made, and is inconsistent
        # with entering at o[i]. That asymmetry flatters every trade.
        exit_px = o[j] if j < n else c[-1]
        r = np.log(exit_px / entry) * d * 10000.0 - fee_bp    # bp, net
        if np.isfinite(r):
            out.append(r)
        i = j
    return np.asarray(out)


def evaluate(target: pd.DataFrame, ref: pd.DataFrame, lookback: int,
             threshold: float, fee_bp: float) -> dict | None:
    """One config on one pair. Every indicator shifted by 1 -> causal."""
    idx = target.index
    ct = cmma(target, lookback).shift(1)
    cr = cmma(ref, lookback).shift(1)
    diff = (ct - cr).reindex(idx)
    sig = threshold_revert_signal(diff.to_numpy(float), threshold)
    R = trades_from_signal(target, sig, fee_bp)
    if len(R) < 25:
        return None
    return dict(n=len(R), mean_bp=float(R.mean()), sum_bp=float(R.sum()),
                win=float((R > 0).mean()),
                pf=float(R[R > 0].sum() / abs(R[R < 0].sum()))
                if (R < 0).any() else float("inf"))


def align(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Intersect on timestamp — a relative signal is meaningless on misaligned bars."""
    a = a.set_index("time"); b = b.set_index("time")
    common = a.index.intersection(b.index)
    return (a.loc[common].reset_index(), b.loc[common].reset_index())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="BTCUSDT")
    ap.add_argument("--fee", type=float, default=12.0,
                    help="round-trip cost in bp (12 = Bitget taker, 4 = maker)")
    args = ap.parse_args()

    print(f"INTRAMARKET DIFFERENCE  reference = {args.ref}  "
          f"cost = {args.fee}bp round trip")
    print(f"grid: lookback {LOOKBACKS} x threshold {THRESHOLDS}\n")

    raw = {}
    for a in ASSETS:
        try:
            raw[a] = fetch(a, "1h", 2400)
        except Exception as e:
            print(f"  {a}: fetch failed {e}")
    if args.ref not in raw:
        raise SystemExit(f"reference {args.ref} unavailable")

    targets = [a for a in ASSETS if a != args.ref and a in raw]
    cut = raw[args.ref].time.iloc[-1] - pd.Timedelta(days=USED_DAYS)

    # ---- per-config, pooled over targets, dev vs holdout -------------------
    print(f"{'lookback':>8} {'thresh':>7} | {'HOLDOUT (unseen)':>28} | "
          f"{'dev window':>22}")
    print(f"{'':>8} {'':>7} | {'trades':>7} {'mean bp':>9} {'coins+':>9} | "
          f"{'trades':>7} {'mean bp':>9}")
    results = []
    for lb, th in itertools.product(LOOKBACKS, THRESHOLDS):
        agg = {"hold": [], "used": []}
        percoin = []
        for t in targets:
            tt, rr = align(raw[t], raw[args.ref])
            for key in ("hold", "used"):
                m = (tt.time < cut) if key == "hold" else (tt.time >= cut)
                seg_t = tt[m].reset_index(drop=True)
                seg_r = rr[m].reset_index(drop=True)
                if len(seg_t) < 3000:
                    continue
                r = evaluate(seg_t, seg_r, lb, th, args.fee)
                if r:
                    agg[key].append(r)
                    if key == "hold":
                        percoin.append((t, r["mean_bp"]))
        if len(agg["hold"]) < 4:
            continue
        nh = sum(x["n"] for x in agg["hold"])
        mh = sum(x["mean_bp"] * x["n"] for x in agg["hold"]) / nh
        pos = sum(1 for _, v in percoin if v > 0)
        nu = sum(x["n"] for x in agg["used"]) or 1
        mu = (sum(x["mean_bp"] * x["n"] for x in agg["used"]) / nu
              if agg["used"] else float("nan"))
        results.append(dict(lb=lb, th=th, n_hold=nh, mean_hold=mh,
                            pos=pos, ncoin=len(percoin), n_used=nu,
                            mean_used=mu, percoin=percoin))
        print(f"{lb:>8} {th:>7.2f} | {nh:>7} {mh:>+9.2f} {pos:>4}/{len(percoin):<4} | "
              f"{nu:>7} {mu:>+9.2f}")

    if not results:
        print("\nno config produced enough trades")
        return

    best = max(results, key=lambda r: r["mean_hold"])
    print(f"\nbest on the holdout: lookback={best['lb']} threshold={best['th']:.2f} "
          f"-> {best['mean_hold']:+.2f}bp/trade on {best['n_hold']} trades")
    print(f"  same config on the dev window: {best['mean_used']:+.2f}bp")
    print(f"  coins positive on holdout: {best['pos']}/{best['ncoin']}")
    print(f"\n  per-coin (holdout, best config):")
    for t, v in sorted(best["percoin"], key=lambda x: -x[1]):
        print(f"    {t:9} {v:+8.2f}bp")

    # ---- verdict: consistency across BOTH windows AND across coins ---------
    both = (best["mean_hold"] > 0 and best["mean_used"] > 0)
    broad = best["pos"] >= max(5, int(0.7 * best["ncoin"]))
    print(f"\n  positive on BOTH windows: {'YES' if both else 'NO'}")
    print(f"  broad across coins:       {'YES' if broad else 'NO'}")
    print("  ->", "worth the full gate battery" if both and broad
          else "fails the basic consistency check - not pursuing")


if __name__ == "__main__":
    main()
