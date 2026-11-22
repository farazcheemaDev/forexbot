"""AUDIT CHECK (2026-11-10): the FORCED-FLOW books as their own account, without trend / MN / daily / carry.

The books whose edge is "someone is forced to trade" (crash bids, capit2, news shorts, bear sleeve, NASDAQ dip-buy)
have never been scored as an account of their own - only as add-ons to the trend machine.  Series = all_books.py's
own (same code, same weights, same costs).  Compared with the DEPLOYED 7-book machine scaled DOWN to the same fall
(the repo's 'bet smaller' line), tune / holdout.

REGISTERED BEFORE THE RUN
  E1 EVENT x1 full-period CAGR +80..+130%, fall 15-30%, months up >= 70%.
  E2 at matched fall the deployed machine keeps the higher TYPICAL year on both halves; EVENT has the better WORST
     12 months on both halves.
  E3 EVENT x1 worst month better than -15% on both halves.

RESULT (2026-11-10, logs/audit_event_only.txt) - a steadier account, NOT a better one.
  EVENT x1: full-period CAGR +121%, fall 22%, 78% of months up, no 12-month window below its start. $300 typical 12 months
  $644 tune / $711 holdout, worst month -10.2% / -19.0% (the holdout's is the news book: -25% in 2026).  Without the news
  book (chosen after looking): CAGR +95%, typical $613 / $545, worst month -12.1% / -3.9%.
  Against the deployed machine (+ news + ndx) scaled DOWN to the same fall: x0.40 / x0.35 makes $1,099 / $1,271 a typical
  year - the event account loses the bet-smaller line on both halves; its worst 12 months is better on the tune half
  ($360 vs $317) and worse on the holdout ($525 vs $556).  Its one clear win is the kind of year: 2022 +143% (sum of daily
  returns) against the machine's +56%; 2026 to September +3% against +188%.
  E1 RIGHT.  E2 typical-year part RIGHT, worst-12-months part right on the tune half only.  E3 WRONG (holdout -19.0%).
  An audit check: no tests / planted-bug round; the series are all_books.py's own (its published table is reproduced by
  the DEPLOYED rows: $4,435 / $9,838).  Trap met: the orderings' calendars differ by a day, so adding a series indexed on
  ordering 0's calendar leaves a NaN last day and stats1 reads it as -100% - align to each ordering's own index.

    python -m backtest.audit_event_only
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
M = ab.machine_books()
idx = M[0].index
news = ab.news_book().reindex(idx).fillna(0.0)
ndx = ab.ndx_dip().reindex(idx).fillna(0.0)
news_start = news[news != 0].index[0]
print("calendar", idx[0].date(), idx[-1].date(), "| news from", news_start.date(), "| CUT", CUT.date())

EV = ["sleeve", "bids", "capit2"]


def ev(x, k=1.0, with_news=True, with_ndx=True):
    s = x[EV].sum(axis=1)
    if with_news:
        s = s + news.reindex(x.index).fillna(0.0)
    if with_ndx:
        s = s + ndx.reindex(x.index).fillna(0.0)
    return k * s


def dep(x, k=1.0):
    return k * (x[ab.BOOKS].sum(axis=1) + news.reindex(x.index).fillna(0.0) + ndx.reindex(x.index).fillna(0.0))


def row(lab, xs):
    out = []
    for half, s in (("tune", summary([x[x.index < CUT] for x in xs])), ("holdout", summary(xs, CUT))):
        out.append(s)
        print(f"   {lab:<40}{half:>8} typ ${s['typ']:>7,.0f} bad ${s['bad']:>6,.0f} worst ${s['worst']:>6,.0f} "
              f"worst mo {s['wm']:>+6.1f}% fall {s['dd']:>4.0f}% up {s['up']:>3.0f}% below-start {s['below']:>3.0f}%")
    return out


def full(lab, xs):
    v = [ab.stats1(x) for x in xs]
    cg, dd, up = (float(np.median([a[k] for a in v])) for k in range(3))
    print(f"   {lab:<40} FULL CAGR {cg * 100:+6.0f}%  fall {dd * 100:4.0f}%  months up {up * 100:3.0f}%")
    return cg, dd, up


print("\n1. FULL PERIOD")
full("EVENT x1 (sleeve+bids+capit2+news+ndx)", [ev(x) for x in M])
full("EVENT x1 without news (not post hoc)", [ev(x, with_news=False) for x in M])
full("EVENT x1 without news and ndx", [ev(x, with_news=False, with_ndx=False) for x in M])
full("EVENT x2", [ev(x, 2.0) for x in M])
full("EVENT x3", [ev(x, 3.0) for x in M])
full("DEPLOYED + news + ndx x1", [dep(x) for x in M])

print("\n2. BY HALF ($300, 12 months)")
R = {}
for lab, f in (("EVENT x1", lambda x: ev(x)), ("EVENT x1 no news", lambda x: ev(x, with_news=False)),
               ("EVENT x2", lambda x: ev(x, 2.0)), ("EVENT x3", lambda x: ev(x, 3.0)),
               ("DEPLOYED+news+ndx x1", lambda x: dep(x))):
    R[lab] = row(lab, [f(x) for x in M])

print("\n3. DEPLOYED scaled to EVENT's fall (the bet-smaller line), per half")
for evlab in ("EVENT x1", "EVENT x2", "EVENT x3"):
    for hi, half in enumerate(("tune", "holdout")):
        target = R[evlab][hi]["dd"]
        best = None
        for k in np.arange(0.05, 1.01, 0.05):
            xs = [dep(x, k) for x in M]
            s = summary([x[x.index < CUT] for x in xs]) if half == "tune" else summary(xs, CUT)
            if s["dd"] <= target:
                best = (k, s)
        if best:
            k, s = best
            e = R[evlab][hi]
            print(f"   {evlab} {half:>8}: fall {e['dd']:.0f}% typ ${e['typ']:,.0f} bad ${e['bad']:,.0f} worst ${e['worst']:,.0f} wm {e['wm']:+.1f}%"
                  f"  |  deployed x{k:.2f}: fall {s['dd']:.0f}% typ ${s['typ']:,.0f} bad ${s['bad']:,.0f} worst ${s['worst']:,.0f} wm {s['wm']:+.1f}%")

print("\n4. EVENT x1 BY CALENDAR YEAR (ordering 0; simple sum of daily returns, %)")
e0 = ev(M[0])
parts = M[0][EV].copy()
parts["news"], parts["ndx"] = news, ndx
yr = (parts.groupby(parts.index.year).sum() * 100).round(1)
yr["EVENT"] = yr.sum(axis=1).round(1)
yr["deployed7"] = (M[0][ab.BOOKS].sum(axis=1).groupby(idx.year).sum() * 100).round(1)
print(yr.to_string())
mo = (1 + e0).resample("ME").prod() - 1
print("\n   EVENT x1 months: median %+.1f%%, p10 %+.1f%%, worst %+.1f%%, best %+.1f%%, share with |ret| < 0.5%%: %.0f%%" % (
    mo.median() * 100, mo.quantile(0.1) * 100, mo.min() * 100, mo.max() * 100, (mo.abs() < 0.005).mean() * 100))
last = e0[e0.index >= "2025-09-14"]
print("   last 12 months (ordering 0): %+.1f%%" % (((1 + last).prod() - 1) * 100))
