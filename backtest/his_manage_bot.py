"""HIS MANAGEMENT AS A BOT - scratch, average down, hedge, at his own evening hours (2026-10-16)

The user, after s67 (his_plain.py): "this data is so insightful, I'm sure we can make our own strategy using it". s65 built
his ENTRY habits into a bot (dead); this builds what s67 found about how he MANAGES a trade - the part not tested yet:
  scratch  a trade that has not reached +7 after 60 s is closed at the first +1 (net of spread) - his +1..+3.5 exits
  average  + when the position is -15, ADD a second unit the same side, its own +7 / scratch exits (2026-09-14: +5.25)
  hedge    + when the position is -15, SELL the other way with +7 / scratch exits, up to 4 in a row while it is open,
           all closed when the stuck position closes (2026-09-14: four sells paid for the -31.75 long)
  base     +7 / -30 only (s65's exit) - the control
Every unit: entry at the real ask / bid, +7 take-profit, the stuck position's -30 stop (his worst -31.75) closes every
open leg, 30-minute cap. Exness USTECm, 1-second grid, 181 tick days 2026-01..09.
HOURS    "his": his two evening windows on HIS clock (PKT 20:00-20:45, 23:15-00:15 = New York 11:00-11:45 / 14:15-15:15
         in summer, an hour earlier before 2026-03-08), <= 3 positions per window; "day": 10:00-16:00 New York, <= 6 a day.
         One look 10 s after each 1-minute close (his 5-24 s habit), only when flat.
SIDE     "trend": the day's direction from the 09:30 open when it is >= 0.3% (s64's stand-in for his side), else no
         trade; "coin": a seeded coin flip. Neither is his side - nothing found carries it (s36-s66).
SPLIT    first 60% of days tune, last 40% holdout; all 16 cells reported, none chosen.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. No cell is net positive on BOTH halves.
    2. Scratching raises the share of green positions over base by >= 5 points, and moves net per position < 1.5 points.
    3. Averaging and hedging raise the share of green positions over scratch, and make the worst position no better.
    4. His hours vs all day: net per position within 1.5 points for the same management and side.
    LEAD LINE: a cell positive on both halves, t >= 2 on each, >= 30 holdout positions -> paper-trade candidate.

RESULT (2026-10-16, logs/his_manage_bot.txt) - DEAD; prediction 1 right, the lead line not hit, 2-4 wrong in detail.
    All 16 cells lose on both halves: -0.74..-4.30 points a position, 58-83% of positions green. The best are his hours
    + a coin flip + scratching (-1.00 / -1.15, 82% / 83% green) - management only reshapes a coin flip's loss.
    Scratching: +2..+9 points of green positions (registered >= 5: wrong in some cells), net -0.98..+0.55.
    Averaging down: same green share, the worst position -58..-99 (two units stuck). Hedging: FEWER green positions
    (58-68%) and a worst no deeper than base - it caps the tail and pays the spread more often (-2.7..-4.3 a position).
    His hours vs all day: -1.23..+1.88 (registered within 1.5: wrong by a hair, no consistent sign).
    The trend-of-the-day "side" loses MORE than a coin flip at his hours. His management is how he survives a wrong
    side; on a coin-flip side it is a slower way to pay the spread.

    python -m backtest.his_manage_bot
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

LOG = ROOT / "logs" / "his_manage_bot.txt"
TP, SL, CAP, ADD, SCR_AFTER, SCR = 7.0, 30.0, 1800, 15.0, 60, 1.0
DST = pd.Timestamp("2026-03-08")


def position(gm, gsp, i, s, mg):
    """One position from second i; returns (net points of all legs, last second, n legs)."""
    end = min(i + CAP, len(gm) - 1)
    legs = [[s, gm[i] + s * gsp[i] / 2, i, True, 0.0]]          # side, entry, start, open, pnl
    added, hedges, k = False, 0, i
    for k in range(i + 1, end + 1):
        for L in legs:
            if not L[3]:
                continue
            p = L[0] * ((gm[k] - L[0] * gsp[k] / 2) - L[1])
            if p >= TP or (mg != "base" and k - L[2] >= SCR_AFTER and p >= SCR):
                L[3], L[4] = False, p
        M = legs[0]
        pm = M[0] * ((gm[k] - M[0] * gsp[k] / 2) - M[1])
        if M[3] and pm <= -SL:
            break
        if not any(L[3] for L in legs):
            return sum(L[4] for L in legs), k, len(legs)
        if M[3] and pm <= -ADD:
            if mg == "average" and not added:
                legs.append([s, gm[k] + s * gsp[k] / 2, k, True, 0.0])
                added = True
            if mg == "hedge" and hedges < 4 and not any(L[3] for L in legs[1:]):
                legs.append([-s, gm[k] - s * gsp[k] / 2, k, True, 0.0])
                hedges += 1
        if not M[3] and mg in ("average", "hedge"):
            for L in legs[1:]:                                    # the stuck position is done: close what it carried
                if L[3]:
                    L[3], L[4] = False, L[0] * ((gm[k] - L[0] * gsp[k] / 2) - L[1])
            return sum(L[4] for L in legs), k, len(legs)
    for L in legs:
        if L[3]:
            L[3], L[4] = False, L[0] * ((gm[k] - L[0] * gsp[k] / 2) - L[1])
    return sum(L[4] for L in legs), k, len(legs)


def windows(d, hours):
    if hours == "day":
        return [(1800, 23400 - CAP, 6)]
    sh = 0 if d >= DST else -3600                                 # PKT is fixed; New York moves on 2026-03-08
    return [(5400 + sh, 8100 + sh, 3), (17100 + sh, 20700 + sh, 3)]   # 11:00-11:45, 14:15-15:15 NY in summer


def run_day(day, d, hours, side, mg, rng):
    g, gm, gsp, _ = day_grid(day)
    if len(g) < 7200:
        return []
    off = int(g[0])
    op = gm[0]
    out = []
    for a, b, cap in windows(d, hours):
        free, n = -1, 0
        for sec in range(a - a % 60 + 10, b, 60):
            i = sec - off
            if i <= free or n >= cap or i < 0 or i >= len(gm) - CAP - 1:
                continue
            if side == "trend":
                dm = (gm[i] - op) / op * 100
                if abs(dm) < 0.3:
                    continue
                s = 1 if dm > 0 else -1
            else:
                s = 1 if rng.random() < 0.5 else -1
            pnl, k, nl = position(gm, gsp, i, s, mg)
            out.append((pnl, nl))
            free, n = k, n + 1
    return out


def main():
    cache = pickle.loads((ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    out = [f"backtest/his_manage_bot.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, holdout from "
           f"{cut:%Y-%m-%d}; +{TP:g} per leg, -{SL:g} on the stuck position, scratch at +{SCR:g} after {SCR_AFTER} s, add/hedge at -{ADD:g}",
           "", f"  {'hours':<6}{'side':<7}{'manage':<9}{'half':>8}{'pos':>6}{'green':>7}{'net/pos':>9}{'t':>6}{'worst':>8}{'legs':>6}"]
    R = {}
    for hours in ("his", "day"):
        for side in ("trend", "coin"):
            for mg in ("base", "scratch", "average", "hedge"):
                for half, sel in (("tune", [d for d in days if d < cut]), ("HOLDOUT", [d for d in days if d >= cut])):
                    rng = np.random.default_rng(7)
                    a = [v for d in sel for v in run_day(cache[d], d, hours, side, mg, rng)]
                    p = np.array([v[0] for v in a])
                    nl = np.array([v[1] for v in a])
                    t = p.mean() / (p.std(ddof=1) / np.sqrt(len(p))) if len(p) > 2 else np.nan
                    R[(hours, side, mg, half)] = (len(p), np.mean(p > 0), p.mean(), t, p.min())
                    out.append(f"  {hours:<6}{side:<7}{mg:<9}{half:>8}{len(p):>6}{np.mean(p > 0) * 100:>6.0f}%{p.mean():>+9.2f}"
                               f"{t:>+6.1f}{p.min():>+8.1f}{nl.mean():>6.2f}")
    cells = {k[:3] for k in R}
    both = sorted(c for c in cells if R[c + ("tune",)][2] > 0 and R[c + ("HOLDOUT",)][2] > 0)
    lead = [c for c in both if R[c + ("tune",)][3] >= 2 and R[c + ("HOLDOUT",)][3] >= 2 and R[c + ("HOLDOUT",)][0] >= 30]
    p2 = [(R[(h, s, "scratch", hf)][1] - R[(h, s, "base", hf)][1], R[(h, s, "scratch", hf)][2] - R[(h, s, "base", hf)][2])
          for h in ("his", "day") for s in ("trend", "coin") for hf in ("tune", "HOLDOUT")]
    p3 = [(R[(h, s, m, hf)][1] - R[(h, s, "scratch", hf)][1], R[(h, s, m, hf)][4] - R[(h, s, "scratch", hf)][4])
          for h in ("his", "day") for s in ("trend", "coin") for m in ("average", "hedge") for hf in ("tune", "HOLDOUT")]
    p4 = [R[("his", s, m, hf)][2] - R[("day", s, m, hf)][2]
          for s in ("trend", "coin") for m in ("base", "scratch", "average", "hedge") for hf in ("tune", "HOLDOUT")]
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 no cell positive on both halves: {len(both)} are {both} -> {'RIGHT' if not both else 'WRONG'}",
            f"  2 scratch vs base: green {min(x[0] for x in p2) * 100:+.0f}..{max(x[0] for x in p2) * 100:+.0f} points, net "
            f"{min(x[1] for x in p2):+.2f}..{max(x[1] for x in p2):+.2f} -> "
            f"{'RIGHT' if all(x[0] >= 0.05 and abs(x[1]) < 1.5 for x in p2) else 'WRONG'}",
            f"  3 average/hedge vs scratch: green {min(x[0] for x in p3) * 100:+.0f}..{max(x[0] for x in p3) * 100:+.0f} points, worst "
            f"{min(x[1] for x in p3):+.1f}..{max(x[1] for x in p3):+.1f} -> "
            f"{'RIGHT' if all(x[0] >= 0 and x[1] <= 0 for x in p3) else 'WRONG'}",
            f"  4 his hours - all day: {min(p4):+.2f}..{max(p4):+.2f} -> {'RIGHT' if all(abs(x) <= 1.5 for x in p4) else 'WRONG'}",
            f"  LEAD LINE: {lead if lead else 'not hit'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
