"""THE POINT-IN-TIME UNIVERSE THROUGH THE ACTUAL DEPLOYED RULES.

    python -m backtest.pit_blend

WHY
    backtest/hindsight.py found that the 3x hindsight divisor is not constant, and that
    in 2025-2026 it INVERTED: a book of "top 12 by last month's volume" beat the
    hand-picked 12 by 6.7x on mean R in 2026. But that comparison ran on
    pit_universe's simpler engine - one timeframe, one unit, 12x trail, no breakeven,
    no shorts - so it established a RATIO and not a return.

    This runs both universes through the REAL rules: 1h + 4h + 12h sleeves, 5-unit long
    pyramid on a 20xATR trail, 1-unit short on 5xATR, breakeven at 3R, the 1000h regime
    gate, 12 shared slots. Same portfolio pass on both sides, so the only difference is
    HOW THE COINS ARE CHOSEN.

HOW THE UNIVERSE IS SWAPPED WITHOUT TOUCHING blend.py
    blend.load() is cache-first on the module global _D, and blend.sleeve() iterates
    blend.BOOK. So both are redirected by assignment:

        blend._D.update(frames)      # dead coins included, keyed by symbol
        blend.BOOK = candidates
        blend._S.clear()             # sleeve cache MUST be dropped or it replays
                                     # the old book's trades under the new label

    That _S.clear() is the whole trap. sleeve() caches per RULE, not per book, so
    without clearing it the "PIT" run silently returns the FIXED book's trades and the
    two columns come out identical - the same failure mode as the byte-identical
    Polymarket tables. An assertion below checks the trade sets actually differ.

    Only coins that appear in SOME month's top 12 can ever be traded, so the sleeve is
    built for that candidate set rather than all 284 coins - same result, far less work.

WHAT THIS CANNOT TELL YOU: THE CAPITAL FLOOR
    blend's floor needs MIN_ORDER per coin, and that table exists only for the 12
    deployed names. The point-in-time universe contains coins that are delisted, may not
    be on MEXC at all, or may carry much larger minimums. So a PIT book might be
    UNTRADEABLE at $221 even if its returns are better, and this file deliberately does
    not print a floor rather than print a wrong one. Establishing tradeability is a
    separate job and it gates any deployment.

REGISTERED PREDICTION (2026-09-14, before running)
    PIT beats FIXED in 2025-2026 under the real rules too, but by LESS than the 6.7x
    seen on the simple engine - because the blend's three timeframes and pyramid already
    diversify away part of what coin selection was fixing. I expect roughly 2-3x on the
    recent window, and FIXED to win over the full history (where its hindsight is real
    and worth ~3x).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend                                        # noqa: E402
from backtest.pit_universe import load_all, monthly_volume        # noqa: E402
from backtest.regime_blend import set_lookback                    # noqa: E402

TOP = 12
SLOTS = 12
RULES = ("1h", "4h", "12h")
DEPLOYED = list(blend.BOOK)


def eligibility(frames):
    """{period -> set of symbols} eligible to ENTER in that month, ranked on the PRIOR
    month's realised dollar volume so the universe never reads its own month."""
    vol = monthly_volume(frames)
    out = {}
    for per, rv in vol.iterrows():
        out[per + 1] = set(rv.dropna().sort_values(ascending=False).head(TOP).index)
    return out


def trades_for_book(book, frames=None):
    """All (entry, exit, R, rule, coin) under the real blend rules for `book`."""
    blend.BOOK = list(book)
    blend._S.clear()                      # see the docstring - non-negotiable
    if frames:
        blend._D.update(frames)
    tr = []
    for rule in RULES:
        a, _stops = blend.sleeve(rule)
        tr += a
    tr.sort(key=lambda x: x[0])
    return tr


def portfolio(tr, allowed, bear, t_from=None, risk=0.30):
    """One portfolio pass. `allowed=None` means every coin is always eligible."""
    f0 = risk / 100.0
    open_until, rows = [], []
    for a, b, r, _rule, c in tr:
        ta = pd.Timestamp(a)
        if t_from is not None and ta < t_from:
            continue
        if allowed is not None:
            ok = allowed.get(ta.to_period("M"))
            if ok is None or c not in ok:
                continue
        open_until = [u for u in open_until if u > a]
        if len(open_until) >= SLOTS:
            continue
        open_until.append(b)
        f = f0 * (blend.REGIME_MULT if bool(bear.asof(ta)) else 1.0)
        rows.append((pd.Timestamp(b), r * f, r))
    if len(rows) < 30:
        return None
    idx = pd.DatetimeIndex([x[0] for x in rows])
    pnl = pd.Series([x[1] for x in rows], index=idx)
    R = np.array([x[2] for x in rows])
    mon = pnl.resample("ME").sum()
    eq = float(np.prod(1.0 + mon.values))
    curve = np.cumprod(1.0 + mon.values)
    peak = np.maximum.accumulate(np.maximum(curve, 1e-12))
    dd = float((1 - curve / peak).max() * 100)
    return dict(n=len(rows), meanR=float(R.mean()), months=len(mon),
                mo=(eq ** (1 / len(mon)) - 1) * 100 if eq > 0 else -100.0,
                win=float((mon > 0).mean() * 100), med=float(mon.median() * 100),
                worst=float(mon.min() * 100), best=float(mon.max() * 100), dd=dd,
                total=(eq - 1) * 100)


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: PIT still beats FIXED recently but by LESS than the")
    print("6.7x on the simple engine (the blend already diversifies part of it) - call it")
    print("2-3x. FIXED wins over the full history, where its hindsight is real.\n")

    print("loading every coin, alive and delisted...", flush=True)
    frames = load_all(verbose=False)
    allowed = eligibility(frames)
    cands = sorted(set().union(*allowed.values()))
    print(f"  {len(frames)} coins loaded, {len(allowed)} months of eligibility")
    print(f"  {len(cands)} coins ever reach a month's top {TOP} — only these can trade")
    print(f"  deployed book overlap: "
          f"{len([c for c in DEPLOYED if c in cands])}/{len(DEPLOYED)}\n")

    set_lookback(1000)
    bear = blend.btc_bear()

    print("building sleeves under the real rules (this is the slow part)...", flush=True)
    tr_pit = trades_for_book(cands, frames)
    print(f"  PIT candidate sleeves: {len(tr_pit):,} trades", flush=True)
    tr_fix = trades_for_book(DEPLOYED)
    print(f"  deployed book sleeves: {len(tr_fix):,} trades", flush=True)
    assert len(tr_pit) != len(tr_fix), (
        "identical trade counts - blend._S was not cleared, so both runs used the same "
        "book. This is the byte-identical-tables failure mode; fix before reading on.")

    print("\n" + "=" * 104)
    print(f"SAME RULES, SAME {SLOTS} SLOTS, SAME 1000h GATE — ONLY THE COIN CHOICE DIFFERS")
    print("=" * 104)
    print(f"  {'window':<14}{'universe':<26}{'trades':>8}{'meanR':>8}{'/mo':>9}"
          f"{'win mo':>8}{'median':>9}{'worst':>8}{'DD':>8}{'divisor':>10}")
    out = {}
    for lab, frm in (("all 2020-2026", None), ("2025 onward", "2025-01-01"),
                     ("2026 onward", "2026-01-01")):
        t = pd.Timestamp(frm) if frm else None
        a = portfolio(tr_fix, None, bear, t)
        b = portfolio(tr_pit, allowed, bear, t)
        for nm, d, div in (("FIXED (hand-picked 12)", a, "/3 needed"),
                           ("POINT-IN-TIME top 12", b, "NONE")):
            if not d:
                print(f"  {lab:<14}{nm:<26}{'too few trades':>20}")
                continue
            out[(lab, nm[:5])] = d
            print(f"  {lab:<14}{nm:<26}{d['n']:>8}{d['meanR']:>8.3f}{d['mo']:>+8.2f}%"
                  f"{d['win']:>7.0f}%{d['med']:>+8.2f}%{d['worst']:>+7.1f}%"
                  f"{d['dd']:>7.1f}%{div:>10}")
        print()

    print("=" * 104)
    print("HONEST SIDE BY SIDE — FIXED gets its 3x haircut, PIT needs none")
    print("=" * 104)
    print(f"  {'window':<16}{'FIXED after /3':>16}{'PIT as measured':>18}{'ratio':>9}")
    for lab in ("all 2020-2026", "2025 onward", "2026 onward"):
        a, b = out.get((lab, "FIXED")), out.get((lab, "POINT"))
        if not (a and b):
            continue
        # The divisor applies to the RETURN, so convert, divide, convert back.
        fa = ((1 + a["mo"] / 100) ** 12 - 1) * 100 / blend.HINDSIGHT
        fa_mo = ((1 + fa / 100) ** (1 / 12) - 1) * 100 if fa > -100 else -100.0
        ratio = (b["mo"] / fa_mo) if fa_mo > 0.01 else float("nan")
        rs = f"{ratio:>8.1f}x" if ratio == ratio else "     n/a"
        print(f"  {lab:<16}{fa_mo:>+15.2f}%{b['mo']:>+17.2f}%{rs:>9}")

    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)
    r26 = out.get(("2026 onward", "POINT")), out.get(("2026 onward", "FIXED"))
    if all(r26):
        p, f = r26
        print(f"  2026: point-in-time {p['mo']:+.2f}%/mo vs hand-picked "
              f"{f['mo']:+.2f}%/mo before any haircut,")
        print(f"        and the hand-picked figure still owes a 3x haircut while this "
              f"one owes none.")
    print("\n  NO CAPITAL FLOOR IS PRINTED ON PURPOSE. MIN_ORDER exists only for the 12")
    print("  deployed coins; the point-in-time universe contains delisted names and")
    print("  coins that may not be on MEXC at all. A better-returning book that cannot")
    print("  be traded at $221 is not an improvement, and proving tradeability is the")
    print("  job that gates deploying this.")


if __name__ == "__main__":
    main()
