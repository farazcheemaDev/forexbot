"""WIDE UNIVERSE TEST — and a genuine out-of-sample result available in HOURS.

THE IDEA THAT MAKES THIS FAST
------------------------------
Time is not the only out-of-sample axis. The 2025-04..2026-09 time holdout is
spent (2 looks, contamination ledger). But every choice made so far - the lookback,
the ranking rule, the winner of a 14-sleeve search - was made using ONLY the 28
coins in xs_momentum.UNIVERSE. Roughly 80 other liquid perps played no part in any
decision. They are virgin data, and they exist right now.

So:
    VIRGIN coins x any period          = fresh out-of-sample
    USED coins  x dev period           = contaminated (fitted here)
    USED coins  x 2025-04.. holdout    = spent

Running the FROZEN parameters on the virgin coins is a real test, today. It is the
same logic as the cross-instrument gate that killed the NASDAQ level-fade.

WHAT THIS SETTLES THAT THE FORWARD TEST WOULD HAVE TAKEN MONTHS TO SETTLE
    xs_combine.py searched 14 sleeves on the USED coins and momsh_168h (rank by
    risk-adjusted move) came out best at Sharpe 1.64 vs 0.95 for plain mom_168h.
    A best-of-14 result on the data it was searched on is a hypothesis, not a
    measurement. The virgin coins can judge it - they were never in that search.

    If momsh still beats mom on coins it was never selected on, the upgrade is
    real. If the ranking scrambles, it was search noise and only mom_168h's
    permutation result stands.

WHAT THIS DOES **NOT** SETTLE
    Nothing about execution. Slippage, real fills, exchange behaviour and whether
    the code works against a live venue are only answerable forward. This replaces
    the forward test's role as an EDGE test, not as an IMPLEMENTATION test.

THREE HONEST CAVEATS, STATED BEFORE ANY NUMBER
    1. SURVIVORSHIP, and it is WORSE here than for the 21 majors. These are coins
       trading TODAY. Coins that were delisted or went to zero are absent, and
       small alts die far more often than BTC. That biases the long leg upward and
       the short leg downward by an unknown amount. It cannot be corrected without
       delisted-symbol history, which Binance's public API does not serve.
    2. LIQUIDITY. Rank ~120 does ~$12M/day. Fine for $50-500, but the spread is
       much wider than BTC's, so 6bp/side is optimistic for the tail. Every table
       is therefore also run at 12bp.
    3. SPOT prices, perp trading. All prior results use spot klines so this keeps
       them comparable. Spot and perp track within a few bp, which a ranking
       strategy is insensitive to, but it is not identical.
    Funding is NOT charged: the archive reaches back only ~670 days and does not
    cover most of these coins. Measured funding on a neutral book was ~+0.1%/yr,
    so this is immaterial - but it IS a zero standing in for a small real cost.

    python -m backtest.xs_wide
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import DATA, fetch  # noqa: E402
from backtest.xs_momentum import UNIVERSE, simulate  # noqa: E402

SYMS = DATA / "wide_universe.json"

# FROZEN. Chosen on the USED coins before any virgin coin was looked at.
SLEEVES = {
    "mom_168h":   dict(lb=168, hold=24, invvol=False, rank_by="ret"),
    "momsh_168h": dict(lb=168, hold=24, invvol=False, rank_by="sharpe"),
    "mom_720h":   dict(lb=720, hold=24, invvol=False, rank_by="ret"),
}
KS = (5, 10, 20)
FEES = (6.0, 12.0)


MIN_COVERAGE = 0.95


def build(symbols: list[str], days: int, min_bars: int, verbose: bool = False):
    """Panels, rejecting GAPPY series but keeping SHORT ones.

    A bar count alone cannot tell these apart, and they are not equivalent:

      short history  (ENA listed 2024-04, 21,434 of ~21,470 possible bars)
          fine. The coin simply did not exist earlier; weights() already skips
          a coin whose momentum is NaN, so it joins the ranking when it appears.

      holes mid-series (LITUSDT spans 2022-08 but holds 22,096 of ~36,010 bars,
          39% missing - halts or a spot delist-and-relist)
          NOT fine. Missing hours mean a stale price feeds the ranking, and a
          coin that looks unchanged through a gap reads as neither a winner nor
          a loser when in truth it is unmeasured.

    So coverage is measured against each coin's OWN observed span, which isolates
    gaps from late listing.
    """
    op, cl, dropped = {}, {}, []
    for s in symbols:
        try:
            d = fetch(s, "1h", days)
        except Exception:
            continue
        d = d.drop_duplicates("time").sort_values("time").set_index("time")
        n = int(d["close"].notna().sum())
        if n < min_bars:
            continue
        span_h = (d.index[-1] - d.index[0]).total_seconds() / 3600 + 1
        cov = n / span_h if span_h > 0 else 0.0
        if cov < MIN_COVERAGE:
            dropped.append((s, n, cov))
            continue
        op[s] = d["open"].astype(float)
        cl[s] = d["close"].astype(float)
    if verbose and dropped:
        print(f"  dropped {len(dropped)} gappy series (<{MIN_COVERAGE:.0%} of "
              f"their own span):")
        for s, n, cov in dropped:
            print(f"    {s:14} {n:>7,} bars, {cov:.0%} coverage")
    O = pd.DataFrame(op).sort_index()
    C = pd.DataFrame(cl).sort_index()
    return O, C


def run(O, C, cfg, k, fee):
    Z = pd.DataFrame(0.0, index=O.index, columns=O.columns)
    return simulate(O, C, Z, er_min=0.0, k=k, fee_bp=fee,
                    charge_funding=False, **cfg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1500)
    ap.add_argument("--min-bars", type=int, default=9000)
    args = ap.parse_args()

    if not SYMS.exists():
        raise SystemExit("run: python -m backtest.wide_fetch  first")
    wide = json.load(open(SYMS))
    used = [s for s in wide if s in UNIVERSE]
    virgin = [s for s in wide if s not in UNIVERSE]
    print(f"WIDE UNIVERSE TEST   {len(wide)} coins with >={args.min_bars} bars")
    print(f"  USED   {len(used):>3} coins — every parameter was chosen on these, "
          f"so they can only confirm, never test")
    print(f"  VIRGIN {len(virgin):>3} coins — played NO part in any choice. "
          f"This is the real test.")
    print(f"  frozen sleeves: {', '.join(SLEEVES)} | k in {KS} | fees {FEES}bp")
    print(f"  funding not charged; survivorship NOT corrected (see docstring)\n",
          flush=True)

    panels = {}
    for tag, syms in (("VIRGIN", virgin), ("USED", used), ("ALL", wide)):
        O, C = build(syms, args.days, args.min_bars, verbose=(tag == "ALL"))
        panels[tag] = (O, C)
        print(f"  {tag:<7} panel {C.shape[1]:>3} coins x {len(C):,} bars  "
              f"{C.index[0]:%Y-%m-%d}..{C.index[-1]:%Y-%m-%d}", flush=True)
    print()

    # ---- the headline table -------------------------------------------------
    print("=" * 104)
    print("FROZEN PARAMETERS ON VIRGIN COINS  (vs the coins they were chosen on)")
    print("=" * 104)
    print(f"{'sleeve':<12} {'k':>3} {'fee':>5} | "
          f"{'VIRGIN  CAGR   DD   Sharpe     t':>36} | "
          f"{'USED    CAGR   Sharpe':>24} | {'ALL   CAGR   Sharpe':>22}")
    res = {}
    for name, cfg in SLEEVES.items():
        for k in KS:
            for fee in FEES:
                row = {}
                for tag in ("VIRGIN", "USED", "ALL"):
                    O, C = panels[tag]
                    if C.shape[1] < 2 * k:
                        row[tag] = None
                        continue
                    row[tag] = run(O, C, cfg, k, fee)
                res[(name, k, fee)] = row
                v, u, a = row["VIRGIN"], row["USED"], row["ALL"]
                if not v:
                    continue
                us = f"{u['cagr']:>+8.1f}% {u['sharpe']:>+8.2f}" if u else " " * 17
                al = f"{a['cagr']:>+8.1f}% {a['sharpe']:>+8.2f}" if a else " " * 17
                print(f"{name:<12} {k:>3} {fee:>4.0f}b | "
                      f"{v['cagr']:>+8.1f}% {v['dd']:>5.1f}% {v['sharpe']:>+8.2f} "
                      f"{v['t']:>+7.2f} | {us} | {al}", flush=True)

    # ---- does the search winner survive on coins it never saw? --------------
    print("\n" + "=" * 104)
    print("THE SEARCH-NOISE QUESTION: momsh_168h beat mom_168h 1.64 vs 0.95 on the "
          "USED coins.")
    print("Does it still beat it on coins that were never in that search?")
    print("=" * 104)
    print(f"{'k':>3} {'fee':>5} | {'mom_168h':>18} {'momsh_168h':>18} "
          f"{'verdict':>28}")
    holds = 0, 0
    nh = nt = 0
    for k in KS:
        for fee in FEES:
            a = res.get(("mom_168h", k, fee), {}).get("VIRGIN")
            b = res.get(("momsh_168h", k, fee), {}).get("VIRGIN")
            if not (a and b):
                continue
            nt += 1
            ok = b["sharpe"] > a["sharpe"]
            nh += ok
            print(f"{k:>3} {fee:>4.0f}b | {a['sharpe']:>+18.2f} "
                  f"{b['sharpe']:>+18.2f} "
                  f"{('momsh still ahead' if ok else 'REVERSED'):>28}")
    if nt:
        print(f"\nmomsh ahead in {nh}/{nt} virgin cells.")
        print("  6/6 -> the ranking upgrade is real, not search noise")
        print("  ~3/6 -> coin-flip, i.e. the 1.64 was a best-of-14 artifact")

    # ---- does a wider universe actually improve quality? --------------------
    print("\n" + "=" * 104)
    print("DOES MORE COINS HELP?  same sleeve, same fee, USED (~28) vs ALL (~100)")
    print("=" * 104)
    print(f"{'sleeve':<12} {'k':>3} {'fee':>5} | {'USED Sharpe':>12} "
          f"{'ALL Sharpe':>11} {'gain':>7} | {'USED DD':>8} {'ALL DD':>8}")
    for name in SLEEVES:
        for k in KS:
            for fee in FEES:
                r = res.get((name, k, fee), {})
                u, a = r.get("USED"), r.get("ALL")
                if not (u and a):
                    continue
                g = a["sharpe"] / u["sharpe"] if u["sharpe"] > 0.05 else float("nan")
                print(f"{name:<12} {k:>3} {fee:>4.0f}b | {u['sharpe']:>+12.2f} "
                      f"{a['sharpe']:>+11.2f} {g:>+7.2f}x | {u['dd']:>7.1f}% "
                      f"{a['dd']:>7.1f}%")

    # ---- best virgin cell, stated with its search size ---------------------
    cells = [(r["VIRGIN"]["sharpe"], n, k, f) for (n, k, f), r in res.items()
             if r.get("VIRGIN")]
    if cells:
        cells.sort(reverse=True)
        s, n, k, f = cells[0]
        v = res[(n, k, f)]["VIRGIN"]
        print(f"\nbest VIRGIN cell: {n} k={k} fee={f:.0f}bp -> "
              f"{v['cagr']:+.1f}%/yr, Sharpe {s:+.2f}, t {v['t']:+.2f}, "
              f"DD {v['dd']:.1f}%, beta {v['beta']:+.2f}")
        print(f"  chosen from {len(cells)} cells — a best-of-{len(cells)} figure, "
              f"so read the WHOLE table, not this line")
        pos = sum(1 for c in cells if c[0] > 0)
        print(f"  positive Sharpe in {pos}/{len(cells)} virgin cells "
              f"({pos/len(cells)*100:.0f}%) — this is the number that matters")


if __name__ == "__main__":
    main()
