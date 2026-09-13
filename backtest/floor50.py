"""DRIVING THE CAPITAL FLOOR TO $50 — and testing the breakeven stop on the MAJORS.

TWO QUESTIONS, ONE FILE
    1. Does the breakeven-at-3R stop help the 9 MAJOR-coin book - the validated one
       at 67.5% drawdown? If it does, the configuration with the most history behind
       it gets both cheaper and better, and that is the version worth real money.
    2. Can the floor reach $50 while still clearing +10%/month?

THE LEVER NOT YET PULLED, AND IT IS THE OBVIOUS ONE
    floor = max over coins of [ min_order x stop_fraction ] / risk_fraction
            / (1 - maxDD)

    The MAX. One coin sets the floor for the whole book. In the 12-coin cheap book
    that coin was NEAR, whose minimum order is $2.282 - three times the next worst.
    Every other coin in that book could have traded on a third of the capital.

    Previous runs treated the book as fixed and attacked maxDD. The cheaper move is
    to SUBSTITUTE the one expensive coin for another liquid coin with a tiny
    minimum, keeping breadth - and breadth is what drives return - while cutting the
    numerator. There are 901 MEXC contracts with a minimum under $2.50, so there is
    no shortage of candidates.

    Second, subtler factor: notional = risk_dollars / stop_fraction, so a coin with
    a WIDE stop needs a SMALLER position to carry the same dollar risk, which makes
    its minimum order harder to clear. Wide-stop coins therefore raise the floor.
    Majors have 1.2-2.2% stops against the alts' 2.5-3.8%, so on this axis majors
    are BETTER - they just have larger minimums. The right selection objective is
    the product, not either factor alone.

WHAT IS BEING SELECTED ON, AND WHY THAT IS ACCEPTABLE
    Coins are ranked by min_order x stop_fraction - a VENUE CONTRACT PROPERTY times a
    VOLATILITY measure. Neither is performance. This is not "pick the coins that went
    up"; a backtest never touches the ranking.

    The volatility half is not entirely innocent, though: selecting low-ATR% coins
    could favour coins that behaved differently, and low volatility is weakly
    associated with weaker trends. So the selected book's return is reported against
    the unselected cheap book's at the same size. If selection has bought a lower
    floor by quietly picking worse-trending coins, that comparison shows it.

REGISTERED PREDICTION (2026-09-13, before running)
    1. Breakeven @3R helps the majors too, though less - their 67.5% drawdown has
       less waste in it than the alts' 95%. Expect maxDD 55-62% and return flat to
       slightly better.
    2. Substitution gets the floor to roughly $60-90, not $50, because the binding
       coin's minimum can only fall so far before liquidity fails. If it reaches $50
       I will check whether the selected book is quietly less liquid.

    python -m backtest.floor50
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.cheap_wide import mexc_min_orders  # noqa: E402
from backtest.ddcontrol import HINDSIGHT, SLOTS  # noqa: E402
from backtest.ddcontrol import load as dload  # noqa: E402
from backtest.ddcontrol import portfolio as dportfolio  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.small_book import stop_fraction  # noqa: E402
import backtest.ddcontrol as dd  # noqa: E402

MIN_BARS = 20000
MAJORS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
          "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
MAJOR_MIN = {"BTCUSDT": 7.677, "ETHUSDT": 24.820, "SOLUSDT": 9.984,
             "XRPUSDT": 1.343, "BNBUSDT": 7.181, "ADAUSDT": 0.205,
             "DOGEUSDT": 8.355, "AVAXUSDT": 0.733, "LINKUSDT": 1.135}
BE_SWEEP = (0.0, 2.0, 3.0, 4.0)


def run_book(book, mins, risk, be):
    """Runs ddcontrol's portfolio on an arbitrary book by swapping its module
    globals. Reusing that function rather than copying it keeps ONE engine in play;
    a second copy is how this project ended up quoting three engines
    interchangeably."""
    dd.MIN_ORDER = dict(mins)
    d = dportfolio(book, risk, breakeven_at=be)
    if not d:
        return None
    worst, wc = 0.0, None
    for c in book:
        df = dload(c)
        if df is None:
            continue
        need = mins[c] * stop_fraction(df) / (risk / 100.0)
        if need > worst:
            worst, wc = need, c
    fl = (worst / (1 - d["dd"] / 100.0)) if d["dd"] < 99.0 and worst else float("nan")
    d["floor"] = fl
    d["binding"] = wc
    return d


HDR = (f"{'book':<22} {'BE':>4} {'risk%':>6} {'n':>6} {'raw /mo':>9} "
       f"{'HONEST /mo':>11} {'DD':>7} {'floor $':>9} {'binding':>9}  note")


def row(tag, be, risk, d):
    if not d:
        return f"{tag:<22} {be:>4.0f} {risk:>6.2f} (no result)"
    note = "** >10%/mo **" if (d["hpm"] > 10.0 and not d["ruined"]) else ""
    if d["ruined"]:
        note = "RUIN"
    if d["hpm"] > 10.0 and np.isfinite(d["floor"]) and d["floor"] <= 50:
        note = "** >10%/mo AND <= $50 **"
    return (f"{tag:<22} {be:>4.0f} {risk:>6.2f} {d['n']:>6} "
            f"{d['raw_pm']:>+8.2f}% {d['hpm']:>+10.2f}% {d['dd']:>6.1f}% "
            f"{d['floor']:>9,.0f} "
            f"{(d['binding'] or '?').replace('USDT',''):>9}  {note}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-min-order", type=float, default=0.80,
                    help="substitution pool: only contracts this cheap to trade")
    ap.add_argument("--pool", type=int, default=40)
    args = ap.parse_args()

    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: BE@3R helps the majors but less (DD 55-62%);")
    print("substitution reaches ~$60-90, not $50. Under $50 -> check liquidity.\n")

    hits = []
    # ---------------- 1. THE MAJORS ----------------------------------------
    print("=" * 118)
    print("1. THE 9 MAJOR COINS — does the breakeven stop help the VALIDATED book?")
    print("=" * 118)
    print(HDR)
    for risk in (0.13, 0.30):
        for be in BE_SWEEP:
            d = run_book(MAJORS, MAJOR_MIN, risk, be)
            if d:
                hits.append(("majors-9", be, risk, d))
            print(row("majors-9", be, risk, d), flush=True)
        print()

    # ---------------- 2. SUBSTITUTION -------------------------------------
    print("=" * 118)
    print(f"2. SUBSTITUTION — a book whose WORST minimum order is tiny "
          f"(<= ${args.max_min_order:.2f})")
    print("=" * 118)
    mins_all = mexc_min_orders(args.max_min_order, args.pool * 3)
    print(f"   {len(mins_all)} liquid MEXC contracts have a minimum order under "
          f"${args.max_min_order:.2f}", flush=True)
    cand = []
    for b in mins_all:
        sym = f"{b}USDT"
        try:
            df = fetch(sym, "1h", 2400)
        except Exception:
            continue
        if df is None or len(df) < MIN_BARS:
            continue
        sf = stop_fraction(df)
        dv = float((df["close"] * df["volume"]).median())
        if not np.isfinite(sf) or sf <= 0:
            continue
        cand.append((mins_all[b][0] * sf, sym, mins_all[b][0], sf, dv))
    cand.sort()                       # by min_order x stop_fraction, the numerator
    print(f"   {len(cand)} of them have >= {MIN_BARS:,} bars of history\n")
    if len(cand) < 6:
        print("   not enough candidates to build a book")
        return
    print(f"{'#':>3} {'coin':<9} {'min$ x stop':>12} {'min order $':>12} "
          f"{'stop %':>8} {'median $vol/bar':>16}")
    for i, (prod, sym, mo, sf, dv) in enumerate(cand[:20], 1):
        print(f"{i:>3} {sym.replace('USDT',''):<9} {prod:>12.4f} {mo:>12.3f} "
              f"{sf*100:>7.2f}% {dv:>16,.0f}")

    order = [c[1] for c in cand]
    sub_mins = {c[1]: c[2] for c in cand}
    print("\n" + HDR)
    for k in (9, 12, 16):
        if k > len(order):
            continue
        book = order[:k]
        dd.MIN_ORDER = sub_mins
        for risk in (0.30, 0.45):
            for be in (0.0, 3.0):
                d = run_book(book, sub_mins, risk, be)
                if d:
                    hits.append((f"substituted-{k}", be, risk, d))
                print(row(f"substituted-{k}", be, risk, d), flush=True)
        print()

    # ---------------- 2b. THE SAME SEARCH WITH A LIQUIDITY FLOOR -----------
    # Ranking purely by min_order x stop_fraction selected ILV, ICX, CVC and
    # friends - $30k-170k of volume per bar against XRP's $6.8M - and every one of
    # those books drew down 99.6-100%. That is not a tuning problem, it is the
    # selection objective picking dying coins: a contract's minimum order is small
    # because the COIN is cheap, and coins get cheap by falling.
    #
    # So impose liquidity as a HARD CONSTRAINT and minimise the floor subject to it,
    # rather than minimising the floor alone. If nothing survives, the conclusion is
    # that the two requirements are in direct conflict and $50 is unreachable.
    for liq_floor in (400_000, 1_000_000):
        pool = [c for c in cand if c[4] >= liq_floor]
        print("=" * 118)
        print(f"2b. SAME SEARCH, LIQUIDITY FLOOR ${liq_floor:,}/bar — "
              f"{len(pool)} coins qualify")
        print("=" * 118)
        if len(pool) < 6:
            print(f"   only {len(pool)} coins clear both tests "
                  f"({', '.join(c[1].replace('USDT','') for c in pool)}) — "
                  f"too few for a book\n")
            continue
        print("   " + ", ".join(f"{c[1].replace('USDT','')}(${c[2]:.3f})"
                                for c in pool[:16]))
        lo = [c[1] for c in pool]
        lmins = {c[1]: c[2] for c in pool}
        print(HDR)
        for k in (6, 9, 12):
            if k > len(lo):
                continue
            for risk in (0.30, 0.45):
                for be in (0.0, 3.0):
                    d = run_book(lo[:k], lmins, risk, be)
                    if d:
                        hits.append((f"liq{liq_floor//1000}k-{k}", be, risk, d))
                    print(row(f"liq{liq_floor//1000}k-{k}", be, risk, d),
                          flush=True)
            print()

    # ---------------- 3. THE ANSWER ---------------------------------------
    print("=" * 118)
    print("CLEARS +10%/MONTH, CHEAPEST CAPITAL FIRST")
    print("=" * 118)
    ok = [h for h in hits if h[3]["hpm"] > 10.0 and not h[3]["ruined"]
          and np.isfinite(h[3]["floor"])]
    if not ok:
        print("  nothing clears +10%/month.")
    else:
        ok.sort(key=lambda h: h[3]["floor"])
        for tag, be, risk, d in ok[:10]:
            flag = "  <-- UNDER $50" if d["floor"] <= 50 else ""
            print(f"  ${d['floor']:>7,.0f}  {tag:<16} BE@{be:.0f}R "
                  f"{risk:.2f}%/unit  {d['hpm']:+.2f}%/month  "
                  f"DD {d['dd']:.1f}%  binding "
                  f"{(d['binding'] or '?').replace('USDT','')}{flag}")
        best = ok[0]
        print(f"\n  CHEAPEST: ${best[3]['floor']:,.0f} — {best[0]}, "
              f"BE@{best[1]:.0f}R, {best[2]:.2f}%/unit, "
              f"{best[3]['hpm']:+.2f}%/month, DD {best[3]['dd']:.1f}%")
        if best[3]["floor"] > 50:
            print(f"  TARGET OF $50 NOT REACHED. Short by "
                  f"${best[3]['floor']-50:,.0f}.")
        else:
            print("  $50 TARGET REACHED — now check the liquidity column above "
                  "before believing it.")
    print("\nEvery figure divided by the 3.0x hindsight premium. Minimum orders are")
    print("MEXC metadata from 2026-09-13 and need one real demo order to confirm.")
    print("A drawdown near 90% on a $50 account leaves single-digit dollars, which")
    print("is at or under the venue minimum - so a LOW floor and a HIGH drawdown in")
    print("the same row is close to self-contradictory. Prefer the lowest drawdown")
    print("that clears the target, not the lowest floor.")


if __name__ == "__main__":
    main()
