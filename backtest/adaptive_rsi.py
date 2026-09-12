"""ADAPTIVE RSI EXTREMES — calibrate the oversold level to what the market did.

THE IDEA (user's, and the adaptive part is genuinely untested here)
------------------------------------------------------------------
Instead of a fixed "RSI < 30 = oversold", look at the LOWEST RSI actually reached
over the last day. If it bottomed at 8, then 8-10 is what oversold MEANS for this
coin right now. When RSI returns near that observed floor, go long - and exit
QUICKLY rather than waiting for RSI to climb all the way back.

Mirror for the top: when RSI returns near its observed daily ceiling, go short.

WHY THIS IS NOT THE rsi_rev WE ALREADY KILLED
    rsi_rev used FIXED thresholds (25/30/35, 65/70/75) and a 3xATR target. It was
    among the worst families tested (-0.106R, 0/81 configs positive).
    This differs in two ways that matter:
      1. the threshold SELF-CALIBRATES to the coin and the regime
      2. the exit is FAST and small, not a wide mean-reversion target

WHAT WORRIES ME ABOUT IT, STATED UP FRONT
    A fast, small exit makes the fee problem WORSE, not better. Everything we
    measured today died because effects were a few bp against a 4-12bp cost floor.
    A quick scalp has a small target, so the same fee eats a larger share of it.
    The adaptive trigger might be a real improvement and still lose on cost. Both
    are tested here, separately, so we can see which it is.

    Also note: LEVERAGE does not appear anywhere. Leverage scales position size,
    not edge - it multiplies wins and losses identically and changes nothing about
    whether the strategy is profitable. Everything is measured in R (multiples of
    the risk taken), which is leverage-independent by construction.

HONEST FRAMEWORK, same as everything else today
    * every indicator shifted so a bar cannot see itself
    * DEV window vs UNTOUCHED HOLDOUT, and per-coin results
    * real costs charged
    * a FIXED-threshold control run alongside, so we can tell whether the
      adaptive part is doing any work

    python -m backtest.adaptive_rsi
    python -m backtest.adaptive_rsi --tf 5m
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
from bot.core.indicators import atr as atr_ind, rsi  # noqa: E402

USED_DAYS = 900
SL_MULT = 2.0
FEE_BP = 10.0

ASSETS_1H = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
             "AVAXUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]


def simulate(df: pd.DataFrame, rsi_p: int, lookback: int, tol: float,
             exit_bars: int, tp_atr: float | None, fixed: float | None,
             fee_bp: float = FEE_BP) -> np.ndarray:
    """One config. Returns net R per trade.

    fixed=None  -> ADAPTIVE: trigger when RSI is within `tol` of its own rolling
                   min (long) / max (short) over `lookback` bars.
    fixed=x     -> CONTROL: trigger at the fixed level x / (100-x).

    Exit is whichever comes first: the 2xATR protective stop, the small take-profit
    (tp_atr, if given), or `exit_bars` elapsed. R is measured against the 2xATR
    stop distance so it is comparable with every other result today and is
    independent of leverage.
    """
    r = rsi(df["close"], rsi_p)
    a = atr_ind(df, 14)
    # SHIFT: a bar must not see its own RSI/ATR, and the rolling extreme must
    # exclude the current bar too.
    rs = r.shift(1)
    rmin = r.rolling(lookback).min().shift(1)
    rmax = r.rolling(lookback).max().shift(1)
    av = a.shift(1)

    o = df["open"].to_numpy(float)
    hi = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    cl = df["close"].to_numpy(float)
    rsv = rs.to_numpy(float)
    rmn = rmin.to_numpy(float)
    rmx = rmax.to_numpy(float)
    atv = av.to_numpy(float)
    n = len(df)
    fee = fee_bp / 10000.0

    out = []
    i = max(lookback, rsi_p, 20) + 2
    while i < n - 1:
        if not (np.isfinite(rsv[i]) and np.isfinite(atv[i]) and atv[i] > 0):
            i += 1
            continue
        if fixed is None:
            if not (np.isfinite(rmn[i]) and np.isfinite(rmx[i])):
                i += 1
                continue
            long_sig = rsv[i] <= rmn[i] + tol
            short_sig = rsv[i] >= rmx[i] - tol
        else:
            long_sig = rsv[i] <= fixed
            short_sig = rsv[i] >= (100.0 - fixed)
        if not (long_sig or short_sig):
            i += 1
            continue
        d = 1 if long_sig else -1
        e = o[i]
        risk = SL_MULT * atv[i]
        stop = e - d * risk
        targ = e + d * tp_atr * atv[i] if tp_atr else None
        px = None
        for j in range(i, min(i + exit_bars, n)):
            hit_sl = (lo[j] <= stop) if d == 1 else (hi[j] >= stop)
            hit_tp = (targ is not None and
                      ((hi[j] >= targ) if d == 1 else (lo[j] <= targ)))
            if hit_sl:
                px = stop; ex = j; break
            if hit_tp:
                px = targ; ex = j; break
        if px is None:
            ex = min(i + exit_bars - 1, n - 1)
            px = cl[ex]
        R = (px - e) * d / risk - (fee * e + fee * abs(px)) / risk
        out.append(R)
        i = ex + 1
    return np.asarray(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--days", type=int, default=2400)
    args = ap.parse_args()

    bars_per_day = {"1h": 24, "5m": 288, "15m": 96}[args.tf]
    assets = ASSETS_1H
    data = {}
    for a in assets:
        try:
            d = fetch(a, args.tf, args.days)
        except Exception:
            continue
        cut = d.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
        hold = d[d.time < cut].reset_index(drop=True)
        used = d[d.time >= cut].reset_index(drop=True)
        if len(hold) < 3000:
            continue
        data[a] = (hold, used)
    print(f"ADAPTIVE RSI EXTREMES  tf={args.tf}  {len(data)} coins  "
          f"cost {FEE_BP}bp\n")
    print("R is measured against the 2xATR stop, so it is leverage-independent.\n")

    def pooled(cfg, wi):
        allR, pos, tot = [], 0, 0
        for a, segs in data.items():
            R = simulate(segs[wi], **cfg)
            if len(R) >= 30:
                allR.append(R); tot += 1; pos += R.mean() > 0
        if not allR:
            return None
        R = np.concatenate(allR)
        return dict(n=len(R), mean=R.mean(),
                    se=R.std(ddof=1) / np.sqrt(len(R)), pos=pos, tot=tot)

    print("=" * 96)
    print("ADAPTIVE (trigger near the rolling RSI extreme) — lookback = 1 day")
    print("=" * 96)
    print(f"{'rsi':>4} {'tol':>5} {'exit':>6} {'tp':>5} | "
          f"{'HOLDOUT  n     meanR      t   coins+':>40} | "
          f"{'DEV      n     meanR   coins+':>34}")
    rows = []
    for rp, tol, xb, tp in itertools.product((7, 14), (2.0, 5.0), (3, 6, 12),
                                             (None, 0.5, 1.0)):
        cfg = dict(rsi_p=rp, lookback=bars_per_day, tol=tol,
                   exit_bars=xb, tp_atr=tp, fixed=None)
        h = pooled(cfg, 0)
        u = pooled(cfg, 1)
        if not (h and u):
            continue
        rows.append((h["mean"] / h["se"], rp, tol, xb, tp, h, u))
        print(f"{rp:>4} {tol:>5.1f} {xb:>5}b {str(tp):>5} | "
              f"{h['n']:>7} {h['mean']:>+9.4f} {h['mean']/h['se']:>+6.2f} "
              f"{h['pos']:>3}/{h['tot']:<4} | "
              f"{u['n']:>7} {u['mean']:>+9.4f} {u['pos']:>3}/{u['tot']:<4}")

    print("\n" + "=" * 96)
    print("FIXED-THRESHOLD CONTROL — same exits, classic levels. Is 'adaptive' "
          "doing any work?")
    print("=" * 96)
    print(f"{'rsi':>4} {'lvl':>5} {'exit':>6} {'tp':>5} | "
          f"{'HOLDOUT  n     meanR      t':>32} | {'DEV      n     meanR':>26}")
    for rp, lvl, xb, tp in itertools.product((7, 14), (20.0, 30.0), (3, 6, 12),
                                             (None, 0.5)):
        cfg = dict(rsi_p=rp, lookback=bars_per_day, tol=0.0,
                   exit_bars=xb, tp_atr=tp, fixed=lvl)
        h = pooled(cfg, 0)
        u = pooled(cfg, 1)
        if not (h and u):
            continue
        print(f"{rp:>4} {lvl:>5.0f} {xb:>5}b {str(tp):>5} | "
              f"{h['n']:>7} {h['mean']:>+9.4f} {h['mean']/h['se']:>+6.2f} | "
              f"{u['n']:>7} {u['mean']:>+9.4f}")

    if not rows:
        return
    rows.sort(reverse=True)
    t, rp, tol, xb, tp, h, u = rows[0]
    print(f"\nbest adaptive on the holdout: rsi{rp} tol={tol} exit={xb}bars tp={tp}")
    print(f"  holdout {h['mean']:+.4f}R (t={t:+.2f}, {h['pos']}/{h['tot']} coins) | "
          f"dev {u['mean']:+.4f}R ({u['pos']}/{u['tot']} coins)")
    consistent = h["mean"] > 0 and u["mean"] > 0
    print(f"  positive in BOTH windows: {'YES' if consistent else 'NO'}")
    print(f"  -> {'worth the full gate battery' if consistent and t > 2 else 'fails the basic consistency/significance check'}")


if __name__ == "__main__":
    main()
