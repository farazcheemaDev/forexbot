"""Does an ADAPTIVE bot actually beat a fixed one?

Builds a pool of strategies, then compares three allocation modes over deep data:
  FIXED     - one strategy, never changes
  EQUAL     - run every strategy all the time
  ADAPTIVE  - every N days, rank strategies on recent performance and trade only
              the top performers (the "relearning" bot)

Adaptive systems frequently LOSE to fixed ones because re-fitting chases noise.
This measures it instead of assuming either way. Accounting in R-multiples.

    python -m backtest.adaptive_test
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import FILTERS, fetch, gen_signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ASSETS = ["DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "XRPUSDT", "BNBUSDT"]
SL_MULT, TP_MULT = 2.0, 3.0
MAKER, TAKER = 0.0002, 0.0006

# the strategy pool the adaptive layer chooses between
POOL = {
    "rsi_mom_7":   ("rsi_mom",  (7, 40, 60),  "er30"),
    "rsi_mom_21":  ("rsi_mom",  (21, 40, 60), "er30"),
    "roc_mom_20":  ("roc_mom",  (20, 1.0),    "er30"),
    "bb_break_30": ("bb_break", (30, 1.5),    "er30"),
    "donchian_20": ("donchian", (20,),        "er30"),
    "ma_cross":    ("ma_cross", (20, 50),     "er30"),
}
FIXED_CHOICE = "rsi_mom_7"          # chosen previously, not with hindsight here


def trades_for(df, fam, p, filt):
    """Return list of (exit_time_ms, R) for one strategy on one asset."""
    sig = FILTERS[filt](df, gen_signals(df, fam, p)).values
    o, h, l = df["open"].values, df["high"].values, df["low"].values
    t = df["time"].values.astype("datetime64[ms]").astype(np.int64)
    # .shift(1): ATR[i] contains bar i's own range, unknown at bar i's open
    # where the entry fills. Using it is look-ahead (see rtest.py).
    a = atr_ind(df, 14).shift(1).values
    out, pos = [], None
    for i in range(len(df)):
        if pos is not None:
            d = pos["d"]
            hit_sl = (l[i] <= pos["sl"]) if d == 1 else (h[i] >= pos["sl"])
            hit_tp = (h[i] >= pos["tp"]) if d == 1 else (l[i] <= pos["tp"])
            px, taker_exit = (pos["sl"], True) if hit_sl else \
                             ((pos["tp"], False) if hit_tp else (None, True))
            if px is not None:
                R = (px - pos["e"]) * d / pos["risk"]
                R -= (MAKER + (TAKER if taker_exit else MAKER)) * pos["e"] / pos["risk"]
                out.append((t[i], R))
                pos = None
        if pos is None and sig[i] != Action.HOLD and np.isfinite(a[i]) and a[i] > 0:
            d = 1 if sig[i] == Action.BUY else -1
            risk = SL_MULT * a[i]
            pos = {"d": d, "e": o[i], "risk": risk,
                   "sl": o[i] - d * risk, "tp": o[i] + d * TP_MULT * a[i]}
    return out


def build(cache={}):
    if cache:
        return cache
    for name, (fam, p, filt) in POOL.items():
        rows = []
        for sym in ASSETS:
            df = fetch(sym, "1h", 900)
            for ts, R in trades_for(df, fam, p, filt):
                rows.append((ts, R))
        rows.sort()
        cache[name] = pd.DataFrame(rows, columns=["ts", "R"])
        print(f"  {name:12} {len(rows):5} trades  meanR={cache[name].R.mean():+.4f}")
    return cache


def simulate(data, mode, risk_pct=1.0, lookback_days=60, rebal_days=30, top_k=2):
    """Walk the timeline, allocating per mode. Returns equity series + stats."""
    all_ts = sorted({int(t) for d in data.values() for t in d.ts})
    start, end = all_ts[0], all_ts[-1]
    day = 86400000
    eq = 1000.0
    curve, times, taken = [], [], []
    active = ([FIXED_CHOICE] if mode == "fixed"
              else list(POOL) if mode == "equal" else None)

    t = start
    while t < end:
        nxt = t + rebal_days * day
        if mode == "adaptive":
            lo = t - lookback_days * day
            scores = {}
            for name, d in data.items():
                w = d[(d.ts >= lo) & (d.ts < t)]
                scores[name] = w.R.mean() if len(w) >= 10 else -9
            active = [k for k, _ in sorted(scores.items(), key=lambda x: -x[1])[:top_k]]
        # trade the active set over this window
        for name in active:
            d = data[name]
            w = d[(d.ts >= t) & (d.ts < nxt)]
            for R in w.R.values:
                eq *= (1 + R * risk_pct / 100.0 / max(len(active), 1))
                taken.append(R)
        curve.append(eq); times.append(t)
        t = nxt

    R = np.array(taken)
    ser = pd.Series(curve, index=pd.to_datetime(times, unit="ms"))
    peak = np.maximum.accumulate(ser.values)
    dd = ((peak - ser.values) / peak).max() * 100
    yrs = (end - start) / (365.25 * day)
    return dict(final=eq, ret=(eq / 1000 - 1) * 100,
                cagr=((eq / 1000) ** (1 / yrs) - 1) * 100,
                dd=dd, n=len(R), meanR=R.mean() if len(R) else 0, curve=ser)


def main():
    print("Building trade sets for each strategy...")
    data = build()

    print(f"\n{'mode':28} {'trades':>7} {'meanR':>8} {'return%':>9} {'CAGR%':>8} {'maxDD%':>8}")
    runs = [("FIXED (rsi_mom_7 only)", dict(mode="fixed")),
            ("EQUAL (all 6 always)", dict(mode="equal")),
            ("ADAPTIVE top-1 / 30d", dict(mode="adaptive", top_k=1)),
            ("ADAPTIVE top-2 / 30d", dict(mode="adaptive", top_k=2)),
            ("ADAPTIVE top-3 / 30d", dict(mode="adaptive", top_k=3)),
            ("ADAPTIVE top-2 / 14d", dict(mode="adaptive", top_k=2, rebal_days=14)),
            ("ADAPTIVE top-2 / 90d", dict(mode="adaptive", top_k=2, rebal_days=90)),
            ]
    results = {}
    for label, kw in runs:
        r = simulate(data, **kw)
        results[label] = r
        print(f"{label:28} {r['n']:>7} {r['meanR']:>+8.4f} {r['ret']:>+9.1f} "
              f"{r['cagr']:>+8.1f} {r['dd']:>8.1f}")

    best_adaptive = max((v['cagr'] for k, v in results.items() if 'ADAPTIVE' in k))
    fixed = results["FIXED (rsi_mom_7 only)"]['cagr']
    equal = results["EQUAL (all 6 always)"]['cagr']
    print(f"\nbest adaptive CAGR {best_adaptive:+.1f}%  vs fixed {fixed:+.1f}%  "
          f"vs equal-weight {equal:+.1f}%")
    print("VERDICT:", "adaptation HELPS" if best_adaptive > max(fixed, equal)
          else "adaptation does NOT beat simply running it all / fixed")


if __name__ == "__main__":
    main()
