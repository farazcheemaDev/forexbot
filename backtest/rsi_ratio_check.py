"""RSI RATIO - THE CHECK ON ITS BEST-LOOKING CELL (2026-11-02): is "+0.37R" money, and does a breadth filter rescue it?

backtest/rsi_ratio.py (448 cells) ended with PASS 0, but its best textbook cell - 1h, RSI(14) crosses under 30, LONG, stop 1 ATR,
target 4R - printed +0.368R / +0.257R (tune / holdout) with t +8.2 / +4.7 and Holm 0.00 (it fails only the 'excess over a random entry at the same
moment' bar). Before anyone reads that as 'a ratio that pays', this asks what an account that takes the signals would earn.

THE TWO MEANS. rsi_ratio's R columns are DAY-VOTE means: every entry day counts once (right for t statistics - a crash day with 100 signals is one
bet). Money is per TRADE. They differ when the days with many signals are the days that lose, which is exactly what a market-wide sell-off is.
BRACKETS  (stop ATR, target R): (1, 4), (1, 2), (2, 2), (0.5, 4) - the four that read best in rsi_ratio.
SECTIONS  1  per-trade vs day-vote mean by half and by year, how much of the total the 10 best days carry, signals per day, the worst day
          2  trades bucketed by how many coins signalled on the SAME CALENDAR DAY (kept to show the trap: it includes signals AFTER the entry hour,
             which nobody knows when entering - a look-ahead) and by how many signalled in the 24 hours UP TO AND INCLUDING the entry hour (causal)
          3  an account: 0.3% of booked equity risked a trade, at most K positions open, 5 random orderings of simultaneous signals, $300, booked at
             exit; ungated, and gated causally on the 24-hour count (<= 24, <= 9)

NOT PRE-REGISTERED. Written after the first run of rsi_ratio.py contradicted a hand check (+0.37R day-vote against -0.15R a trade), so the predictions
below are the ones I would have written, stated with that disclosure:
  C1  the per-trade mean is negative in both halves and every year for all four brackets (the day-vote mean is a weighting artifact).
  C2  a bucket by the SAME-DAY signal count looks like a rescue (few signals = positive, flush days = negative) - and the causal 24-hour count does not.
  C3  every capped account loses money in both halves.

    python -m backtest.rsi_ratio_check
"""
from __future__ import annotations

import heapq
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_manage as cm  # noqa: E402
from backtest import candle_scan as cs  # noqa: E402
from backtest import rsi_ratio as rr  # noqa: E402

LOG = ROOT / "logs" / "rsi_ratio_check.txt"
BR = [(1.0, 4.0), (1.0, 2.0), (2.0, 2.0), (0.5, 4.0)]
FLAG = "lo30"
CUT = pd.Timestamp("2024-08-29")
RISK = 0.003
START = 300.0
BUCKETS = ((1, 3), (4, 9), (10, 24), (25, 49), (50, 999))
DAY_BUCKETS = ((1, 1), (2, 3), (4, 9), (10, 24), (25, 999))


def collect():
    """One row per taken trade (one position per coin): coin, bracket index, entry time, exit time (end of the exit bar), net R, 1R as a share of price."""
    from backtest.capitulation_wide import hourly
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    elig = drop_non_crypto(eligibility(40))
    coins = sorted(s for s in elig if elig[s] and s.endswith("USDT"))
    rows = []
    for sym in coins:
        hh = hourly(sym)
        if hh is None:
            continue
        em = np.array(sorted(elig[sym]), dtype="datetime64[M]")
        d = rr.to_tf(hh, 1)
        n = len(d)
        if n < 200:
            continue
        t = d["time"].to_numpy("datetime64[ns]")
        o, h, l, c = (d[k].to_numpy(float) for k in ("o", "h", "l", "c"))
        atr = cm.atr14(h, l, c)
        f = rr.rsi_flags(rr.rsi14(c), d["v"].to_numpy(float))[FLAG]
        step = 3600 * 10 ** 9
        base_ok = (cs.valid_mask(t, step, rr.CAP) & rr.warm_mask(t, step, rr.WARM) & np.isin(t.astype("datetime64[M]"), em)
                   & (o > 0) & (c > 0) & np.isfinite(atr) & (atr > 0))
        for bi, (stp, tgt) in enumerate(BR):
            valid = base_ok.copy()
            E = np.flatnonzero(valid)
            if not len(E):
                continue
            valid[E[stp * atr[E] / o[E + 1] < cm.MIN_RISK]] = False
            E = np.flatnonzero(valid)
            if not len(E):
                continue
            rg, kx, rf = cm.simulate(o, h, l, c, atr, E, 1, dict(stop=stp, be=None, trail=None, target=tgt, cap=rr.CAP))
            net = rg - np.broadcast_to(cm.cost_r(kx, rf, 1, 1), rg.shape)
            net_full = np.full(n, np.nan)
            net_full[E] = net
            ex = np.zeros(n, int)
            ex[E] = E + kx
            rfull = np.zeros(n)
            rfull[E] = rf
            idx = np.flatnonzero(f & valid & np.isfinite(net_full))
            for i in cm.pick_trades(idx, ex.tolist()):
                rows.append((sym, bi, t[i + 1], t[ex[i]] + np.timedelta64(1, "h"), float(net_full[i]), float(rfull[i])))
    df = pd.DataFrame(rows, columns=["coin", "bi", "t_in", "t_out", "net", "rf"])
    df["day"] = pd.to_datetime(df.t_in).dt.floor("D")
    return df


def trailing_counts(t_in, hours=24):
    """For each trade (sorted by entry time): how many trades entered in the `hours` hours up to AND INCLUDING its own entry hour - everything a
    bot could know when it enters (same-hour signals are all known at that bar's close). Future entries never count."""
    t = np.asarray(t_in, "datetime64[ns]")
    hi = np.searchsorted(t, t, side="right")
    lo = np.searchsorted(t, t - np.timedelta64(hours, "h"), side="right")
    return hi - lo


def account(x, k, risk=RISK, seed=0, start=START):
    """Sizes each trade at 0.3% of BOOKED equity when it opens, books it at its exit, skips a signal when k positions are open.
    Returns (final equity, booked equity series by exit time)."""
    rng = np.random.default_rng(seed)
    x = x.assign(r=rng.random(len(x))).sort_values(["t_in", "r"], kind="stable")
    eq, heap, open_n, curve = start, [], 0, []
    for r in x.itertuples():
        while heap and heap[0][0] <= r.t_in:
            to, pnl = heapq.heappop(heap)
            eq += pnl
            open_n -= 1
            curve.append((to, eq))
        if open_n >= k:
            continue
        heapq.heappush(heap, (r.t_out, risk * eq * r.net))
        open_n += 1
    while heap:
        to, pnl = heapq.heappop(heap)
        eq += pnl
        curve.append((to, eq))
    return eq, pd.Series([c for _, c in curve], index=[a for a, _ in curve])


def main():
    df = collect()
    L = [f"backtest/rsi_ratio_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; 1h {FLAG} LONG on the PIT top-40 perps, {len(df):,} trades over "
         f"{df.coin.nunique()} coins, 4 brackets; tune < {CUT:%Y-%m-%d}", ""]
    checks = {"c1": True, "c3": True}
    L.append("1. PER-TRADE vs DAY-VOTE (R)")
    for bi, (stp, tgt) in enumerate(BR):
        x = df[df.bi == bi]
        L.append(f"  stop {stp} ATR / target {tgt}R: {len(x):,} trades, stop distance {x.rf.mean() * 100:.2f}% of price on average")
        for nm, sel in (("tune", x.day < CUT), ("holdout", x.day >= CUT)):
            y = x[sel]
            ds = y.groupby("day").net.sum()
            top10 = ds.sort_values(ascending=False).head(10).sum()
            if y.net.mean() >= 0:
                checks["c1"] = False
            L.append(f"    {nm:8s} {len(y):6d} trades {len(ds):4d} days   per-trade {y.net.mean():+.3f}R   day-vote {y.groupby('day').net.mean().mean():+.3f}R   "
                     f"win {100 * (y.net > 0).mean():.0f}%   total {ds.sum():+8.1f}R   best 10 days {top10:+8.1f}R   without them {(ds.sum() - top10) / len(y):+.3f}R/trade")
        yr = x.groupby(x.day.dt.year).net.agg(["size", "mean"])
        if (yr["mean"] >= 0).any():
            checks["c1"] = False
        L.append("    by year (per-trade): " + "  ".join(f"{int(i)}: n{int(r['size'])} {r['mean']:+.2f}R" for i, r in yr.iterrows()))
        per_day = x.groupby("day").size()
        ds = x.groupby("day").net.sum()
        L.append(f"    signals per day: median {per_day.median():.0f}, p90 {per_day.quantile(0.9):.0f}, max {per_day.max()}; worst day {ds.min():+.1f}R on "
                 f"{per_day[ds.idxmin()]} trades ({ds.idxmin():%Y-%m-%d}); best day {ds.max():+.1f}R")
    L += ["", "2. BUCKETS (per-trade mean net R and win share; tune / holdout)",
          "   A. by signals on the SAME CALENDAR DAY - includes signals after the entry hour: A LOOK-AHEAD, shown only for comparison"]
    d2 = df.copy()
    d2["nday"] = d2.groupby(["bi", "day"]).coin.transform("size")
    parts = []
    for bi in range(len(BR)):
        x = d2[d2.bi == bi].sort_values("t_in", kind="stable").copy()
        x["n24"] = trailing_counts(x.t_in.to_numpy())
        parts.append(x)
    d2 = pd.concat(parts)

    def table(col, buckets):
        res = {}
        for bi, (stp, tgt) in enumerate(BR):
            x = d2[d2.bi == bi]
            L.append(f"     stop {stp} ATR / {tgt}R")
            for lo, hi in buckets:
                o = []
                for nm, sel in (("tune", x.t_in < CUT), ("holdout", x.t_in >= CUT)):
                    y = x[sel & (x[col] >= lo) & (x[col] <= hi)]
                    o.append(f"{nm}: n{len(y):6d} {y.net.mean() if len(y) else float('nan'):+.3f}R win {100 * (y.net > 0).mean() if len(y) else float('nan'):.0f}%")
                    res[(bi, lo, nm)] = (len(y), float(y.net.mean()) if len(y) else float("nan"))
                L.append(f"       {lo:>3}-{hi:<3}   " + "   ".join(o))
        return res
    ra = table("nday", DAY_BUCKETS)
    L.append("   B. by signals in the 24 hours up to and including the entry hour - CAUSAL")
    rb = table("n24", BUCKETS)
    a_pos = sum(1 for (bi, lo, nm), (n, m) in ra.items() if lo < 25 and n >= 50 and m > 0)
    a_all = sum(1 for (bi, lo, nm), (n, m) in ra.items() if lo < 25 and n >= 50)
    b_pos = sum(1 for (bi, lo, nm), (n, m) in rb.items() if n >= 50 and m > 0)
    b_all = sum(1 for (bi, lo, nm), (n, m) in rb.items() if n >= 50)
    L += ["", f"   same-day buckets under 25 signals with a positive per-trade mean: {a_pos} of {a_all};  causal buckets with a positive mean: {b_pos} of {b_all}", "",
          f"3. ACCOUNT ({RISK * 100:.1f}% of booked equity risked a trade, K positions at most, 5 orderings, ${START:.0f}, booked at exit)"]
    for bi, (stp, tgt) in enumerate(BR):
        for gate in (None, 24, 9):
            x = d2[d2.bi == bi] if gate is None else d2[(d2.bi == bi) & (d2.n24 <= gate)]
            for k in (3, 5, 10):
                s = []
                for nm, sel in (("tune", x.t_in < CUT), ("holdout", x.t_in >= CUT)):
                    y = x[sel]
                    r = [account(y, k, seed=sd) for sd in range(5)]
                    mult = float(np.mean([z[0] for z in r])) / START
                    yrs = (y.t_in.max() - y.t_in.min()).days / 365.25
                    fall = float(np.mean([(z[1] / z[1].cummax() - 1).min() for z in r]))
                    if mult >= 1.0:
                        checks["c3"] = False
                    s.append(f"{nm}: n{len(y)} x{mult:.2f} over {yrs:.1f}y ({(mult ** (1 / yrs) - 1) * 100:+.0f}%/yr) fall {fall * 100:.0f}%")
                L.append(f"  stop {stp} ATR/{tgt}R gate {'none' if gate is None else '<=' + str(gate):>5} K={k:2d}   " + "   ".join(s))
    L += ["", "PREDICTIONS (stated after the fact - see the docstring)",
          f"  C1 per-trade mean negative in both halves and every year, all four brackets -> {'RIGHT' if checks['c1'] else 'WRONG'}",
          f"  C2 same-day buckets rescue it, causal buckets do not -> {'RIGHT' if (a_pos >= 10 and b_pos == 0) else 'see the counts above'} "
          f"(same-day positive {a_pos}/{a_all}, causal positive {b_pos}/{b_all})",
          f"  C3 every capped account loses in both halves -> {'RIGHT' if checks['c3'] else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
