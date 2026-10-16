"""CUTTING THE TAIL OF AVERAGING DOWN - a stop on the WHOLE position (2026-10-16)

The user, after his_manage_bot.py (averaging: same green share, worst position -58..-99): "how can we eliminate it".
The worst came from two units stuck together, each allowed to -30. Here the add at -15 stays, and ONE combined stop
closes both units when their summed P&L (open + already banked legs) reaches -C, C = 15 / 20 / 30 / 45; also C = none
(his_manage_bot's 'average'), and plain scratch (no add) as the line to beat. Same hours, sides, days, spread, split.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. The combined stop caps the worst position near -C (gaps aside): worst within C + 8 points.
    2. The green share FALLS as C tightens (more positions stopped), and net per position changes by < 1.5 points:
       the tail is traded for frequency, not removed.
    3. No cell positive on both halves.

RESULT (2026-10-16, logs/his_manage_tail.txt) - the tail CAN be cut, the loss cannot; predictions 2-3 right, 1 wrong.
    A combined stop at -15 takes the 1-in-100 worst position from -53..-63 to -19..-24 and the single worst to -24..-43
    (a fast second with two units on moves them twice as far: prediction 1, 'within C + 8', wrong). But the green share
    falls 76-83% -> 58-67%, and net per position stays -1.5..-3.0 (uncapped averaging -1.2..-4.1): the tail is traded for
    more frequent small stops. -45 changes nothing (the first unit's own -30 fires first). No cell positive on both halves.

    python -m backtest.his_manage_tail
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_manage_bot as MB  # noqa: E402

LOG = ROOT / "logs" / "his_manage_tail.txt"
C_ = None


def position(gm, gsp, i, s, mg):
    """his_manage_bot.position for 'average', plus one stop on the combined P&L of every leg."""
    if mg != "avgcap":
        return ORIG(gm, gsp, i, s, mg)
    end = min(i + MB.CAP, len(gm) - 1)
    legs = [[s, gm[i] + s * gsp[i] / 2, i, True, 0.0]]
    added, k = False, i

    def val(L, k):
        return L[0] * ((gm[k] - L[0] * gsp[k] / 2) - L[1])

    for k in range(i + 1, end + 1):
        for L in legs:
            if L[3]:
                p = val(L, k)
                if p >= MB.TP or (k - L[2] >= MB.SCR_AFTER and p >= MB.SCR):
                    L[3], L[4] = False, p
        tot = sum(val(L, k) if L[3] else L[4] for L in legs)
        if any(L[3] for L in legs) and tot <= -C_:
            break
        if legs[0][3] and val(legs[0], k) <= -MB.SL:
            break
        if not any(L[3] for L in legs):
            return sum(L[4] for L in legs), k, len(legs)
        if legs[0][3] and not added and val(legs[0], k) <= -MB.ADD:
            legs.append([s, gm[k] + s * gsp[k] / 2, k, True, 0.0])
            added = True
    for L in legs:
        if L[3]:
            L[3], L[4] = False, val(L, k)
    return sum(L[4] for L in legs), k, len(legs)


ORIG = MB.position


def main():
    global C_
    MB.position = position
    cache = pickle.loads((ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    out = [f"backtest/his_manage_tail.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, holdout from {cut:%Y-%m-%d}",
           "", f"  {'hours':<6}{'side':<7}{'manage':<16}{'half':>8}{'pos':>6}{'green':>7}{'net/pos':>9}{'t':>6}{'worst':>8}{'p1%':>8}"]
    R = {}
    for hours in ("his", "day"):
        for side in ("trend", "coin"):
            for lab, mg, C in [("scratch", "scratch", None), ("average", "average", None)] + \
                              [(f"avg, stop -{c}", "avgcap", c) for c in (45, 30, 20, 15)]:
                C_ = C
                for half, sel in (("tune", [d for d in days if d < cut]), ("HOLDOUT", [d for d in days if d >= cut])):
                    rng = np.random.default_rng(7)
                    p = np.array([v[0] for d in sel for v in MB.run_day(cache[d], d, hours, side, mg, rng)])
                    t = p.mean() / (p.std(ddof=1) / np.sqrt(len(p)))
                    R[(hours, side, lab, half)] = (np.mean(p > 0), p.mean(), t, p.min(), C)
                    out.append(f"  {hours:<6}{side:<7}{lab:<16}{half:>8}{len(p):>6}{np.mean(p > 0) * 100:>6.0f}%{p.mean():>+9.2f}"
                               f"{t:>+6.1f}{p.min():>+8.1f}{np.percentile(p, 1):>+8.1f}")
    caps = [k for k in R if R[k][4]]
    p1 = [R[k][3] + R[k][4] for k in caps]
    both = sorted({k[:3] for k in R if R[k[:3] + ("tune",)][1] > 0 and R[k[:3] + ("HOLDOUT",)][1] > 0})
    mono = all(R[(h, s, "avg, stop -15", hf)][0] <= R[(h, s, "avg, stop -45", hf)][0]
               for h in ("his", "day") for s in ("trend", "coin") for hf in ("tune", "HOLDOUT"))
    dn = [R[k][1] - R[k[:2] + ("average", k[3])][1] for k in caps]
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 worst within C + 8: worst + C = {min(p1):+.1f}..{max(p1):+.1f} -> {'RIGHT' if min(p1) >= -8 else 'WRONG'}",
            f"  2 green falls as C tightens: {'yes' if mono else 'no'}; net vs uncapped averaging {min(dn):+.2f}..{max(dn):+.2f} -> "
            f"{'RIGHT' if mono and all(abs(x) < 1.5 for x in dn) else 'WRONG'}",
            f"  3 no cell positive on both halves: {both if both else 'none'} -> {'RIGHT' if not both else 'WRONG'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
