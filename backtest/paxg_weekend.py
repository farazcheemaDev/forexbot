"""WEEKEND GOLD: when the gold market is shut, does the gold TOKEN wander off and snap back at the reopen? (2026-11-10)

THE USER: "I want something of my own" (after an audit whose one fast lead was copying another trader).  This is a
mechanism nobody in this repo has tested and that belongs to the family that has paid here (forced convergence):
    PAXG (a token backed by physical gold) trades 24/7 on Binance.  The gold market is shut from Friday 17:00 to Sunday
    18:00 New York.  In those 49 hours nobody can arbitrage the token against gold, so a weekend move in PAXG is either
    INFORMATION (gold reopens there) or NOISE (crypto traders pushing a thin market; it snaps back when gold reopens and
    the arbitrage desks return).  If it is partly noise, fading PAXG's weekend move just before the reopen pays.

DATA (all on disk)
    PAXGUSDT 1h spot bars, Binance, 2020-08-28 .. 2026-09-11 (strategy_analysis/data/PAXGUSDT_1h_2400d.json; last-trade
    prices).  Gold: HistData XAUUSD 1-minute BID bars (New York clock with DST, histdata_1m.py), 2010 .. 2026-09.

FAMILY 1 - the weekend fade, PAXG only (9 cells)
    ref     PAXG at Friday 17:00 New York (gold's close)
    signal  dev = PAXG at Sunday 16:00 / ref - 1; trade only if |dev| >= theta, theta in 0.25% / 0.5% / 1.0%
    entry   PAXG at Sunday 17:00 (one full bar AFTER the signal print, so a bid-ask bounce in the signal price cannot
            pay the trade), side = against the move
    exit    PAXG at reopen + H hours, H in 2 / 6 / 24
    cost    12bp round trip (the repo's perp cost); the 20bp spot cost is printed beside it
    PRIMARY CELL: theta 0.5%, H 6.
FAMILY 2 - the hedged premium at the reopen (4 cells): prem = PAXG / gold - 1 against its median over the week just ended;
    signal at Sunday 19:00 (gold has been open an hour), entry at 20:00, short the rich leg / long the cheap one for 4 or
    22 hours, 14.5bp for both legs; thresholds 0.25% / 0.5%.
PLACEBO - family 1's rule on a weekday window where gold is OPEN (ref Monday 15:00, signal Wednesday 14:00, entry 15:00).
SPLIT   tune = the first 60% of weekends, holdout = the last 40%.  One weekend = one independent event.
THE BAR a cell PASSES with net > 0 and t >= 2 on BOTH halves, >= 20 holdout trades, and a Holm-adjusted holdout p < 0.05
        over its family.  Fewer than 20 holdout trades = 'cannot tell' (the minimum detectable edge is printed).

REGISTERED BEFORE THE FIRST RUN (2026-11-10)
    W1  PAXG's weekend move is partly information: the slope of gold's reopen gap on it is between 0.3 and 0.8.
    W2  PAXG reverts after the reopen: the slope of its next-6-hours return on the weekend move is -0.1 .. -0.5.
    W3  Weekends with |dev| >= 0.5% are under 15% of weekends.
    W4  The primary cell is positive on both halves and has too few holdout trades to pass: a LEAD at best.  Chance that
        any of the 9 cells passes the whole bar: 15%.
    W5  The weekday placebo shows no reversion (slope within +-0.1).
    W6  Premium gaps of 0.25%+ at the reopen happen on under 10% of weekends.

RESULT (2026-11-10, logs/paxg_weekend.txt; 254 weekends, tune 152 / holdout 102) - THE SNAP-BACK IS REAL AND TOO SMALL.
    The token wanders a median 0.24% while gold is shut (0.5%+ on 22% of weekends, 1%+ on 5%); gold's own gap is a median
    0.11%.  About a third of the token's move is information (gold's gap on it: slope +0.29) and about a third is given
    back by reopen + 6h (slope -0.28 tune / -0.37 holdout); on the weekday placebo the slope is -0.02 and the same rule
    loses its cost (-0.10% / -0.15%).  But after 12bp: 0 of 9 cells pass.  PRIMARY (0.5%, 6h) +0.17% / +0.17% a trade,
    t 1.2 / 0.75, 11.5 trades a year = about +2% a year on the money used; +0.09% at the spot cost; +0.02% without its
    three best trades (2025-01-31 +4.4%, 2024-04-12 +2.4%, 2021-01-08 +1.6%); the short side carries it (+0.31%, n 42;
    long -0.23%, n 14); 2026 is negative (-0.27%, n 12).  Moves of 1%+: +0.55..+0.78% a trade on 13 trades in six years.
    Hedged at the reopen (family 2, 4 hours): about zero - the convergence is over within the first hour or two.
    W2, W5 right; W1 wrong by a hair (+0.29); W3, W6 wrong (the token wanders more often than I thought); W4 wrong on the
    count (25 holdout trades, so the cell is 'no pass', not 'cannot tell').  A design flaw of mine: family 2's 22-hour
    exit lands on Monday 18:00, just after gold's daily break, so its cells are nearly empty - they say nothing.
    tests/test_paxg_weekend.py 9 (a planted snap-back is found and paid; information is not paid); no planted-bug round.

    python -m backtest.paxg_weekend
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "paxg_weekend.txt"
NY = "America/New_York"
H1 = pd.Timedelta(hours=1)
COST, COST_SPOT, COST_HEDGED = 0.0012, 0.0020, 0.00145
THETAS, HOLDS = (0.0025, 0.005, 0.01), (2, 6, 24)
PRIMARY = (0.005, 6)
TUNE_SHARE, MIN_HOLD_N = 0.6, 20


def load_paxg(path=None):
    """Hourly PAXG: close and volume indexed by the bar's END time (UTC, ns)."""
    rows = json.loads(Path(path or DATA / "PAXGUSDT_1h_2400d.json").read_text())
    d = pd.DataFrame(rows)
    end = pd.to_datetime(d["t"].astype("int64"), unit="ms", utc=True).dt.as_unit("ns") + H1
    return pd.DataFrame({"c": d["c"].to_numpy(float), "v": d["v"].to_numpy(float)}, index=pd.DatetimeIndex(end))


def load_gold(path=None):
    """Gold bid, 1-minute closes indexed by the minute's END time (UTC, ns)."""
    d = pd.read_parquet(Path(path or DATA / "histdata" / "XAUUSD.parquet"))
    end = pd.to_datetime(d["t"].astype("int64"), unit="ms", utc=True).dt.as_unit("ns") + pd.Timedelta(minutes=1)
    return pd.Series(d["c"].to_numpy(float), index=pd.DatetimeIndex(end))


def px(P, ts, need_volume=True):
    """PAXG close of the bar ENDING at ts; NaN if the bar is missing or (need_volume) nothing traded in it."""
    if ts not in P.index:
        return np.nan
    r = P.loc[ts]
    return float(r["c"]) if (r["v"] > 0 or not need_volume) else np.nan


def gold_at(G, ts, max_age_min=30):
    """The last gold bid printed at or before ts, no older than max_age_min; else NaN (market shut)."""
    i = G.index.searchsorted(ts, side="right") - 1
    if i < 0 or ts - G.index[i] > pd.Timedelta(minutes=max_age_min):
        return np.nan
    return float(G.iloc[i])


def ny(day, hour):
    """New York wall-clock (day, hour) as a UTC timestamp - DST-safe."""
    return pd.Timestamp(year=day.year, month=day.month, day=day.day, hour=hour, tz=NY).tz_convert("UTC").as_unit("ns")


def weekends(P, G):
    """One row per weekend the gold market shut on Friday 17:00 and reopened on Sunday 18:00 New York."""
    rows = []
    first, last = P.index[0].tz_convert(NY).normalize(), P.index[-1].tz_convert(NY).normalize()
    for fri in pd.date_range(first, last, freq="W-FRI"):
        sun = fri + pd.Timedelta(days=2)
        f17, s16, s17, s18, s19, s20 = ny(fri, 17), ny(sun, 16), ny(sun, 17), ny(sun, 18), ny(sun, 19), ny(sun, 20)
        g_close, g_19 = gold_at(G, f17), gold_at(G, s19)
        if not (np.isfinite(g_close) and np.isfinite(g_19)) or np.isfinite(gold_at(G, s17, 60 * 24)):
            continue                                            # a holiday: gold did not shut or did not reopen on time
        ref, p16, p17, p19, p20 = px(P, f17), px(P, s16), px(P, s17), px(P, s19), px(P, s20)
        if not all(np.isfinite(v) for v in (ref, p16, p17)):
            continue
        r = dict(fri=fri.tz_localize(None), dev16=p16 / ref - 1, dev17=p17 / ref - 1, entry=p17, gap19=g_19 / g_close - 1,
                 p19=p19, p20=p20, g19=g_19, g20=gold_at(G, s20), ref=ref, g_close=g_close)
        for h in HOLDS:
            r[f"x{h}"] = px(P, s18 + h * H1)
        for h in (4, 22):
            r[f"hx{h}"], r[f"hg{h}"] = px(P, s20 + h * H1), gold_at(G, s20 + h * H1)
        # the week's normal premium: hourly PAXG / gold from Monday 00:00 to Friday 16:00 New York
        hrs = pd.date_range(ny(fri - pd.Timedelta(days=4), 0), ny(fri, 16), freq="h")
        pr = [px(P, t, False) / gold_at(G, t) - 1 for t in hrs]
        pr = [v for v in pr if np.isfinite(v)]
        r["base_prem"] = float(np.median(pr)) if len(pr) >= 24 else np.nan
        rows.append(r)
    return pd.DataFrame(rows)


def placebo(P, G):
    """Family 1's rule on a window where gold is open: ref Monday 15:00, signal Wednesday 14:00, entry 15:00 New York."""
    rows = []
    first, last = P.index[0].tz_convert(NY).normalize(), P.index[-1].tz_convert(NY).normalize()
    for mon in pd.date_range(first, last, freq="W-MON"):
        wed = mon + pd.Timedelta(days=2)
        ref, p14, p15 = px(P, ny(mon, 15)), px(P, ny(wed, 14)), px(P, ny(wed, 15))
        if not all(np.isfinite(v) for v in (ref, p14, p15)) or not np.isfinite(gold_at(G, ny(wed, 15))):
            continue
        r = dict(fri=mon.tz_localize(None), dev16=p14 / ref - 1, entry=p15)
        for h in HOLDS:
            r[f"x{h}"] = px(P, ny(wed, 16) + h * H1)
        rows.append(r)
    return pd.DataFrame(rows)


def fade(W, theta, h, cost=COST):
    """Net return of each trade of one cell (index = the weekend's row label)."""
    w = W[(W["dev16"].abs() >= theta) & np.isfinite(W[f"x{h}"])]
    return -np.sign(w["dev16"]) * (w[f"x{h}"] / w["entry"] - 1) - cost


def hedged(W, theta, h, cost=COST_HEDGED):
    x = W["p19"] / W["g19"] - 1 - W["base_prem"]
    ok = (x.abs() >= theta) & np.isfinite(W["p20"]) & np.isfinite(W["g20"]) & np.isfinite(W[f"hx{h}"]) & np.isfinite(W[f"hg{h}"])
    w = W[ok]
    return -np.sign(x[ok]) * ((w[f"hx{h}"] / w["p20"] - 1) - (w[f"hg{h}"] / w["g20"] - 1)) - cost


def tstat(r):
    r = np.asarray(r, float)
    if len(r) < 3 or r.std(ddof=1) == 0:
        return np.nan
    return float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r))))


def p_upper(t, n):
    """One-sided p for mean > 0 (Student's t, n - 1 degrees of freedom)."""
    from scipy import stats
    return float(stats.t.sf(t, n - 1)) if np.isfinite(t) and n > 2 else 1.0


def holm(ps):
    """Holm-adjusted p values, monotone."""
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    adj, run = np.empty(len(ps)), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def slope(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 5 or x.std() == 0:
        return np.nan, np.nan, len(x)
    b = float(np.cov(x, y, ddof=1)[0, 1] / x.var(ddof=1))
    return b, float(np.corrcoef(x, y)[0, 1] ** 2), len(x)


def split(W):
    cut = int(len(W) * TUNE_SHARE)
    return W.index[:cut], W.index[cut:]


def table(W, fn, cells, label):
    tune, hold = split(W)
    L, ps, rows = [f"{label}", f"   {'cell':<22}{'half':>8}{'n':>5}{'net':>9}{'t':>7}{'won':>6}{'worst':>8}"], [], []
    for cell in cells:
        r = fn(W, *cell)
        a, b = r[r.index.isin(tune)], r[r.index.isin(hold)]
        ta, tb = tstat(a), tstat(b)
        ps.append(p_upper(tb, len(b)))
        rows.append((cell, a, b, ta, tb))
    adj = holm(ps)
    out = {}
    for (cell, a, b, ta, tb), pa in zip(rows, adj):
        name = f"theta {cell[0] * 100:.2f}% H {cell[1]}"
        for half, r, t in (("tune", a, ta), ("holdout", b, tb)):
            L.append(f"   {name:<22}{half:>8}{len(r):>5}{(r.mean() * 100 if len(r) else np.nan):>+8.2f}%{t:>+7.2f}"
                     f"{((r > 0).mean() * 100 if len(r) else np.nan):>5.0f}%{(r.min() * 100 if len(r) else np.nan):>+7.1f}%")
        ok = len(a) and len(b) and a.mean() > 0 and b.mean() > 0 and ta >= 2 and tb >= 2 and len(b) >= MIN_HOLD_N and pa < 0.05
        verdict = "PASS" if ok else ("cannot tell" if len(b) < MIN_HOLD_N else "no pass")
        mde = 2.8 * b.std(ddof=1) / np.sqrt(len(b)) * 100 if len(b) > 2 else np.nan
        L.append(f"   {'':<22}{'':>8} Holm p {pa:.2f}  minimum detectable edge on the holdout {mde:.2f}% a trade -> {verdict}")
        out[cell] = dict(a=a, b=b, ta=ta, tb=tb, holm=pa, verdict=verdict)
    return L, out


def main():
    P, G = load_paxg(), load_gold()
    W = weekends(P, G)
    tune, hold = split(W)
    L = [f"backtest/paxg_weekend.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(W)} weekends {W.fri.iloc[0]:%Y-%m-%d} .. "
         f"{W.fri.iloc[-1]:%Y-%m-%d}; tune {len(tune)} (to {W.fri[tune[-1]]:%Y-%m-%d}) / holdout {len(hold)}", ""]
    ad = W["dev16"].abs() * 100
    L += ["1. HOW FAR DOES THE TOKEN WANDER WHILE GOLD IS SHUT? (|PAXG Sunday 16:00 / Friday 17:00 - 1|)",
          f"   median {ad.median():.2f}%  75th {ad.quantile(.75):.2f}%  90th {ad.quantile(.9):.2f}%  99th {ad.quantile(.99):.2f}%  max {ad.max():.2f}%",
          "   share of weekends at or over: " + "  ".join(f"{t * 100:.2f}% -> {(ad >= t * 100).mean() * 100:.0f}%" for t in THETAS),
          f"   gold's own reopen gap (Sunday 19:00 vs Friday 17:00): median |gap| {W.gap19.abs().median() * 100:.2f}%, 90th {W.gap19.abs().quantile(.9) * 100:.2f}%", ""]
    L.append("2. INFORMATION OR NOISE?")
    for lab, idx in (("all", W.index), ("tune", tune), ("holdout", hold)):
        w = W.loc[idx]
        b1, r1, n1 = slope(w["dev17"], w["gap19"])
        b2, r2, n2 = slope(w["dev16"], w["x6"] / w["entry"] - 1)
        L.append(f"   {lab:<8} gold's gap on the token's weekend move: slope {b1:+.2f} (R2 {r1:.2f}, n {n1})   |   "
                 f"the token's next move (17:00 -> reopen + 6h) on it: slope {b2:+.2f} (R2 {r2:.2f}, n {n2})")
    big = W[W["dev16"].abs() >= 0.005]
    b1, r1, n1 = slope(big["dev17"], big["gap19"])
    b2, r2, n2 = slope(big["dev16"], big["x6"] / big["entry"] - 1)
    L += [f"   |move| >= 0.5% only: gap slope {b1:+.2f} (R2 {r1:.2f}, n {n1})   |   next-move slope {b2:+.2f} (R2 {r2:.2f}, n {n2})", ""]
    cells = [(t, h) for t in THETAS for h in HOLDS]
    T1, R1 = table(W, fade, cells, "3. FAMILY 1 - fade the weekend move, PAXG only, 12bp")
    L += T1
    r = R1[PRIMARY]
    both = pd.concat([r["a"], r["b"]])
    L += ["", f"   PRIMARY (theta 0.5%, H 6) all trades: n {len(both)}, net {both.mean() * 100:+.2f}% at 12bp, "
              f"{(both.mean() - (COST_SPOT - COST)) * 100:+.2f}% at the 20bp spot cost, t {tstat(both):+.2f}, {len(both) / (len(W) / 52.18):.1f} trades a year"]
    yr = pd.DataFrame({"y": W.loc[both.index, "fri"].dt.year, "r": both.to_numpy()})
    L.append("   by year (n, mean): " + "  ".join(f"{y} {len(g)} {g.r.mean() * 100:+.2f}%" for y, g in yr.groupby("y")))
    top = both.sort_values(ascending=False)
    L += [f"   without its 3 best trades: {top.iloc[3:].mean() * 100:+.2f}% (n {len(top) - 3});  the 3 best: "
          + ", ".join(f"{W.fri[i]:%Y-%m-%d} {v * 100:+.1f}%" for i, v in top.iloc[:3].items()),
          "   long side (token fell) / short side (token rose): "
          + " / ".join(f"n {len(g)} {g.mean() * 100:+.2f}%" for g in (both[W.loc[both.index, 'dev16'] < 0], both[W.loc[both.index, 'dev16'] > 0])), ""]
    x = (W["p19"] / W["g19"] - 1 - W["base_prem"]).abs() * 100
    L += [f"4. THE PREMIUM AT THE REOPEN (PAXG / gold against the week's median, Sunday 19:00): median {x.median():.2f}%, 90th {x.quantile(.9):.2f}%, "
          f"share >= 0.25% {(x >= 0.25).mean() * 100:.0f}%, >= 0.5% {(x >= 0.5).mean() * 100:.0f}%"]
    T2, R2 = table(W, hedged, [(t, h) for t in (0.0025, 0.005) for h in (4, 22)], "   FAMILY 2 - hedged (PAXG against gold), 14.5bp")
    L += T2 + [""]
    Wp = placebo(P, G)
    bp, rp, n_p = slope(Wp["dev16"], Wp["x6"] / Wp["entry"] - 1)
    T3, R3 = table(Wp, fade, [PRIMARY], f"5. PLACEBO - the same rule on a weekday window, gold open ({len(Wp)} weeks; next-move slope {bp:+.2f}, R2 {rp:.2f})")
    L += T3 + [""]
    ball, _, _ = slope(W["dev17"], W["gap19"])
    brev, _, _ = slope(W["dev16"], W["x6"] / W["entry"] - 1)
    share = (ad >= 0.5).mean()
    any_pass = any(v["verdict"] == "PASS" for v in R1.values())
    prim = R1[PRIMARY]
    L += ["REGISTERED PREDICTIONS",
          f"  W1 gap slope 0.3..0.8 ({ball:+.2f}) -> {'RIGHT' if 0.3 <= ball <= 0.8 else 'WRONG'}",
          f"  W2 next-move slope -0.1..-0.5 ({brev:+.2f}) -> {'RIGHT' if -0.5 <= brev <= -0.1 else 'WRONG'}",
          f"  W3 |dev| >= 0.5% on under 15% of weekends ({share * 100:.0f}%) -> {'RIGHT' if share < 0.15 else 'WRONG'}",
          f"  W4 primary positive on both halves, too few holdout trades; no cell passes (primary {prim['a'].mean() * 100:+.2f}% / {prim['b'].mean() * 100:+.2f}%, "
          f"holdout n {len(prim['b'])}, any pass: {any_pass}) -> "
          f"{'RIGHT' if (prim['a'].mean() > 0 and prim['b'].mean() > 0 and len(prim['b']) < MIN_HOLD_N and not any_pass) else 'WRONG'}",
          f"  W5 placebo slope within +-0.1 ({bp:+.2f}) -> {'RIGHT' if abs(bp) <= 0.1 else 'WRONG'}",
          f"  W6 premium >= 0.25% at the reopen on under 10% of weekends ({(x >= 0.25).mean() * 100:.0f}%) -> {'RIGHT' if (x >= 0.25).mean() < 0.10 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
