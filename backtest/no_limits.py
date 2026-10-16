"""NO CAPITAL LIMIT, LIQUIDATION MODELLED: how much leverage and how many slots do the PIT books want? (2026-10-16)

The user: "run every test on crypto with liquidation far away, more room to play, and the tests we didn't do because of
capital". The repo's backtests are percentage-based - capital never limited a TEST; it limited what could RUN (the pair
needs ~25,000 PKR, v3 ~100-150k PKR, pair_min_capital.py). What was held back was LEVERAGE and SLOT COUNT: pair_books.py
tried only 1x and 2x (at 2x the daily book fell 98%), 8 slots a book. Here, with capital unconstrained:
    LEVERAGE  1.0 / 1.25 / 1.5 / 1.75 / 2.0 / 3.0 - each position ISOLATED: liquidated (its margin lost) when its worst
              adverse move reaches 1/L - 0.56% (pair_books.curve's rule); otherwise its P&L x L
    SLOTS     8 / 12 / 16 / 24 per book (smaller positions, more of the signals taken)
BOOKS     the daily Bollinger trend book and the 4h capitulation book (tp5_nw, phase 0), both point-in-time top-40 with dead
          coins (pair_books.py), alone and as the pair (half each). No hindsight haircut (rule 5: PIT universe).
REPORTED  CAGR full / tune (to 2024-04-07) / holdout; worst fall (equity booked at close - intra-trade dips not marked,
          as in pair_books); worst month; liquidations.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. The pair's growth-optimal leverage is 1.0-1.5 on BOTH halves; at 2x its fall exceeds 60%.
    2. More slots lower the daily book's CAGR (the pump trades are diluted) and its fall; the capitulation book gains
       from more slots (it skips signals at 8).
    3. No leverage above 1.5 beats 1.0 on the holdout for the daily book.

RESULT (2026-10-16, logs/no_limits.txt) - all three predictions right.
    LEVERAGE: the DAILY trend book does not want it - holdout +32%/yr at 1x, +11% at 1.25x, +4% at 1.5x, -56% at 2x (its
    trades' worst moves liquidate 16 / 43 / 126 of 1,563 positions); the tune half's +147 -> +200% at 1.5x is the 2021
    bull. The CAPITULATION book does: 1-4 liquidations in 455 trades even at 3x; holdout +23 -> +50 -> +80%/yr at 1 / 2 /
    3x, but its tune half is flat at every leverage (-3..-10%) and its fall grows 35 -> 57 -> 72%. The pair: growth-optimal
    1.5x on the tune half, 1.0x on the holdout - stay at 1x.
    SLOTS (only possible with more capital): more, smaller positions trade return for a smaller fall - the pair at 1x
    8 / 12 / 16 / 24 slots: +50 / +46 / +41 / +31%/yr, fall 37 / 28 / 24 / 17%, worst month -12 / -9 / -8 / -8%.
    Return per point of fall rises with slots (1.35 -> 1.82). The daily book's holdout drops at 24 slots (+32 -> +18%).

    python -m backtest.no_limits
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.pair_books import curve  # noqa: E402

LOG = ROOT / "logs" / "no_limits.txt"
CUT = pd.Timestamp("2024-04-07")
LEVS = (1.0, 1.25, 1.5, 1.75, 2.0, 3.0)
SLOTS = (8, 12, 16, 24)


def daily_book():
    from backtest.capitulation_wide import funding_cum, hourly
    from backtest.rsi_factors import prep
    from backtest.tv_indicators import bars, indicators, own_exit
    from backtest.wide_book import eligibility
    el = eligibility(40)
    rows = []
    for s in sorted(k for k, m in el.items() if m):
        h = hourly(s)
        if h is None:
            continue
        d = bars(h, "1d", 0)
        if len(d) < 120:
            continue
        P = prep(d, np.full(len(d), np.nan))
        fc = funding_cum(s, d.time.to_numpy(), h)
        ent, exs = indicators(P)["bb"]
        ym, t = d.time.dt.strftime("%Y-%m").to_numpy(), d.time.to_numpy()
        free = 0
        for i in np.flatnonzero(np.nan_to_num(ent).astype(bool)):
            if i < 60 or i < free or i + 3 >= len(t) or ym[i] not in el[s]:
                continue
            j, net, worst = own_exit(i, np.nan_to_num(exs).astype(bool), P, fc, 30)
            rows.append((s, t[i + 1], t[min(j, len(t) - 1)], net, worst))
            free = j + 1
    D = pd.DataFrame(rows, columns=["coin", "t_in", "t_out", "net", "worst"])
    D["t_in"], D["t_out"] = pd.to_datetime(D.t_in), pd.to_datetime(D.t_out)
    return D


def st(eq):
    d = eq.resample("D").last().ffill()

    def cagr(x):
        if len(x) < 30 or x.iloc[0] <= 0:
            return np.nan
        yrs = (x.index[-1] - x.index[0]).days / 365
        return (x.iloc[-1] / x.iloc[0]) ** (1 / yrs) - 1 if x.iloc[-1] > 0 else -1.0
    mo = d.resample("ME").last().pct_change().dropna()
    return (cagr(d), cagr(d[d.index < CUT]), cagr(d[d.index >= CUT]), float((1 - d / d.cummax()).max()), mo.min())


def pair(ed, ec):
    idx = ed.index.union(ec.index)
    return (ed.reindex(idx).ffill().fillna(1.0) - 1) + (ec.reindex(idx).ffill().fillna(1.0) - 1) + 1


def main():
    D = daily_book()
    C = pd.read_csv(ROOT / "logs" / "capitulation_exits_trades.csv", parse_dates=["t_in", "t_out"])
    C = C[(C.exit == "tp5_nw") & (C.off == 0)]
    out = [f"backtest/no_limits.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; daily book {len(D)} trades, capitulation "
           f"{len(C)}; isolated liquidation at 1/L - 0.56%; holdout from {CUT:%Y-%m-%d}", "",
           f"  {'book':<14}{'lev':>5}{'slots':>6}{'CAGR':>8}{'tune':>8}{'holdout':>9}{'fall':>7}{'worst mo':>10}{'liq':>6}"]
    R = {}
    for lev in LEVS:
        liq = 1 / lev - 0.005 - 0.0006
        nl = {"daily": int((D.worst >= liq).sum()), "capit": int((C.worst >= liq).sum())}
        for slots in SLOTS:
            ed, ec = curve(D, lev, slots), curve(C, lev, slots)
            res = {"daily": st(ed), "capit": st(ec), "PAIR": st(pair(curve(D, lev, slots, .5), curve(C, lev, slots, .5)))}
            for nm, v in res.items():
                R[(nm, lev, slots)] = v
                out.append(f"  {nm:<14}{lev:>5.2f}{slots:>6}{v[0] * 100:>+7.0f}%{v[1] * 100:>+7.0f}%{v[2] * 100:>+8.0f}%"
                           f"{v[3] * 100:>6.0f}%{v[4] * 100:>+9.0f}%{nl.get(nm, nl['daily'] + nl['capit']):>6}")
        out.append("")
    best = {}
    for half, k in (("tune", 1), ("holdout", 2)):
        for nm in ("daily", "capit", "PAIR"):
            v = max((R[(nm, L, 8)][k], L) for L in LEVS)
            best[(nm, half)] = v[1]
            out.append(f"  growth-optimal leverage at 8 slots, {nm:<6} {half:<8}: {v[1]:.2f}x ({v[0] * 100:+.0f}%/yr)")
    p1 = best[("PAIR", "tune")] <= 1.5 and best[("PAIR", "holdout")] <= 1.5 and R[("PAIR", 2.0, 8)][3] > 0.60
    p2 = all(R[("daily", 1.0, s)][0] <= R[("daily", 1.0, 8)][0] for s in SLOTS[1:]) and \
        all(R[("capit", 1.0, s)][0] >= R[("capit", 1.0, 8)][0] for s in SLOTS[1:])
    p3 = all(R[("daily", L, 8)][2] <= R[("daily", 1.0, 8)][2] for L in LEVS if L > 1.5)
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 pair optimum 1.0-1.5 on both halves ({best[('PAIR', 'tune')]:.2f} / {best[('PAIR', 'holdout')]:.2f}), 2x fall > 60% "
            f"({R[('PAIR', 2.0, 8)][3] * 100:.0f}%) -> {'RIGHT' if p1 else 'WRONG'}",
            f"  2 more slots: daily CAGR down, capitulation up -> {'RIGHT' if p2 else 'WRONG'}",
            f"  3 no daily leverage > 1.5 beats 1.0 on the holdout -> {'RIGHT' if p3 else 'WRONG'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
