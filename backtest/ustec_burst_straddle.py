"""THE BURST STRADDLE - use the one thing ustec_burst_anatomy.py found (WHEN a NASDAQ burst comes) without the thing it could
not find (WHICH WAY): rest a buy-stop above and a sell-stop below at high-volatility seconds and let the burst pick the
side (2026-10-12)

WHY      ustec_burst_anatomy.py: burst occurrence AUC 0.861 on unseen days (recent movement alone, av30, 0.89); direction
         0.513. A bracket of stop orders needs no direction - it enters whichever way the price breaks first. It pays only
         if, in a volatile stretch, a break of k points carries on to +7 more often than it reverses to -7 (momentum inside
         bursts). ustec_burst.py found following a 2.5-point / 3-s burst = random at ordinary seconds; this conditions on
         the volatile seconds the anatomy says bursts come from.

RULE     signal: av30 (sum of absolute 1-second mid moves over the last 30 s) at or above the TUNE days' quantile q
         (99.5% / 98%). At the signal second, a buy-stop at mid + k and a sell-stop at mid - k (k = 2 / 3 / 4 points),
         cancelled after 60 s. The first to trigger fills at the REAL ask / bid of the 1-second grid point where the mid
         has crossed (slippage included - the grid price is past the stop). Then the +-7 race at real prices, 30-minute cap
         (ustec_burst_anatomy.race). One position at a time. CONTROL: the same bracket placed at random seconds of the
         same days, same count.
DATA     Exness USTECm ticks, strategy_analysis/data/ustec_tick_days.pkl (181 days 2026-01..09), first 60% of days tune.

REGISTERED BEFORE THE RUN (2026-10-12)
    S1  The straddle loses after the spread at every k and both thresholds on the holdout days (net points a trade <= 0).
    S2  It beats the same bracket at random seconds by less than 0.5 points a trade at every cell (no momentum inside bursts
        worth the spread).

RESULT (2026-10-12, logs/ustec_burst_straddle.txt) - DEAD. S1 RIGHT, S2 RIGHT.
    Holdout, every cell: won 35.0-36.0% of the +-7 races, net -1.96..-2.09 points a trade (t -26..-43; 7,308-20,339
    trades). The same bracket at random seconds: -2.07..-2.21. Difference +0.05..+0.16 (se 0.06-0.09) - a break of 2-4
    points inside a volatile stretch carries on about as often as anywhere else. Tune half the same (-0.13..+0.12).
    Knowing when NASDAQ will move is worth ~0.1 point a trade against a ~2-point toll.

    python -m backtest.ustec_burst_straddle
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.ustec_burst_anatomy import day_frame, race, X  # noqa: E402

LOG = ROOT / "logs" / "ustec_burst_straddle.txt"
KS, QS, WAIT = (2.0, 3.0, 4.0), (0.995, 0.98), 60


def bracket(gm, gsp, i, k):
    """stops at mid[i] +- k for WAIT s: (side, fill second) of the first to trigger, else None."""
    w = gm[i + 1:i + 1 + WAIT] - gm[i]
    up, dn = np.flatnonzero(w >= k), np.flatnonzero(w <= -k)
    a = up[0] if len(up) else 10**9
    b = dn[0] if len(dn) else 10**9
    if min(a, b) == 10**9:
        return None
    return (1, i + 1 + a) if a < b else (-1, i + 1 + b)


def run(day_grids, sig_idx, k):
    pts = []
    for d, idx in sig_idx.items():
        g, gm, gsp = day_grids[d]
        free = -1
        for i in idx:
            if i <= free or i + WAIT + 1801 >= len(g):
                continue
            hit = bracket(gm, gsp, i, k)
            if hit is None:
                continue
            side, j = hit
            pnl, dur = race(gm, gsp, j, side)
            pts.append(pnl)
            free = j + dur
    return np.array(pts)


def main():
    cache = pickle.loads((ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    grids, av = {}, {}
    for d in days:
        F, grid = day_frame(*cache[d])
        grids[d], av[d] = grid, F["av30"].to_numpy()
    tune_av = np.concatenate([av[d] for d in days if d < cut])
    rng = np.random.default_rng(5)
    lines = [f"backtest/ustec_burst_straddle.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Exness USTECm {len(days)} days, "
             f"holdout from {cut:%Y-%m-%d}; stops +-k for {WAIT} s at av30 >= the tune days' quantile; race +-{X:g} at real prices", ""]
    verdict = []
    for q in QS:
        th = np.quantile(tune_av, q)
        for half, sel in (("tune", [d for d in days if d < cut]), ("HOLDOUT", [d for d in days if d >= cut])):
            sig = {d: np.flatnonzero(av[d] >= th) for d in sel}
            rnd = {d: np.sort(rng.choice(len(av[d]), size=min(len(sig[d]), len(av[d])), replace=False)) for d in sel}
            for k in KS:
                s, r = run(grids, sig, k), run(grids, rnd, k)
                if not len(s) or not len(r):
                    continue
                se = np.sqrt(s.var(ddof=1) / len(s) + r.var(ddof=1) / len(r))
                lines.append(f"q {q:.3f} (av30 >= {th:.1f}) {half:7s} k {k:g}: {len(s):5d} trades won {np.mean(s >= X) * 100:4.1f}% "
                             f"net {s.mean():+.2f} pts (t {s.mean() / (s.std(ddof=1) / np.sqrt(len(s))):+.1f}) | random seconds "
                             f"{len(r):5d} won {np.mean(r >= X) * 100:4.1f}% net {r.mean():+.2f} | diff {s.mean() - r.mean():+.2f} (se {se:.2f})")
                if half == "HOLDOUT":
                    verdict.append((q, k, s.mean(), s.mean() - r.mean()))
        lines.append("")
    lines.append("REGISTERED PREDICTIONS (holdout)")
    lines.append(f"  S1 net <= 0 in every cell: " + ", ".join(f"q{q:.3f}/k{k:g} {m:+.2f}" for q, k, m, _ in verdict) +
                 f" -> {'RIGHT' if all(m <= 0 for _, _, m, _ in verdict) else 'WRONG'}")
    lines.append(f"  S2 beats random seconds by < 0.5 in every cell: " + ", ".join(f"{dd:+.2f}" for *_, dd in verdict) +
                 f" -> {'RIGHT' if all(dd < 0.5 for *_, dd in verdict) else 'WRONG'}")
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
