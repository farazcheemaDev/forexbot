"""DO HIS TRADES RIDE BURSTS? - what the move after his click looks like, against any +-7 move in the same windows (2026-10-12)

THE USER (2026-10-12): "the burst in NASDAQ - I think that has something to do with his strategy". ustec_burst_anatomy.py
showed bursts are foreseeable in time, not in direction, and that his clicks do not sit at predicted bursts. This asks
the other half: AFTER his click, does a burst come more often, and does his +7 arrive faster or burstier than any +7?

DATA     his NASDAQ clicks (his_headlines.clicks) on the Exness USTECm tick days; ustec_burst_anatomy.day_frame's 1-s grid
         (burst = >= 7 points within 5 s). Baseline: every 13th second of his own +-20-minute windows, the side that
         reaches +-7 first.

REGISTERED BEFORE THE RUN (2026-10-12)
    P1  a 5-s burst starts within 10 s of his click no more than 2x as often as at other seconds of his windows.
    P2  the median time from his click to a +7-point mid move his way is > 30 s.

RESULT (2026-10-12, logs/his_burst_after.txt) - his moves are ORDINARY moves; only the SIDE is special.
    41 clicks; his side reached +7 on the mid first in 39 (95%).
    P1 RIGHT: a burst follows within 10 s 22% of the time vs 23% at his windows' other seconds (ratio 0.94).
    P2 WRONG by a second: median 29 s (quartiles 14 / 68); baseline 33 s (14 / 78). Within 10 s: 18% vs 18%.
    Completed by a 5-s burst his way: 36% of his wins vs 38% of any +-7 move.
    So the burst is the market's normal way of covering 7 points, not his signal: his trades are no faster, no burstier
    and no more often followed by a burst than any other second. What he has is which way, nothing else.

    python -m backtest.his_burst_after
"""
import pickle, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from backtest.ustec_burst_anatomy import day_frame
from backtest.his_headlines import clicks
cache = pickle.loads((ROOT / "strategy_analysis/data/ustec_tick_days.pkl").read_bytes())
N = clicks(); N = N[N.kind == "NASDAQ"]
his10, base10, tt, burst_win, frames = [], [], [], [], {}
for r in N.itertuples():
    et = r.utc.tz_localize("UTC").tz_convert("America/New_York"); d = pd.Timestamp(et.date())
    if d not in cache or cache[d] is None: continue
    if d not in frames: frames[d] = day_frame(*cache[d])
    F, (g, gm, gsp) = frames[d]
    tsec = (et - et.normalize()).total_seconds() - 9.5 * 3600
    i = np.searchsorted(g, tsec, "right") - 1
    if i < 1 or i + 1800 >= len(g): continue
    occ = F.occ.to_numpy(); dr = F.dir.to_numpy()
    side = 1 if r.side == "BUY" else -1
    his10.append(occ[i:i + 10].any())
    lo, hi = max(np.searchsorted(g, tsec - 1200), 0), min(np.searchsorted(g, tsec + 1200), len(g) - 11)
    base10.append(np.mean([occ[j:j + 10].any() for j in range(lo, hi, 7)]))
    p = side * (gm[i + 1:i + 1800] - gm[i])
    up, dn = np.flatnonzero(p >= 7), np.flatnonzero(p <= -7)
    if len(up) and (not len(dn) or up[0] < dn[0]):
        tt.append(up[0] + 1)
        # did the +7 arrive inside one 5-s burst his way, i.e. a burst start in his favour within the 5 s before the hit?
        k = i + 1 + up[0]
        burst_win.append(bool(((occ[max(k - 5, i):k + 1]) & (dr[max(k - 5, i):k + 1] == side)).any()))
    else:
        tt.append(np.nan)
his10, base10, tt = np.array(his10), np.array(base10), np.array(tt, float)
print(f"his NASDAQ clicks on tick days: {len(his10)}")
print(f"P1 a 5-s burst starts within 10 s of his click: {his10.mean()*100:.0f}% | his own +-20-min windows: {base10.mean()*100:.0f}% "
      f"-> ratio {his10.mean()/base10.mean():.2f} ({'RIGHT' if his10.mean() <= 2*base10.mean() else 'WRONG'})")
w = tt[~np.isnan(tt)]
print(f"P2 his side reached +7 (mid) first in {len(w)} of {len(tt)}; time from click: median {np.median(w):.0f} s, "
      f"quartiles {np.percentile(w,25):.0f} / {np.percentile(w,75):.0f} s; within 10 s {np.mean(w<=10)*100:.0f}% "
      f"({'RIGHT' if np.median(w) > 30 else 'WRONG'})")
print(f"   of his wins, the +7 completed by a 5-s burst his way: {np.mean(burst_win)*100:.0f}%")
# baseline: other seconds of the same windows, the side that reaches +-7 first, same two measures
bt, bb = [], []
for r in N.itertuples():
    et = r.utc.tz_localize("UTC").tz_convert("America/New_York"); d = pd.Timestamp(et.date())
    if d not in frames: continue
    F, (g, gm, gsp) = frames[d]; occ = F.occ.to_numpy(); dr = F.dir.to_numpy()
    tsec = (et - et.normalize()).total_seconds() - 9.5 * 3600
    lo, hi = max(np.searchsorted(g, tsec - 1200), 1), min(np.searchsorted(g, tsec + 1200), len(g) - 1801)
    for j in range(lo, hi, 13):
        q = gm[j + 1:j + 1800] - gm[j]
        up, dn = np.flatnonzero(q >= 7), np.flatnonzero(q <= -7)
        a = up[0] if len(up) else 10**9; b = dn[0] if len(dn) else 10**9
        if min(a, b) == 10**9: continue
        s, h = (1, a) if a < b else (-1, b)
        bt.append(h + 1); k = j + 1 + h
        bb.append(bool(((occ[max(k - 5, j):k + 1]) & (dr[max(k - 5, j):k + 1] == s)).any()))
bt = np.array(bt, float)
print(f"   baseline (other seconds, whichever side hits 7 first, n={len(bt)}): median {np.median(bt):.0f} s, quartiles "
      f"{np.percentile(bt,25):.0f} / {np.percentile(bt,75):.0f}, within 10 s {np.mean(bt<=10)*100:.0f}%, completed by a burst {np.mean(bb)*100:.0f}%")
