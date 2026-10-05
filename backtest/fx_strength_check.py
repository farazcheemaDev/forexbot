"""IS THE ONE LIVE CELL A ROLLOVER ARTIFACT? - fx_strength.py's "reversal N1 H24 + rising volume", at every hour.

fx_strength.py: 0 of 24 strength cells pass. One stood out - fading the last hour's strongest-vs-weakest move over
24 hours, +2.70 bp net (Holm 0.32), and when that hour's tick volume was >= 1.5x its norm, +7.2 / +21.4 bp more on
tune / holdout (190 trades). Prediction 4 there said volume would not lift it by 1 bp. It did - so look for the bug.

THE SUSPECTED BUG: that cell steps 24 bars at a time, so every trade sits at ONE hour of the day. If that hour is the
daily FX ROLLOVER (21:00-23:00 UTC, when the day's swap is booked), broker quotes widen and jump for minutes and tick
volume spikes with quote updates - a "move with rising volume" that is spread noise and snaps back. That would fake
exactly this result.

THE CHECK: the same rule started at each of the 24 hours of the day (one trade a day, hour h -> hour h next day),
with and without the volume condition, both halves.

REGISTERED PREDICTION (2026-10-06, before running)
    1. fx_strength's cell sits at or next to the rollover (21-23 UTC).
    2. The volume-confirmed reversal is positive on both halves ONLY at rollover hours; at the other 21 hours it averages
       under +2 bp net with no both-halves pattern - an artifact of quote noise, not a tradable relationship.

    python -m backtest.fx_strength_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.fx_strength import CCY, COST_USD, COST_X, SWAP_NIGHT, load  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def at_hour(P, V, hour, N=1, sign=-1):
    a, v, idx = P.to_numpy(), V.to_numpy(), P.index
    hrs = idx.hour.to_numpy()
    starts = np.nonzero(hrs == hour)[0]
    rows = []
    for t in starts:
        if t < 24 * 20 + N:
            continue
        nxt = idx.searchsorted(idx[t] + pd.Timedelta(hours=24))
        if nxt >= len(idx) or (idx[nxt] - idx[t]).total_seconds() > 26 * 3600:
            continue                                                   # skip weekends and gaps
        r = a[t] - a[t - N]
        s = r - r.mean()
        hi, lo = int(np.argmax(s)), int(np.argmin(s))
        x, y = (hi, lo) if sign > 0 else (lo, hi)
        gross = ((a[nxt, x] - a[nxt, y]) - (a[t, x] - a[t, y])) * 1e4
        usd = CCY[x] == "USD" or CCY[y] == "USD"
        cost = (COST_USD if usd else COST_X) + SWAP_NIGHT
        same = np.nonzero(hrs[t - 24 * 20:t] == hour)[0] + (t - 24 * 20)
        base = v[same][:, [x, y]].mean(axis=0)
        ratio = float(np.mean(v[t][[x, y]] / np.where(base > 0, base, np.nan)))
        rows.append((idx[t], gross - cost, ratio))
    return pd.DataFrame(rows, columns=["t", "net", "vratio"])


def main():
    P, V = load()
    cut = P.index[int(len(P) * 0.6)]
    print(f"reversal, N = 1 h, held 24 h, one trade a day at each start hour (UTC = Exness server time); "
          f"tune < {cut:%Y-%m-%d} <= holdout")
    print(f"  {'hour':>5}{'n':>6}{'net all':>9}{'tune':>8}{'hold':>8} | {'vol>=1.5x n':>12}{'tune':>8}{'hold':>8}")
    rows = []
    for h in range(24):
        T = at_hour(P, V, h)
        if len(T) < 50:
            continue
        tu, ho = T[T.t < cut], T[T.t >= cut]
        vc = T[T.vratio >= 1.5]
        vt, vh = vc[vc.t < cut], vc[vc.t >= cut]
        rows.append(dict(h=h, n=len(T), all=T.net.mean(), tune=tu.net.mean(), hold=ho.net.mean(),
                         vn=len(vc), vtune=vt.net.mean() if len(vt) else np.nan,
                         vhold=vh.net.mean() if len(vh) else np.nan))
        r = rows[-1]
        roll = "  <- rollover" if h in (21, 22, 23) else ""
        print(f"  {h:>5}{r['n']:>6}{r['all']:>+9.2f}{r['tune']:>+8.2f}{r['hold']:>+8.2f} | {r['vn']:>12}"
              f"{r['vtune']:>+8.2f}{r['vhold']:>+8.2f}{roll}")
    R = pd.DataFrame(rows)
    roll = R[R.h.isin([21, 22, 23])]
    rest = R[~R.h.isin([21, 22, 23])]
    print(f"\n  volume-confirmed, both halves positive: rollover hours {int(((roll.vtune > 0) & (roll.vhold > 0)).sum())}"
          f" of {len(roll)}; other hours {int(((rest.vtune > 0) & (rest.vhold > 0)).sum())} of {len(rest)}")
    print(f"  volume-confirmed mean net: rollover {np.nanmean(np.r_[roll.vtune, roll.vhold]):+.2f} bp, "
          f"other hours {np.nanmean(np.r_[rest.vtune, rest.vhold]):+.2f} bp")


if __name__ == "__main__":
    main()
