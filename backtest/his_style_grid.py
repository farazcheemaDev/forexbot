"""TWEAKING THE HIS-STYLE BOT - 256 versions, chosen on the first 60% of days, judged once on the rest (2026-10-16)

The user: "change it or tweak it, whatever gives a better result". Done the only way that cannot fool us: a wide grid, the
best chosen on the TUNE days only, then read once on the HOLDOUT days, plus a count of versions positive on both halves
against what luck gives.
ENTRIES (16) on Exness USTECm 1-s ticks, 10:00-16:00 New York, <= 3 a day, >= 5 minutes apart:
    day move from the 09:30 open >= 0.3% / 0.6%  x  pullback >= 3 / 8 points (up to 15) against the day's direction in
    the last 60 s  x  calm tape required or not  x  side WITH the day's trend or AGAINST it (fade)
EXITS (16): target +5 / +7 / +10 / +15  x  stop -7 / -10 / -15 / -30 points, at the real bid / ask, 30-minute cap.
CHANCE   with no edge, about 1 in 4 versions is positive on both halves by luck if halves are independent (fewer, since
         neighbouring versions share trades).

REGISTERED BEFORE THE RUN (2026-10-16)
    1. The tune-chosen best version is net <= 0 on the holdout.
    2. Versions positive on both halves: no more than ~25% of 256 (chance).
    LEAD LINE: the tune-chosen best is positive on the holdout with t >= 2 AND >= 30 holdout trades -> paper-trade it.

RESULT (2026-10-16, logs/his_style_grid.txt) - DEAD; both predictions right, lead line not hit.
    The tune days' best (day >= 0.3%, pullback >= 3, FADE, +15 / -30) - +0.76 a trade on tune (t +0.7) - reads -0.25 on the
    holdout. 2 of 256 versions are positive on both halves (1%; chance would give more), both at t <= 1.0. Trading WITH
    the day's trend loses -2.75 / -3.52 a trade on average; fading it -1.70 / -0.68 - every family below zero.

    python -m backtest.his_style_grid
"""
from __future__ import annotations

import itertools
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.his_style_bot import day_grid  # noqa: E402

LOG = ROOT / "logs" / "his_style_grid.txt"
TPS, SLS, CAP = (5, 7, 10, 15), (7, 10, 15, 30), 1800
ENTRY = list(itertools.product((0.3, 0.6), (3, 8), (True, False), ("trend", "fade")))


def entries(g, gm, gsp, cnt, D, P, calm, side_mode):
    op = gm[0]
    c30 = pd.Series(cnt).rolling(30, min_periods=30).sum().to_numpy()
    c600 = pd.Series(cnt).rolling(600, min_periods=600).sum().to_numpy() / 20
    hi = pd.Series(gm).rolling(60, min_periods=60).max().to_numpy()
    lo = pd.Series(gm).rolling(60, min_periods=60).min().to_numpy()
    out, last = [], -10**9
    for i in range(1800, min(23400, len(g) - CAP - 1)):
        if len(out) >= 3:
            break
        if i - last < 300:
            continue
        dm = (gm[i] - op) / op * 100
        if abs(dm) < D:
            continue
        s = 1 if dm > 0 else -1
        if calm and not (c30[i] <= c600[i]):
            continue
        back = s * (gm[i] - (hi[i] if s > 0 else lo[i]))
        if not (-15 <= back <= -P):
            continue
        out.append((i, s if side_mode == "trend" else -s))
        last = i
    return out


def exits(gm, gsp, i, s):
    """the spread-inclusive path his way for 30 minutes, scored for every target / stop pair."""
    e = gm[i] + s * gsp[i] / 2
    j = min(i + CAP, len(gm) - 1)
    p = s * ((gm[i + 1:j] - s * gsp[i + 1:j] / 2) - e)
    res = {}
    for tp in TPS:
        up = np.flatnonzero(p >= tp)
        for sl in SLS:
            dn = np.flatnonzero(p <= -sl)
            if len(up) and (not len(dn) or up[0] < dn[0]):
                res[(tp, sl)] = tp
            elif len(dn):
                res[(tp, sl)] = -sl
            else:
                res[(tp, sl)] = float(p[-1]) if len(p) else 0.0
    return res


def main():
    cache = pickle.loads((ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    pts = {}                                                            # (entry, tp, sl, half) -> list
    for d in days:
        g, gm, gsp, cnt = day_grid(cache[d])
        if len(g) < 7200:
            continue
        half = "tune" if d < cut else "hold"
        for ek in ENTRY:
            for i, s in entries(g, gm, gsp, cnt, *ek):
                for (tp, sl), v in exits(gm, gsp, i, s).items():
                    pts.setdefault((ek, tp, sl, half), []).append(v)
    cells = []
    for ek in ENTRY:
        for tp in TPS:
            for sl in SLS:
                a = np.array(pts.get((ek, tp, sl, "tune"), []))
                b = np.array(pts.get((ek, tp, sl, "hold"), []))
                if len(a) < 10 or len(b) < 10:
                    continue
                cells.append(dict(D=ek[0], P=ek[1], calm=ek[2], side=ek[3], tp=tp, sl=sl,
                                  n_t=len(a), net_t=a.mean(), t_t=a.mean() / (a.std(ddof=1) / np.sqrt(len(a))),
                                  n_h=len(b), net_h=b.mean(), t_h=b.mean() / (b.std(ddof=1) / np.sqrt(len(b))),
                                  win_h=np.mean(b > 0)))
    C = pd.DataFrame(cells)
    both = C[(C.net_t > 0) & (C.net_h > 0)]
    best = C.sort_values("net_t", ascending=False).iloc[0]
    top5 = C.sort_values("net_t", ascending=False).head(5)
    fmt = lambda r: (f"day>={r.D}% pull>={r.P} calm={'Y' if r.calm else 'N'} {r.side:<5} +{r.tp}/-{r.sl}: tune {r.net_t:+.2f} "
                     f"(t {r.t_t:+.1f}, {r.n_t}) | HOLDOUT {r.net_h:+.2f} (t {r.t_h:+.1f}, {r.n_h}, won {r.win_h * 100:.0f}%)")
    out = [f"backtest/his_style_grid.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, holdout from {cut:%Y-%m-%d}; "
           f"{len(C)} versions (net points a trade at the real spread)", "",
           "THE TUNE DAYS' TOP 5, read on the holdout:"] + ["   " + fmt(r) for r in top5.itertuples()]
    out += ["", f"versions positive on BOTH halves: {len(both)} of {len(C)} ({len(both) / len(C) * 100:.0f}%)"]
    out += ["   " + fmt(r) for r in both.sort_values("net_h", ascending=False).head(8).itertuples()]
    out += ["", f"by side: trend versions net (tune / holdout) {C[C.side == 'trend'].net_t.mean():+.2f} / {C[C.side == 'trend'].net_h.mean():+.2f}; "
            f"fade {C[C.side == 'fade'].net_t.mean():+.2f} / {C[C.side == 'fade'].net_h.mean():+.2f}"]
    lead = best.net_h > 0 and best.t_h >= 2 and best.n_h >= 30
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 tune-chosen best on the holdout {best.net_h:+.2f} <= 0 -> {'RIGHT' if best.net_h <= 0 else 'WRONG'}",
            f"  2 positive on both halves {len(both) / len(C) * 100:.0f}% <= 25% -> {'RIGHT' if len(both) / len(C) <= 0.25 else 'WRONG'}",
            f"  LEAD LINE: {'HIT - ' + fmt(best) if lead else 'not hit'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
