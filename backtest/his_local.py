"""HIS MOMENT vs THE OTHER MOMENTS OF THE SAME 20 MINUTES - isolating the trigger itself.

Measured on mid prices (a 3-minute race to +7 or -7), his clean entries win 87% (20/23) while random
entries IN HIS DIRECTION within 20 minutes of his entry win 54%, and any time that day 50.5% (p = 0.001):
the day, the hour and the direction add ~4 points; his exact MOMENT adds ~33. Every earlier feature test
compared his moment with the same clock time on OTHER days, which mixes the day's regime into the
comparison. This compares his moment with moments on the SAME day within 20 minutes, same direction -
same regime, same hour, same trend - so what differs is the trigger.

FEATURES (his_microstructure.feats + the last 1-minute candle + round-number distance + tick rate):
  f_move f_eff f_dip f_retr f_last5 f_quiet f_step f_upstep f_fresh   (see his_microstructure.py)
  c_wick   the last closed 1-minute candle's wick AGAINST his direction / its range
  c_body   that candle's body, his way (points)
  lvl25    distance of the price (futures terms, NQ=F basis) to the nearest 25-point level
  rate30   ticks in the last 30 s / ticks in the prior 5 min (per second)
STAGE A: each entry's feature is ranked among ~80 same-day moments within +-20 min (excluding +-30 s),
same direction (0.50 = ordinary for that stretch of market). Holm across 13.
STAGE B: among ALL those nearby moments (~1,900), does the feature (top vs bottom third) predict the
3-minute mid race? A feature that marks his moments AND predicts outcomes by itself is the trigger.

REGISTERED PREDICTION (2026-09-26, before running): one or two features separate in A (f_last5 / c_wick,
already hinted), and in B they do not predict outcomes (<= 3 points), i.e. they are his habit, not his
edge. 0 features pass both.

    python -m backtest.his_local
"""
from __future__ import annotations

import pickle
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_levels import daily_basis  # noqa: E402
from backtest.his_microstructure import feats as micro  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0
FEATS = ("f_move", "f_eff", "f_dip", "f_retr", "f_last5", "f_quiet", "f_step", "f_upstep", "f_fresh",
         "c_wick", "c_body", "lvl25", "rate30")


def extra(ts, mid, t, s, basis):
    m0 = np.floor(t / 60) * 60                                  # the minute he is in; its predecessor closed at m0
    i0, i1 = np.searchsorted(ts, m0 - 60), np.searchsorted(ts, m0)
    if i1 - i0 < 2:
        return None
    seg = mid[i0:i1]
    o, h, l, c = seg[0], seg.max(), seg.min(), seg[-1]
    rg = h - l
    against = (min(o, c) - l) if s == 1 else (h - max(o, c))
    k = np.searchsorted(ts, t, side="right")
    fut = mid[k - 1] + basis
    j30, j300 = np.searchsorted(ts, t - 30), np.searchsorted(ts, t - 300)
    r300 = (k - j300) / 300.0
    return dict(c_wick=against / rg if rg > 0 else np.nan, c_body=s * (c - o),
                lvl25=abs(fut - np.round(fut / 25) * 25), rate30=((k - j30) / 30.0) / r300 if r300 > 0 else np.nan)


def race(ts, mid, t, s, W=180, T=7):
    i = np.searchsorted(ts, t, side="right") - 1
    if i < 0:
        return None
    j1 = np.searchsorted(ts, t + W, side="right")
    for j in range(i + 1, j1):
        p = s * (mid[j] - mid[i])
        if p >= T:
            return 1
        if p <= -T:
            return 0
    return None


def allfeats(ts, mid, t, s, basis):
    a = micro(ts, mid, t, s)
    b = extra(ts, mid, t, s, basis)
    if a is None or b is None:
        return None
    return a | b


def main():
    cache = pickle.loads(TICKS.read_bytes())
    basis = daily_basis()
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-01"]
    rng = np.random.default_rng(12)
    ranks, pool = [], []
    for r in x.itertuples():
        et = pd.Timestamp(r.utc).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        day = et.normalize()
        if day not in cache or cache[day] is None or day not in basis.index:
            continue
        ts, mid, _ = cache[day]
        t0 = (et - (day + pd.Timedelta(hours=9, minutes=30))).total_seconds()
        s = 1 if r.side == "BUY" else -1
        mine = allfeats(ts, mid, t0, s, basis[day])
        if mine is None:
            continue
        near = []
        for _ in range(120):
            tt = t0 + rng.uniform(30, 1200) * rng.choice((-1, 1))
            f = allfeats(ts, mid, tt, s, basis[day])
            if f is None:
                continue
            o = race(ts, mid, tt, s)
            near.append(f)
            if o is not None:
                pool.append(f | {"o": o, "day": day})
            if len(near) >= 80:
                break
        N = pd.DataFrame(near)
        ranks.append({k: (N[k].dropna() < mine[k]).mean() + 0.5 * (N[k].dropna() == mine[k]).mean()
                      for k in FEATS if not np.isnan(mine[k])})
    RA, P = pd.DataFrame(ranks), pd.DataFrame(pool)
    pA = {}
    for k in FEATS:
        v = RA[k].dropna()
        z = (v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))
        pA[k] = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    order = sorted(pA, key=pA.get)
    holm = {k: min(1.0, max(pA[j] * (len(pA) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in pA}
    days = sorted(P.day.unique()); mid_day = days[len(days) // 2]
    print(f"STAGE A - his {len(RA)} clean entries ranked among ~80 moments of the SAME day within 20 min, same direction")
    print(f"STAGE B - {len(P)} of those nearby moments: 3-min mid race win rate, bottom vs top third of the feature "
          f"(base {P.o.mean()*100:.1f}%)\n")
    print(f"  {'feature':<9}{'rank':>6}{'top 1/3':>9}{'p':>7}{'Holm':>7}   |{'low 1/3':>9}{'high 1/3':>9}{'diff':>7}{'1st half':>9}{'2nd half':>9}")
    for k in FEATS:
        v = RA[k].dropna()
        q = P.dropna(subset=[k])
        lo, hi = q[k].quantile(1 / 3), q[k].quantile(2 / 3)
        w = lambda g: g.o.mean() * 100 if len(g) else np.nan  # noqa: E731
        d1 = w(q[(q[k] >= hi) & (q.day < mid_day)]) - w(q[(q[k] <= lo) & (q.day < mid_day)])
        d2 = w(q[(q[k] >= hi) & (q.day >= mid_day)]) - w(q[(q[k] <= lo) & (q.day >= mid_day)])
        print(f"  {k:<9}{v.mean():>6.2f}{np.mean(v > 2/3)*100:>8.0f}%{pA[k]:>7.3f}{holm[k]:>7.3f}   |"
              f"{w(q[q[k] <= lo]):>8.1f}%{w(q[q[k] >= hi]):>8.1f}%{w(q[q[k] >= hi]) - w(q[q[k] <= lo]):>+7.1f}{d1:>+9.1f}{d2:>+9.1f}")
    RA.to_csv(ROOT / "logs" / "his_local_ranks.csv", index=False)


if __name__ == "__main__":
    main()
