"""WHICH FAKE BREAKS DOES HE TAKE? - the reclaim setup split by what a trader sees in it (2026-11-22)

THE USER (2026-11-22), continuing the hint his_reclaim.py turned into a finding: he trades fake breaks (7 of 7 won) while the setup itself
is a coin flip on every day (50-52%). The next question a trader asks: what is different about the fake breaks that really reverse?
DATA   the same moments as his_reclaim.py (181 Exness tick days, every 1-minute close + 14 s, 09:45-15:45 New York; the nearest swing level
       of the last 120 minutes within 10 points, broken by more than 3 points, the price back on the broken side; reclaim side traded).
WHAT A TRADER SEES (at the moment, closed data only)
  depth        how far the break went beyond the level (points, to the deepest point since it formed)
  beyond       how many closed 1-minute bars traded beyond the level (by more than 3 points)
  since_ext    minutes since that deepest point
  snap         points the price has already come back from the deepest point
  dist_now     points the price still sits beyond the level (how close to reclaiming it)
  touches      tests of the level before it broke
  activity     ticks in the last 60 s against the 10 minutes before (x)
TESTS  the reclaim race (+-7, race2, 10 minutes) by quintile of each feature, both halves; and where his 7 reclaims sit in each feature's
       distribution (percentile among all the setup's moments).
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  C1  No quintile of any feature reaches 58% on both halves (61% is needed to pay a ~1.5-point spread). (75%)
  C2  His 7 reclaims are not concentrated: no feature has 5 or more of the 7 in one quintile. (55%)

RESULT (2026-11-22, logs/his_reclaim_detail.txt): HIS FAKE BREAKS LOOK LIKE EVERY OTHER FAKE BREAK. No quintile of depth, bars beyond,
  minutes since the extreme, snap-back, distance to the level, touches or tick activity lifts the reclaim race above 52-56% on both
  halves (best: depth 10-18 points, 52.0% / 54.4%). His 7 reclaims are spread across every feature's quintiles (at most 3-4 of 7 in one):
  breaks of 11-49 points, 2-51 bars beyond, 1-47 minutes after the extreme, the price back within 0.2-4.2 points of the level. C1, C2
  right. What he trades is visible (fake breaks, re-entered near the level); which of them he takes is not in these readings.

    python -m backtest.his_reclaim_detail
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_level_memory import BREAK, K, LOOK, NEAR, TICKS, TOUCH, minute_bars, swings  # noqa: E402

LOG = ROOT / "logs" / "his_reclaim_detail.txt"
FEATS = ("depth", "beyond", "since_ext", "snap", "dist_now", "touches", "activity")


def detail(ts, mid, hi, lo, sh, sl, t: float):
    i = np.searchsorted(ts, t - 1.0, side="right") - 1
    if i < 0:
        return None
    p = float(mid[i])
    M = int(t // 60) - 1
    best = None
    for kind, idx, arr in (("hi", sh, hi), ("lo", sl, lo)):
        for j in idx[(idx <= M - K) & (idx >= M - LOOK)]:
            d = abs(arr[j] - p)
            if d <= NEAR and (best is None or d < best[0]):
                best = (d, kind, int(j), float(arr[j]))
    if best is None:
        return None
    _, kind, j, v = best
    seg_lo, seg_hi = lo[j + 1:M + 1], hi[j + 1:M + 1]
    if not len(seg_lo):
        return None
    if kind == "lo":
        brk = np.flatnonzero(seg_lo < v - BREAK)
        if not len(brk) or p >= v:
            return None
        e = int(np.nanargmin(seg_lo))
        depth, snap, dist_now, side = v - seg_lo[e], p - seg_lo[e], v - p, 1
        touches = int(np.sum(np.abs(lo[j + K + 1:j + 1 + brk[0]] - v) <= TOUCH))
    else:
        brk = np.flatnonzero(seg_hi > v + BREAK)
        if not len(brk) or p <= v:
            return None
        e = int(np.nanargmax(seg_hi))
        depth, snap, dist_now, side = seg_hi[e] - v, seg_hi[e] - p, p - v, -1
        touches = int(np.sum(np.abs(hi[j + K + 1:j + 1 + brk[0]] - v) <= TOUCH))
    a60 = np.searchsorted(ts, t - 60) ; a660 = np.searchsorted(ts, t - 660); b = np.searchsorted(ts, t, side="right")
    act = (b - a60) / max((a60 - a660) / 10.0, 1.0)
    return dict(side=side, depth=float(depth), beyond=int(len(brk)), since_ext=int(M - (j + 1 + e)), snap=float(snap),
                dist_now=float(dist_now), touches=touches, activity=float(act))


def main():
    import backtest.his_tape as TP
    from backtest.his_race_curve import race2
    cache = pickle.loads(TICKS.read_bytes())
    prep = {}
    for day, dd in cache.items():
        if dd is None:
            continue
        ts, mid = dd[0], dd[1]
        hi, lo = minute_bars(ts, mid)
        sh, sl = swings(hi, lo)
        prep[day] = (ts, mid, hi, lo, sh, sl)
    days = sorted(prep)
    cut = days[int(len(days) * 0.6)]
    rows = []
    for day in days:
        ts, mid, hi, lo, sh, sl = prep[day]
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            d = detail(ts, mid, hi, lo, sh, sl, t)
            if d is None:
                continue
            w = race2(ts, mid, t, d["side"], 600, 7, 7)
            if w is not None:
                rows.append(dict(day=day, win=w, **d))
    R = pd.DataFrame(rows)
    R["half"] = np.where(R.day < cut, "tune", "hold")
    his = []
    for r in TP.entries().itertuples():
        pr = prep.get(r.d)
        if pr is None or r.t < 15 * 60:
            continue
        d = detail(*pr, r.t)
        if d is not None and d["side"] == r.s:
            his.append(dict(win=race2(pr[0], pr[1], r.t, r.s, 600, 7, 7), **d))
    Hh = pd.DataFrame(his)
    out = [f"backtest/his_reclaim_detail.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(R):,} reclaim moments on {len(days)} days "
           f"(split {pd.Timestamp(cut):%Y-%m-%d}); his reclaim trades: {len(Hh)} (won {int((Hh.win == 1).sum())})", ""]
    best = []
    for f in FEATS:
        q = R[f].rank(method="first", pct=True)
        R["_q"] = np.minimum((q * 5).astype(int), 4)
        edges = R.groupby("_q")[f].agg(["min", "max"])
        line = f"  {f:<10}"
        for k in range(5):
            wt = R[(R._q == k) & (R.half == "tune")].win.mean()
            wh = R[(R._q == k) & (R.half == "hold")].win.mean()
            best.append((min(wt, wh), f, k, wt, wh))
            line += f"  Q{k + 1} [{edges.loc[k, 'min']:.4g}-{edges.loc[k, 'max']:.4g}] {wt:.0%}/{wh:.0%}"
        his_pct = [float((R[f] < v).mean() * 100) for v in Hh[f]]
        his_q = [min(int(pc / 20), 4) + 1 for pc in his_pct]
        line += f"   | his 7 in quintiles {sorted(his_q)}"
        out.append(line)
    best.sort(reverse=True)
    top = best[0]
    conc = {}
    for f in FEATS:
        qs = [min(int(float((R[f] < v).mean() * 100) / 20), 4) for v in Hh[f]]
        conc[f] = max(np.bincount(qs, minlength=5))
    out += ["", f"  (each cell: the reclaim's race win rate tune / holdout in that quintile; bracket = the feature's range)",
            f"  best quintile on its weaker half: {top[1]} Q{top[2] + 1} {top[3]:.1%} / {top[4]:.1%}", "",
            "  his reclaim trades, the features a trader sees:"]
    for r in Hh.itertuples():
        out.append(f"    {'BUY ' if r.side > 0 else 'SELL'} depth {r.depth:5.1f}  beyond {r.beyond:>2} bars  {r.since_ext:>3} min since the extreme  "
                   f"snap {r.snap:5.1f}  {r.dist_now:4.1f} pts from the level  touches {r.touches}  activity {r.activity:4.2f}x  "
                   f"{'won' if r.win == 1 else 'lost' if r.win == 0 else '-'}")
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  C1 no quintile reaches 58% on both halves -> {ok(top[0] < 0.58)} (best {top[1]} Q{top[2] + 1}: {top[0]:.1%} on its weaker half)",
            f"  C2 no feature has 5+ of his 7 in one quintile -> {ok(max(conc.values()) < 5)} ("
            + ", ".join(f"{f} {c}" for f, c in conc.items()) + ")"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
