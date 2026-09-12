"""CROSS-ASSET GATE on the VSA absorption filter.

WHY THIS GATE AND NOT ANOTHER P-VALUE
-------------------------------------
VSA passed MCPT at p=0.0099 (0/100 permutations). But gold also passed MCPT at
p=0.0050 and then lost 14.9%/yr on unseen data, and this gate - not MCPT - is what
killed the NASDAQ level-fade (5 supporting signals, failed on ES/RTY/YM/GC) and
meta-labeling (p=0.049 pooled, then 2 of 4 unseen coins got WORSE). It is the most
discriminating test we have, so it decides.

THREE TESTS, WEAKEST TO STRONGEST
---------------------------------
  1. LEAVE-COINS-OUT. The rule `dev < -0.5` was picked from a 6-rule sweep pooled
     over all 9 coins, so all 9 contributed to the choice. Here the rule is
     re-selected using only 5 coins, then applied blind to the other 4.

  2. FRESH CRYPTO. Eight liquid coins this project has NEVER loaded, with the rule
     FIXED at dev < -0.5. No selection of any kind on these.

  3. NON-CRYPTO. Gold (PAXG) and Nasdaq futures (NQ). If absorption is a real
     microstructure effect it should not care what is being traded; if it only
     exists on the nine coins we happened to pick, it was noise.

A pass requires the filter to BEAT UNFILTERED on most instruments - not merely to
be positive, since the underlying momentum strategy is already near zero.

    python -m backtest.vsa_crossasset
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.holdout_sweep import USED_DAYS, signals_for  # noqa: E402
from backtest.mass_search import FILTERS, fetch  # noqa: E402
from backtest.rtest import run_r  # noqa: E402
from backtest.vsa import FEE_BP, SL, TP, vsa_indicator  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ORIGINAL = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
            "AVAXUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]
SELECT_ON = ORIGINAL[:5]
TEST_ON = ORIGINAL[5:]
# never loaded by this project before today
FRESH = ["LTCUSDT", "DOTUSDT", "ATOMUSDT", "FILUSDT",
         "NEARUSDT", "ETCUSDT", "UNIUSDT", "AAVEUSDT"]

RULES = {
    "unfiltered": None,
    "dev<-0.5": lambda s: s < -0.5,
    "dev<-1.0": lambda s: s < -1.0,
    "dev>0.5": lambda s: s > 0.5,
    "dev>1.0": lambda s: s > 1.0,
    "|dev|<0.25": lambda s: s.abs() < 0.25,
}
PRIMARY = ("bb_break", (30, 1.5))


def run_rule(df: pd.DataFrame, rule) -> tuple[float, int]:
    sig = FILTERS["none"](df, signals_for(df, *PRIMARY))
    if rule is not None:
        sig = sig.where(rule(vsa_indicator(df).shift(1)), Action.HOLD)
    R, _ = run_r(df, sig, SL, TP, FEE_BP)
    if len(R) < 30:
        return float("nan"), len(R)
    return float(R.mean()), len(R)


def segments(sym: str, tf: str = "1h", days: int = 2400):
    try:
        d = fetch(sym, tf, days)
    except Exception:
        return None
    cut = d.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
    hold = d[d.time < cut].reset_index(drop=True)
    used = d[d.time >= cut].reset_index(drop=True)
    if len(hold) < 3000:
        return None
    return hold, used


def main():
    print("CROSS-ASSET GATE on VSA absorption filter (dev < -0.5)")
    print(f"primary signal {PRIMARY[0]}{PRIMARY[1]}, cost {FEE_BP}bp\n")

    # ---------- 1. leave-coins-out ----------
    print("=" * 78)
    print(f"1. LEAVE-COINS-OUT — pick the rule on {SELECT_ON}")
    print(f"   then apply it BLIND to {TEST_ON}")
    print("=" * 78)
    sel = {}
    for label, rule in RULES.items():
        tot_n, tot_s = 0, 0.0
        for a in SELECT_ON:
            segs = segments(a)
            if not segs:
                continue
            m, n = run_rule(segs[0], rule)
            if np.isfinite(m):
                tot_n += n; tot_s += m * n
        if tot_n:
            sel[label] = tot_s / tot_n
    best = max((k for k in sel if k != "unfiltered"), key=lambda k: sel[k])
    print(f"  rule chosen on the 5 selection coins: {best}  "
          f"({sel[best]:+.4f}R, unfiltered {sel['unfiltered']:+.4f}R)")
    print(f"\n  {'coin':10} {'window':8} {'unfilt':>9} {'filtered':>9} {'better?':>8}")
    wins = tot = 0
    for a in TEST_ON:
        segs = segments(a)
        if not segs:
            continue
        for wi, wn in ((0, "holdout"), (1, "dev")):
            u, _ = run_rule(segs[wi], None)
            f, nf = run_rule(segs[wi], RULES[best])
            if not (np.isfinite(u) and np.isfinite(f)):
                continue
            tot += 1; wins += f > u
            print(f"  {a:10} {wn:8} {u:>+9.4f} {f:>+9.4f} "
                  f"{'YES' if f > u else 'no':>8}")
    print(f"\n  filter beat unfiltered on {wins}/{tot} coin-windows")

    # ---------- 2. fresh crypto ----------
    print("\n" + "=" * 78)
    print("2. FRESH CRYPTO — 8 coins never loaded, rule FIXED at dev<-0.5")
    print("=" * 78)
    print(f"  {'coin':10} {'window':8} {'trades':>7} {'unfilt':>9} "
          f"{'filtered':>9} {'better?':>8}")
    w2 = t2 = 0
    pooled = {"u": [], "f": []}
    for a in FRESH:
        segs = segments(a)
        if not segs:
            print(f"  {a:10} unavailable / too little history")
            continue
        for wi, wn in ((0, "holdout"), (1, "dev")):
            u, nu = run_rule(segs[wi], None)
            f, nf = run_rule(segs[wi], RULES["dev<-0.5"])
            if not (np.isfinite(u) and np.isfinite(f)):
                continue
            t2 += 1; w2 += f > u
            pooled["u"].append((u, nu)); pooled["f"].append((f, nf))
            print(f"  {a:10} {wn:8} {nf:>7} {u:>+9.4f} {f:>+9.4f} "
                  f"{'YES' if f > u else 'no':>8}")
    if t2:
        pu = sum(m * n for m, n in pooled["u"]) / sum(n for _, n in pooled["u"])
        pf = sum(m * n for m, n in pooled["f"]) / sum(n for _, n in pooled["f"])
        print(f"\n  pooled over fresh coins: unfiltered {pu:+.4f}R  "
              f"filtered {pf:+.4f}R")
        print(f"  filter beat unfiltered on {w2}/{t2} coin-windows")

    # ---------- 3. non-crypto ----------
    print("\n" + "=" * 78)
    print("3. NON-CRYPTO — does absorption care what is being traded?")
    print("=" * 78)
    print(f"  {'market':12} {'window':8} {'trades':>7} {'unfilt':>9} "
          f"{'filtered':>9} {'better?':>8}")
    w3 = t3 = 0
    for sym, label in (("PAXGUSDT", "gold (PAXG)"),):
        segs = segments(sym)
        if not segs:
            print(f"  {label:12} unavailable")
            continue
        for wi, wn in ((0, "holdout"), (1, "dev")):
            u, nu = run_rule(segs[wi], None)
            f, nf = run_rule(segs[wi], RULES["dev<-0.5"])
            if not (np.isfinite(u) and np.isfinite(f)):
                continue
            t3 += 1; w3 += f > u
            print(f"  {label:12} {wn:8} {nf:>7} {u:>+9.4f} {f:>+9.4f} "
                  f"{'YES' if f > u else 'no':>8}")
    # Nasdaq futures, from the level-fade work (1h, 730d, no volume issues)
    try:
        from backtest.nasdaq_levelfade import fetch_nq
        nq = fetch_nq("1h", "730d")
        mid = len(nq) // 2
        for seg, wn in ((nq.iloc[:mid].reset_index(drop=True), "1st half"),
                        (nq.iloc[mid:].reset_index(drop=True), "2nd half")):
            u, nu = run_rule(seg, None)
            f, nf = run_rule(seg, RULES["dev<-0.5"])
            if np.isfinite(u) and np.isfinite(f):
                t3 += 1; w3 += f > u
                print(f"  {'NASDAQ (NQ)':12} {wn:8} {nf:>7} {u:>+9.4f} "
                      f"{f:>+9.4f} {'YES' if f > u else 'no':>8}")
    except Exception as e:
        print(f"  NASDAQ unavailable: {type(e).__name__}")
    print(f"\n  filter beat unfiltered on {w3}/{t3} non-crypto windows")

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    print(f"  leave-coins-out : {wins}/{tot}")
    print(f"  fresh crypto    : {w2}/{t2}")
    print(f"  non-crypto      : {w3}/{t3}")
    allw, allt = wins + w2 + w3, tot + t2 + t3
    print(f"  TOTAL           : {allw}/{allt} = {allw/max(allt,1)*100:.0f}%")
    print("  ->", "GENERALISES — the first thing in this project to clear every gate"
          if allt and allw / allt >= 0.7 else
          "does NOT generalise — same fate as level_fade and meta-labeling")


if __name__ == "__main__":
    main()
