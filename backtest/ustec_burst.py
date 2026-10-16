"""THE INDEPENDENT BOT TEST: does a sharp NASDAQ burst pay a +7 / -7 race on its own? (2026-10-12)

The council's bot-or-kill test for "he reacts to the first seconds of a move" - run for completeness after
his_clock_exits.py found his clock exact and the market NOT moving his way before his clicks (median 0.00 points in the
5 s before), which already closes that reading of him. This asks the question without him: on Exness's USTECm ticks
(strategy_analysis/data/ustec_tick_days.pkl: 181 days, 09:30-19:30 New York, mid and spread), after the mid moves
>= 2.5 points within 3 seconds, enter at the next second at the real ask / bid and race +7 / -7 points (30-minute cap) -
FOLLOW the burst, or FADE it; against RANDOM entries in the same hours. One position at a time.

REGISTERED BEFORE THE RUN (2026-10-12)
    U1  Neither FOLLOW nor FADE wins the race often enough to beat the spread: net points a trade <= 0 for both, on both
        halves (ustec_seconds.py found 5-60 s REVERSAL worth ~0.1bp - far under a 1-point spread).
    U2  FOLLOW wins under 50% of races (bursts partly reverse); FADE 50-55%.

RESULT (2026-10-12 14:46 UTC, logs/ustec_burst.txt; 181 days, ~200,000 bursts each way)
    - U1 RIGHT: a +-7 race entered 1 s after a >= 2.5-point burst at the real price loses about the spread either way -
      FOLLOW -2.29 points a trade (won 33.6%), FADE -2.11 (34.9%), against RANDOM entries -2.00 (35.4%); both halves.
      (A +-7 race on the EXIT side of a ~1-point spread is won ~35% at random - the spread is in both legs.)
    - U2 WRONG in letter (FADE 34.9%, not 50-55% - the spread-inclusive race) but right in kind: following bursts does
      slightly worse than random, fading slightly better - and neither beats a coin.
    Reading: there is no burst-following or burst-fading NASDAQ bot at retail spreads.

    python -m backtest.ustec_burst
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "ustec_burst.txt"
X, MOVE, WIN = 7.0, 2.5, 3


def race(ts, mid, spr, j, side):
    """enter at tick j at the real price; first of +-X on the exit side within 30 min. Returns net points."""
    e = mid[j] + side * spr[j] / 2
    k = np.searchsorted(ts, ts[j] + 1800)
    p = side * ((mid[j + 1:k] - side * spr[j + 1:k] / 2) - e)
    up, dn = np.flatnonzero(p >= X), np.flatnonzero(p <= -X)
    if len(up) and (not len(dn) or up[0] < dn[0]):
        return X, ts[j + 1 + up[0]]
    if len(dn):
        return -X, ts[j + 1 + dn[0]]
    return (float(p[-1]) if len(p) else 0.0), ts[k - 1] if k > j + 1 else ts[j]


def main():
    cache = pickle.loads((ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    rng = np.random.default_rng(7)
    rows = []
    for d in days:
        ts, mid, spr = cache[d]
        grid = np.arange(np.ceil(ts[0]) + WIN, ts[-1] - 1800, 1.0)
        gi = np.searchsorted(ts, grid, "right") - 1
        gm = mid[gi]
        ch = gm[WIN:] - gm[:-WIN]
        free = {"FOLLOW": -1.0, "FADE": -1.0, "RANDOM": -1.0}
        for n in np.flatnonzero(np.abs(ch) >= MOVE):
            t_sig = grid[n + WIN]
            j = np.searchsorted(ts, t_sig + 1.0, "left")            # next second: reaction time
            if j >= len(ts) - 2:
                continue
            for nm, side in (("FOLLOW", np.sign(ch[n])), ("FADE", -np.sign(ch[n]))):
                if t_sig < free[nm]:
                    continue
                pts, t_out = race(ts, mid, spr, j, int(side))
                rows.append((d, nm, pts))
                free[nm] = t_out
        for t0 in rng.uniform(ts[0] + 60, ts[-1] - 1800, 40):
            j = np.searchsorted(ts, t0, "left")
            pts, _ = race(ts, mid, spr, j, int(rng.choice([-1, 1])))
            rows.append((d, "RANDOM", pts))
    D = pd.DataFrame(rows, columns=["day", "rule", "pts"])
    cut = days[int(len(days) * 0.6)]
    lines = [f"backtest/ustec_burst.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Exness USTECm ticks, {len(days)} days "
             f"{days[0]:%Y-%m-%d} .. {days[-1]:%Y-%m-%d}; burst = mid moves >= {MOVE} points in {WIN} s; entry 1 s later at the real "
             f"price; race +-{X:g} points (30-min cap); holdout from {cut:%Y-%m-%d}", ""]
    res = {}
    for nm, g in D.groupby("rule"):
        a, b = g[g.day < cut].pts, g[g.day >= cut].pts
        t = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))  # noqa: E731
        won = (g.pts >= X).mean()
        res[nm] = (g.pts.mean(), a.mean(), b.mean(), won)
        lines.append(f"  {nm:6} {len(g):6} trades | won the race {won * 100:4.1f}% | net {g.pts.mean():+.2f} points a trade "
                     f"(tune {a.mean():+.2f} t {t(a):+.1f} / holdout {b.mean():+.2f} t {t(b):+.1f})")
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    u1 = all(res[k][1] <= 0 or res[k][2] <= 0 for k in ("FOLLOW", "FADE"))
    lines.append(f"  U1 neither rule positive on both halves: FOLLOW {res['FOLLOW'][1]:+.2f}/{res['FOLLOW'][2]:+.2f}, FADE "
                 f"{res['FADE'][1]:+.2f}/{res['FADE'][2]:+.2f} -> {'RIGHT' if u1 else 'WRONG'}")
    lines.append(f"  U2 FOLLOW won {res['FOLLOW'][3] * 100:.1f}% (< 50%?), FADE {res['FADE'][3] * 100:.1f}% (50-55%?) -> "
                 f"{'RIGHT' if res['FOLLOW'][3] < 0.5 and 0.5 <= res['FADE'][3] <= 0.55 else 'WRONG'}")
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
