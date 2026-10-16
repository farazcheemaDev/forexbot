"""A BOT BUILT FROM HIS HABITS - every tip from s30-s64 in one rule, on Exness ticks at the real spread (2026-10-16)

The user: "we can build something of our own, taking tips from his strategy". Each habit alone was tested and lost (s25,
s36, s52, s55); this combines all of them, with the one missing piece - his SIDE - replaced by the best stand-in his record
suggests: the day's own trend (his days lean to trending days, s64).
RULE     10:00-16:00 New York, Exness USTECm, 1-second grid (181 tick days 2026-01..09-14).
  day      today's move from the 09:30 open >= D% (D = 0.3 / 0.4 / 0.6): trade only in that direction
  calm     quote count over the last 30 s <= its 10-minute pace (his winners came in quiet tape; his losers in fast)
  pullback in the last 60 s the price came back against the day's trend by P..15 points (P = 3 / 5 / 8), and the last 5 s
           are flat or still against (|move his way| < 1) - never at the extreme of the last minute (position <= 0.6)
  exit     +7 points take-profit at the real bid / ask; -30 emergency stop (his worst loser was -31.75); 30-minute cap
  limits   one position at a time, at most 3 entries a day
CONTROL  the same entries with the side flipped, and the trend-only rule (same day filter, any second, no calm/pullback).
SPLIT    first 60% of days tune, last 40% holdout; the 9 cells reported on both, none chosen.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. No cell is net positive at the spread on BOTH halves.
    2. The best cell's win rate is within 8 points of the flipped side's (the habits do not carry direction).
    LEAD LINE: a cell positive on both halves with t >= 2 on each and >= 30 trades on the holdout -> a paper-trade candidate.

RESULT (2026-10-16, logs/his_style_bot.txt) - DEAD; both predictions right, lead line not hit.
    All 9 cells lose on both halves: wins 67-74% of trades, -2.5..-5.1 points a trade (t -1.9..-4.5; 155-318 trades a
    half). The SAME entries with the side FLIPPED win 73-77% and lose less (-1.5..-3.2). The trend-only rule: 68-73%,
    -2.5..-4.7. The 70% win rate is the +7 / -30 shape (small target, wide stop), not an edge: one -30 eats four +7s.

    python -m backtest.his_style_bot
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "his_style_bot.txt"
TP, SL, CAP = 7.0, 30.0, 1800


def trade(gm, gsp, i, s):
    e = gm[i] + s * gsp[i] / 2
    j = min(i + CAP, len(gm) - 1)
    p = s * ((gm[i + 1:j] - s * gsp[i + 1:j] / 2) - e)
    up, dn = np.flatnonzero(p >= TP), np.flatnonzero(p <= -SL)
    if len(up) and (not len(dn) or up[0] < dn[0]):
        return TP, up[0] + 1
    if len(dn):
        return -SL, dn[0] + 1
    return (float(p[-1]) if len(p) else 0.0), len(p)


def day_grid(day):
    ts, mid, spr = day
    g = np.arange(max(np.ceil(ts[0]), 0), ts[-1], 1.0)
    gi = np.searchsorted(ts, g, "right") - 1
    cnt = np.diff(np.r_[0, np.searchsorted(ts, g, "right")]).astype(float)
    return g, mid[gi], spr[gi], cnt


def run_day(day, D, P, mode):
    g, gm, gsp, cnt = day_grid(day)
    if len(g) < 7200:
        return []
    op = gm[0]
    c30 = pd.Series(cnt).rolling(30, min_periods=30).sum().to_numpy()
    c600 = pd.Series(cnt).rolling(600, min_periods=600).sum().to_numpy() / 20
    s60 = pd.Series(gm)
    hi60 = s60.rolling(60, min_periods=60).max().to_numpy()
    lo60 = s60.rolling(60, min_periods=60).min().to_numpy()
    out, free, n = [], -1, 0
    for i in range(1800, min(23400, len(g) - CAP - 1)):        # 10:00 .. 16:00 New York
        if i <= free or n >= 3:
            continue
        dm = (gm[i] - op) / op * 100
        if abs(dm) < D:
            continue
        s = 1 if dm > 0 else -1
        if mode == "trend_only":
            if i % 300:                                          # one look every 5 minutes, like a slow trend bot
                continue
        else:
            if not (c30[i] <= c600[i]):
                continue
            back = s * (gm[i] - (hi60[i] if s > 0 else lo60[i]))  # negative = came back against the trend
            if not (-15 <= back <= -P):
                continue
            if abs(gm[i] - gm[i - 5]) >= 1 or s * (gm[i] - gm[i - 5]) >= 1:
                continue
            pos = (gm[i] - lo60[i]) / max(hi60[i] - lo60[i], 1e-9)
            if (pos if s > 0 else 1 - pos) > 0.6:
                continue
        side = -s if mode == "flipped" else s
        pnl, dur = trade(gm, gsp, i, side)
        out.append(pnl)
        free, n = i + dur, n + 1
    return out


def main():
    cache = pickle.loads((ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    out = [f"backtest/his_style_bot.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, holdout from {cut:%Y-%m-%d}; "
           f"+{TP:g} / -{SL:g} points at the real spread, 30-min cap, <= 3 a day", "",
           f"  {'cell':<26}{'half':>9}{'trades':>8}{'won':>7}{'net pts':>9}{'t':>7}{'flipped won':>13}{'flipped net':>13}"]
    res = {}
    for D in (0.3, 0.4, 0.6):
        for P in (3, 5, 8):
            for half, sel in (("tune", [d for d in days if d < cut]), ("HOLDOUT", [d for d in days if d >= cut])):
                a = np.array([v for d in sel for v in run_day(cache[d], D, P, "his")])
                b = np.array([v for d in sel for v in run_day(cache[d], D, P, "flipped")])
                if len(a) < 2:
                    continue
                t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
                res[(D, P, half)] = (len(a), np.mean(a >= TP), a.mean(), t, np.mean(b >= TP) if len(b) else np.nan)
                out.append(f"  {f'day >= {D}%, pullback >= {P}':<26}{half:>9}{len(a):>8}{np.mean(a >= TP) * 100:>6.0f}%{a.mean():>+9.2f}{t:>+7.1f}"
                           f"{(np.mean(b >= TP) * 100 if len(b) else np.nan):>12.0f}%{(b.mean() if len(b) else np.nan):>+13.2f}")
    for D in (0.3, 0.4, 0.6):
        for half, sel in (("tune", [d for d in days if d < cut]), ("HOLDOUT", [d for d in days if d >= cut])):
            a = np.array([v for d in sel for v in run_day(cache[d], D, 0, "trend_only")])
            out.append(f"  {f'TREND ONLY, day >= {D}%':<26}{half:>9}{len(a):>8}{np.mean(a >= TP) * 100:>6.0f}%{a.mean():>+9.2f}"
                       f"{a.mean() / (a.std(ddof=1) / np.sqrt(len(a))):>+7.1f}")
    both = [(D, P) for D in (0.3, 0.4, 0.6) for P in (3, 5, 8)
            if (D, P, "tune") in res and (D, P, "HOLDOUT") in res and res[(D, P, "tune")][2] > 0 and res[(D, P, "HOLDOUT")][2] > 0]
    best = max(((k, v) for k, v in res.items() if k[2] == "HOLDOUT"), key=lambda kv: kv[1][1])
    lead = [(D, P) for D, P in both if res[(D, P, "tune")][3] >= 2 and res[(D, P, "HOLDOUT")][3] >= 2 and res[(D, P, "HOLDOUT")][0] >= 30]
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 no cell net positive on both halves: {len(both)} cells are ({both}) -> {'RIGHT' if not both else 'WRONG'}",
            f"  2 best holdout win rate {best[1][1] * 100:.0f}% vs flipped {best[1][4] * 100:.0f}% within 8 points -> "
            f"{'RIGHT' if abs(best[1][1] - best[1][4]) <= 0.08 else 'WRONG'}",
            f"  LEAD LINE: {lead if lead else 'not hit'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
