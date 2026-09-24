"""PROFITING FROM CRASHES WITHOUT PREDICTING THEM: resting bids far below the price.

Asked 2026-09-24: "how can we benefit from crashes then, there must be something". crash_days.py
showed the book cannot short a crash (it would have to be short BEFORE it). The other side of a
crash is the forced seller. cascade_redux.py (doc 11) killed the TAKER version on 4 years of 5-minute
data - buying at the bar close after a liquidation cascade nets -3 to +2bp - and its own docstring
named the one route left: "maker entry would be the only route". A resting limit bid, placed in
advance, is filled AT the wick instead of after it. That has never been tested here.

A. WICK BIDS. Every hour, on every PIT top-40 perp (dead coins included), a resting buy k% below the
   previous hour's close, k = 10 / 15 / 20 / 30. FILLED only if the hour's low goes 0.1% THROUGH the
   bid (a touch does not fill a queued limit order); fill at min(bid, open) (a gap opens below it).
   Exits: the fill hour's close; +4h; +24h; or a take-profit at +k/2 inside 24h, else +24h.
   A coin whose data ends exits at its last print. Costs: 2bp maker in + 6bp taker out (Bitget),
   and again at 12bp. The mirror (resting SELLS k% above: squeezes) is run too.
B. As a PORTFOLIO: each fill takes f of equity (entry-sized), all coins at once, total exposure
   capped at 100% of equity - because a crash fills dozens of bids in the same hour.
C. Checks: tune/holdout (2024-08-29), by year, the share of profit from the three biggest crash
   days, the worst fills (coins that kept falling or died), and a glitch check on the top fills.

REGISTERED PREDICTION (2026-09-24, before running): bids at 10-15% below make +2% to +4% per fill by
the fill hour's close and less by +24h; a handful of crash days carry most of the profit; dying coins
cost -50% or worse on their fills; as a portfolio +5% to +15% a year, positive on both halves but on
few events. The mirror (selling spikes) loses: squeezes continue (doc 13's carry test).

    python -m backtest.crash_buy
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.market_neutral import drop_non_crypto  # noqa: E402
from backtest.wide_book import DATA, MIN_AGE_D, eligibility  # noqa: E402

CUT = pd.Timestamp("2024-08-29")
KS = (0.10, 0.15, 0.20, 0.30)
PEN = 0.001
FEES = {"8bp (maker in, taker out)": 8e-4, "12bp": 12e-4}


def load_1h(sym):
    p = DATA / f"{sym}_1h.csv.gz"
    if not p.exists():
        return None
    d = pd.read_csv(p, usecols=["time", "open", "high", "low", "close"])
    d["time"] = pd.to_datetime(d["time"]).astype("datetime64[ns]")
    d = d[(d.close > 0) & (d.low > 0)].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return d if len(d) > 800 else None


def fills_for(sym, d, months, first, side):
    """Every fill of a resting order k% away from the previous close, with its exits."""
    o, h, l, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    t = d["time"].to_numpy()
    m = pd.DatetimeIndex(t).strftime("%Y-%m").to_numpy()
    ok = np.array([mm in months for mm in m]) & ((pd.DatetimeIndex(t) - first).days >= MIN_AGE_D)
    n = len(c)
    out = []
    for k in KS:
        prev = np.r_[np.nan, c[:-1]]
        if side == "buy":
            lvl = prev * (1 - k)
            hit = (l < lvl * (1 - PEN)) & ok
        else:
            lvl = prev * (1 + k)
            hit = (h > lvl * (1 + PEN)) & ok
        for i in np.flatnonzero(hit):
            fill = min(lvl[i], o[i]) if side == "buy" else max(lvl[i], o[i])
            sgn = 1 if side == "buy" else -1
            ex = {}
            for lab, j in (("close", i), ("x4h", i + 4), ("x24h", i + 24)):
                ex[lab] = sgn * (c[min(j, n - 1)] / fill - 1)
            # take-profit at k/2 inside 24h (the fill hour's own later prices excluded: order unknown)
            tp = fill * (1 + sgn * k / 2)
            seg_h, seg_l = h[i + 1:min(i + 25, n)], l[i + 1:min(i + 25, n)]
            hitp = np.flatnonzero(seg_h >= tp) if side == "buy" else np.flatnonzero(seg_l <= tp)
            ex["tp"] = sgn * k / 2 if len(hitp) else ex["x24h"]
            out.append(dict(sym=sym, t=pd.Timestamp(t[i]), k=k, side=side, gap=float(fill / prev[i] - 1),
                            dead=bool(i + 24 >= n - 1), **ex))
    return out


def portfolio(F, k, exit_lab, f, fee):
    """Entry-sized: each fill takes f of equity at its fill hour; exposure capped at 100%;
    P&L booked at the exit hour. Returns the daily equity curve."""
    x = F[(F.k == k)].sort_values("t")
    hold = {"close": 1, "x4h": 4, "x24h": 24, "tp": 24}[exit_lab]
    ev = []
    for _, r in x.iterrows():
        ev.append((r.t, 1, r[exit_lab] - fee))
        ev.append((r.t + pd.Timedelta(hours=hold), 0, None))
    eq, open_amt, pts, book = 1.0, [], [], []
    for r in x.itertuples():
        # close every position whose exit time has passed, then open this one
        book.sort(key=lambda z: z[0])
        while book and book[0][0] <= r.t:
            _, amt, ret = book.pop(0)
            eq += amt * ret; pts.append((r.t, eq))
        used = sum(z[1] for z in book)
        amt = min(f * eq, max(eq - used, 0.0))
        if amt <= 0:
            continue
        book.append((r.t + pd.Timedelta(hours=hold), amt, getattr(r, exit_lab) - fee))
    for tt, amt, ret in sorted(book):
        eq += amt * ret; pts.append((tt, eq))
    if not pts:
        return None
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    return s[~s.index.duplicated(keep="last")].resample("D").last().ffill()


def main():
    elig = drop_non_crypto(eligibility(40))
    syms = sorted(s for s, ms in elig.items() if ms)
    rows = []
    for s in syms:
        d = load_1h(s)
        if d is None:
            continue
        first = d.time.iloc[0]
        rows += fills_for(s, d, elig[s], first, "buy")
        rows += fills_for(s, d, elig[s], first, "sell")
    F = pd.DataFrame(rows)
    print(f"{len(syms)} coins ever in the PIT top-40 (dead included); fills found: {len(F)}\n")

    print("A. PER FILL (mean return, before fees), by distance k and exit")
    print(f"  {'side':<5}{'k':>5}{'fills':>7}{'per yr':>8}{'close':>9}{'4h':>9}{'24h':>9}{'tp':>9}"
          f"{'win(24h)':>10}{'worst 24h':>11}{'TUNE 24h':>10}{'HOLD 24h':>10}{'TUNE close':>11}{'HOLD close':>10}")
    yrs = (F.t.max() - F.t.min()).days / 365.25
    for side in ("buy", "sell"):
        for k in KS:
            x = F[(F.side == side) & (F.k == k)]
            if not len(x):
                continue
            tu, ho = x[x.t < CUT], x[x.t >= CUT]
            print(f"  {side:<5}{k*100:>4.0f}%{len(x):>7}{len(x)/yrs:>8.0f}{x['close'].mean()*100:>+8.2f}%{x['x4h'].mean()*100:>+8.2f}%"
                  f"{x['x24h'].mean()*100:>+8.2f}%{x['tp'].mean()*100:>+8.2f}%{(x['x24h'] > 0).mean()*100:>9.0f}%"
                  f"{x['x24h'].min()*100:>+10.0f}%{tu['x24h'].mean()*100:>+9.2f}%{ho['x24h'].mean()*100:>+9.2f}%"
                  f"{tu['close'].mean()*100:>+10.2f}%{ho['close'].mean()*100:>+9.2f}%")

    for lab, col in (("24h", "x24h"), ("the fill hour's close", "close")):
        print(f"\n  BUY bids: by year, mean return per fill exiting at {lab} (fills)")
        for k in (0.10, 0.15, 0.20):
            x = F[(F.side == "buy") & (F.k == k)]
            print(f"   k {k*100:.0f}%: " + "  ".join(f"{y}: {g[col].mean()*100:+.1f}% ({len(g)})"
                                                  for y, g in x.groupby(x.t.dt.year)))
    x = F[(F.side == "buy") & (F.k == 0.15)]
    day = x.groupby(x.t.dt.normalize())["x24h"].agg(["sum", "count"]).sort_values("sum", ascending=False)
    top3 = day.head(3)
    print(f"\n  k 15%: the 3 biggest days carry {top3['sum'].sum() / day['sum'].sum() * 100:.0f}% of the summed 24h return "
          f"({', '.join(f'{d:%Y-%m-%d} ({int(n)} fills)' for d, n in zip(top3.index, top3['count']))})")
    print("  k 15%: the worst 5 fills (24h):")
    for _, r in x.nsmallest(5, "x24h").iterrows():
        print(f"    {r.t:%Y-%m-%d %H:00} {r.sym:<14} fill gap {r.gap*100:+.0f}%  24h {r['x24h']*100:+.0f}%  {'(data ended - delisted)' if r.dead else ''}")
    print("  k 15%: the best 5 fills (24h) - glitch check, a real crash wick recovers over hours, not in one print:")
    for _, r in x.nlargest(5, "x24h").iterrows():
        print(f"    {r.t:%Y-%m-%d %H:00} {r.sym:<14} fill gap {r.gap*100:+.0f}%  close {r['close']*100:+.0f}%  24h {r['x24h']*100:+.0f}%")

    print("\nB. AS A PORTFOLIO: buy bids, each fill f of equity, exposure capped at 100% (CAGR / worst day / max DD)")
    for fee_lab, fee in FEES.items():
        print(f"  fees {fee_lab}")
        for k in (0.10, 0.15, 0.20):
            for ex in ("close", "x24h", "tp"):
                cells = []
                for f in (0.05, 0.10):
                    c = portfolio(F[F.side == "buy"], k, ex, f, fee)
                    if c is None or len(c) < 30:
                        cells.append("   n/a"); continue
                    yrs_c = (c.index[-1] - c.index[0]).days / 365.25
                    cagr = (c.iloc[-1] ** (1 / yrs_c) - 1) * 100
                    dd = (1 - c / c.cummax()).max() * 100
                    wd = c.pct_change().min() * 100
                    tu = c[c.index < CUT]; ho = c[c.index >= CUT]
                    g = lambda z: ((z.iloc[-1] / z.iloc[0]) ** (365.25 / max((z.index[-1] - z.index[0]).days, 1)) - 1) * 100  # noqa: E731
                    cells.append(f"f{f*100:.0f}%: {cagr:+6.1f}%/yr (tune {g(tu):+5.1f} hold {g(ho):+5.1f}) worst day {wd:+5.1f}% DD {dd:4.0f}%")
                print(f"    k {k*100:>2.0f}% exit {ex:<5} " + " | ".join(cells))


if __name__ == "__main__":
    main()
