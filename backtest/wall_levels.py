"""TOP-15 LEVELS OF THE BITGET DOGE BOOK, EVERY SECOND (data preparation for backtest/wall_persistence.py).

backtest/book_hist.py rebuilds the book from the exchange's update stream and keeps only the touch (cache grid_<day>.pkl). The wall study needs
the depth, so this runs the SAME validated rebuild (`book_hist.rebuild`) with a different row function: per second, the best 15 price levels of
each side as (price, quantity). 15 because on the five 'snapshot' days (2025-03 .. 2026-03) the stream carries only the top 15 levels
(CLAUDE.md s10, 2026-10-28); the two real update-stream days (2026-06-01, 2026-09-01) are cut to the same 15 so every day is measured alike.

Columns: t (ms), bp1..bp15, bq1..bq15 (bids, best first), ap1..ap15, aq1..aq15 (asks, best first); a missing level is NaN / 0.

    python -m backtest.wall_levels 2025-03-01 2025-06-01 ...      builds strategy_analysis/data/book_hist/levels_<day>.pkl (git-ignored)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import book_hist as bh  # noqa: E402

K = 15
COLS = (["t"] + [f"bp{i}" for i in range(1, K + 1)] + [f"bq{i}" for i in range(1, K + 1)]
        + [f"ap{i}" for i in range(1, K + 1)] + [f"aq{i}" for i in range(1, K + 1)])


def level_row(bt: list, at: list, bids: dict, asks: dict) -> tuple:
    """Same signature as book_hist.feat_row: bt / at = the best 20 (price, qty) pairs of each side, best first."""
    nan = float("nan")
    b = (list(bt[:K]) + [(nan, 0.0)] * K)[:K]
    a = (list(at[:K]) + [(nan, 0.0)] * K)[:K]
    return (tuple(p for p, _ in b) + tuple(q for _, q in b) + tuple(p for p, _ in a) + tuple(q for _, q in a))


def levels_for(day: str, force: bool = False):
    pk = bh.CACHE / f"levels_{day}.pkl"
    if pk.exists() and not force:
        return pd.read_pickle(pk)
    keep = bh.feat_row, bh.GRID_COLS
    bh.feat_row, bh.GRID_COLS = level_row, COLS
    try:
        g, st = bh.rebuild(bh.DATA / f"{day}_incremental_book_L2.csv.gz")
    finally:
        bh.feat_row, bh.GRID_COLS = keep
    out = (g, st)
    pd.to_pickle(out, pk)
    return out


if __name__ == "__main__":
    for d in sys.argv[1:]:
        g, st = levels_for(d)
        print(d, len(g), "seconds", st, flush=True)
