"""Does MAKER execution actually rescue the thin momentum edge?

Maker saves fees (~2bp vs ~20bp) but introduces ADVERSE SELECTION: a limit order
only fills if price comes to you, so you miss the trades that run and
preferentially fill the ones that turn against you. Both effects are modeled.

Accounting is in R-multiples (each trade risks exactly 1R) so results are
comparable across assets and free of the lot-size clamp that distorted returns.

    python -m backtest.maker_test
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

UNSEEN = ["DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "XRPUSDT", "BNBUSDT"]
SEEN = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
CONFIG = ("rsi_mom", (7, 40, 60), "er30")     # best survivor after bug fix
SL_MULT, TP_MULT = 2.0, 3.0


def simulate(df, fam, p, fn, mode, fee_bp, offset_bp):
    """mode='taker' -> enter at open, taker fees both sides.
       mode='maker' -> post limit offset_bp better than open; fills only if
       touched that bar; maker fee on entry and on TP exit, taker on SL exit."""
    sig = FILTERS[fn](df, gen_signals(df, fam, p)).values
    o, h, l, c = (df[x].values for x in ("open", "high", "low", "close"))
    # .shift(1): ATR[i] contains bar i's own range, unknown at bar i's open
    # where the entry fills. Using it is look-ahead (see rtest.py).
    a = atr_ind(df, 14).shift(1).values

    pos = None
    Rs = []
    missed = 0
    for i in range(len(df)):
        # ---- manage open position ----
        if pos is not None:
            d = pos["dir"]
            hit_sl = (l[i] <= pos["sl"]) if d == 1 else (h[i] >= pos["sl"])
            hit_tp = (h[i] >= pos["tp"]) if d == 1 else (l[i] <= pos["tp"])
            exit_px, taker_exit = None, True
            if hit_sl:                       # SL first (conservative)
                exit_px, taker_exit = pos["sl"], True
            elif hit_tp:
                exit_px, taker_exit = pos["tp"], (mode == "taker")
            elif sig[i] != Action.HOLD and ((sig[i] == Action.BUY) != (d == 1)):
                exit_px, taker_exit = o[i], True
            if exit_px is not None:
                r = (exit_px - pos["entry"]) * d / pos["risk"]
                # fees in R: fee_rate * price / risk_distance, per side
                ein = (fee_bp if mode == "taker" else 2.0) / 10000.0
                eout = (fee_bp / 10000.0) if taker_exit else (2.0 / 10000.0)
                r -= (ein + eout) * pos["entry"] / pos["risk"]
                Rs.append(r)
                pos = None

        # ---- entries ----
        if pos is None and sig[i] != Action.HOLD and np.isfinite(a[i]) and a[i] > 0:
            d = 1 if sig[i] == Action.BUY else -1
            if mode == "taker":
                entry = o[i]
                filled = True
            else:
                entry = o[i] * (1 - d * offset_bp / 10000.0)
                filled = (l[i] <= entry) if d == 1 else (h[i] >= entry)
            if not filled:
                missed += 1
                continue
            risk = SL_MULT * a[i]
            pos = {"dir": d, "entry": entry, "risk": risk,
                   "sl": entry - d * risk, "tp": entry + d * TP_MULT * a[i]}

    Rs = np.array(Rs)
    if len(Rs) < 30:
        return None
    wins, losses = Rs[Rs > 0], Rs[Rs < 0]
    return dict(n=len(Rs), missed=missed,
                pf=wins.sum() / -losses.sum() if len(losses) and losses.sum() < 0 else 99,
                exp=Rs.mean(), win=(Rs > 0).mean() * 100, total=Rs.sum())


def main():
    fam, p, fn = CONFIG
    print(f"Strategy: {fam} {p} + {fn}   (accounting in R, 1R risked per trade)\n")
    scenarios = [
        ("TAKER  20bp", "taker", 20, 0),
        ("TAKER  40bp", "taker", 40, 0),
        ("MAKER  at-open", "maker", 20, 0),
        ("MAKER  5bp inside", "maker", 20, 5),
        ("MAKER 15bp inside", "maker", 20, 15),
    ]
    for label, symbols in (("UNSEEN ASSETS", UNSEEN), ("SEEN ASSETS", SEEN)):
        print(f"{'='*92}\n{label}\n{'='*92}")
        print(f"  {'scenario':18} {'assets pf>1':>12} {'mean PF':>9} {'mean exp(R)':>12} "
              f"{'mean win%':>10} {'mean trades':>12} {'missed':>8}")
        for slabel, mode, fee, off in scenarios:
            rows = []
            for s in symbols:
                df = fetch(s, "1h", 900)
                r = simulate(df, fam, p, fn, mode, fee, off)
                if r:
                    rows.append(r)
            if not rows:
                continue
            npos = sum(1 for r in rows if r["pf"] > 1.0)
            print(f"  {slabel:18} {npos:>7}/{len(rows):<4} "
                  f"{np.mean([r['pf'] for r in rows]):>9.2f} "
                  f"{np.mean([r['exp'] for r in rows]):>+12.4f} "
                  f"{np.mean([r['win'] for r in rows]):>10.1f} "
                  f"{np.mean([r['n'] for r in rows]):>12.0f} "
                  f"{np.mean([r['missed'] for r in rows]):>8.0f}")
        print()


if __name__ == "__main__":
    main()
