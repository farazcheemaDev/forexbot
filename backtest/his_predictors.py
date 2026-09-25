"""DO THE PREDICTORS FOUND AROUND HIS TRADES HOLD ON EVERY DAY - and after the spread?

his_local.py, among ~1,800 moments within 20 minutes of his 25 clean entries (same day, same direction),
found two features that predict the 3-minute mid race to +7/-7 on both halves:
  c_wick   the last closed 1-minute candle's wick AGAINST the trade direction / its range: top vs bottom
           third +6.4 points (+2.8 / +9.6) - AND his entries rank high on it (0.62, p 0.036);
  f_move   the 5-minute move in the trade's direction: top vs bottom third -11.5 (-12.4 / -10.5) - joining
           an extended move is WORSE; f_eff (its straightness) the same, -11.5.
Those came from his ~12 trading days only. Here: every day 2026-04-01..09-14 (114), 40 random seconds a day
10:00-16:00 ET x both directions:
  1. the tercile split for c_wick, f_move, f_eff, c_body, f_fresh on ALL days, both halves;
  2. a RULE from the two: at each minute close (entry 15 s into the next minute, as he does), go in the
     direction s where the last candle's wick against s >= 50% of its range AND the 5-min move in s is
     <= 0 (not extended); net of the REAL spread (enter at the quote, +7 / -7 on the exit side, 180 s) -
     against the same exit on random minutes.

REGISTERED PREDICTION (2026-09-26, before running): on all days c_wick keeps a small positive split (+2 to +4)
and f_move a negative one (-5 to -8) - short-term reversal is real in NASDAQ - but the rule does not
beat the spread: its net race win rate is within 3 points of random entries, both near 40%.

    python -m backtest.his_predictors
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_levels import daily_basis  # noqa: E402
from backtest.his_local import allfeats, race  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"


def race_net(ts, mid, spr, t, s, W=180, T=7):
    i = np.searchsorted(ts, t, side="right") - 1
    if i < 0:
        return None
    e = mid[i] + s * spr[i] / 2
    j1 = np.searchsorted(ts, t + W, side="right")
    for j in range(i + 1, j1):
        p = s * ((mid[j] - s * spr[j] / 2) - e)
        if p >= T:
            return 1
        if p <= -T:
            return 0
    return None


def main():
    cache = pickle.loads(TICKS.read_bytes())
    basis = daily_basis()
    days = [d for d in sorted(cache) if cache[d] is not None and d in basis.index]
    mid_day = days[len(days) // 2]
    rng = np.random.default_rng(13)
    rows = []
    for d in days:
        ts, mid, spr = cache[d]
        for t in rng.uniform(1800, 23400, 40):
            for s in (1, -1):
                f = allfeats(ts, mid, t, s, basis[d])
                o = race(ts, mid, t, s)
                if f is not None and o is not None:
                    rows.append(f | {"o": o, "day": d})
    P = pd.DataFrame(rows)
    print(f"1. ALL {len(days)} DAYS: {len(P)} random moment x direction pairs; 3-min MID race win rate by feature third "
          f"(base {P.o.mean()*100:.1f}%)")
    print(f"  {'feature':<9}{'low 1/3':>9}{'high 1/3':>10}{'diff':>7}{'1st half':>10}{'2nd half':>10}")
    for k in ("c_wick", "f_move", "f_eff", "c_body", "f_fresh", "f_last5", "f_dip"):
        q = P.dropna(subset=[k])
        lo, hi = q[k].quantile(1 / 3), q[k].quantile(2 / 3)
        w = lambda g: g.o.mean() * 100  # noqa: E731
        a = w(q[q[k] >= hi]) - w(q[q[k] <= lo])
        d1 = w(q[(q[k] >= hi) & (q.day < mid_day)]) - w(q[(q[k] <= lo) & (q.day < mid_day)])
        d2 = w(q[(q[k] >= hi) & (q.day >= mid_day)]) - w(q[(q[k] <= lo) & (q.day >= mid_day)])
        print(f"  {k:<9}{w(q[q[k] <= lo]):>8.1f}%{w(q[q[k] >= hi]):>9.1f}%{a:>+7.1f}{d1:>+10.1f}{d2:>+10.1f}")

    print("\n2. THE RULE (wick against s >= 50% of the last candle, 5-min move in s <= 0), entry 15 s into the next")
    print("   minute at the quote; +7 / -7 on the exit side within 180 s; vs random minutes, same timing and exit")
    res = {"rule": [], "random": []}
    for d in days:
        ts, mid, spr = cache[d]
        busy = -1.0
        for m in range(31, 390):
            t_close = (m + 1) * 60.0
            t_in = t_close + 15
            for s in (1, -1):
                f = allfeats(ts, mid, t_close, s, basis[d])
                if f is None or t_in <= busy:
                    continue
                if f["c_wick"] >= 0.5 and f["f_move"] <= 0:
                    o = race_net(ts, mid, spr, t_in, s)
                    if o is not None:
                        res["rule"].append((d, o)); busy = t_in + 180
            if rng.random() < 0.08:
                o = race_net(ts, mid, spr, t_in, rng.choice((-1, 1)))
                if o is not None:
                    res["random"].append((d, o))
    for k, v in res.items():
        f = pd.DataFrame(v, columns=["day", "o"])
        print(f"   {k:<7} n {len(f):>5}  net win {f.o.mean()*100:5.1f}%  (1st half {f[f.day < mid_day].o.mean()*100:5.1f}% / "
              f"2nd half {f[f.day >= mid_day].o.mean()*100:5.1f}%)   -> points a trade {f.o.mean()*14 - 7:+.2f}")


if __name__ == "__main__":
    main()
