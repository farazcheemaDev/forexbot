"""PYRAMIDING — adding to winners. The position-management lever never tested here.

THE BLIND SPOT
    Every result that moved today came from position management, not signals:
        profit cap removed      11 trend families: dead -> +0.27R
        position cap enforced   new listings: +0.122R -> -28%/yr
        trail width 12x -> 20x  +210.8% -> +324.5%/yr
        stop width 2x -> 6x     drawdown 83% -> 39%
    Nineteen indicator families, by contrast, all found the same thing.

    But the engine has always taken ONE unit per signal and trailed it out. It has
    never ADDED to a position that is working. That is how trend systems actually
    produce outsized returns - the Turtles, Dunn, Chesapeake all pyramided - and it
    is the one construction choice I never questioned.

WHY IT SHOULD MATTER MORE THAN ANY INDICATOR
    This strategy's return lives entirely in its tail: 13% win rate, max single
    trade +116R to +183R. If the rare monster trade is carried at 3 units instead
    of 1, the tail triples while the 87% of trades that lose still lose one unit,
    because additions only happen AFTER price has moved in favour.

    That is an asymmetry the exits cannot reach. A trail decides when to leave; a
    pyramid decides how much is on when you are right.

HOW IT IS IMPLEMENTED, AND THE HONEST RISK
    * unit 1 enters on the signal, stop at entry - sl_mult x ATR
    * each further unit is added when price has advanced `add_every` R from the
      ORIGINAL entry, up to `max_units`
    * every unit shares ONE trailing stop, ratcheted to the highest price reached
    * R is reported per UNIT of initial risk, so numbers stay comparable with every
      other result in this project

    THE RISK THIS CREATES, STATED UP FRONT: between an addition and the trail
    catching up, total open risk is larger than one unit. If price reverses hard
    right after a 3rd add, the loss is bigger than a normal stop-out. Pyramiding
    raises the variance of the tail in BOTH directions - it is not free leverage.
    The max_loss column below reports the worst single outcome so that shows up.

    python -m backtest.pyramid
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import describe  # noqa: E402
from backtest.mass_search import fetch, gen_signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
         "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
_D: dict = {}


def load(c, days=2400):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", days)
        except Exception:
            _D[c] = None
    return _D[c]


def run_pyramid(df: pd.DataFrame, sig: pd.Series, *, sl_mult: float = 2.0,
                trail: float = 20.0, max_units: int = 1,
                add_every: float = 2.0, fee_bp: float = FEE_BP,
                atr_period: int = 14):
    """R per closed POSITION (all units combined), in units of the initial risk.

    Causality is identical to run_uncapped: entry at open[i] sized from atr[i-1],
    stop checked against the bar's own extreme before the trail advances.
    """
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    a = atr_ind(df, atr_period).to_numpy(float)
    n = len(df)
    fee = fee_bp / 1e4

    Rs, idx, units_used, held = [], [], [], []
    pos = None
    for i in range(1, n):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            risk = sl_mult * a[i - 1]
            pos = dict(risk=risk, stop=o[i] - risk, best=o[i], bar=i,
                       entries=[o[i]], next_add=1)
        if pos is None:
            continue
        risk = pos["risk"]
        hit = lo[i] <= pos["stop"]
        if hit:
            px = pos["stop"]
            # every unit exits at the shared trailing stop
            gross = sum((px - e) for e in pos["entries"]) / risk
            cost = sum(fee * e for e in pos["entries"]) / risk
            Rs.append(gross - cost); idx.append(i)
            units_used.append(len(pos["entries"]))
            held.append(i - pos["bar"])
            pos = None
            continue
        # ADD a unit once price has advanced add_every R from the FIRST entry
        if len(pos["entries"]) < max_units:
            gain_r = (h[i] - pos["entries"][0]) / risk
            if gain_r >= pos["next_add"] * add_every:
                # fill at the trigger level, not the bar high - the high is the
                # bar's best price and assuming it would be look-ahead
                pos["entries"].append(pos["entries"][0]
                                      + pos["next_add"] * add_every * risk)
                pos["next_add"] += 1
        pos["best"] = max(pos["best"], h[i])
        cand = pos["best"] - trail * a[i - 1]
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None:                       # close what is still open at the end
        px = c[n - 1]
        gross = sum((px - e) for e in pos["entries"]) / pos["risk"]
        cost = sum(fee * e for e in pos["entries"]) / pos["risk"]
        Rs.append(gross - cost); idx.append(n - 1)
        units_used.append(len(pos["entries"]))
        held.append(n - 1 - pos["bar"])
    # bars HELD is returned because a portfolio pass needs the entry time to
    # enforce a concurrent-position cap. Returning zeros there would make every
    # position occupy no time, so the cap would silently never bind - the exact
    # error that made new-listing momentum look profitable.
    return (np.asarray(Rs), np.asarray(idx, dtype=int),
            np.asarray(units_used, dtype=int), np.asarray(held, dtype=int))


def pool(coins, max_units, add_every, trail, sl_mult, risk):
    Rs, Ts, Us = [], [], []
    for c in coins:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        sig = gen_signals(df, "bb_break", (30, 1.5))
        if sig is None:
            continue
        sig = sig.where(sig != Action.SELL, Action.HOLD)     # long only
        R, idx, u, _h = run_pyramid(df, sig, sl_mult=sl_mult, trail=trail,
                                    max_units=max_units, add_every=add_every)
        if len(R):
            Rs.append(R); Ts.append(df["time"].iloc[idx]); Us.append(u)
    if not Rs:
        return None
    o = np.argsort(np.concatenate([t.values for t in Ts]))
    R = np.concatenate(Rs)[o]
    U = np.concatenate(Us)[o]
    T = pd.Series(np.concatenate([t.values for t in Ts])[o])
    d = describe(R, T, risk)
    if d:
        d["avg_units"] = float(U.mean())
        d["max_loss"] = float(R.min())
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risk", type=float, default=0.5)
    args = ap.parse_args()

    print("PYRAMIDING — adding to winners. 9 coins, 1h, long only, "
          f"risk {args.risk}%/unit, fee {FEE_BP}bp")
    print("  unit 1 on the signal; further units every `add` R of advance; one "
          "shared trailing stop")
    print("  max_units=1 is the CONTROL and reproduces the current engine\n")
    print("=" * 116)
    print(f"{'units':>6} {'add@':>6} {'trail':>6} {'n':>6} {'avgU':>5} {'WIN%':>6} "
          f"{'meanR':>8} {'maxR':>8} {'worst':>7} {'CAGR':>9} {'DD':>7} "
          f"{'MAR':>6} {'/month':>8}")
    rows = []
    for mu, ae in ((1, 0.0), (2, 2.0), (3, 2.0), (4, 2.0),
                   (3, 1.0), (3, 4.0), (5, 2.0)):
        for tr in (12.0, 20.0):
            d = pool(COINS, mu, ae if ae else 2.0, tr, 2.0, args.risk)
            if not d:
                continue
            pm = ((1 + d["cagr"] / 100) ** (1 / 12) - 1) * 100 \
                if d["cagr"] > -100 else -100
            ru = " RUIN" if d["ruined"] else ""
            rows.append((d["cagr"], mu, ae, tr, d, pm))
            print(f"{mu:>6} {ae:>6.1f} {tr:>5.0f}x {d['n']:>6} "
                  f"{d['avg_units']:>5.2f} {d['win']:>5.1f}% {d['mean']:>+8.3f} "
                  f"{d['mx']:>8.1f} {d['max_loss']:>+7.2f} {d['cagr']:>+8.1f}% "
                  f"{d['dd']:>6.1f}% {d['mar']:>+6.2f} {pm:>+7.2f}%{ru}",
                  flush=True)
    if not rows:
        return
    rows.sort(reverse=True)
    cagr, mu, ae, tr, d, pm = rows[0]
    base = [r for r in rows if r[1] == 1]
    print(f"\nbest: {mu} units, add every {ae:.0f}R, trail {tr:.0f}x -> "
          f"{cagr:+.1f}%/yr ({pm:+.2f}%/month), DD {d['dd']:.1f}%")
    if base:
        b = max(base)
        print(f"control (1 unit): {b[0]:+.1f}%/yr ({b[5]:+.2f}%/month), "
              f"DD {b[4]['dd']:.1f}%")
        print(f"pyramiding is worth {cagr/b[0]:.2f}x on CAGR" if b[0] > 0 else "")
    print("\nWatch 'worst': pyramiding enlarges the tail in BOTH directions. If the "
          "worst single\nposition is much below -1R, the additions are being caught "
          "by reversals.")
    print("These are FIXED-universe numbers. Divide CAGR by ~3.05 for the "
          "point-in-time\nequivalent (the hindsight ratio measured twice today).")


if __name__ == "__main__":
    main()
