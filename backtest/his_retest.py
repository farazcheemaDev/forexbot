"""THE MICRO-LEVEL SCALP - does he trade off (or toward) the highs and lows of the last few minutes? (2026-10-12)

WHY      his_chart_capfx.py (his own chart, 2026-10-08): inside a violent range he SOLD as a bounce stalled and took profit
         at the low of four minutes before, then BOUGHT the retest of that same low and was out 6 s later. Day-scale levels
         (his_keylevels.py) and the last 14 bars' swing (his_model.py) were ordinary at his moments; this tests the
         specific picture - levels a few minutes old, a RETEST of them, and room to the other side - on all his trades,
         and as a rule on every day.

DATA     Exness USTECm ticks (strategy_analysis/data/ustec_tick_days.pkl, 181 days 2026-01..09-14), 1-second mid and
         spread; his NASDAQ entries at the corrected clock (his_tape.entries).
AT A MOMENT T, side s, the level window = [T - 15 min, T - 60 s]:
    lo / hi        its low / high;  p = mid at T
    dist_level     points from p to the level BEHIND the trade (p - lo for a buy, hi - p for a sell): small = trading off it
    room           points to the level AHEAD (hi - p for a buy, p - lo for a sell)
    retest         the level behind was touched, price moved >= 10 points away from it, and p is back within 8 points
    side_by_range  the side a range-trader takes: buy in the lower third of [lo, hi], sell in the upper third
TESTS
    A  his entries vs the same sitting's moments (+-1..20 min, his direction): rank of dist_level (low = at a level) and
       room (high = room to run); retest rate; does side_by_range agree with HIS side?
    B  THE RULE on all 181 days, every 15 s: on a retest of the 15-minute low buy, of the high sell (+-7 race at the real
       ask / bid, 30-min cap, one position at a time) - against random sides at the same moments; tune / holdout halves.

REGISTERED BEFORE THE RUN (2026-10-12)
    1. A: dist_level rank 0.40-0.60 and room rank 0.40-0.60 (his moments ordinary on micro-levels as on day levels).
    2. A: retest rate at his entries under 1.5x the sitting's; side_by_range agrees with his side 40-65%.
    3. B: the retest rule wins within +-3 points of random sides and nets <= 0 after the spread on both halves.
    LEAD LINE: dist_level rank <= 0.35 or retest >= 2x with p < 0.01, AND B positive on both halves -> a micro-level bot.

RESULT (2026-10-12, logs/his_retest.txt) - A STYLE LEAN, NOT AN EDGE. Lead line not hit.
    A (42 entries, 1,553 sitting moments): he enters a little nearer the 15-minute level behind him (median 18.3 vs 25.7
      points, rank 0.41, p 0.044) with a little more room ahead (24.9 vs 19.5, rank 0.59, p 0.10); retests 17% vs 10%
      (1.59x, p 0.20). The range-trader's side (buy low in the range, sell high) agrees with his side 50% of 30.
      Prediction 1 right (inside 0.40-0.60, just), 2 wrong (1.59x, over 1.5x, not significant).
    B the rule on 181 days: won 36.1% / 36.3% of +-7 races, -1.92 / -1.90 points a trade (tune / holdout) - random
      sides at the same moments 35.9% / 35.1%. Prediction 3 right.
    Like s34's "entries in the better part of the minute": he enters on a pullback toward a recent level, with room to
    run - but the level does not tell the side, and trading it as a rule is the coin flip minus the spread.

    python -m backtest.his_retest
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402

LOG = ROOT / "logs" / "his_retest.txt"
WIN, LAG, AWAY, NEAR, X = 900, 60, 10.0, 8.0, 7.0


def grid(day):
    ts, mid, spr = day
    g = np.arange(np.ceil(ts[0]), ts[-1], 1.0)
    gi = np.searchsorted(ts, g, "right") - 1
    return g, mid[gi], spr[gi]


def feats(g, gm, i, s):
    """features at grid second i for side s; None when the window is not there."""
    a, b = i - WIN, i - LAG
    if a < 0:
        return None
    w = gm[a:b]
    lo, hi, p = w.min(), w.max(), gm[i]
    if hi - lo < 1:
        return None
    if s == 1:
        lvl_i = int(np.argmin(w))
        away = gm[a + lvl_i:i].max() - lo
        dist, room = p - lo, hi - p
    else:
        lvl_i = int(np.argmax(w))
        away = hi - gm[a + lvl_i:i].min()
        dist, room = hi - p, p - lo
    pos = (p - lo) / (hi - lo)
    side_rng = 1 if pos <= 1 / 3 else (-1 if pos >= 2 / 3 else 0)
    return dict(dist=dist, room=room, retest=bool(away >= AWAY and dist <= NEAR), side_rng=side_rng)


def race(gm, gsp, i, side, cap=1800):
    e = gm[i] + side * gsp[i] / 2
    p = side * ((gm[i + 1:i + cap] - side * gsp[i + 1:i + cap] / 2) - e)
    up, dn = np.flatnonzero(p >= X), np.flatnonzero(p <= -X)
    if len(up) and (not len(dn) or up[0] < dn[0]):
        return X, up[0] + 1
    if len(dn):
        return -X, dn[0] + 1
    return (float(p[-1]) if len(p) else 0.0), len(p)


def main():
    from scipy.stats import binomtest, wilcoxon
    cache = pickle.loads(TP.TICKS.read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    grids = {}
    x = TP.entries()
    rows = []
    for r in x.itertuples():
        if r.d not in cache or cache[r.d] is None or r.t < WIN + 60:
            continue
        if r.d not in grids:
            grids[r.d] = grid(cache[r.d])
        g, gm, _ = grids[r.d]
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if r.t + 60 * m > WIN + 60 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            i = int(np.searchsorted(g, t, "right") - 1)
            if i >= len(g):
                continue
            f = feats(g, gm, i, r.s)
            if f is not None:
                rows.append(dict(entry=r.Index, who=who, s=r.s, **f))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    out = [f"backtest/his_retest.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; levels = the high / low of [T-15 min, T-60 s]; "
           f"{len(H)} of his entries, {len(N)} same-sitting moments", ""]

    def rank(col):
        rk = []
        for _, gg in D.groupby("entry"):
            h, n = gg[gg.who == "his"], gg[gg.who == "near"]
            if len(h) and len(n) >= 10:
                hv, nv = h[col].iat[0], n[col].to_numpy()
                rk.append((nv < hv).mean() + 0.5 * (nv == hv).mean())
        rk = np.array(rk)
        return rk.mean(), wilcoxon(rk - 0.5).pvalue, len(rk)

    rd, pd_, n1 = rank("dist")
    rr, pr, _ = rank("room")
    out.append("A. HIS ENTRIES vs his sittings' other moments (his direction)")
    out.append(f"   dist to the level behind: his median {H.dist.median():.1f} pts vs {N.dist.median():.1f}; rank {rd:.2f} (p {pd_:.3f}, "
               f"{n1} entries; low = nearer the level)")
    out.append(f"   room to the level ahead:  his median {H.room.median():.1f} pts vs {N.room.median():.1f}; rank {rr:.2f} (p {pr:.3f})")
    ht, nt = H.retest.mean(), N.retest.mean()
    p_rt = binomtest(int(H.retest.sum()), len(H), max(nt, 1e-9)).pvalue
    out.append(f"   retest of a 15-min level: his {ht * 100:.0f}% ({int(H.retest.sum())} of {len(H)}) vs {nt * 100:.0f}% -> "
               f"{ht / max(nt, 1e-9):.2f}x (p {p_rt:.3f})")
    v = H[H.side_rng != 0]
    ag = (v.side_rng == v.s).mean() if len(v) else np.nan
    p_ag = binomtest(int((v.side_rng == v.s).sum()), len(v), 0.5).pvalue if len(v) else np.nan
    out.append(f"   range-trader's side agrees with HIS side: {ag * 100:.0f}% of {len(v)} entries in an outer third (p {p_ag:.3f}); "
               f"{(H.side_rng == 0).sum()} in the middle third")
    out.append("")

    # B. the rule on every day
    cut = days[int(len(days) * 0.6)]
    rng = np.random.default_rng(7)
    res = {"tune": ([], []), "HOLDOUT": ([], [])}
    for d in days:
        g, gm, gsp = grids.get(d) or grid(cache[d])
        half = "tune" if d < cut else "HOLDOUT"
        free = -1
        for i in range(WIN + 60, len(g) - 1801, 15):
            if i <= free:
                continue
            fb, fs = feats(g, gm, i, 1), feats(g, gm, i, -1)
            side = 1 if (fb and fb["retest"]) else (-1 if (fs and fs["retest"]) else 0)
            if fb and fs and fb["retest"] and fs["retest"]:
                side = 0
            if side == 0:
                continue
            pnl, dur = race(gm, gsp, i, side)
            res[half][0].append(pnl)
            res[half][1].append(race(gm, gsp, i, int(rng.choice([-1, 1])))[0])
            free = i + dur
    out.append("B. THE RULE on all days: buy the retest of the 15-min low / sell the retest of the high, +-7 at real prices")
    bpos = []
    for half, (a, b) in res.items():
        a, b = np.array(a), np.array(b)
        t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
        out.append(f"   {half:7s}: {len(a):6d} trades won {np.mean(a >= X) * 100:4.1f}% net {a.mean():+.2f} pts (t {t:+.1f}) | random side "
                   f"won {np.mean(b >= X) * 100:4.1f}% net {b.mean():+.2f} | diff {(np.mean(a >= X) - np.mean(b >= X)) * 100:+.1f} points of win rate")
        bpos.append((a.mean() > 0, (np.mean(a >= X) - np.mean(b >= X)) * 100))
    out.append("")
    out.append("REGISTERED PREDICTIONS")
    out.append(f"  1 dist rank {rd:.2f}, room rank {rr:.2f} within 0.40-0.60 -> "
               f"{'RIGHT' if 0.4 <= rd <= 0.6 and 0.4 <= rr <= 0.6 else 'WRONG'}")
    out.append(f"  2 retest {ht / max(nt, 1e-9):.2f}x < 1.5x and range-side agreement {ag * 100:.0f}% within 40-65% -> "
               f"{'RIGHT' if ht / max(nt, 1e-9) < 1.5 and 0.40 <= ag <= 0.65 else 'WRONG'}")
    out.append(f"  3 rule within +-3 win-rate points of random and net <= 0 on both halves: " +
               ", ".join(f"{dd:+.1f}" for _, dd in bpos) +
               f" -> {'RIGHT' if all(abs(dd) <= 3 and not pos for pos, dd in bpos) else 'WRONG'}")
    lead = (rd <= 0.35 or (ht >= 2 * nt and p_rt < 0.01)) and all(pos for pos, _ in bpos)
    out.append(f"  LEAD LINE: {'HIT - a micro-level bot candidate' if lead else 'not hit'}")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
