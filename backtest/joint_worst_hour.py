"""THE WORST HOUR FOR THE WHOLE ACCOUNT: the trend book and the wick bids caught in the same crash.

risk_300.py part C replayed the trend book hour by hour with every open unit at its coin's worst price
of the hour: the worst hour left 62% of the account (2025-10-10 21:00, ordering 0). wick_5m.py found
that the wick bids fill in exactly those hours and keep falling after the fill: on 2025-10-10 21:00
the top-40 book's paper loss, every fill at its low at once, was -52% of the account at x1. Both are
losses on the SAME account (cross margin), so the question that decides the wick book's size is the
sum: how much of the account is left in the worst hour of the two together?

   left(h) = 1 + trend worst-price loss(h) / account + wick paper loss(h) / account

for 3 orderings of the trend book, and the wick book (top-40, skip BEAR days, 1/40 per bid) with no
cap, and with the remaining bids cancelled after the first 20 / 10 / 5 fills in the hour (fills taken
in their 5-minute order, ties by ordering 0). The market-neutral book and the sleeve are left out:
the MN book made +2.3 / +3.8 / +2.5% on the three crash days (crash_days.py), and the sleeve was flat.

REGISTERED PREDICTION (2026-09-24, before running): the joint worst hour is 2025-10-10 21:00 in
every ordering; ordering 0 leaves ~10-15% of the account with no cap (a near wipe-out: at ~2x
notional on 10% equity the exchange would liquidate), ~30% with cap 20, ~45% with cap 10.

    python -m backtest.joint_worst_hour
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.dd_fixes as D  # noqa: E402
from backtest import blend  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.risk_300 import sim_units  # noqa: E402
from backtest.wick_5m import CACHE, per_fill  # noqa: E402
from backtest.wick_better import fills, load_all  # noqa: E402


def trend_frac(rows, bn, bv, sd, grid, H):
    """Account left if every open trend unit sat at its coin's worst price of the hour (risk_300 part C)."""
    pts, units = sim_units(rows, bn, bv, sd)
    real = pd.Series([e for _, e in pts], index=pd.DatetimeIndex([t for t, _ in pts]).as_unit("ns"))
    real = real[~real.index.duplicated(keep="last")].reindex(grid, method="ffill").fillna(1.0).to_numpy()
    worst = np.zeros(len(grid))
    gi = grid.asi8
    for coin, side, t_open, t_close, e, q in units:
        if coin not in H:
            continue
        a, b = np.searchsorted(gi, t_open, side="left"), np.searchsorted(gi, t_close, side="left")
        if b <= a:
            continue
        h = H[coin]
        worst[a:b] += q * ((h["low"].to_numpy()[a:b] - e) if side == "long" else (e - h["high"].to_numpy()[a:b]))
    return pd.Series(worst / real, index=grid)


def main():
    px = {}
    for c in blend.BOOK:
        d = blend.load(c)
        if d is not None:
            px[c] = d.set_index(pd.DatetimeIndex(d["time"]).as_unit("ns"))[["high", "low", "close"]]
    grid = pd.date_range(min(p.index[0] for p in px.values()), max(p.index[-1] for p in px.values()),
                         freq="h").as_unit("ns")
    H = {c: p.reindex(grid).ffill() for c, p in px.items()}
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    rows = D.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))

    XA, _, bear_day = load_all()
    ok = per_fill(fills(XA[XA.in40], k=0.10, skip_bear=bear_day), pickle.loads(CACHE.read_bytes()))
    ok = ok[ok.ok.astype(bool)]
    x = ok.assign(tie=np.random.default_rng(0).random(len(ok))).sort_values(["t", "minute", "tie"])
    wick = {}
    for K in (999, 20, 10, 5):
        y = x[x.groupby("t").cumcount() < K]
        w = y.groupby("t").after.sum() / 40
        w.index = pd.DatetimeIndex(w.index).as_unit("ns")
        wick[K] = w.reindex(grid).fillna(0.0)

    print("Account left in the worst hour, trend book + wick bids together (each at its worst price of the hour)\n")
    print(f"  {'':<22}{'trend alone':>22}" + "".join(f"{('+ wicks, no cap' if K == 999 else f'+ wicks, cap {K}'):>26}"
                                                     for K in wick))
    for sd in (0, 1, 2):
        tf = trend_frac(rows, bn, bv, sd, grid, H)
        cells = [f"{(1 + tf.min())*100:>5.0f}% {tf.idxmin():%Y-%m-%d %H:00}"]
        for K, w in wick.items():
            j = 1 + tf + w
            cells.append(f"{j.min()*100:>5.0f}% {j.idxmin():%Y-%m-%d %H:00}")
        print(f"  ordering {sd:<13}" + "".join(f"{c:>26}" for c in cells))
        for day in ("2021-05-19", "2025-10-10"):
            m = (grid >= pd.Timestamp(day)) & (grid < pd.Timestamp(day) + pd.Timedelta(days=1))
            print(f"    {day}: trend alone {(1 + tf[m].min())*100:.0f}%, " + ", ".join(
                f"{'no cap' if K == 999 else f'cap {K}'} {(1 + tf[m] + w[m]).min()*100:.0f}%" for K, w in wick.items()))


if __name__ == "__main__":
    main()
