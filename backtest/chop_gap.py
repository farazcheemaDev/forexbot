"""THE SIDEWAYS GAP, MEASURED ON THE MACHINE THAT RUNS NOW (2026-10-18)

The user: "we don't have a bot for choppy markets ... try everything, we have something for every situation, we need to
fill this gap too". Doc 20's "typical sideways month -4.5%" was measured on machine v2 (trend + MN + sleeve + bids).
The running final machine has 9 books (trend 6.25x guard, MN blend, carry x0.5, sleeve, daily x0.5, capit2 1.0 x 2x,
news, NASDAQ dip; the crash bids are not in it). Nobody has measured IT by market type. This file does, book by book.

    months     labelled by the BTC regime most of their days carried (market_neutral.btc_regime: BTC vs its 50-day
               mean and that mean's 20-day slope, +-2% - the same labels as doc 14 / doc 20 and the bear sleeve)
    a book's   its DOLLAR P&L in the month as a share of the account at the month's start (they add up to the
    month      account's month: scorecard_bands.dollar_windows' rule); 10 orderings pooled; trend gains shrunk
    reported   per regime: months, the account's average / typical (median) month, months up, worst month; each
               book's average and typical contribution; and the account WITHOUT the trend book (what the rest earns)

REGISTERED BEFORE THE RUN (2026-10-18)
    C1 the 9-book machine's typical SIDEWAYS month is still negative but better than doc 20's -4.5%: between -3.5%
       and 0%.
    C2 in sideways months the trend book is the drag (typical contribution below -2%); news, capit2 and NASDAQ dip
       each average above 0.
    C3 sideways months up: between 35% and 50% (doc 20: 32%).

RESULT (2026-10-18, logs/chop_gap.txt) - C1 / C2 / C3 all RIGHT. 25 sideways months: the 9-book machine's typical
sideways month -2.1% (doc 20's v2: -4.5%), average +10.3%, 44% up; WITHOUT the trend book +7.8% typical. Every other book
averages >= 0 in sideways months (MN +4.5, daily +3.6, news +2.3, capit2 +2.2, ndx +1.4, carry +0.9; sleeve -0.8); the
trend book's typical sideways month is -7.3%. The gap is the trend book, and its worst sideways months (2023-10, 2024-02)
came right before bull runs.

    python -m backtest.chop_gap
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "chop_gap.txt"
NAMES = {"trend": "trend", "mn_blend": "mn", "carry": "carry", "sleeve": "sleeve", "daily": "daily",
         "capit2": "capit2"}
BOOKS = ["trend", "mn", "carry", "sleeve", "daily", "capit2", "news", "ndx"]


def machine():
    """Every ordering's daily book returns on its own calendar (scorecard_bands' fix) + the daily BTC regime."""
    from backtest.all_books import machine_books, ndx_dip, news_book
    from backtest.market_neutral import btc_regime, load_panel
    M = machine_books()
    nw, nd = news_book(), ndx_dip()
    out = []
    for x in M:
        d = pd.DataFrame({nm: x[src] for src, nm in NAMES.items()})
        d["news"] = nw.reindex(x.index).fillna(0.0)
        d["ndx"] = nd.reindex(x.index).fillna(0.0)
        out.append(d)
    C, _, _ = load_panel()
    return out, btc_regime(C)


def monthly(d: pd.DataFrame) -> pd.DataFrame:
    """Each book's dollar P&L per calendar month as a share of the account at the month's start, + the account's."""
    R = d[BOOKS].sum(axis=1)
    E = (1 + R).cumprod()
    Eprev = E.shift(1).fillna(1.0)
    dollars = d[BOOKS].mul(Eprev, axis=0)
    start = Eprev.groupby(d.index.to_period("M")).first()
    m = dollars.groupby(d.index.to_period("M")).sum().div(start, axis=0)
    m["account"] = m[BOOKS].sum(axis=1)
    m["no_trend"] = m[[b for b in BOOKS if b != "trend"]].sum(axis=1)
    return m


def month_labels(reg: pd.Series) -> pd.Series:
    return reg.groupby(reg.index.to_period("M")).agg(lambda s: s.value_counts().idxmax())


def table(P: pd.DataFrame, lines: list):
    lines.append(f"   {'market':<9}{'months':>7}{'average':>9}{'typical':>9}{'up':>6}{'worst':>8}{'  no-trend typ':>15}")
    for g in ("bull", "chop", "bear"):
        x = P[P.reg == g]
        n = x.month.nunique()
        a = x.account
        lines.append(f"   {g:<9}{n:>7}{a.mean() * 100:>+8.1f}%{a.median() * 100:>+8.1f}%{(a > 0).mean() * 100:>5.0f}%"
                     f"{a.min() * 100:>+7.1f}%{x.no_trend.median() * 100:>+13.1f}%")
    lines.append("")
    lines.append(f"   book contribution, average / typical month (% of the account at the month's start)")
    lines.append("   " + " " * 9 + "".join(f"{b:>15}" for b in BOOKS))
    for g in ("bull", "chop", "bear"):
        x = P[P.reg == g]
        lines.append(f"   {g:<9}" + "".join(f"{x[b].mean() * 100:>+7.1f}/{x[b].median() * 100:>+5.1f}%" for b in BOOKS))


def main():
    Ms, reg = machine()
    lab = month_labels(reg)
    parts = []
    for k, d in enumerate(Ms):
        m = monthly(d)
        m = m.iloc[1:-1]                                  # drop the partial first / last month
        m["reg"] = lab.reindex(m.index).to_numpy()
        m["order"], m["month"] = k, m.index.astype(str)
        parts.append(m)
    P = pd.concat(parts).dropna(subset=["reg"])
    lines = [f"backtest/chop_gap.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; "
             f"{P.month.min()} .. {P.month.max()}, 10 orderings pooled; trend gains shrunk, the rest raw", "",
             "1. THE 9-BOOK MACHINE BY MARKET (month labelled by the BTC regime most of its days carried)"]
    table(P, lines)
    news_live = P.month >= "2021-12"
    lines += ["", "2. THE SAME, ONLY MONTHS SINCE THE NEWS BOOK HAS DATA (2021-12 on)"]
    table(P[news_live], lines)
    ch = P[P.reg == "chop"]
    lines += ["", "3. SIDEWAYS MONTHS ONE BY ONE (median over orderings, % of the account)",
              f"   {'month':<9}{'account':>9}" + "".join(f"{b:>8}" for b in BOOKS)]
    for mo, x in ch.groupby("month"):
        med = x[BOOKS + ["account"]].median()
        lines.append(f"   {mo:<9}{med.account * 100:>+8.1f}%" + "".join(f"{med[b] * 100:>+7.1f}%" for b in BOOKS))
    typ = ch.account.median()
    up = (ch.account > 0).mean()
    tr_typ = ch.trend.median()
    avgs = {b: ch[b].mean() for b in ("news", "capit2", "ndx")}
    lines += ["", "REGISTERED PREDICTIONS",
              f"  C1 typical sideways month {typ * 100:+.1f}% (-3.5 .. 0) -> {'RIGHT' if -0.035 <= typ <= 0 else 'WRONG'}",
              f"  C2 trend typical {tr_typ * 100:+.1f}% (< -2); averages news {avgs['news'] * 100:+.2f} capit2 "
              f"{avgs['capit2'] * 100:+.2f} ndx {avgs['ndx'] * 100:+.2f} (> 0) -> "
              f"{'RIGHT' if tr_typ < -0.02 and all(v > 0 for v in avgs.values()) else 'WRONG'}",
              f"  C3 sideways months up {up * 100:.0f}% (35 .. 50) -> {'RIGHT' if 0.35 <= up <= 0.50 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)
    P.to_pickle(ROOT / "logs" / "chop_gap_months.pkl")


if __name__ == "__main__":
    main()
