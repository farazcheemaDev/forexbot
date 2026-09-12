"""RE-TEST OF THE REMAINING CAPPED STRATEGIES, UNCAPPED. Crypto + BTC alone.

WHY
    Six files' verdicts were void because every trade was force-closed at a fixed
    target (see validation_protocol.md, "THE PROFIT-CAP ERROR"):
        holdout_sweep.py   -> already redone in holdout_uncapped.py
        mass_search.py     -> covered by that same re-run (18 families)
        vsa.py             -> NOT yet redone      <- here
        adaptive_rsi.py    -> NOT yet redone      <- here
        nasdaq_levelfade.py-> not crypto, deferred
        final_oos.py       -> gold, deferred

    The two done here had the tightest caps of all. adaptive_rsi used tp_atr of
    0.5 and 1.0 against a 2xATR stop, i.e. winners capped at +0.25R and +0.50R.
    A 0.25R cap needs an ~80% win rate merely to break even. That is not a test of
    a signal, it is a test of a straitjacket.

WHAT IS MEASURED
    Each signal, unchanged, run through the uncapped trailing engine:
        capped control  (2xATR stop, 3xATR target -> +1.5R max)
        trail 3/5/8/12 xATR, no target
    Reported per family: mean R, the FEE TOLL in R, CAGR/DD at fixed-fractional
    sizing, P(month > +10%), and the long/short split.

THE TWO COLUMNS THAT DECIDE IT
    feeR  - the fee toll is fee*price/(2*ATR), a fixed cost per trade (~0.067R on
            1h crypto). A family whose gross edge does not clear it is dead no
            matter how good the signal looks.
    short - long-side and short-side mean R separately. Crypto compounded ~40%/yr
            over this window, so a family that earns only on the long side has
            found asset-class drift, not an edge. That single column reclassified
            an apparent +174%/yr discovery as beta earlier today.

HONESTY
    This is the RECENT window (the one every prior experiment touched), so it can
    only generate hypotheses, not confirm them. Anything promising goes to the
    virgin-coin gate (convex_wide.py), which needs no fresh time period.

    python -m backtest.retest_uncapped
    python -m backtest.retest_uncapped --btc-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import describe, run_uncapped  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.rtest import run_r  # noqa: E402
from backtest.vsa import vsa_indicator  # noqa: E402
from bot.core.indicators import atr as atr_ind, rsi  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
         "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
TRAILS = (3.0, 5.0, 8.0, 12.0)
RISK = 0.5
_D: dict = {}


def load(c, tf="1h", days=2400):
    if (c, tf, days) not in _D:
        try:
            _D[(c, tf, days)] = fetch(c, tf, days)
        except Exception:
            _D[(c, tf, days)] = None
    return _D[(c, tf, days)]


# ----------------------------------------------------------- signal makers --
def sig_vsa(df: pd.DataFrame, thresh: float = -0.5, direction: int = 1) -> pd.Series:
    """VSA absorption: a bar whose range is far BELOW what its volume predicts.

    dev = norm_range - predicted(norm_volume). Strongly negative dev = heavy volume
    with little price movement = absorption. Original vsa.py traded it as a
    reversal signal; both directions are tested because the earlier verdict was
    reached through the profit cap and may have had the sign backwards.
    """
    dev = vsa_indicator(df).shift(1)          # SHIFT: a bar cannot see itself
    out = pd.Series(Action.HOLD, index=df.index)
    hit = dev <= thresh
    out[hit] = Action.BUY if direction > 0 else Action.SELL
    return out


def sig_adaptive_rsi(df: pd.DataFrame, rsi_p: int = 14, lookback: int = 24,
                     tol: float = 5.0) -> pd.Series:
    """The user's idea: trigger when RSI returns near its OWN recent extreme.

    Long when RSI is within `tol` of its rolling minimum, short when within `tol`
    of its rolling maximum. Identical trigger logic to adaptive_rsi.py - only the
    EXIT differs here (that file used tp_atr 0.5/1.0, capping winners at +0.25R
    and +0.50R).
    """
    r = rsi(df["close"], rsi_p)
    rs = r.shift(1)
    rmin = r.rolling(lookback).min().shift(1)
    rmax = r.rolling(lookback).max().shift(1)
    out = pd.Series(Action.HOLD, index=df.index)
    out[rs <= rmin + tol] = Action.BUY
    out[rs >= rmax - tol] = Action.SELL
    return out


FAMS = {
    "vsa_long":      lambda d: sig_vsa(d, -0.5, +1),
    "vsa_short":     lambda d: sig_vsa(d, -0.5, -1),
    "vsa_strong":    lambda d: sig_vsa(d, -1.0, +1),
    "adaptRSI_24":   lambda d: sig_adaptive_rsi(d, 14, 24, 5.0),
    "adaptRSI_24t2": lambda d: sig_adaptive_rsi(d, 14, 24, 2.0),
    "adaptRSI_168":  lambda d: sig_adaptive_rsi(d, 14, 168, 5.0),
    "adaptRSI_r7":   lambda d: sig_adaptive_rsi(d, 7, 24, 5.0),
}


def pool(coins, maker, mode, trail):
    Rs, Ts, Ds = [], [], []
    for c in coins:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        try:
            sig = maker(df)
        except Exception:
            continue
        if sig is None or int((sig != Action.HOLD).sum()) == 0:
            continue
        if mode == "capped":
            R, idx = run_r(df, sig, 2.0, 3.0, FEE_BP)
            D = np.zeros(len(R), dtype=int)
        else:
            R, idx, _b, D = run_uncapped(df, sig, sl_mult=2.0, fee_bp=FEE_BP,
                                         mode="trail_atr", trail=trail)
        if len(R):
            Rs.append(R); Ts.append(df["time"].iloc[idx]); Ds.append(D)
    if not Rs:
        return None
    o = np.argsort(np.concatenate([t.values for t in Ts]))
    R = np.concatenate(Rs)[o]
    D = np.concatenate(Ds)[o]
    T = pd.Series(np.concatenate([t.values for t in Ts])[o])
    return describe(R, T, RISK, dirs=(D if D.any() else None))


def fee_toll(coins, maker, trail) -> float:
    """Exact fee cost per trade in R, by differencing a zero-fee run."""
    Rs = []
    for fb in (FEE_BP, 0.0):
        acc = []
        for c in coins:
            df = load(c)
            if df is None:
                continue
            try:
                sig = maker(df)
            except Exception:
                continue
            R, _i, _b, _d = run_uncapped(df, sig, sl_mult=2.0, fee_bp=fb,
                                         mode="trail_atr", trail=trail)
            if len(R):
                acc.append(R)
        Rs.append(np.concatenate(acc).mean() if acc else np.nan)
    return float(Rs[1] - Rs[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--btc-only", action="store_true")
    args = ap.parse_args()
    coins = ["BTCUSDT"] if args.btc_only else COINS

    print(f"RE-TEST UNCAPPED   {len(coins)} coin(s)   1h   fee {FEE_BP}bp round "
          f"trip   risk {RISK}%/trade")
    print("  families never re-tested after the profit-cap error: VSA, adaptive RSI")
    print("  adaptive_rsi.py capped winners at +0.25R and +0.50R — an 80% win rate "
          "just to break even")
    print("  RECENT window: generates hypotheses, cannot confirm them\n")

    print("=" * 124)
    print(f"{'family':<15} {'exit':<12} {'n':>6} {'meanR':>8} {'feeR':>7} "
          f"{'t':>7} {'PF':>5} {'maxR':>7} {'longR':>8} {'shortR':>8} "
          f"{'CAGR':>9} {'DD':>7} {'mo>10%':>7}")
    rows = []
    for name, maker in FAMS.items():
        base = pool(coins, maker, "capped", 0.0)
        if base:
            print(f"{name:<15} {'capped 1.5R':<12} {base['n']:>6} "
                  f"{base['mean']:>+8.3f} {'':>7} {base['t']:>+7.2f} "
                  f"{base['pf']:>5.2f} {base['mx']:>7.1f} {'':>8} {'':>8} "
                  f"{base['cagr']:>+8.1f}% {base['dd']:>6.1f}% "
                  f"{base['mo_over10']:>6.1f}%", flush=True)
        for tr in TRAILS:
            d = pool(coins, maker, "trail", tr)
            if not d:
                continue
            ft = fee_toll(coins, maker, tr)
            ru = " RUIN" if d["ruined"] else ""
            print(f"{name:<15} {'trail '+str(int(tr))+'xATR':<12} {d['n']:>6} "
                  f"{d['mean']:>+8.3f} {ft:>7.3f} {d['t']:>+7.2f} {d['pf']:>5.2f} "
                  f"{d['mx']:>7.1f} {d['long_r']:>+8.3f} {d['short_r']:>+8.3f} "
                  f"{d['cagr']:>+8.1f}% {d['dd']:>6.1f}% {d['mo_over10']:>6.1f}%"
                  f"{ru}", flush=True)
            rows.append((d["mean"], name, tr, d, ft, base))
        print()

    if not rows:
        print("nothing produced trades")
        return
    print("=" * 124)
    print("DID THE CAP HIDE ANYTHING HERE?")
    print("=" * 124)
    for name in FAMS:
        sub = [r for r in rows if r[1] == name]
        if not sub:
            continue
        best = max(sub, key=lambda r: r[0])
        b = best[5]
        cap = b["mean"] if b else float("nan")
        clears = best[0] > 0 and best[0] > best[4]
        sym = (np.isfinite(best[3]["short_r"]) and
               best[3]["short_r"] > 0.3 * abs(best[3]["long_r"]))
        print(f"  {name:<15} capped {cap:>+7.3f} -> best uncapped {best[0]:>+7.3f} "
              f"(trail {int(best[2])}x)  clears fee toll: "
              f"{'YES' if clears else 'NO':<3}  symmetric: "
              f"{'YES' if sym else 'NO'}")
    print("\n'clears fee toll' = net mean R positive AND larger than the per-trade "
          "fee.\n'symmetric' = short side at least 30% of the long side, i.e. not "
          "just crypto drift.\nBoth must be YES for this to be worth the "
          "virgin-coin gate.")


if __name__ == "__main__":
    main()
