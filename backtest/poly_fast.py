"""SETTLING THE POLYMARKET EDGE FROM HISTORY — by testing the artifact directly.

THE SITUATION
    backtest/polymarket_bias.py found markets priced 0.50-0.65 resolving YES 80-86%
    of the time - a +25% edge that survived event clustering, a time split and two
    independent samples. Three measurement artifacts were found and fixed inside that
    same test, so a fourth is the default assumption, and one was named but not ruled
    out:

        REQUIRING N DAYS OF PRICE HISTORY MAY SELECT TOWARD YES.
        A market heading for NO often stops trading early - the candidate withdraws,
        the event fizzles - while one heading for YES trades until it resolves. If so,
        "has 30+ days of history" is partly a filter for outcomes that happened.

    The forward test settles it cleanly but needs 120 resolutions in one band, which
    is weeks away. This file asks whether history can settle it sooner.

THE TEST THAT DECIDES IT
    If the effect is caused by the history-length filter, it MUST vary with market
    lifetime: strong where the filter bites (long-lived markets) and absent where it
    barely applies (short-lived ones).

        stratify by how long the market actually traded
        measure the 0.50-0.65 gap inside each stratum

    A gap that is FLAT across lifetimes cannot be produced by a lifetime filter. A gap
    that grows with lifetime is the artifact, and the edge is dead.

    Second, weaker filter: at a ONE DAY horizon a market needs only one day of history
    to qualify, so nearly everything is included and the selection pressure is close to
    nil. If the effect survives at 1 day on a large sample, that is hard to explain by
    selection.

    Third: three DIFFERENT sample orderings. Ordering by volume selects markets where
    something dramatic happened; by endDate selects long-dated ones; by start date
    selects neither. Agreement across all three is worth more than any single sample.

REGISTERED PREDICTION (2026-09-14, before running)
    The gap GROWS with market lifetime - near zero for markets that traded under a
    week, large for those that traded months - and the edge is therefore the artifact.
    That is the way to bet given three artifacts already found in this test.

    If the gap is FLAT across lifetime strata and holds at a 1-day horizon on all
    three orderings, I will stop calling it an artifact and treat it as real pending
    the forward test.

    python -m backtest.poly_fast --markets 2500
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.polymarket_bias import (BUCKETS, fetch_markets, history,  # noqa: E402
                                      parse, price_at)

BAND = (0.50, 0.65)
LIFETIME_STRATA = [(0, 7), (7, 30), (30, 90), (90, 10_000)]


def collect(n, orders):
    """(price, outcome, event, lifetime_days, horizon) rows across several orderings.

    Deduplicated on the market's own token, so a market appearing in two orderings is
    counted once - otherwise the overlap between samples would be double-counted and
    every standard error would be understated.
    """
    seen, rows = set(), []
    for order in orders:
        ms = fetch_markets(n, order)
        good = [g for g in (parse(m) for m in ms) if g]
        print(f"    {order:<12} {len(ms):>5} fetched, {len(good):>5} cleanly resolved",
              flush=True)
        for y, tok, ce, ev in good:
            if tok in seen:
                continue
            seen.add(tok)
            pts = history(tok)
            ts = [p for p in pts if p.get("t") is not None and p.get("p") is not None]
            if len(ts) < 2:
                continue
            life = (ts[-1]["t"] - ts[0]["t"]) / 86400.0
            for h in (1, 7, 30):
                p = price_at(pts, ce, h)
                if p is None or not (0.0 < p < 1.0):
                    continue
                rows.append((p, y, ev, life, h))
    return rows


def band_stats(rows, label):
    """Per-EVENT gap inside the 0.50-0.65 band. Events, not markets - markets inside
    one event resolve together by construction."""
    sel = [r for r in rows if BAND[0] <= r[0] < BAND[1]]
    if len(sel) < 12:
        return None, f"  {label:<26} n={len(sel):<4} too few"
    ev = {}
    for p, y, e, life, h in sel:
        ev.setdefault(e, []).append((p, y))
    P = np.array([np.mean([x[0] for x in v]) for v in ev.values()])
    Y = np.array([np.mean([x[1] for x in v]) for v in ev.values()])
    gap = float(Y.mean() - P.mean())
    se = float(Y.std(ddof=1) / np.sqrt(len(Y))) if len(Y) > 1 else float("nan")
    t = gap / se if se and np.isfinite(se) and se > 0 else 0.0
    star = " *" if abs(t) >= 2 else ""
    return (gap, se, len(sel), len(ev)), (
        f"  {label:<26} n={len(sel):<4} events={len(ev):<4} "
        f"price {P.mean():.3f}  resolved {Y.mean():.3f}  "
        f"gap {gap:>+7.3f} +/- {se:.3f}  t {t:>+5.2f}{star}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", type=int, default=2500)
    args = ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: the gap GROWS with market lifetime, which would")
    print("make it the artifact. Flat across lifetimes + holding at 1 day on all three")
    print("orderings and I stop calling it an artifact.\n")

    print(f"collecting up to {args.markets} resolved markets per ordering...",
          flush=True)
    rows = collect(args.markets, ("volumeNum", "endDate", "startDate"))
    if not rows:
        print("no usable rows"); return
    uniq = len({(r[2], r[3]) for r in rows})
    print(f"  {len(rows):,} (market, horizon) observations after dedup\n")

    # ---- 1. THE DECIDING TEST -------------------------------------------
    print("=" * 104)
    print("1. DOES THE GAP DEPEND ON MARKET LIFETIME?  (the artifact test)")
    print("=" * 104)
    print("If 'has enough history' is what creates the edge, the gap must GROW with")
    print("lifetime. Flat means a lifetime filter cannot be the cause.\n")
    strat = []
    for lo, hi in LIFETIME_STRATA:
        sub = [r for r in rows if lo <= r[3] < hi and r[4] == 1]
        st, line = band_stats(sub, f"lived {lo}-{hi if hi < 9999 else '+'} days")
        print(line, flush=True)
        if st:
            strat.append((lo, hi, st))
    print()

    # ---- 2. weakest possible filter -------------------------------------
    print("=" * 104)
    print("2. AT A 1-DAY HORIZON — a market needs 1 day of history, so the selection")
    print("   pressure is close to nil")
    print("=" * 104)
    for h in (1, 7, 30):
        sub = [r for r in rows if r[4] == h]
        _st, line = band_stats(sub, f"{h} day(s) before close")
        print(line, flush=True)
    print()

    # ---- 3. the whole curve, for shape ----------------------------------
    print("=" * 104)
    print("3. THE FULL CALIBRATION CURVE at 1 day out — is the shape sane?")
    print("=" * 104)
    print(f"  {'band':<13} {'n':>6} {'events':>7} {'price':>8} {'resolved':>9} "
          f"{'gap':>8}")
    one = [r for r in rows if r[4] == 1]
    for lo, hi in BUCKETS:
        sel = [r for r in one if lo <= r[0] < hi]
        if len(sel) < 15:
            continue
        ev = {}
        for p, y, e, life, h in sel:
            ev.setdefault(e, []).append((p, y))
        P = np.array([np.mean([x[0] for x in v]) for v in ev.values()])
        Y = np.array([np.mean([x[1] for x in v]) for v in ev.values()])
        print(f"  {f'{lo:.2f}-{hi:.2f}':<13} {len(sel):>6} {len(ev):>7} "
              f"{P.mean():>8.3f} {Y.mean():>9.3f} {Y.mean()-P.mean():>+8.3f}")

    # ---- verdict ---------------------------------------------------------
    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)
    if len(strat) < 2:
        print("  not enough lifetime strata to judge")
        return
    gaps = [s[2][0] for s in strat]
    lows = [s[0] for s in strat]
    print("  gap by lifetime: " + "  ".join(
        f"{lo}d+:{g:+.3f}" for lo, g in zip(lows, gaps)))
    short_g, long_g = gaps[0], gaps[-1]
    trend = long_g - short_g
    if trend > 0.10:
        print(f"\n  THE GAP GROWS WITH LIFETIME ({short_g:+.3f} -> {long_g:+.3f}).")
        print("  That is the history-length selection artifact, and it explains the")
        print("  backtested edge. Polymarket is not mispriced; the sample was.")
    elif abs(trend) <= 0.10 and short_g > 0.05:
        print(f"\n  THE GAP IS FLAT ACROSS LIFETIMES ({short_g:+.3f} -> {long_g:+.3f})")
        print("  and present in markets that lived under a week, where the filter")
        print("  barely applies. A lifetime filter cannot produce that. This is the")
        print("  first evidence FOR the edge rather than against it - but the forward")
        print("  test still decides, because only it is immune to sampling entirely.")
    elif trend < -0.05:
        print("")
        print(f"  THE GAP SHRINKS WITH LIFETIME ({short_g:+.3f} -> "
              f"{long_g:+.3f}) - the OPPOSITE of the artifact signature,")
        print("  and it is largest in markets that lived under a week, where a")
        print("  history-length filter barely applies. Selection cannot")
        print("  produce this shape.")
        print("  But read the per-stratum errors before calling it a trend: the")
        print("  shrinking end is usually the smallest, least precise sample.")
    else:
        print(f"\n  MIXED / WEAK ({short_g:+.3f} -> {long_g:+.3f}). Not enough to call")
        print("  either way; the forward test remains the decider.")
    print("\n  Whatever this says, the entry cost is ~1.9% of price in this band and")
    print("  the band is the most liquid on the venue, so the cost is not what")
    print("  decides it either way.")


if __name__ == "__main__":
    main()
