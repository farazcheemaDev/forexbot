"""FULL BREADTH ON CHEAP CONTRACTS — can we get >10%/month without $1,140?

THE INSIGHT THIS TESTS
    backtest/small_book.py measured two things that were being confused:

        RETURN scales with BREADTH.   3 coins +1.9%/mo, 9 coins +10.7%/mo
        CAPITAL scales with the single most EXPENSIVE contract in the book.

    Those are independent. The 9-coin book needs $1,140 only because the nine I
    used happen to include ETH, whose smallest step is 0.01 ETH ~ $25. Nothing in
    the strategy requires ETH. It ranks coins and trades breakouts; it has no
    opinion about which tickers.

    So: build a NINE (or twelve) coin book entirely out of contracts whose minimum
    order is a dollar or two, and we should get full-breadth return at a small
    account's floor. If that works it is the answer to the whole capital problem.

WHY IT MIGHT NOT WORK — stated before running
    1. Cheap contracts are cheap because the coin's unit price is low, which
       correlates with smaller market cap. Smaller caps are more volatile and less
       liquid, so slippage and fee drag are worse than on majors.
    2. small_book.py measured a real penalty for cheapness at low k: at 4 coins,
       cheap-first earned 47pp LESS CAGR than volume-first. If that penalty scales,
       a cheap-9 book could land well below the +10.7%/month a major-9 book gives.
       (At k=9 the penalty vanished, but only because both books WERE the same nine
       coins. This file is the first honest test of the penalty at full breadth.)
    3. Small caps die. Nine small caps is a survivorship trap, and the correction
       for that is the same 3x hindsight divisor used throughout, which may be too
       generous here rather than too harsh.

REGISTERED PREDICTION (2026-09-13, before the run)
    A cheap-9 book lands between +5% and +9%/month honest - BELOW the major-9
    book's +10.7%, because of penalty (2), but far above the cheap-4 book's +3.0%.
    Floor under $150.

    If it comes out ABOVE +10.7%/month I will assume a bug before believing it,
    because that would mean small caps beat majors at equal breadth, which the
    k=4 comparison contradicts.

    A RISK SWEEP is included because the target is >10%/month and 0.13%/unit may
    simply not reach it. Higher risk cuts both ways: it lifts return but deepens
    drawdown, and a deeper drawdown RAISES the capital floor, because the floor
    divides by (1 - drawdown). Those may cancel. The grid shows whether they do.

    python -m backtest.cheap_wide
    python -m backtest.cheap_wide --max-min-order 2.5 --pool 24
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ccxt  # noqa: E402

from backtest.mass_search import fetch  # noqa: E402
from backtest.small_book import (LONG_TRAIL, SHORT_TRAIL, portfolio,  # noqa: E402
                                 stop_fraction)

STABLES = {"USDC", "FDUSD", "TUSD", "DAI", "BUSD", "USDP", "EURI", "AEUR", "USDE"}
HINDSIGHT = 3.0          # cross-checked in small_book.py: 719.8 / 240.1 = 3.00
MIN_BARS = 20000         # ~2.3 years of 1h. Below this a coin cannot see a cycle.


def mexc_min_orders(max_min: float, pool: int):
    """MEXC USDT perps whose minimum order is at most max_min dollars.

    PRE-FILTERED BY THE EXCHANGE'S OWN 24h VOLUME, keeping only the `pool` most
    liquid. 901 contracts pass the min-order test, and downloading 2400 days of
    hourly history for each would take hours to answer a question that only
    concerns the top of the liquidity list - the strategy needs coins deep enough
    to absorb an order, and a contract with a $2 minimum and no volume is useless
    whatever its step size.

    The exchange's 24h figure is a crude liquidity proxy and a POINT-IN-TIME one
    (it reflects today, not 2021). It is used only to shortlist; the real ranking
    below uses median dollar volume measured across the full history.

    Returns {BASE: (min_notional, last_price)}.
    """
    ex = ccxt.mexc({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    ex.load_markets()
    try:
        tick = ex.fetch_tickers()
    except Exception:
        tick = {}
    out = {}
    for sym, m in ex.markets.items():
        if not (m.get("swap") and m.get("active")):
            continue
        if m.get("quote") != "USDT" or m.get("settle") != "USDT":
            continue
        base = m.get("base") or ""
        if base in STABLES or not base:
            continue
        px = None
        t = tick.get(sym) or {}
        for k in ("last", "close", "info"):
            v = t.get(k)
            if isinstance(v, (int, float)) and v > 0:
                px = float(v); break
        if px is None:
            continue
        lim = (m.get("limits") or {})
        amt_min = (lim.get("amount") or {}).get("min")
        cost_min = (lim.get("cost") or {}).get("min")
        csize = m.get("contractSize") or 1.0
        cands = [c for c in (cost_min,
                             (amt_min * csize * px) if amt_min else None) if c]
        if not cands:
            continue
        mn = max(cands)
        if mn > max_min:
            continue
        qv = t.get("quoteVolume")
        try:
            qv = float(qv) if qv is not None else 0.0
        except (TypeError, ValueError):
            qv = 0.0
        out[base] = (float(mn), px, qv)
    # shortlist by the exchange's 24h quote volume, most liquid first
    top = sorted(out.items(), key=lambda kv: -kv[1][2])[:pool]
    return {b: (v[0], v[1]) for b, v in top}


def usable(bases, max_min_map):
    """Keep coins that have enough Binance 1h history to backtest, ranked by
    median dollar volume per bar — the liquidity the strategy needs."""
    rows = []
    for b in bases:
        sym = f"{b}USDT"
        try:
            df = fetch(sym, "1h", 2400)
        except Exception:
            continue
        if df is None or len(df) < MIN_BARS:
            continue
        dv = float((df["close"] * df["volume"]).median())
        rows.append((dv, sym, len(df), max_min_map[b][0], stop_fraction(df)))
    rows.sort(reverse=True)
    return rows


def floor_for(book, dd, risk_pct, mins, sfs):
    worst, worst_c = 0.0, None
    for c in book:
        need = mins[c] * sfs[c] / (risk_pct / 100.0)
        if need > worst:
            worst, worst_c = need, c
    if dd >= 99.0 or worst == 0:
        return float("nan"), worst_c
    return worst / (1 - dd / 100.0), worst_c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-min-order", type=float, default=2.5,
                    help="only contracts whose minimum order is at most this")
    ap.add_argument("--pool", type=int, default=20,
                    help="how many of the most liquid qualifying coins to consider")
    ap.add_argument("--slots", type=int, default=8)
    args = ap.parse_args()

    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: cheap-9 lands +5% to +9%/month honest, floor")
    print("under $150. Above +10.7%/month I look for a bug first.\n")

    print(f"querying MEXC for USDT perps with minimum order <= "
          f"${args.max_min_order:.2f} ...", flush=True)
    mins = mexc_min_orders(args.max_min_order, args.pool * 3)
    print(f"  shortlisted {len(mins)} most liquid of them "
          f"(901 pass the min-order test; downloading history for all would take "
          f"hours to answer a question about the top of the list)", flush=True)
    if not mins:
        return
    rows = usable(list(mins), mins)
    print(f"  {len(rows)} of them have >= {MIN_BARS:,} bars of Binance 1h history\n")
    rows = rows[:args.pool]
    print("=" * 104)
    print(f"CANDIDATE POOL — cheap contracts with real history, ranked by "
          f"liquidity")
    print("=" * 104)
    print(f"{'#':>3} {'coin':<10} {'median $vol/bar':>16} {'bars':>8} "
          f"{'min order $':>12} {'median stop %':>14}")
    for i, (dv, sym, n, mn, sf) in enumerate(rows, 1):
        print(f"{i:>3} {sym.replace('USDT',''):<10} {dv:>16,.0f} {n:>8,} "
              f"{mn:>12,.3f} {sf*100:>13.2f}%")

    order = [r[1] for r in rows]
    mn_map = {r[1]: r[3] for r in rows}
    sf_map = {r[1]: r[4] for r in rows}

    print("\n" + "=" * 116)
    print("GRID — book size x risk per unit.  HONEST = raw / "
          f"{HINDSIGHT:.1f} hindsight premium.  Target is HONEST > +10%/month")
    print("=" * 116)
    print(f"{'k':>3} {'risk%':>6} {'longs':>6} {'shorts':>7} {'decl':>6} "
          f"{'raw /mo':>9} {'HONEST /mo':>11} {'DD':>7} {'floor $':>9} "
          f"{'binding':>9}  verdict")
    hits = []
    for k in (6, 9, 12, len(order)):
        if k > len(order):
            continue
        book = order[:k]
        for risk in (0.13, 0.20, 0.30):
            d = portfolio(book, args.slots, risk)
            if not d:
                print(f"{k:>3} {risk:>6.2f} (no result)")
                continue
            hc = d["cagr"] / HINDSIGHT if d["cagr"] > -100 else -100.0
            hpm = ((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0
            fl, wc = floor_for(book, d["dd"], risk, mn_map, sf_map)
            ok = (hpm > 10.0) and not d["ruined"] and np.isfinite(fl)
            tag = "** CLEARS 10% **" if ok else ("RUIN" if d["ruined"] else "")
            if ok:
                hits.append((fl, k, risk, hpm, d, wc))
            print(f"{k:>3} {risk:>6.2f} {d['L']:>6} {d['S']:>7} "
                  f"{d['declined']:>6} {d['pm']:>+8.2f}% {hpm:>+10.2f}% "
                  f"{d['dd']:>6.1f}% {fl:>9,.0f} "
                  f"{(wc or '?').replace('USDT',''):>9}  {tag}", flush=True)
        print()

    print("=" * 116)
    if not hits:
        print("NOTHING CLEARS +10%/MONTH on a cheap-contract book at any risk "
              "level tested.")
        print("That is the finding. Raising risk lifts return and deepens "
              "drawdown, and a")
        print("deeper drawdown raises the capital floor - the two cancel, so "
              "there is no")
        print("cheap shortcut to the major-coin book's return.")
        return
    # --------------------------------------------------------------------
    # THE SLOT CAP IS BINDING HARD and it is the one lever not yet pulled.
    # At 12 coins / 8 slots the grid above DECLINES more trades than it takes
    # (5,394 declined against 2,782 longs). Those declines are not a cost of the
    # strategy, they are a cost of an arbitrary cap: the 8 was chosen when the book
    # had 9 coins, and the earlier breadth work found the peak sits where
    # COINS ~= SLOTS + 1.
    #
    # Crucially, raising slots does NOT raise the capital floor. The floor is set
    # by ONE coin's minimum order; more concurrent positions only need more margin,
    # and at 10x with these position sizes margin is not the binding constraint.
    # So this is the only lever tested here that might buy return without buying
    # drawdown.
    print("SLOT SWEEP — the cap was set for a 9-coin book and is now binding")
    print("=" * 116)
    print(f"{'k':>3} {'slots':>6} {'risk%':>6} {'taken':>7} {'decl':>6} "
          f"{'raw /mo':>9} {'HONEST /mo':>11} {'DD':>7} {'floor $':>9}  verdict")
    for k in (12, min(20, len(order))):
        if k > len(order):
            continue
        book = order[:k]
        for slots in (8, 12, 16, 20):
            if slots > k:
                continue
            for risk in (0.13, 0.20):
                d = portfolio(book, slots, risk)
                if not d:
                    continue
                hc = d["cagr"] / HINDSIGHT if d["cagr"] > -100 else -100.0
                hpm = ((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0
                fl, wc = floor_for(book, d["dd"], risk, mn_map, sf_map)
                ok = hpm > 10.0 and not d["ruined"] and np.isfinite(fl)
                if ok:
                    hits.append((fl, k, risk, hpm, d, wc))
                tag = "** CLEARS 10% **" if ok else ""
                print(f"{k:>3} {slots:>6} {risk:>6.2f} {d['L']+d['S']:>7} "
                      f"{d['declined']:>6} {d['pm']:>+8.2f}% {hpm:>+10.2f}% "
                      f"{d['dd']:>6.1f}% {fl:>9,.0f}  {tag}", flush=True)
        print()

    print("=" * 116)
    hits.sort()
    print("CLEARS +10%/MONTH, CHEAPEST CAPITAL FIRST")
    print("=" * 116)
    for fl, k, risk, hpm, d, wc in hits:
        print(f"  {k} coins at {risk:.2f}%/unit -> {hpm:+.2f}%/month honest, "
              f"DD {d['dd']:.1f}%, needs ${fl:,.0f} "
              f"(binding: {(wc or '?').replace('USDT','')})")
    best = hits[0]
    print(f"\nCHEAPEST ROUTE TO >10%/MONTH: ${best[0]:,.0f} "
          f"on {best[1]} coins at {best[2]:.2f}%/unit")
    print("\nBefore acting: the minimum orders are MEXC metadata, the 3x divisor "
          "is a\nstraight-line correction anchored at one book size, and a "
          f"{best[4]['dd']:.0f}% drawdown on\n${best[0]:,.0f} leaves "
          f"${best[0]*(1-best[4]['dd']/100):,.0f}. Verify with one real demo "
          "order.")


if __name__ == "__main__":
    main()
