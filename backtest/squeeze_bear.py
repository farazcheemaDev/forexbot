"""SELLING SQUEEZE SPIKES IN BEAR MARKETS - the crash bids' mirror, where it has a reason to work.

doc 15: resting SELLS 10% above the last close, sold back at the fill hour's close, made ~0 across
all markets (crash_buy.py: sell side). But the crash bids themselves only work OUTSIDE bears
(wick_better.py: bear-day wicks +0.12% a fill) because in a bear a wick is continuation. The mirror
logic: in a BEAR market a sudden 10% hourly spike is forced short-covering against the trend, and
bear rallies fade (doc 13's breadth sleeve shorts exactly those). So the mirror might work ONLY on
BEAR days. Fills: every PIT top-40 perp, dead coins included, a resting sell k above the previous
close, filled only when the high goes 0.1% through it, at max(level, open); covered at the fill
hour's close (and +4h / +24h shown); 8bp fees + 30bp slippage; the BTC label as in wick_better.

REGISTERED PREDICTION (2026-09-25, before running): on BEAR days sells at 10% make +1% or more a fill
at the hour's close on both halves; on other days ~0 or negative; the worst single fill is -50% or
worse (a squeeze that keeps going), so a book would need the same kind of cap as the bids.

    python -m backtest.squeeze_bear
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.crash_buy import CUT, fills_for, load_1h  # noqa: E402
from backtest.market_neutral import drop_non_crypto  # noqa: E402
from backtest.wick_better import load_all  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

COST = 8e-4 + 0.003


def main():
    _, reg, _ = load_all()
    el = drop_non_crypto(eligibility(40))
    rows = []
    for s in sorted(x for x, ms in el.items() if ms):
        d = load_1h(s)
        if d is not None:
            rows += fills_for(s, d, el[s], d.time.iloc[0], "sell")
    F = pd.DataFrame(rows)
    F["regime"] = F.t.dt.normalize().map(reg).fillna("?")
    print(f"{len(F)} sell fills (all k), top-40 PIT, dead coins included; per fill after 38bp\n")
    print(f"  {'k':>4} {'regime':<6}{'fills':>7}{'close: all':>12}{'tune':>8}{'hold':>8}{'losing':>8}{'worst':>8}"
          f"{'+4h':>8}{'+24h':>8}")
    for k in (0.10, 0.15, 0.20):
        for rg in ("bear", "chop", "bull"):
            x = F[(F.k == k) & (F.regime == rg)]
            if not len(x):
                continue
            n = x["close"] - COST
            tu, ho = x[x.t < CUT], x[x.t >= CUT]
            print(f"  {k*100:>3.0f}% {rg:<6}{len(x):>7}{n.mean()*100:>+11.2f}%{(tu['close'] - COST).mean()*100:>+7.2f}%"
                  f"{(ho['close'] - COST).mean()*100:>+7.2f}%{(n < 0).mean()*100:>7.0f}%{n.min()*100:>+7.0f}%"
                  f"{(x['x4h'] - COST).mean()*100:>+7.2f}%{(x['x24h'] - COST).mean()*100:>+7.2f}%")
    b = F[(F.k == 0.10) & (F.regime == "bear")]
    print("\n  BEAR, 10%: by year (close exit): " + "  ".join(
        f"{y}: {(g['close'] - COST).mean()*100:+.2f}% ({len(g)})" for y, g in b.groupby(b.t.dt.year)))
    print("  the 5 worst:", ", ".join(f"{r.t:%Y-%m-%d %H:00} {r.sym} {(r.close - COST)*100:+.0f}%"
                                      for r in b.nsmallest(5, "close").itertuples()))


if __name__ == "__main__":
    main()
