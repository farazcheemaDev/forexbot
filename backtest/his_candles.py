"""THE 1-MINUTE CANDLE THAT CLOSED JUST BEFORE HE CLICKED - rebuilt from ticks.

17 of his 46 NASDAQ entries are 10-19 seconds into a minute (7.7 expected; his exits and gold entries are
uniform): the timing of a human who watches a 1-minute candle close, decides, and clicks. If so, the
candle that closed just before his entry is his trigger - its body and its wicks, which a chart scalper
reads as hammer / engulfing / rejection. Rebuilt exactly from USTECm ticks for each clean entry (April on,
his_strategy.md s25), SIGN-ALIGNED (+ = his direction):
  body1          the last closed candle's close - open (points)
  wick_his       the wick on the side AGAINST him (lower wick for a buy), as a share of the range:
                 a long one = a rejection of the move against him
  wick_far       the other wick, same scale
  range1_rel     its range / the median 1-minute range of that clock minute on other days
  body2          the candle before it
  hammer         wick_his >= 0.5 of the range and the close in his half of the candle (0/1)
  engulf         body1 his way and bigger than body2's (against him) - a reversal candle (0/1)
Each ranked against the same clock minute on 20 other days, same direction (0.50 = ordinary); the two
flags compared as rates.

REGISTERED PREDICTION (2026-09-26, before running): the candle before his entry shows a rejection wick
against the move he trades (wick_his rank > 0.6) - a hammer-type close in a small pullback; body1 ordinary.
p ~ 0.05 at best on 26 entries; nothing survives Holm over 5.

    python -m backtest.his_candles
"""
from __future__ import annotations

import pickle
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0


def candles(ts, mid, m_start, n=3):
    """The n one-minute candles ending at minute boundary m_start (seconds from 09:30 ET): list of OHLC."""
    out = []
    for k in range(n, 0, -1):
        a, b = m_start - 60 * k, m_start - 60 * (k - 1)
        i0, i1 = np.searchsorted(ts, a), np.searchsorted(ts, b)
        if i1 - i0 < 2:
            return None
        seg = mid[i0:i1]
        out.append((seg[0], seg.max(), seg.min(), seg[-1]))
    return out


def feats(ts, mid, m_start, s):
    c = candles(ts, mid, m_start)
    if c is None:
        return None
    (o2, h2, l2, c2), (o1, h1, l1, c1) = c[-2], c[-1]
    rng1 = h1 - l1
    if rng1 <= 0:
        return None
    against = (min(o1, c1) - l1) if s == 1 else (h1 - max(o1, c1))
    far = (h1 - max(o1, c1)) if s == 1 else (min(o1, c1) - l1)
    body1, body2 = s * (c1 - o1), s * (c2 - o2)
    his_half = (c1 - l1) / rng1 >= 0.5 if s == 1 else (h1 - c1) / rng1 >= 0.5
    return dict(body1=body1, wick_his=against / rng1, wick_far=far / rng1, range1=rng1, body2=body2,
                hammer=float(against / rng1 >= 0.5 and his_half), engulf=float(body1 > 0 and body2 < 0 and body1 > -body2))


def main():
    cache = pickle.loads(TICKS.read_bytes())
    days = [d for d in sorted(cache) if cache[d] is not None]
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-01"]
    rng = np.random.default_rng(8)
    rows = []
    for r in x.itertuples():
        et = pd.Timestamp(r.utc).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        day = et.normalize()
        if day not in cache or cache[day] is None:
            continue
        m_start = (et.floor("min") - (day + pd.Timedelta(hours=9, minutes=30))).total_seconds()
        s = 1 if r.side == "BUY" else -1
        mine = feats(cache[day][0], cache[day][1], m_start, s)
        if mine is None:
            continue
        C = []
        for dd in rng.permutation(days):
            if dd == day:
                continue
            f = feats(cache[dd][0], cache[dd][1], m_start, s)
            if f:
                C.append(f)
            if len(C) >= 20:
                break
        C = pd.DataFrame(C)
        rec = {k: (C[k] < mine[k]).mean() + 0.5 * (C[k] == mine[k]).mean() for k in ("body1", "wick_his", "wick_far", "body2")}
        rec["range1_rel"] = mine["range1"] / C["range1"].median()
        rec.update(hammer=mine["hammer"], engulf=mine["engulf"], c_hammer=C.hammer.mean(), c_engulf=C.engulf.mean(),
                   sec=et.second, body1_raw=mine["body1"], wick_raw=mine["wick_his"])
        rows.append(rec)
    R = pd.DataFrame(rows)
    print(f"{len(R)} clean entries; the candle that closed before his entry vs the same clock minute on 20 other days "
          f"(0.50 = ordinary; + = his direction)\n")
    for k, lab in (("body1", "last candle's body, his way"), ("wick_his", "wick AGAINST him (rejection)"),
                   ("wick_far", "wick on his side"), ("body2", "the candle before")):
        v = R[k]
        z = (v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))
        p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
        print(f"  {lab:<32} mean rank {v.mean():.2f}  top third {np.mean(v > 2/3)*100:3.0f}%  p {p:.3f}")
    print(f"  last candle's range / that minute's median: median {R.range1_rel.median():.2f}")
    for k in ("hammer", "engulf"):
        print(f"  {k:<8} his entries {R[k].mean()*100:.0f}%  vs other days {R['c_' + k].mean()*100:.0f}%")
    print(f"  last candle body his way in {np.mean(R.body1_raw > 0)*100:.0f}% of entries")


if __name__ == "__main__":
    main()
