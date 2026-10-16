"""LIQUIDATION STRESS FOR THE FINAL MACHINE - every open position at its coin's worst price of every hour (2026-10-16)

final_confidence.py named liquidation the biggest real-money risk the backtests cannot see: they book at closes, and the
account (cross margin, gross cap 11.5x since 2026-10-16) would be closed inside an hour like 2025-10-10 21:00. The user:
"we can do something about it - we downloaded some data". We have every perp's HOURLY high / low since 2020 (dead coins
in) and joint_worst_hour.py's method: for each hour, put every open position at its coin's worst price of that hour
(low for longs, high for shorts) at the same time - harsher than reality, since coins do not all bottom in one minute.
BOOKS (ordering 0 / 1 / 2: trend seed, daily / capit2 phase and slot order)
    trend   the triple, joint_worst_hour.trend_frac (risk_300.sim_units; no 6.25x guard - the unguarded book reached
            12.2x, so this is harsher than the deployed book)
    bids    crash bids, top-40, none on BEAR days, cap 10 fills an hour, 1/40 each, each fill at its later 5-min low
            (wick_5m.per_fill), as in joint_worst_hour
    capit2  final_books: 8 slots of the whole account at 2x (and 1x for comparison); each taken trade's notional =
            L / 8 of the account, entered at its hour's open, marked at each hour's low until it closes
    daily   0.5 x 8 slots, the 20-day-mean exit, the same way
    left out: MN blend + carry (hedged long / short baskets: +2.3..+3.8% on the three crash days, crash_days.py; their
            risk is a short squeeze, handled by the +50% exit, worst week -29%, mn_combos.py) and the sleeve (flat then)
LIQUIDATION LINE: a cross-margin account is closed when what is left falls to the maintenance margin - ~1.5% of gross
    notional on Bitget's small tiers; at 11.5x that is 17% of the account. "left" = 1 + the sum of the books' worst-price
    losses in the hour, as a share of the account.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. The worst hour is 2025-10-10 21:00 in every ordering, for the full machine.
    2. capit2 at 2x makes that hour worse than at 1x by under 10 points (it rarely holds much on a crash hour's eve:
       it buys AFTER a capitulation).
    3. The full machine keeps more than the 17% liquidation line in every ordering, but under 50% in at least one.

RESULT (2026-10-16, logs/liq_stress.txt) - NO hour since 2020 crosses the 17% line; capit2 at 2x is the new tail.
    Deployed machine, worst hour left (ordering 0 / 1 / 2): 41% (2025-10-10 21:00: trend -38, bids -15, daily -6) / 29%
    (2021-12-04 05:00: capit2 -54, daily -14) / 50% (2025-02-03 02:00: capit2 -62). capit2 2x alone: 69 / 32 / 38% - in
    a cascade its buys keep falling (2021-05-19 13:00: -68% of the account at the hour's lows). Predictions: 1 wrong (the
    worst hour moves with capit2), 2 wrong (2x costs 0 / 27 / 24 points vs 1x), 3 right (above 17%, under 50%).

    python -m backtest.liq_stress
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.dd_fixes as D  # noqa: E402
from backtest import blend  # noqa: E402
from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402
from backtest import machine_combos as mc  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.capitulation_wide import hourly  # noqa: E402
from backtest.joint_worst_hour import trend_frac  # noqa: E402
from backtest.wick_5m import CACHE, per_fill  # noqa: E402
from backtest.wick_better import fills, load_all  # noqa: E402

LOG = ROOT / "logs" / "liq_stress.txt"
LIQ = 0.015 * 11.5


def book_worst(T, taken, grid, notional, Hc):
    """Per hour, the sum over open positions of notional x (hour low / entry - 1) - a long book's worst-price loss."""
    gi = grid.asi8
    out = np.zeros(len(grid))
    tin = T.t_in.to_numpy("datetime64[ns]").astype("int64")
    tout = T.t_out.to_numpy("datetime64[ns]").astype("int64")
    coins = T.coin.to_numpy()
    for q in taken:
        c = coins[q]
        if c not in Hc:
            Hc[c] = hourly(c)
        h = Hc[c]
        if h is None:
            continue
        hi = pd.DatetimeIndex(h.time).as_unit("ns").asi8
        a, b = np.searchsorted(hi, tin[q], "left"), np.searchsorted(hi, tout[q], "left")
        if b <= a:
            continue
        e = float(h.open.iloc[a])
        loss = notional * (h.low.to_numpy()[a:b + 1] / e - 1)
        ga = np.searchsorted(gi, hi[a:b + 1])
        m = ga < len(grid)
        np.add.at(out, ga[m], np.minimum(loss[m], 0.0))
    return out


def main():
    px = {}
    for c in blend.BOOK:
        d = blend.load(c)
        if d is not None:
            px[c] = d.set_index(pd.DatetimeIndex(d["time"]).as_unit("ns"))[["high", "low", "close"]]
    grid = pd.date_range(min(p.index[0] for p in px.values()), max(p.index[-1] for p in px.values()), freq="h").as_unit("ns")
    H = {c: p.reindex(grid).ffill() for c, p in px.items()}
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    rows = D.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    XA, _, bear_day = load_all()
    ok = per_fill(fills(XA[XA.in40], k=0.10, skip_bear=bear_day), pickle.loads(CACHE.read_bytes()))
    ok = ok[ok.ok.astype(bool)]
    x = ok.assign(tie=np.random.default_rng(0).random(len(ok))).sort_values(["t", "minute", "tie"])
    y = x[x.groupby("t").cumcount() < 10]
    w = y.groupby("t").after.sum() / 40
    w.index = pd.DatetimeIndex(w.index).as_unit("ns")
    bids = w.reindex(grid).fillna(0.0).to_numpy()
    Hc = {}
    dT = {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES}
    cT = {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER)) for off in cc.PHASES}
    out = [f"backtest/liq_stress.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; hourly grid {grid[0]:%Y-%m-%d} .. {grid[-1]:%Y-%m-%d}; "
           f"every open position at its coin's worst price of the hour; liquidation line {LIQ:.0%} left", "",
           "  account LEFT in the worst hour (and when), by what is on the account"]
    R = {}
    for sd in (0, 1, 2):
        tr = trend_frac(rows, bn, bv, sd, grid, H).to_numpy()
        doff, coff = dc.PHASES[sd % 3], cc.PHASES[sd % 4]
        dtk = [q for q, _, _ in dc.allocate(dT[doff], sd)]
        ctk = {L: [q for q, _, _ in dc.allocate(cT[coff].assign(units=None), sd, L)] for L in (1.0, 2.0)}
        daily = book_worst(dT[doff], dtk, grid, 0.5 / 8, Hc)
        cap = {L: book_worst(cT[coff], ctk[L], grid, L * 1.0 / 8, Hc) for L in (1.0, 2.0)}
        combos = {"trend alone": tr, "trend + bids": tr + bids, "trend + bids + daily": tr + bids + daily,
                  "FULL, capit2 1x": tr + bids + daily + cap[1.0], "FULL, capit2 2x (deployed)": tr + bids + daily + cap[2.0],
                  "capit2 2x alone": cap[2.0], "daily alone": daily}
        out.append(f"\n  ordering {sd}")
        for nm, v in combos.items():
            left = 1 + v
            i = int(np.argmin(left))
            R[(sd, nm)] = (left[i], grid[i], left)
            out.append(f"    {nm:<30}{left[i] * 100:>6.0f}%  {grid[i]:%Y-%m-%d %H:00}   hours under 50%: {(left < 0.5).sum():>3}, "
                       f"under the line: {(left < LIQ).sum():>2}")
        full = combos["FULL, capit2 2x (deployed)"]
        o = np.argsort(full)[:5]
        out.append("    the 5 worst hours, deployed: " + ", ".join(f"{grid[i]:%Y-%m-%d %H:00} {(1 + full[i]) * 100:.0f}% "
                   f"(trend {tr[i] * 100:+.0f}, bids {bids[i] * 100:+.0f}, daily {daily[i] * 100:+.0f}, capit2 {cap[2.0][i] * 100:+.0f})"
                   for i in o))
    fk = "FULL, capit2 2x (deployed)"
    p1 = all(R[(sd, fk)][1] == pd.Timestamp("2025-10-10 21:00") for sd in (0, 1, 2))
    p2 = all(R[(sd, "FULL, capit2 1x")][0] - R[(sd, fk)][0] < 0.10 for sd in (0, 1, 2))
    p3 = all(R[(sd, fk)][0] > LIQ for sd in (0, 1, 2)) and any(R[(sd, fk)][0] < 0.5 for sd in (0, 1, 2))
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 worst hour 2025-10-10 21:00 in every ordering: {[f'{R[(sd, fk)][1]:%Y-%m-%d %H:00}' for sd in (0, 1, 2)]} -> {'RIGHT' if p1 else 'WRONG'}",
            f"  2 capit2 2x worse than 1x by < 10 points: {[round((R[(sd, 'FULL, capit2 1x')][0] - R[(sd, fk)][0]) * 100, 1) for sd in (0, 1, 2)]} -> "
            f"{'RIGHT' if p2 else 'WRONG'}",
            f"  3 above the line everywhere, under 50% somewhere: {[round(R[(sd, fk)][0] * 100) for sd in (0, 1, 2)]} -> {'RIGHT' if p3 else 'WRONG'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
