"""REPLAYING THE CRASH-BID PAPER BOOK ON PAST CRASH HOURS, BOTH VENUES.

wick_paper.py computes each hour from 1-minute candles after it closes. Before it runs forward, this
feeds it real past hours - 2025-10-10 21:00 and the five non-BEAR holdout hours with the most fills
before the cap in the backtest (wick_5m.py) - with the backtest's own point-in-time top-40
for the month (the paper book's live universe function cannot rebuild a past month). It checks:
  1. BINANCE: does the paper book's code reproduce the backtest's kept fills and P&L on those hours?
     (1-minute bars instead of 5-minute: the fill set can differ only through the cap's order.)
  2. BITGET: what did the same 40 coins do on Bitget in those hours? Bitget's 1-minute history
     for 2025-10-10 had never been looked at (doc 15's Bitget check started 2025-10-24).

REGISTERED PREDICTION (2026-09-25, before running): Binance reproduces the backtest's kept fills
on each hour to within 2 fills and its hour P&L to within a fifth; on Bitget fewer bids fill on
2025-10-10 (shallower wicks) and the in-hour paper loss is smaller than Binance's.
OUTCOME (logs/wick_replay.txt): all six hours keep 10 fills on both venues (right). Hour P&L within
a fifth of the backtest on 3 of 6 (wrong on 3: -29%, -20%, -54%) - WHICH ten the cap keeps differs
between 1-minute order and the backtest's random 5-minute ties, and that moves an hour's P&L a lot;
the sign never differed. Bitget on 2025-10-10: 35 fills vs Binance 38, paper loss -16.0% vs -16.3%
(right, but barely: that night Bitget's wicks were nearly as deep). The 1-minute paper loss (-16.3%)
is deeper than the 5-minute backtest's (-15.8%), so wick_paper.py's H4 limit was set to -20%, not
-16%, before the book started.

    python -m backtest.wick_replay
"""
from __future__ import annotations

import pickle
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wick_paper as w  # noqa: E402
from backtest.crash_buy import CUT  # noqa: E402
from backtest.market_neutral import drop_non_crypto  # noqa: E402
from backtest.wick_5m import CACHE, per_fill  # noqa: E402
from backtest.wick_better import fills, load_all  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402


def main():
    XA, _, bear = load_all()
    ok = per_fill(fills(XA[XA.in40], k=0.10, skip_bear=bear), pickle.loads(CACHE.read_bytes()))
    ok = ok[ok.ok.astype(bool)]
    x = ok.assign(tie=np.random.default_rng(0).random(len(ok))).sort_values(["t", "minute", "tie"])
    kept = x[x.groupby("t").cumcount() < 10]
    hold = kept[kept.t >= CUT]
    first = pd.Timestamp("2025-10-10 21:00")
    n_all = ok[ok.t >= CUT].groupby("t").size().sort_values(ascending=False, kind="stable")
    hours = [first] + [t for t in n_all.index if t != first][:5]      # most UNCAPPED fills
    el = drop_non_crypto(eligibility(40))
    listed = w.bitget_listed()
    w.set_dir(Path(tempfile.mkdtemp()))
    print("hour               venue     coins fills kept   hour P&L   paper loss   | backtest (Binance, 5-min): kept, P&L")
    for t in hours:
        H = int(pd.Timestamp(t).value // 10**6)
        month, day = f"{t:%Y-%m}", f"{t:%Y-%m-%d}"
        coins = sorted(s for s, ms in el.items() if month in ms)
        st = w.fresh()
        st["universes"][month], st["labels"][day] = coins, "replay"
        w.process_hour(st, H, listed=listed)
        bt = hold[hold.t == t]
        bt_pnl = (bt["hour close"] * 300.0 / 40).sum()
        for v in w.VENUES:
            L = st["led"][v]
            print(f"{t:%Y-%m-%d %H:00}   {v:<8}{len(coins):>6}{L['fills']:>6}{L['kept']:>5}"
                  f"{L['equity'] - 300.0:>+10.2f}${L['worst_hour'] * 100:>+11.1f}%"
                  + (f"   | {len(bt)}, {bt_pnl:+.2f}$" if v == "binance" else ""))


if __name__ == "__main__":
    main()
