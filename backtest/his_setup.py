"""HIS SETUP, ALL MARKERS TOGETHER: trend + a quiet hammer + (a round number) -> in 15 s into the next minute.

Each marker found in his 25-26 clean entries is weak alone (p ~0.04-0.05, his_strategy.md s26), but together
they describe one classic price-action setup:
  - a small NASDAQ move: 5-minute move >= 5 points his way (62% of his entries);
  - the 1-minute candle that just closed is QUIET (range below that minute's median; his: 0.71x) and a
    HAMMER against the move: the wick against him >= 50% of its range and the close in his half
    (32% of his entries vs 16% of other days);
  - (variant) its extreme sits within 3 points of a 25-point round number in FUTURES terms (35% vs 20%);
  - he enters 10-19 s into the next minute; here: at the price 15 s into it (ask for a buy).
Exit +7 (bid side) / -20 / 300 s; one position at a time. Every trading day 2026-04-01..09-14, 10:00-16:00
ET, real USTECm bid/ask ticks; the futures basis from NQ=F (his_levels.daily_basis).
  A   trend + quiet hammer
  B   A + the candle's extreme near a ROUND 25 level
  C   A + the extreme near an OFFSET level (12.5 off the round grid) - B's control
  R   a random minute close, same entry timing and exit - the baseline

REGISTERED PREDICTION (2026-09-26, before running): A, B, C all within +-0.7 points a trade of R (~-2.9);
B does not beat C. The markers describe his habits, not an edge that a rule can take.

    python -m backtest.his_setup
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_levels import daily_basis  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"


def minute_bars(ts, mid):
    """1-minute OHLC from 09:30 ET, indexed by minute number."""
    m = (ts // 60).astype(int)
    df = pd.DataFrame({"m": m, "p": mid})
    g = df.groupby("m").p
    return pd.DataFrame({"o": g.first(), "h": g.max(), "l": g.min(), "c": g.last()})


def trade(ts, mid, spr, t_in, side):
    i = np.searchsorted(ts, t_in, side="right") - 1
    if i < 0:
        return None
    e = mid[i] + side * spr[i] / 2
    j1 = np.searchsorted(ts, t_in + 300, side="right")
    for j in range(i + 1, j1):
        pnl = side * ((mid[j] - side * spr[j] / 2) - e)
        if pnl >= 7:
            return 7.0, ts[j]
        if pnl <= -20:
            return pnl, ts[j]
    j = min(j1, len(mid) - 1)
    return side * ((mid[j] - side * spr[j] / 2) - e), ts[j]


def main():
    cache = pickle.loads(TICKS.read_bytes())
    basis = daily_basis()
    days = [d for d in sorted(cache) if cache[d] is not None and d in basis.index]
    mid_day = days[len(days) // 2]
    # the median 1-minute range of each clock minute, over all days (for "quiet")
    allbars = {d: minute_bars(cache[d][0], cache[d][1]) for d in days}
    rngs = pd.concat([(b.h - b.l).rename(d) for d, b in allbars.items()], axis=1)
    med_rng = rngs.median(axis=1)
    rng = np.random.default_rng(9)
    res = {k: [] for k in "ABCR"}
    for d in days:
        ts, mid, spr = cache[d]
        B = allbars[d]
        busy = {k: -1 for k in "ABCR"}
        for m in range(31, 390):                                   # minute closes from 10:01 to 16:00 ET
            if m not in B.index or (m - 5) not in B.index:
                continue
            o, h, l, c = B.loc[m, ["o", "h", "l", "c"]]
            rg = h - l
            t_close = (m + 1) * 60.0
            i_now = np.searchsorted(ts, t_close, side="right") - 1
            i300 = np.searchsorted(ts, t_close - 300, side="right") - 1
            if i_now < 0 or i300 < 0 or rg <= 0:
                continue
            mv = mid[i_now] - mid[i300]
            t_in = t_close + 15
            if rng.random() < 0.05 and busy["R"] < t_in:
                side = rng.choice((-1, 1))
                r = trade(ts, mid, spr, t_in, side)
                if r:
                    res["R"].append((d, r[0])); busy["R"] = r[1] + 60
            for side in (1, -1):
                if side * mv < 5:
                    continue
                against = (min(o, c) - l) if side == 1 else (h - max(o, c))
                his_half = ((c - l) / rg >= 0.5) if side == 1 else ((h - c) / rg >= 0.5)
                quiet = rg < med_rng.get(m, np.inf)
                if not (against / rg >= 0.5 and his_half and quiet):
                    continue
                ext = (l if side == 1 else h) + basis[d]                # the extreme, in futures terms
                near_round = abs(ext - np.round(ext / 25) * 25) <= 3
                near_off = abs(ext - (np.round((ext - 12.5) / 25) * 25 + 12.5)) <= 3
                for k, ok in (("A", True), ("B", near_round), ("C", near_off)):
                    if ok and busy[k] < t_in:
                        r = trade(ts, mid, spr, t_in, side)
                        if r:
                            res[k].append((d, r[0])); busy[k] = r[1] + 60
    print(f"{len(days)} days, 10:00-16:00 ET, real bid/ask; entry 15 s after the signal candle closes; +7 / -20 / 300 s.")
    print(f"{'rule':<46}{'n':>6}{'/day':>6}{'pts/trade':>11}{'1st half':>10}{'2nd half':>10}{'win%':>6}")
    labs = {"A": "A trend + quiet hammer", "B": "B A + near a ROUND 25 level", "C": "C A + near an OFFSET level (control)",
            "R": "R random minute (baseline)"}
    for k in "ABCR":
        f = pd.DataFrame(res[k], columns=["day", "pts"])
        if not len(f):
            print(f"{labs[k]:<46} no trades"); continue
        print(f"{labs[k]:<46}{len(f):>6}{len(f)/len(days):>6.1f}{f.pts.mean():>+11.2f}{f[f.day < mid_day].pts.mean():>+10.2f}"
              f"{f[f.day >= mid_day].pts.mean():>+10.2f}{(f.pts > 0).mean()*100:>6.0f}")


if __name__ == "__main__":
    main()
