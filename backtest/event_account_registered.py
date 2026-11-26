"""THE EVENT ACCOUNT, EXACTLY AS IT WILL RUN: what the backtest says about the book set that `event_bot.py` paper-trades (2026-11-27).

THE USER (2026-11-26/27): "what can we do" -> an event-only paper record -> "Yes, set it up". audit_event_only.py (2026-11-10)
measured the EVENT set sleeve + bids + capit2 + news + ndx (+121%/yr, fall 22%). The account that is being built is a
DIFFERENT set: carry + capit2 + news + NASDAQ dip + crash bids, NO bear sleeve (it is -$9 live on main and not an event
book in the sense of a forced seller with a trigger the account can wait for), NO trend, MN or daily book. This file prices
that set before any live day of it exists, so the registered claim is its own and not borrowed from the old one.

SIZING (registered before the run): every book at the final machine's weight - bids 1/40 of equity a bid, capit2 x1.0 at 2x,
news and the NASDAQ dip as in news_books.py - EXCEPT carry at x1.0, twice the machine's x0.5. Why: on 2026-11-13 / 11-07 the
machine's carry rebalance came back EMPTY on both paper accounts because K_CARRY x equity x 0.5 / n fell under Bitget's $5
(final_books.py:459) - the one book making money switched itself off after a 20% fall. At x1.0 the same arithmetic holds
until equity falls under $120 (n = 12 longs). The backtest series are linear in the weight, so carry x1.0 = 2 x the
deployed carry column (all_books.py: carry = 0.5 * the funding-ranked short-exit run).

REGISTERED BEFORE THE RUN (2026-11-27)
  V1  The registered set (carry x1.0) has a full-period CAGR between +50% and +130% and a fall under 35%.            (65%)
  V2  Carry adds to the account: CAGR with carry x1.0 is higher than without carry, on both halves.                    (50%)
  V3  Months up >= 60% and worst month better than -20% on both halves.                                                 (55%)
  V4  The set loses the repo's 'bet smaller' line to the deployed machine on at least one half (as audit_event_only's did). (70%)
  V5  2026 to September is the account's weakest year (news -25% and the alt bleed).                                    (60%)

    python -m backtest.event_account_registered      (writes logs/event_account_registered.txt)
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import all_books as ab  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402

warnings.filterwarnings("ignore")
LOG = ROOT / "logs" / "event_account_registered.txt"
lines: list = []


def out(s: str = ""):
    lines.append(s)
    print(s, flush=True)


M = ab.machine_books()
idx = M[0].index
news = ab.news_book().reindex(idx).fillna(0.0)
ndx = ab.ndx_dip().reindex(idx).fillna(0.0)
out(f"backtest/event_account_registered.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; calendar {idx[0].date()} .. {idx[-1].date()}; "
    f"split (CUT) {CUT.date()}; {len(M)} slot orderings; series = all_books.py's own (same code, weights, costs)")


def reg(x, kc=1.0, carry=True, sleeve=False):
    """The registered set: carry (deployed column is x0.5, so kc/0.5 of it) + bids + capit2 + news + ndx [+ sleeve]."""
    s = x[["bids", "capit2"]].sum(axis=1) + news.reindex(x.index).fillna(0.0) + ndx.reindex(x.index).fillna(0.0)
    if carry:
        s = s + x["carry"] * (kc / 0.5)
    if sleeve:
        s = s + x["sleeve"]
    return s


def dep(x, k=1.0):
    return k * (x[ab.BOOKS].sum(axis=1) + news.reindex(x.index).fillna(0.0) + ndx.reindex(x.index).fillna(0.0))


def full(lab, xs):
    v = [ab.stats1(x) for x in xs]
    cg, dd, up = (float(np.median([a[k] for a in v])) for k in range(3))
    out(f"   {lab:<52} FULL CAGR {cg * 100:+6.0f}%  fall {dd * 100:4.0f}%  months up {up * 100:3.0f}%")
    return cg, dd, up


def row(lab, xs):
    res = []
    for half, s in (("tune", summary([x[x.index < CUT] for x in xs])), ("holdout", summary(xs, CUT))):
        res.append(s)
        out(f"   {lab:<44}{half:>8} typ ${s['typ']:>7,.0f} bad ${s['bad']:>6,.0f} worst ${s['worst']:>6,.0f} "
            f"worst mo {s['wm']:>+6.1f}% fall {s['dd']:>4.0f}% up {s['up']:>3.0f}% below-start {s['below']:>3.0f}%")
    return res


out("\n1. FULL PERIOD")
A = full("REGISTERED: carry x1.0 + bids + capit2 + news + ndx", [reg(x) for x in M])
full("  carry x0.5 (the machine's weight)", [reg(x, 0.5) for x in M])
B = full("  without carry (bids + capit2 + news + ndx)", [reg(x, carry=False) for x in M])
full("  registered + the bear sleeve (audit_event_only's set + carry)", [reg(x, sleeve=True) for x in M])
full("  audit_event_only's set (sleeve + bids + capit2 + news + ndx)", [reg(x, carry=False, sleeve=True) for x in M])
full("DEPLOYED machine + news + ndx x1", [dep(x) for x in M])

out("\n2. BY HALF ($300, 12 months)")
R = {}
for lab, f in (("REGISTERED (carry x1.0)", lambda x: reg(x)), ("carry x0.5", lambda x: reg(x, 0.5)),
               ("no carry", lambda x: reg(x, carry=False))):
    R[lab] = row(lab, [f(x) for x in M])

out("\n3. THE 'BET SMALLER' LINE: the deployed machine scaled down to the registered set's fall, per half")
for hi, half in enumerate(("tune", "holdout")):
    target = R["REGISTERED (carry x1.0)"][hi]["dd"]
    best = None
    for k in np.arange(0.05, 1.01, 0.05):
        xs = [dep(x, k) for x in M]
        s = summary([x[x.index < CUT] for x in xs]) if half == "tune" else summary(xs, CUT)
        if s["dd"] <= target:
            best = (k, s)
    if best:
        k, s = best
        e = R["REGISTERED (carry x1.0)"][hi]
        out(f"   {half:>8}: registered fall {e['dd']:.0f}% typ ${e['typ']:,.0f} bad ${e['bad']:,.0f} worst ${e['worst']:,.0f} wm {e['wm']:+.1f}%"
            f"  |  deployed x{k:.2f}: fall {s['dd']:.0f}% typ ${s['typ']:,.0f} bad ${s['bad']:,.0f} worst ${s['worst']:,.0f} wm {s['wm']:+.1f}%")

out("\n4. REGISTERED SET BY CALENDAR YEAR (ordering 0; simple sum of daily returns, %)")
e0 = reg(M[0])
parts = pd.DataFrame({"carry x1.0": M[0]["carry"] * 2.0, "bids": M[0]["bids"], "capit2": M[0]["capit2"], "news": news, "ndx": ndx})
yr = (parts.groupby(parts.index.year).sum() * 100).round(1)
yr["ACCOUNT"] = yr.sum(axis=1).round(1)
out(yr.to_string())
mo = (1 + e0).resample("ME").prod() - 1
out("\n   months: median %+.1f%%, p10 %+.1f%%, worst %+.1f%%, best %+.1f%%, share with |ret| < 0.5%%: %.0f%%" % (
    mo.median() * 100, mo.quantile(0.1) * 100, mo.min() * 100, mo.max() * 100, (mo.abs() < 0.005).mean() * 100))
last = e0[e0.index >= "2025-09-14"]
out("   last 12 months (ordering 0): %+.1f%%" % (((1 + last).prod() - 1) * 100))

out("\n5. THE LIVE WINDOW 2026-10-09 .. 2026-09 end of data is outside this calendar; the live record is the test.")
v1 = 0.50 <= A[0] <= 1.30 and A[1] < 0.35
v2 = all(R["REGISTERED (carry x1.0)"][h]["typ"] > R["no carry"][h]["typ"] for h in (0, 1))
v3 = all(R["REGISTERED (carry x1.0)"][h]["up"] >= 60 and R["REGISTERED (carry x1.0)"][h]["wm"] > -20 for h in (0, 1))
out(f"\nV1 CAGR +50..+130% and fall < 35% -> {'RIGHT' if v1 else 'WRONG'} ({A[0] * 100:+.0f}%, {A[1] * 100:.0f}%)")
out(f"V2 carry adds on both halves (typical year) -> {'RIGHT' if v2 else 'WRONG'}")
out(f"V3 months up >= 60% and worst month > -20% on both halves -> {'RIGHT' if v3 else 'WRONG'}")
LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
