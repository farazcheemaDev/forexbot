"""SIMPLE MATHS: take small profits, no stop, trade WITH the day's trend after a small pullback - the user's reading of how he wins (2026-11-03)

The user, 2026-11-03: "I think it's simple maths, not some magical strategy: he takes what he can get, small profits ... and he is so good and experienced at it - do that."
his_exit_shape.py showed that a small target with no stop from RANDOM entries wins 93-96% and still loses the spread (30 of 30 exit combinations negative); the break-even win rate is ~95% because the rare loser is huge (-132 points).
So 'experience' has to be an entry filter that removes the rare disasters. The two things we KNOW he does at entry (his_strategy s34, s69-70): he trades with the trend of the day (trending, high-volatility days; he joins a
NASDAQ-led move) and he enters after a small pullback against himself. This is that, as plainly as it can be written, on the 181 Exness tick days:
    trend filter   the entry side agrees with the day: side x (price - the session's first price) >= TREND points  (TREND in 0, 15, 30 index points)
    pullback       the price moved against the side by at least PULL points in the 30 seconds before (PULL in 0, 1.5)
    exit           +T points (T in 3, 5, 7), no stop, held to the 16:00 print if it never comes (his way); entry at the quote, exit at the other side's quote (the spread is charged exactly)
100 random seconds a day (10:00-15:55 New York) x both sides, 36,200 entries before filtering; 18 cells; day-clustered t; tune = first 60% of days. Holm over 18 for the 'both halves' test.

REGISTERED BEFORE THE FIRST RUN (2026-11-03)
    S1  No cell has a positive expectancy with t >= 3.0 on BOTH halves (Holm over 18). The best cell is within noise of zero or negative.
    S2  The trend filter RAISES the win rate (from ~94% toward 96-98%) but also makes the rare loser bigger (trend days reverse hard: 2026-09-14), so expectancy does not turn positive.
    S3  Some cell's worst single loser is beyond -100 points (a no-stop book is one bad day from ruin at his leverage).

RESULT (2026-11-03; logs/small_profit_scalp.txt; 36,034 entries on 181 tick days)
    S1 RIGHT: 0 of 18 cells has a positive expectancy; the best (trend >= 30, +7) is -1.66 points a trade (t -1.9; tune -2.36, holdout -0.59); the most filtered cell (trend >= 30, pullback >= 1.5, +7) wins 94.2% with an
    average loser of -148.5 and an expectancy of -1.94. Every cell sits 1-2 points of win rate BELOW its break-even (94.7-98.1%): +3 wins 95.8-96.6% against 97.7-98.1% needed, +7 wins 93.4-94.2% against 94.7-95.5%.
    S2 HALF RIGHT: the filters made the rare loser bigger (-126 -> -136 / -148 points) but lifted the win rate by only 0.5-0.8 points, not toward 96-98%. S3 RIGHT: the worst single loser is -991 points (one trade).
    Note: 'pullback >= 0' means 'the price has not moved WITH the side in the last 30 s' (about half of all entries), so the first row is not the unfiltered baseline (his_exit_shape.py's -1.82 is).
    Reading: taking small profits is the simple maths, and the maths says it needs a 95-98% win rate; random entries get 93-96%, and the two entry habits we can write down (with the day's trend, after a pullback) add
    under one point. The 'experience' that closes a 1-2 point gap in win rate is the entry skill nothing here reproduces.

    python -m backtest.small_profit_scalp        writes logs/small_profit_scalp.txt          tests: python tests/test_small_profit_scalp.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.his_exit_shape import clustered_t, first_hits, outcome, path_points  # noqa: E402
from backtest.his_ta import TICKS  # noqa: E402

PER_DAY = 100
TRENDS = (0.0, 15.0, 30.0)
PULLS = (0.0, 1.5)
TARGETS = (3, 5, 7)


def features(ts, mid, t, s):
    """(trend, pull) for an entry at second t, side s: trend = s x (price now - the session's first price); pull = s x (price 30 s ago - price now) (positive = it pulled back against the side)."""
    i = int(np.searchsorted(ts, t, side="right")) - 1
    j = int(np.searchsorted(ts, t - 30.0, side="right")) - 1
    if i < 1 or j < 0:
        return None
    return s * (mid[i] - mid[0]), s * (mid[j] - mid[i])


def collect(cache, days, seed=53):
    rng = np.random.default_rng(seed)
    rows = []
    for d in days:
        ts, mid, spr = cache[d]
        for t in rng.uniform(1800, 23100, PER_DAY):
            for s in (1, -1):
                f = features(ts, mid, t, s)
                p = path_points(ts, mid, spr, t, s)
                if f is None or p is None:
                    continue
                up, dn, end = first_hits(p)
                rows.append(dict(day=d, trend=f[0], pull=f[1], up=up, dn=dn, end=end))
    return rows


def cell(rows, tune_mask, trend_min, pull_min, T):
    m = np.array([r["trend"] >= trend_min and r["pull"] >= pull_min for r in rows])
    if m.sum() < 30:
        return None
    x = np.array([outcome(r["up"], r["dn"], r["end"], T, None) for r, k in zip(rows, m) if k])
    day = np.array([r["day"] for r, k in zip(rows, m) if k])
    tune = tune_mask[m]
    mean, t = clustered_t(x, day)
    L = x[x <= 0]
    return dict(n=int(m.sum()), win=(x > 0).mean() * 100, loser=L.mean() if len(L) else 0.0, worst=x.min(), ev=mean, t=t,
                tune=x[tune].mean() if tune.any() else float("nan"), hold=x[~tune].mean() if (~tune).any() else float("nan"),
                pstar=(-L.mean() / (T - L.mean()) * 100) if len(L) else float("nan"))


def main():
    cache = pickle.loads(TICKS.read_bytes())
    days = [d for d in sorted(cache) if cache[d] is not None]
    cut = days[int(len(days) * 0.6)]
    rows = collect(cache, days)
    tune_mask = np.array([r["day"] < cut for r in rows])
    out = [f"backtest/small_profit_scalp.py - {len(rows)} random entries on {len(days)} tick days (tune before {cut:%Y-%m-%d}); +T no stop, held to the close; net of the spread, points a trade",
           f"   {'trend>=':>8}{'pullback>=':>11}{'T':>3}{'n':>7}{'win %':>7}{'avg loser':>10}{'worst':>8}{'EV':>8}{'t':>6}{'tune':>7}{'hold':>7}{'break-even win %':>17}"]
    cells = {}
    for tr in TRENDS:
        for pu in PULLS:
            for T in TARGETS:
                c = cell(rows, tune_mask, tr, pu, T)
                if c is None:
                    continue
                cells[(tr, pu, T)] = c
                out.append(f"   {tr:>8.0f}{pu:>11.1f}{T:>3}{c['n']:>7}{c['win']:>7.1f}{c['loser']:>+10.1f}{c['worst']:>+8.0f}{c['ev']:>+8.2f}{c['t']:>+6.1f}{c['tune']:>+7.2f}{c['hold']:>+7.2f}{c['pstar']:>17.1f}")
    pos = [k for k, c in cells.items() if c["ev"] > 0 and c["t"] >= 3.0 and c["tune"] > 0 and c["hold"] > 0]
    best = max(cells.items(), key=lambda kv: kv[1]["ev"])
    out.append(f"\n   cells with a positive expectancy, t >= 3.0 on both halves: {len(pos)} of {len(cells)}; best {best[0]} EV {best[1]['ev']:+.2f} (t {best[1]['t']:+.1f}, tune {best[1]['tune']:+.2f}, holdout {best[1]['hold']:+.2f})")
    base = cells[(0.0, 0.0, 7)]
    top = cells.get((30.0, 1.5, 7))
    out.append(f"   unfiltered +7: win {base['win']:.1f}%, avg loser {base['loser']:+.1f}, EV {base['ev']:+.2f};  most filtered +7 (trend >= 30, pullback >= 1.5): "
               + (f"win {top['win']:.1f}%, avg loser {top['loser']:+.1f}, EV {top['ev']:+.2f}, n {top['n']}" if top else "too few entries"))
    out.append(f"   worst single loser over all cells: {min(c['worst'] for c in cells.values()):+.0f} points")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "small_profit_scalp.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
