"""THE SCORECARD'S YARDSTICK: what each book's backtest says is normal for a stretch of N days (2026-10-17)

The user asked for a system that tells, while it runs, whether each part is doing what the backtest said. This file
writes dashboard_bands.json (repo root, committed): for every book of the final machine and the whole account, the
distribution of its result over every N-day stretch of the backtest, N = 1 .. 365 days on a grid, as quantiles.
dashboard_push.py (VM) puts each account's LIVE result for its age into that distribution: a percentile and a status.

    books      trend / mn / carry / sleeve / daily / capit2 / news / ndx - the final machine as deployed
               (all_books.machine_books: trend guard 6.25x with gains shrunk for hindsight, MN blend, carry x0.5,
               sleeve, daily x0.5, capit2 1.0 x 2x; news 1/10 a trade; NASDAQ dip x1). The crash bids are not in the
               running final bot (no --wick), so they are not in its yardstick either.
    a book's   the SUM of its daily returns over the stretch = its P&L as a share of the account at the start of the
    result     stretch (the live side: the book's booked + open P&L / the account's start)
    account    the compounded sum of the 8 books
    windows    every start day, all 10 orderings pooled (news and NASDAQ: the same in every ordering, counted once,
               and only from the first day the news book has data)
    stored     33 quantile levels per (book, N), the share of stretches with no P&L at all (idle), and the median
WHAT IT IS NOT: a forecast. It is the backtest's own range - unconditional on the market type, trend gains shrunk,
everything else raw - so a live book sitting at its 50th percentile is doing as well as the backtest, which
final_confidence.py says to expect only discounted. Read low percentiles as "worse than the backtest", not "broken".

REGISTERED BEFORE THE RUN (2026-10-17; the main account was 8.2 days old, -7.1% live, trend -$8.4, mn -$5.1, carry
-$7.1, daily -$0.2, the others ~0):
    S1 the main account's 8-day result sits between the 3rd and 15th percentile of the account's 8-day stretches
       (final_confidence.py put the 7-day -10.6% at 7.3).
    S2 the trend book is below its own 25th percentile; carry below its 10th (carry -2.4% of the account in 8 days at
       x0.5 is a lot for a book that falls 17% at its worst).
    S3 sleeve, capit2 and news are idle in at least 30% of 8-day stretches (so their live $0 reads "idle, normal").

RUN 1 (2026-10-17 01:35 UTC, books as a plain SUM of daily returns): S1 WRONG (16.2 - the account is less unusual
than predicted), S2 WRONG (trend 30.5, carry 6.1), S3 RIGHT (68 / 90 / 48%). Two faults found before using it:
    1. a book's stretch was the sum of its daily returns, which is not its dollars as a share of the start once the
       account grows - fixed (dollar_windows, books now add up to the account exactly, asserted);
    2. the MN and carry books are booked WEEKLY in the backtest and daily live, so stretches under a week do not compare -
       dashboard_push.py shows no scorecard before 7 days. (The trend book is booked at each close in the backtest,
       marked to market live: comparable over a week or more, noted not fixed.)
RUN 2 died: the orderings' calendars differ by a day at the ends, and news / NASDAQ indexed on ordering 0's days made a
2,401-day total beside 2,400-day books (every ordering is now on its own calendar, asserted). all_books.py adds news the
same way - one NaN day in those orderings' totals, skipped by cumprod; tiny, not re-measured.
RUN 3 (2026-10-18 00:53 UTC, logs/scorecard_bands.txt - the one dashboard_bands.json holds): the books' dollar stretches
add up to the account's (asserted). 7- and 30-day bands barely move from run 1; 365-day book bands are far wider (the
account compounds). Predictions unchanged: S1 WRONG (16.2), S2 WRONG (trend 30.7, carry 6.3), S3 RIGHT.
First live read (dashboard_push.py, 2026-10-18, main account 9.0 days, -4.5%): account 25th percentile; carry 5.9th
(-$7.75); NASDAQ 5.6th (one open trade -$0.76 where the backtest is usually idle); the rest 38th-65th or idle.

    python -m backtest.scorecard_bands
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "dashboard_bands.json"
LOG = ROOT / "logs" / "scorecard_bands.txt"
LEVELS = [0, 0.5, 1, 2, 3, 5, 7.5, 10, 12.5, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 87.5, 90,
          92.5, 95, 97, 98, 99, 99.5, 100]
LENGTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 17, 21, 25, 30, 35, 42, 50, 60, 75, 90, 105, 120, 150, 180, 240, 300,
           365]
NAMES = {"trend": "trend", "mn_blend": "mn", "carry": "carry", "sleeve": "sleeve", "daily": "daily",
         "capit2": "capit2"}


def windows(r: pd.Series, n: int, compound: bool = False) -> np.ndarray:
    """Every n-day stretch's result: the sum of daily returns, or the compounded return."""
    if compound:
        lg = np.log1p(r.clip(lower=-0.999))
        return np.expm1(lg.rolling(n).sum().dropna().to_numpy())
    return r.rolling(n).sum().dropna().to_numpy()


def dollar_windows(r_book: np.ndarray, r_total: np.ndarray, n: int, first: int = 0) -> np.ndarray:
    """A book's DOLLAR P&L over every n-day stretch as a share of the ACCOUNT at the stretch's start - what the live
    side measures (book $ / the account's start). A plain sum of the book's daily returns is not that: each day's
    return is a share of that day's equity, which grows (the first run used the sum and understated long stretches).
    first = the first allowed start day (the news book has no data before it)."""
    E = np.r_[1.0, np.cumprod(1 + r_total)]                 # equity after t days, E[0] = the start
    C = np.r_[0.0, np.cumsum(E[:-1] * r_book)]              # cumulative dollars the book made
    s = np.arange(first, len(r_book) - n + 1)
    return (C[s + n] - C[s]) / E[s]


def band(vals: np.ndarray) -> dict:
    return dict(q=[round(float(x), 6) for x in np.percentile(vals, LEVELS)],
                idle=round(float(np.mean(np.abs(vals) < 1e-9)), 4), n=int(len(vals)))


def pctile(v: float, levels: list, q: list) -> float:
    """Where v sits in the stored quantiles (ties: the middle of the tied range) - dashboard_push.pctile's twin."""
    q = np.asarray(q)
    if v < q[0]:
        return 0.0
    if v > q[-1]:
        return 100.0
    eq = np.where(np.abs(q - v) < 1e-12)[0]
    if len(eq):
        return float((levels[eq[0]] + levels[eq[-1]]) / 2)
    i = int(np.searchsorted(q, v)) - 1
    return float(levels[i] + (levels[i + 1] - levels[i]) * (v - q[i]) / (q[i + 1] - q[i]))


def main():
    from backtest.all_books import machine_books, ndx_dip, news_book
    M = machine_books()
    idx = M[0].index
    news_all, ndx_all = news_book(), ndx_dip()
    news = news_all.reindex(idx).fillna(0.0)
    ndx = ndx_all.reindex(idx).fillna(0.0)
    news_from = news[news != 0].index[0]
    out = dict(made=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", source="backtest/scorecard_bands.py",
               span=f"{idx[0]:%Y-%m-%d} .. {idx[-1]:%Y-%m-%d}", levels=LEVELS, lengths=LENGTHS, books={})
    # every ordering on ITS OWN calendar (they differ by a day at the ends; adding a series indexed on another
    # ordering's days silently made a 2,401-day total next to 2,400-day books - run 2 died on it)
    nw = [news_all.reindex(x.index).fillna(0.0).to_numpy() for x in M]
    nd = [ndx_all.reindex(x.index).fillna(0.0).to_numpy() for x in M]
    tot = [x[list(NAMES)].sum(axis=1).to_numpy() + a + b for x, a, b in zip(M, nw, nd)]
    nf = [int(np.searchsorted(x.index, news_from)) for x in M]
    series = {nm: [x[src].to_numpy() for x in M] for src, nm in NAMES.items()}
    series["news"], series["ndx"] = nw, nd
    for nm, rs in series.items():
        out["books"][nm] = {str(n): band(np.concatenate([dollar_windows(r, t, n, nf[k] if nm == "news" else 0)
                                                          for k, (r, t) in enumerate(zip(rs, tot))]))
                            for n in LENGTHS}
    assert all(len(r) == len(t) for rs in series.values() for r, t in zip(rs, tot))
    out["total"] = {str(n): band(np.concatenate([windows(pd.Series(t), n, compound=True) for t in tot])) for n in LENGTHS}
    # self-check: the books' dollar stretches add up to the account's compounded stretch, ordering 0, 30 days
    chk = sum(dollar_windows(series[nm][0], tot[0], 30) for nm in series) - windows(pd.Series(tot[0]), 30, compound=True)
    assert np.abs(chk).max() < 1e-9, f"books do not add up to the account: {np.abs(chk).max()}"
    OUT.write_text(json.dumps(out, separators=(",", ":")))

    lines = [f"backtest/scorecard_bands.py, {out['made']}; {out['span']}; news from {news_from:%Y-%m-%d}",
             f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.0f} KB)", "",
             "MEDIAN / 5th / 25th / 75th / 95th percentile of a stretch, % of the account; idle = share with no P&L"]
    for n in (1, 7, 30, 90, 365):
        lines.append(f"  {n} days")
        for nm, b in list(out["books"].items()) + [("ACCOUNT", out["total"])]:
            q = dict(zip(LEVELS, b[str(n)]["q"]))
            lines.append(f"    {nm:<8} median {q[50] * 100:+7.2f}   5% {q[5] * 100:+7.2f}   25% {q[25] * 100:+7.2f}   "
                         f"75% {q[75] * 100:+7.2f}   95% {q[95] * 100:+7.2f}   idle {b[str(n)]['idle'] * 100:4.0f}%")
    # the registered checks, on the main account as it stood when they were written (8 days)
    live8 = dict(trend=-8.43 / 300, carry=-7.06 / 300)
    acct8 = 278.6 / 300 - 1
    p_acct = pctile(acct8, LEVELS, out["total"]["8"]["q"])
    p_tr = pctile(live8["trend"], LEVELS, out["books"]["trend"]["8"]["q"])
    p_ca = pctile(live8["carry"], LEVELS, out["books"]["carry"]["8"]["q"])
    idle = {k: out["books"][k]["8"]["idle"] for k in ("sleeve", "capit2", "news")}
    lines += ["", "REGISTERED PREDICTIONS (main account at 8 days)",
              f"  S1 account {acct8 * 100:+.1f}% -> percentile {p_acct:.1f} (3..15) -> {'RIGHT' if 3 <= p_acct <= 15 else 'WRONG'}",
              f"  S2 trend {live8['trend'] * 100:+.2f}% -> {p_tr:.1f} (< 25); carry {live8['carry'] * 100:+.2f}% -> {p_ca:.1f} (< 10) -> "
              f"{'RIGHT' if p_tr < 25 and p_ca < 10 else 'WRONG'}",
              f"  S3 idle share of 8-day stretches: " + ", ".join(f"{k} {v * 100:.0f}%" for k, v in idle.items())
              + f" (>= 30% each) -> {'RIGHT' if all(v >= 0.3 for v in idle.values()) else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
