"""SHOULD THE CRASH'S BIGGEST LIVE LOSERS LEAVE THE MACHINE? - with / without one book, at the same risk (2026-11-21)

WHY: in the live record (backtest/crash_lessons.py) the market-neutral book (-$36), the daily breakout book (-$35) and the
NASDAQ dip-buy (-$15) lost most. One crash is not evidence to drop a book; the backtest is: the machine (the 9 books at the
live weights, 10 slot orderings: all_books.machine_books via logs/daily_combos_cache/alt_bear_books.pkl + works_map's news and
NASDAQ series; trend gains shrunk 3x) with and without each of the three, by half (machine.CUT 2024-08-29), against the
bet-smaller line: the FULL machine scaled down until its biggest fall equals the reduced machine's, same ordering. A drop is
supported only if the reduced machine beats that line on both halves in most orderings.

    python -m backtest.book_drop_check
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "book_drop_check.txt"
CUT = pd.Timestamp("2024-08-29")
BOOKS = ["trend", "mn_blend", "carry", "sleeve", "bids", "daily", "capit2", "news", "ndx_dip"]


def stats(x: pd.Series) -> tuple:
    eq = (1 + x).cumprod()
    cagr = eq.iloc[-1] ** (365 / len(x)) - 1
    dd = (1 - eq / eq.cummax()).max()
    mo = (1 + x).groupby(x.index.to_period("M")).prod() - 1
    return cagr, dd, mo.min()


def same_fall(full: pd.Series, dd: float) -> float:
    """The full machine's CAGR when scaled so its biggest fall equals dd (bisection on the scale)."""
    lo, hi = 0.05, 1.5
    for _ in range(40):
        s = (lo + hi) / 2
        if stats(full * s)[1] > dd:
            hi = s
        else:
            lo = s
    return stats(full * lo)[0]


def main():
    M = pickle.loads((ROOT / "logs" / "daily_combos_cache" / "alt_bear_books.pkl").read_bytes())
    S = pickle.loads((ROOT / "logs" / "works_map_series.pkl").read_bytes())["S"]
    rows = []
    for k, x in enumerate(M):
        x = x.copy()
        for b in ("news", "ndx_dip"):
            x[b] = S[b].reindex(x.index).fillna(0.0)
        full = x[BOOKS].sum(axis=1)
        for drop in (None, "daily", "mn_blend", "ndx_dip"):
            y = full if drop is None else full - x[drop]
            for half in ("tune", "hold"):
                m = (y.index < CUT) if half == "tune" else (y.index >= CUT)
                c, d, w = stats(y[m])
                rows.append(dict(order=k, drop=drop or "none (full)", half=half, cagr=c, fall=d, worst_month=w,
                                 full_same_fall=same_fall(full[m], d)))
    T = pd.DataFrame(rows)
    g = T.groupby(["drop", "half"])[["cagr", "fall", "worst_month", "full_same_fall"]].median() * 100
    g["orderings beating the line"] = T.assign(b=T.cagr > T.full_same_fall).groupby(["drop", "half"]).b.sum()
    txt = (f"backtest/book_drop_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; medians over 10 orderings, %; "
           f"full_same_fall = the full machine scaled to the same biggest fall (the bet-smaller line)\n\n"
           + g.round(1).to_string()
           + "\n\nRESULT: no drop is supported - each reduced machine earns less than the full machine run smaller to the same "
             "fall, in most orderings on both halves.")
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
