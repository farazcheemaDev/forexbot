"""THE MENDED VERSION - his trade architecture with a hard stop and a measurable side (2026-10-16)

The user's /goal, part 2: keep his +7 take-profit and his ~0.7-point pullback entry, add a hard stop, and replace his
side with a measurable signal - order-flow imbalance (OFI) or retail sentiment. Find the stop and the win rate needed.

THE MATH (exact for a driftless price; Exness USTECm, entry at the ask / bid, exits at the opposite side)
    A +7 / -S trade needs the MID to go +(7 + c) before -(S - c), c = the round-trip spread in points.
    break-even win rate     p* = S / (7 + S)                     (net +7 a win, -S a loss)
    a coin flip's win rate  p0 = (S - c) / (7 + S)
    edge needed             p* - p0 = c / (7 + S)                 -> a wider stop needs fewer points of edge, but a signal
                                                                     must then stay right for longer
SIDES TESTED (none is his side)
    qofi    Exness quote-flow imbalance: up-ticks minus down-ticks of the mid over the last 30 / 60 / 120 s, its top
            quintile (tuned on the first 60% of days) gives the side - 181 days, 10:00-16:00 New York
    cofi    CME NQ trade-flow imbalance (buy-aggressor minus sell-aggressor volume, his_tape.py) over 30 / 60 / 120 s,
            top quintile - only inside his 31 cached windows (22.8 hours)
    coin    a seeded coin flip - the control
    sentiment: NOT testable - the recorder holds 14 NAS100 snapshots (2026-10-12 08:51-20:29 UTC, 30 minutes apart;
            strategy_analysis/data/sentiment/fxssi_ratios.csv) and stopped; a 30-minute retail ratio cannot time a 30-s
            pullback, and its own predictions (sentiment_rec.py R1-R3) need >= 3 months of recording.
ENTRY    the side's signal is on, and in the last 3 s the mid came back AGAINST it by >= 0.7 points (his pullback,
         s34 / his_loopholes.py), the last second not still running against it by > 1.5. One position at a time.
EXIT     +7 at the real bid / ask, -S hard stop (S = 5 / 7 / 10 / 15 / 20 / 30), 30-minute cap.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. Coin-flip win rates sit 4-15 points below break-even at every stop (the spread).
    2. No qofi cell is net positive on BOTH halves.
    3. cofi wins within 4 points of the coin at the same stop.
    LEAD LINE: a cell positive on both halves, t >= 2 on each, >= 100 holdout trades -> a paper-trade candidate.

RESULT (2026-10-16, logs/his_mended.txt) - DEAD; no cell positive on both halves, the lead line not hit.
    Measured spread c = 2.16 points (median, 10:00-16:00 NY, 181 days). Every side at every stop loses about the spread:
    coin -2.07..-2.50 a trade, quote-flow (qofi) -2.14..-2.90 (slightly WORSE than the coin), CME trade flow (cofi, only
    50-430 trades a cell inside his windows) -0.59..-5.01, its one positive cell (+0.75, 30-s flow, stop 30, tune) -2.73
    on the holdout. The stop changes the win rate (28% at -5 .. 73% at -30), never the expectancy. The pullback entry
    adds nothing: a coin flip entered on a 0.7-point pullback pays the same 2.2 points as any entry.
    Predictions: 2 right; 1 wrong by a hair (coin 7.8-15.1 points under break-even, registered 4-15); 3 wrong (cofi
    -10..+10 points from the coin - small cells, no consistent sign).
    WIN RATE NEEDED (per-trade Sharpe = (p - p*) / sqrt(p(1-p)), annual = x sqrt(trades)): for an annual Sharpe of 2 on
    500 trades a year, 46% at -5, 55% at -7, 63% at -10, 72% at -15, 78% at -20, 84% at -30 - 9 to 23 points of
    direction above a coin flip. The best side measured anywhere in s36-s68 adds 0-5.

    python -m backtest.his_mended
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.his_style_bot import day_grid  # noqa: E402

DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "his_mended.txt"
TP, CAP = 7.0, 1800
STOPS = (5, 7, 10, 15, 20, 30)
WS = (30, 60, 120)


def trade(gm, gsp, i, s, S):
    e = gm[i] + s * gsp[i] / 2
    j = min(i + CAP, len(gm) - 1)
    p = s * ((gm[i + 1:j] - s * gsp[i + 1:j] / 2) - e)
    up, dn = np.flatnonzero(p >= TP), np.flatnonzero(p <= -S)
    if len(up) and (not len(dn) or up[0] < dn[0]):
        return float(p[up[0]]), up[0] + 1
    if len(dn):
        return float(p[dn[0]]), dn[0] + 1
    return (float(p[-1]) if len(p) else 0.0), len(p)


def pullback_ok(gm, i, s):
    back = s * (gm[i] - gm[i - 3:i + 1].max() if s > 0 else gm[i] - gm[i - 3:i + 1].min())
    return back <= -0.7 and s * (gm[i] - gm[i - 1]) > -1.5


def run(gm, gsp, sig, lo, hi, S, rng=None):
    """sig: array of side (+1 / -1 / 0) per second; None = coin flip at a pullback in either direction."""
    out, free = [], -1
    for i in range(max(lo, 5), min(hi, len(gm) - CAP - 1)):
        if i <= free:
            continue
        if sig is None:
            s = 1 if rng.random() < 0.5 else -1
        else:
            s = sig[i]
            if s == 0:
                continue
        if not pullback_ok(gm, i, s):
            continue
        pnl, dur = trade(gm, gsp, i, s, S)
        out.append(pnl)
        free = i + dur
    return out


def stats(a):
    a = np.asarray(a)
    if len(a) < 3:
        return len(a), np.nan, np.nan, np.nan
    return len(a), np.mean(a > 0), a.mean(), a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))


def main():
    cache = pickle.loads((DATA / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    G = {}
    spreads = []
    for d in days:
        g, gm, gsp, cnt = day_grid(cache[d])
        if len(g) < 7200:
            continue
        up = np.r_[0, np.sign(np.diff(gm))]
        G[d] = (gm, gsp, {w: pd.Series(up).rolling(w, min_periods=w).sum().to_numpy() for w in WS})
        spreads.append(np.median(gsp[1800:23400]))
    c = float(np.median(spreads))
    out = [f"backtest/his_mended.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(G)} Exness tick days, holdout from "
           f"{cut:%Y-%m-%d}; median spread c = {c:.2f} points", "",
           "THE MATH: +7 / -S at spread c",
           f"  {'stop S':>7}{'break-even p*':>15}{'coin p0':>9}{'edge needed':>13}"]
    for S in STOPS:
        out.append(f"  {S:>7}{S / (7 + S) * 100:>14.1f}%{(S - c) / (7 + S) * 100:>8.1f}%{c / (7 + S) * 100:>11.1f} pts")
    # thresholds for qofi tuned on the tune half only
    thr = {w: np.nanquantile(np.abs(np.concatenate([G[d][2][w][1800:23400] for d in G if d < cut])), 0.8) for w in WS}
    out += ["", f"  {'side':<14}{'stop':>5}{'half':>9}{'trades':>8}{'won':>7}{'p*':>7}{'net/trade':>11}{'t':>7}"]
    R = {}
    for S in STOPS:
        for half, sel in (("tune", [d for d in G if d < cut]), ("HOLDOUT", [d for d in G if d >= cut])):
            rng = np.random.default_rng(11)
            a = [v for d in sel for v in run(G[d][0], G[d][1], None, 1800, 23400, S, rng)]
            R[("coin", S, half)] = stats(a)
            for w in WS:
                q = G
                a = []
                for d in sel:
                    f = q[d][2][w]
                    sig = np.where(np.nan_to_num(f) >= thr[w], 1, np.where(np.nan_to_num(f) <= -thr[w], -1, 0))
                    a += run(q[d][0], q[d][1], sig, 1800, 23400, S)
                R[(f"qofi{w}", S, half)] = stats(a)
    # CME trade-flow imbalance inside his windows
    import backtest.his_tape as TP
    T = pickle.loads((DATA / "nq_trades_windows.pkl").read_bytes())
    ns = np.concatenate([v.ns.to_numpy() for v in T.values()])
    o = np.argsort(ns, kind="stable")
    ns = ns[o]
    sv = np.concatenate([(v["size"] * v.aggr).to_numpy() for v in T.values()])[o]
    cum = np.r_[0, np.cumsum(sv)]
    tv = np.r_[0, np.cumsum(np.abs(sv))]
    wins = TP.windows(TP.entries())
    cofi_vals = {w: [] for w in WS}
    plan = []
    for a_, b_ in wins:
        d = (a_.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)).normalize()
        if d not in G:
            continue
        base = (d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        lo, hi = int((a_ - base).total_seconds()) + 130, int((b_ - base).total_seconds())
        sec = np.arange(lo, hi)
        at = (base.value + sec * 10**9)
        j = np.searchsorted(ns, at, "right")
        sig = {}
        for w in WS:
            i0 = np.searchsorted(ns, at - w * 10**9, "right")
            vol = tv[j] - tv[i0]
            sig[w] = np.where(vol > 0, (cum[j] - cum[i0]) / np.maximum(vol, 1), 0.0)
            cofi_vals[w].append(sig[w])
        plan.append((d, lo, hi, sig))
    cthr = {w: np.quantile(np.abs(np.concatenate(cofi_vals[w])), 0.8) for w in WS}
    for S in STOPS:
        for half in ("tune", "HOLDOUT"):
            sel = [p for p in plan if (p[0] < cut) == (half == "tune")]
            for w in WS:
                a = []
                for d, lo, hi, sig in sel:
                    gm, gsp, _ = G[d]
                    full = np.zeros(len(gm), dtype=int)
                    v = sig[w]
                    lo_c, hi_c = max(lo, 0), min(hi, len(gm))
                    if hi_c - lo_c < 10:
                        continue
                    full[lo_c:hi_c] = np.where(v[lo_c - lo:hi_c - lo] >= cthr[w], 1, np.where(v[lo_c - lo:hi_c - lo] <= -cthr[w], -1, 0))
                    a += run(gm, gsp, full, lo_c, hi_c, S)
                R[(f"cofi{w}", S, half)] = stats(a)
            rng = np.random.default_rng(13)
            a = [v for d, lo, hi, _ in sel if min(hi, len(G[d][0])) - max(lo, 0) >= 10
                 for v in run(G[d][0], G[d][1], None, max(lo, 0), hi, S, rng)]
            R[("coin@windows", S, half)] = stats(a)
    for k in sorted(R, key=lambda k: (k[0], k[1], k[2] != "tune")):
        n, wr, m, t = R[k]
        out.append(f"  {k[0]:<14}{k[1]:>5}{k[2]:>9}{n:>8}{wr * 100:>6.0f}%{k[1] / (7 + k[1]) * 100:>6.0f}%{m:>+11.2f}{t:>+7.1f}")
    names = {k[0] for k in R}
    both = sorted((nm, S) for nm in names for S in STOPS
                  if R[(nm, S, "tune")][2] > 0 and R[(nm, S, "HOLDOUT")][2] > 0)
    lead = [b for b in both if R[b + ("tune",)][3] >= 2 and R[b + ("HOLDOUT",)][3] >= 2 and R[b + ("HOLDOUT",)][0] >= 100]
    gap = [S / (7 + S) - R[("coin", S, h)][1] for S in STOPS for h in ("tune", "HOLDOUT")]
    qb = [b for b in both if b[0].startswith("qofi")]
    cg = [R[(f"cofi{w}", S, h)][1] - R[("coin@windows", S, h)][1] for w in WS for S in STOPS for h in ("tune", "HOLDOUT")
          if np.isfinite(R[(f"cofi{w}", S, h)][1])]
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 coin below break-even by 4-15 points: {min(gap) * 100:.1f}..{max(gap) * 100:.1f} -> "
            f"{'RIGHT' if min(gap) >= .04 and max(gap) <= .15 else 'WRONG'}",
            f"  2 no qofi cell positive on both halves: {qb if qb else 'none'} -> {'RIGHT' if not qb else 'WRONG'}",
            f"  3 cofi within 4 points of the coin: {min(cg) * 100:+.0f}..{max(cg) * 100:+.0f} -> "
            f"{'RIGHT' if all(abs(x_) <= .04 for x_ in cg) else 'WRONG'}",
            f"  positive on both halves: {both if both else 'none'}",
            f"  LEAD LINE: {lead if lead else 'not hit'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
