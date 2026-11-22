"""LIQUIDITY SWEEP + CONFLUENCE: can other factors lift the sweep's small, real information above the fee? (2026-10-30)

THE USER (2026-10-30): "analyst desk book - I see potential there, especially in the liquidity sweep; if combined with other factors we can
make the quality of signals better, and I am possibly looking at a good signal generator even for less capital".

WHAT IS ALREADY KNOWN (so this is not a fresh start)
  backtest/sweep_reclaim.py (2026-10-08, PIT top-40, hourly): an hour that trades under the prior day's low and closes back above it beats a
    matched random entry on both halves (long excess +0.14% t +7.3 / +0.08% t +4.6; short +0.07% / +0.04%) and STILL LOSES after 12bp
    (long -0.08% / -0.13% a trade). Information real, size smaller than the fee.
  The Analyst desk's SMC rule (24-bar low swept and reclaimed, same-bar close up; analyst_replay.py): hit 13.0% vs 14.4% for a random entry
    with the same stop and target, -0.22R a call. The desk's stop (0.25 ATR under the sweep) and 2R target are NOT what sweep_reclaim measured.

THE EVENT (this file): the desk's own definition, on the PIT top-40 (dead coins in), 1h bars, 2020-2026, both sides.
  LONG   bar low < the lowest low of the 24 bars before it, close > that low, close > open.   SHORT mirrors (high > the 24-bar high, close back
         under it, close < open). Events of one coin and side within 12 bars of a kept event are dropped (declustering, causal).
THE TRADE (primary, T24): in at the NEXT bar's open, stop = the sweep's extreme (intrabar, checked first; a gap through it = no trade), no
  target, out at the close 24 bars later. 12bp round trip + funding. Secondary (TP2): the same with a +2% target (sweep_reclaim's exits).
THE CONTROL (per event): a random hour of the same coin and month with the SAME stop distance and the same exits. Excess = event - control.
  t is by distinct DAY (the 40 coins share one market), halves split 2024-04-07 (pair_lab.HOLDOUT).

THE FACTORS (7, fixed here, each with its favourable direction; every one is read from bars up to and including the signal bar)
  F1 depth    how far the bar went through the level, in ATR(14)                    favourable = HIGH
  F2 vol      the bar's quote volume / the median of the 24 bars before it         favourable = HIGH   (forced selling leaves volume)
  F3 loc      where the bar closed in its own range (long: (c-l)/(h-l))            favourable = HIGH   (a firm reclaim)
  F4 breadth  how many eligible coins have the same-side sweep in the same hour     favourable = HIGH   (a market-wide flush - the capitulation family)
  F5 trend    side x (close / its 168-bar mean - 1)                                 favourable = HIGH   (a sweep WITH the weekly trend)
  F6 touch    other bars in the previous 72 whose extreme sits within 0.25 ATR of the level (equal lows / highs: stops resting there)  favourable = HIGH
  F7 fund     -side x the last funding rate                                          favourable = HIGH   (a long wick where shorts pay, a short wick where longs pay)
STAGE 1 (one factor at a time). The cut is the 2/3 quantile of the factor on the TUNE half's events (per side); an event is FLAGGED if it is at
  or above the cut. Spread = flagged minus unflagged net return per trade, t by day (regression of the trade return on the flag, clustered by
  day). A factor is CONFIRMED when its tune spread is > 0 with t > 2 AND its holdout spread is > 0 with a one-sided p < 0.05 after Holm over the
  14 cells (7 factors x 2 sides). Cut-offs are never re-fitted on the holdout.
STAGE 2 (stacking, walk-forward). The factors with tune spread > 0 and t > 2 are SELECTED (per side). Score = how many of them flag the event.
  k = the lowest threshold that maximises the TUNE mean net return with >= 300 tune trades; the holdout is read at that k and only that k
  (all k are printed). TRADABLE = the chosen subset's net return is > 0 on both halves, t by day > 2 on the holdout, >= 100 holdout trades.
  Break-even fee = the subset's gross return per trade (the round-trip fee at which its net would be zero).
DIAGNOSTICS (not tests): share of the chosen long subset that is a capitulation (coin down >= 10% over 24 bars at the signal), because
  capit2 already trades that; and the same stage-2 read with the flag randomly permuted (placebo, same share).

REGISTERED BEFORE THE FIRST RUN (2026-10-30)
  Q1  Unfiltered, the 24-bar sweep loses after 12bp on both halves for both sides (like sweep_reclaim and the desk's replay) while its excess
      over the control is positive on both halves for LONGS.
  Q2  Stage 1 confirms at most 3 of the 14 cells. The likeliest: F2 vol and F4 breadth on longs (the capitulation family). F5 trend and F7 fund
      are the likeliest to flip sign between halves.
  Q3  Stage 2 finds NO tradable subset (probability 70%): the best stacked long subset's holdout net is at most +0.10% a trade at 12bp. If one is
      found, it is a long, with F2 and/or F4 in its score.
  Q4  The chosen long subset is mostly capitulation: >= 40% of its events have the coin down >= 10% over 24 bars.
  Q5  The best subset's gross edge per trade is under 0.35% (a break-even round-trip fee under 35bp), so even a maker-fee version leaves little.
  Verdict rules: a subset that passes TRADABLE is a CANDIDATE for a forward paper record in the Analyst desk (registered separately), not a
  deployment. Anything that looks good gets the causality check (tests/test_sweep_confluence.py) and the placebo before it is believed.

RESULT (2026-10-30, logs/sweep_confluence.txt; 60,664 events, 359 PIT coins, 28,715 long / 31,949 short): NO FACTOR LIFTS THE SWEEP, NO TRADABLE SUBSET.
  Unfiltered, the sweep beats its matched random entry (long excess +0.24% t 2.1 tune / +0.07% t 0.7 holdout in T24; +0.11% t 2.5 / +0.10% t 2.3 in TP2;
    short +0.13% / +0.05%) but its gross edge is +0.19% (long, 2020-24) and -0.08% (long, since 2024-04): under the 12bp fee on the holdout for both sides.
  Stage 1: 0 of 14 cells confirmed. The one cell with a significant holdout move is NEGATIVE: long sweeps in a high-breadth hour (>= 15 coins sweeping at once)
    net -0.59% on the holdout (spread -0.55%, t -3.1; -0.47% without the three worst days), against +0.21% on the tune half - a flip, not a lead.
  Stage 2: the tune half selected no long factor (best t +1.4) and one short factor (trend); that short subset nets +0.05% tune / -0.05% holdout, 7bp gross,
    placebo +0.1 sd. NOT TRADABLE.
  Predictions: Q1 half right (7 of 8 rows lose after 12bp; the long T24 tune row is +0.07%, t 0.7; long excess is positive in all four rows, t > 2 in three);
    Q2 right on the count (0, limit 3), WRONG on which cells - vol and breadth were the predicted best and breadth is the one significant NEGATIVE; Q3 right (70%);
    Q4 not testable (no long subset); Q5 right (gross never above +0.19%).
  Amended after the first printout, before any verdict was read: t_by_day averaged DAY means while the printed mean is per trade, so a negative mean could print a
    positive t (long holdout net -0.20% "t +3.6"). It is now the per-trade mean with day-clustered errors; the stage-1 spreads were always clustered, so the verdicts
    did not change. test_holm_and_the_day_t fails on the old function.

    python -m backtest.sweep_confluence            run (caches the event table in logs/sweep_confluence_events.pkl)
    python -m backtest.sweep_confluence --refit    rebuild the event table
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest.capitulation_wide import PERPS, funding_cum  # noqa: E402

LOG = ROOT / "logs" / "sweep_confluence.txt"
CACHE = ROOT / "logs" / "sweep_confluence_events.pkl"
HOLDOUT = pl.HOLDOUT
FEE = 0.0012
HOLD = 24
TP = 0.02
COOL = 12
LOOK, TOUCH_LOOK, TREND = 24, 72, 168
FACTORS = ["depth", "vol", "loc", "breadth", "trend", "touch", "fund"]
MIN_TUNE_TRADES, MIN_HOLD_TRADES = 300, 100


# ------------------------------------------------------------------ the features (causal: bar i uses bars <= i)

def features(t, o, h, l, c, q, rate):
    """Per side (+1 long, -1 short): a boolean `ev` and the factor arrays, all of length n. Nothing at bar i reads a later bar."""
    n = len(c)
    S = pd.Series
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    atr = S(tr).rolling(14).mean().to_numpy()
    pl_ = S(l).rolling(LOOK).min().shift(1).to_numpy()
    ph_ = S(h).rolling(LOOK).max().shift(1).to_numpy()
    qmed = S(q).rolling(LOOK).median().shift(1).to_numpy()
    sma = S(c).rolling(TREND).mean().to_numpy()
    r24 = c / np.r_[np.full(LOOK, np.nan), c[:-LOOK]] - 1
    rng = np.maximum(h - l, 1e-12)
    ok = np.zeros(n, bool)
    if n > TREND:
        ok[TREND:] = (t[TREND:] - t[:-TREND]) == np.timedelta64(TREND, "h")        # 168 contiguous hours before every event bar
    out = {}
    for side, ext, lvl in ((1, l, pl_), (-1, h, ph_)):
        touch = np.full(n, np.nan)
        if n > TOUCH_LOOK:
            W = sliding_window_view(ext, TOUCH_LOOK)[: n - TOUCH_LOOK]               # row j = bars j .. j+71, used for bar i = j+72
            touch[TOUCH_LOOK:] = (np.abs(W - lvl[TOUCH_LOOK:, None]) <= 0.25 * atr[TOUCH_LOOK:, None]).sum(1) - 1
        if side > 0:
            ev = (l < pl_) & (c > pl_) & (c > o)
            depth, loc = (pl_ - l) / atr, (c - l) / rng
        else:
            ev = (h > ph_) & (c < ph_) & (c < o)
            depth, loc = (h - ph_) / atr, (h - c) / rng
        ev = ev & ok & np.isfinite(atr) & np.isfinite(qmed) & (qmed > 0) & np.isfinite(sma) & np.isfinite(r24)
        out[side] = dict(ev=ev, level=lvl, extreme=ext, depth=depth, vol=q / np.where(qmed > 0, qmed, np.nan), loc=loc,
                         trend=side * (c / sma - 1), touch=touch, fund=-side * rate, r24=r24)
    return out


def last_rate(sym, times):
    """The last funding rate settled at or before each bar's start (0 if the coin has none)."""
    f = PERPS / f"{sym}_funding.csv.gz"
    if not f.exists():
        return np.zeros(len(times))
    fu = pd.read_csv(f)
    s = pd.to_datetime(fu["time"]).dt.floor("h").astype("datetime64[ns]")
    ser = pd.Series(fu["rate"].to_numpy(float), index=s.to_numpy()).groupby(level=0).last().sort_index()
    return np.nan_to_num(ser.reindex(np.asarray(times, "datetime64[ns]"), method="ffill").to_numpy(float))


# ------------------------------------------------------------------ the trade

def trade(i, side, stop, tp, o, h, l, c, fc):
    """In at o[i+1]; stop intrabar (first), optional +tp target intrabar, else the close HOLD bars later. Returns (net, gross) or None."""
    n = len(c)
    e = o[i + 1]
    if side > 0 and stop >= e or side < 0 and stop <= e:
        return None
    j_end = min(i + HOLD, n - 1)
    for j in range(i + 1, j_end + 1):
        if (l[j] <= stop) if side > 0 else (h[j] >= stop):
            x = min(o[j], stop) if side > 0 else max(o[j], stop)
            g = side * (x / e - 1) - side * (fc[j] - fc[i + 1]) / e
            return g - FEE, g
        if tp is not None and ((h[j] >= e * (1 + tp)) if side > 0 else (l[j] <= e * (1 - tp))):
            g = tp - side * (fc[j] - fc[i + 1]) / e
            return g - FEE, g
    g = side * (c[j_end] / e - 1) - side * (fc[j_end] - fc[i + 1]) / e
    return g - FEE, g


def build_events() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    H = pl.hourly_all()
    el = pl.universe()
    raw, pre = [], {}
    for s, hh in H.items():
        t = hh.time.to_numpy("datetime64[ns]")
        o, h, l, c, q = (hh[k].to_numpy(float) for k in ("open", "high", "low", "close", "qvol"))
        F = features(t, o, h, l, c, q, last_rate(s, t))
        ym = pd.DatetimeIndex(t).strftime("%Y-%m").to_numpy()
        elig = np.array([m in el[s] for m in ym]) if el[s] else np.zeros(len(t), bool)
        pre[s] = (t, o, h, l, c, F, ym, elig)
        for side in (1, -1):
            idx = np.flatnonzero(F[side]["ev"] & elig)
            raw.append(pd.DataFrame(dict(side=side, t=t[idx])))
    cnt = pd.concat(raw).groupby(["side", "t"]).size()
    rows = []
    for s, (t, o, h, l, c, F, ym, elig) in pre.items():
        fc = funding_cum(s, t, H[s])
        day = pd.DatetimeIndex(t).floor("D")
        by_month = pd.Series(np.arange(len(t))).groupby(ym).apply(lambda x: x.to_numpy())
        for side in (1, -1):
            f, last = F[side], -10 ** 9
            for i in np.flatnonzero(f["ev"] & elig):
                if i - last < COOL or i + HOLD + 2 >= len(c):
                    continue
                stop = float(f["extreme"][i])
                r1, r2 = trade(i, side, stop, None, o, h, l, c, fc), trade(i, side, stop, TP, o, h, l, c, fc)
                if r1 is None or r2 is None:
                    continue
                last = i
                dist = abs(stop / c[i] - 1)
                pool = by_month[ym[i]]
                pool = pool[(pool > TREND) & (pool + HOLD + 2 < len(c))]
                k = int(rng.choice(pool))
                cs = c[k] * (1 - side * dist)
                k1, k2 = trade(k, side, cs, None, o, h, l, c, fc), trade(k, side, cs, TP, o, h, l, c, fc)
                if k1 is None or k2 is None:
                    continue
                rows.append((s, t[i + 1], day[i + 1], side, dist, f["depth"][i], f["vol"][i], f["loc"][i], cnt.get((side, t[i]), 1),
                             f["trend"][i], f["touch"][i], f["fund"][i], f["r24"][i], r1[0], r1[1], k1[0], r2[0], r2[1], k2[0]))
    cols = ["coin", "t_in", "day", "side", "dist", "depth", "vol", "loc", "breadth", "trend", "touch", "fund", "r24",
            "net", "gross", "ctrl", "net_tp", "gross_tp", "ctrl_tp"]
    T = pd.DataFrame(rows, columns=cols)
    T["ex"], T["ex_tp"] = T.net - T.ctrl, T.net_tp - T.ctrl_tp
    return T


# ------------------------------------------------------------------ the statistics

def t_by_day(x: pd.Series, day: pd.Series) -> float:
    """t of the per-TRADE mean, standard error clustered by day (the coins of one day share one market). The first run of this file averaged the DAY means
    instead (sweep_reclaim.py's convention): a day with 30 coins sweeping at once counted once in the t and thirty times in the printed mean, so a negative
    mean could print a positive t. Changed 2026-10-30 after the first run, before any verdict was read from it."""
    y = x.to_numpy(float)
    codes = pd.factorize(day.to_numpy())[0]
    G, N = codes.max() + 1, len(y)
    if G < 3:
        return float("nan")
    m = y.mean()
    S = np.zeros(G)
    np.add.at(S, codes, y - m)
    se = np.sqrt(G / (G - 1) * (S ** 2).sum()) / N
    return float(m / se) if se > 0 else float("nan")


def spread_t(y: np.ndarray, flag: np.ndarray, day: np.ndarray):
    """OLS y = a + b flag, standard errors clustered by day. Returns (b, t)."""
    X = np.c_[np.ones(len(y)), flag.astype(float)]
    XtXi = np.linalg.pinv(X.T @ X)
    beta = XtXi @ X.T @ y
    e = y - X @ beta
    codes = pd.factorize(day)[0]
    G = codes.max() + 1
    sc = np.zeros((G, 2))
    np.add.at(sc, codes, X * e[:, None])
    V = XtXi @ (sc.T @ sc) @ XtXi * (G / max(G - 1, 1))
    se = np.sqrt(max(V[1, 1], 1e-30))
    return float(beta[1]), float(beta[1] / se)


def p_one_sided(t: float, df: float = 1e9) -> float:
    from math import erf, sqrt
    return 0.5 * (1 - erf(t / sqrt(2)))


def holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for r, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - r) * p))
        out[k] = run
    return out


def cell(x: pd.DataFrame, col="net") -> str:
    if len(x) == 0:
        return "n 0"
    t = t_by_day(x[col], x.day)
    return f"n {len(x)}, net {x[col].mean() * 100:+.2f}% (t {t:+.1f}), gross {x.gross.mean() * 100:+.2f}%, hit {np.mean(x[col] > 0) * 100:.0f}%"


def report(T: pd.DataFrame, rng) -> str:
    L = []
    P = L.append
    P(f"backtest/sweep_confluence.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-40 1h, 24-bar sweep+reclaim, in at the next open, stop at the sweep extreme, "
      f"T24 (exit 24 bars later) / TP2 (+2% target), 12bp + funding, halves split {HOLDOUT.date()}")
    P(f"events {len(T)}: " + ", ".join(f"{('long' if s > 0 else 'short')} {int((T.side == s).sum())}" for s in (1, -1)) + f"; {T.coin.nunique()} coins, "
      f"{T.t_in.min().date()} .. {T.t_in.max().date()}")
    tune, hold = T.t_in < HOLDOUT, T.t_in >= HOLDOUT
    P("\nQ1  UNFILTERED")
    for side, nm in ((1, "LONG "), (-1, "SHORT")):
        for struct, nc, ec in (("T24", "net", "ex"), ("TP2", "net_tp", "ex_tp")):
            for half, m in (("tune", tune), ("holdout", hold)):
                x = T[(T.side == side) & m]
                P(f"  {nm} {struct} {half:8s} {cell(x, nc)}; excess vs control {x[ec].mean() * 100:+.2f}% (t {t_by_day(x[ec], x.day):+.1f})")
    # ---- stage 1
    P("\nSTAGE 1 - one factor at a time (cut = 2/3 quantile of the factor on the TUNE half; flagged = at or above it)")
    cuts, pvals, res = {}, {}, {}
    for side, nm in ((1, "LONG"), (-1, "SHORT")):
        g = T[T.side == side]
        for f in FACTORS:
            cut = float(np.nanquantile(g[tune.loc[g.index]][f], 2 / 3))
            cuts[side, f] = cut
            flag = (g[f] >= cut).to_numpy()
            r = {}
            for half, m in (("tune", tune.loc[g.index]), ("hold", hold.loc[g.index])):
                mm = m.to_numpy()
                b, tt = spread_t(g.net.to_numpy()[mm], flag[mm], g.day.to_numpy()[mm])
                r[half] = dict(b=b, t=tt, share=flag[mm].mean(), net_flag=g.net.to_numpy()[mm][flag[mm]].mean(), n_flag=int(flag[mm].sum()))
            res[side, f] = r
            pvals[side, f] = p_one_sided(r["hold"]["t"])
    hp = holm(pvals)
    P(f"  {'cell':14s} {'cut':>9s} {'share':>6s} | tune: spread  t   flagged net | holdout: spread  t   flagged net  Holm p | CONFIRMED")
    confirmed = []
    for side, nm in ((1, "LONG"), (-1, "SHORT")):
        for f in FACTORS:
            r = res[side, f]
            ok = r["tune"]["b"] > 0 and r["tune"]["t"] > 2 and r["hold"]["b"] > 0 and hp[side, f] < 0.05
            if ok:
                confirmed.append((side, f))
            P(f"  {nm + ' ' + f:14s} {cuts[side, f]:9.4g} {r['tune']['share'] * 100:5.0f}% | {r['tune']['b'] * 100:+6.2f}% {r['tune']['t']:+5.1f}   "
              f"{r['tune']['net_flag'] * 100:+6.2f}% | {r['hold']['b'] * 100:+6.2f}% {r['hold']['t']:+5.1f}   {r['hold']['net_flag'] * 100:+6.2f}%   "
              f"{hp[side, f]:5.2f} | {'YES' if ok else ''}")
    P(f"  confirmed cells: {len(confirmed)} of {len(res)}  {confirmed}")
    g = T[(T.side == 1) & (T.t_in >= HOLDOUT) & (T.breadth >= cuts[1, "breadth"])]
    dd = g.groupby("day").net.agg(["sum", "count"]).sort_values("sum")
    rest = g[~g.day.isin(dd.index[:3])]
    P(f"  diagnostic - LONG high-breadth sweeps on the holdout: {len(g)} trades on {g.day.nunique()} days; the 3 worst days {', '.join(str(d.date()) for d in dd.index[:3])} "
      f"hold {int(dd['count'].iloc[:3].sum())} trades and {dd['sum'].iloc[:3].sum() / dd['sum'].sum() * 100:.0f}% of the summed loss; without them the flagged net is {rest.net.mean() * 100:+.2f}% (n {len(rest)})")
    # ---- stage 2
    P("\nSTAGE 2 - stacking the factors that the TUNE half selected (spread > 0, t > 2); k chosen on tune only")
    chosen = {}
    for side, nm in ((1, "LONG"), (-1, "SHORT")):
        g = T[T.side == side].copy()
        sel = [f for f in FACTORS if res[side, f]["tune"]["b"] > 0 and res[side, f]["tune"]["t"] > 2]
        P(f"  {nm}: selected on tune: {sel}")
        if not sel:
            continue
        g["score"] = sum((g[f] >= cuts[side, f]).astype(int) for f in sel)
        gt, gh = g[g.t_in < HOLDOUT], g[g.t_in >= HOLDOUT]
        best, best_net = None, -9
        for k in range(1, len(sel) + 1):
            a, b = gt[gt.score >= k], gh[gh.score >= k]
            if len(a) >= MIN_TUNE_TRADES and a.net.mean() > best_net:
                best, best_net = k, a.net.mean()
            P(f"    score >= {k}: tune  {cell(a)}")
            P(f"                 holdout {cell(b)}")
        if best is None:
            P("    no k has enough tune trades")
            continue
        a, b = gt[gt.score >= best], gh[gh.score >= best]
        yrs = (b.t_in.max() - b.t_in.min()).days / 365.25 if len(b) else 1
        tr = len(b) >= MIN_HOLD_TRADES and b.net.mean() > 0 and a.net.mean() > 0 and t_by_day(b.net, b.day) > 2
        chosen[side] = (g, best)
        P(f"    CHOSEN k = {best} (best tune mean net {best_net * 100:+.2f}%): holdout n {len(b)} ({len(b) / yrs:.0f} a year), net {b.net.mean() * 100:+.2f}% "
          f"(t {t_by_day(b.net, b.day):+.1f}), gross {b.gross.mean() * 100:+.2f}% = break-even round-trip fee {b.gross.mean() * 1e4:.0f}bp; "
          f"excess vs control {b.ex.mean() * 100:+.2f}%")
        P(f"    TRADABLE (net > 0 on both halves, holdout t > 2, >= {MIN_HOLD_TRADES} trades): {'YES' if tr else 'no'}")
        cap = ((a.r24 <= -0.10).mean(), (b.r24 <= -0.10).mean())
        P(f"    diagnostic - share with the coin down >= 10% over 24 bars (capit2's family): tune {cap[0] * 100:.0f}% / holdout {cap[1] * 100:.0f}%; "
          f"holdout net without them {b[b.r24 > -0.10].net.mean() * 100:+.2f}% (n {int((b.r24 > -0.10).sum())})")
        pl_ = []
        for _ in range(200):
            fl = rng.permutation((gh.score >= best).to_numpy())
            pl_.append(gh.net.to_numpy()[fl].mean())
        P(f"    placebo - the same share of holdout events flagged at random, 200 draws: mean net {np.mean(pl_) * 100:+.2f}% (sd {np.std(pl_) * 100:.2f}); "
          f"the chosen subset is {(b.net.mean() - np.mean(pl_)) / max(np.std(pl_), 1e-9):+.1f} sd above it")
    return "\n".join(L)


def main():
    if "--refit" in sys.argv or not CACHE.exists():
        T = build_events()
        T.to_pickle(CACHE)
    else:
        T = pd.read_pickle(CACHE)
    txt = report(T, np.random.default_rng(1))
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
