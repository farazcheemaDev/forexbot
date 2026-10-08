"""PHASE 2 (the thin kills): memecoin graduations on DAYS OTHER THAN THE ONE THE KILL USED (2026-10-08).

THE KILL (doc 02, "buying Solana memecoin graduations", meme_grad.py): every pump.fun graduate of ONE day (631 real
ones), bought 1 / 5 / 15 minutes after graduation: -27.9% (sell +15m), -55.1% (+1h), -80.0% (+6h) mean net of 2%. The
evidence is strong within the day and thin across days - one day of a market whose mood changes week to week.
meme_collector.py has logged every graduation since 2026-09-21 (logs/meme_graduates.csv, ~7,000). Here: up to 25
random graduates from each later day, their first 13 hours of minute candles from GeckoTerminal (fetched around the
graduation, cached in strategy_analysis/data/meme/ohlcv_days/), scored with meme_grad.outcome unchanged (same real-
graduation filter, glitch flag, 2% cost, sub-5% exits booked at -100%).

REGISTERED BEFORE RUNNING: every day's mean at "buy +1 min, sell +1h" is negative; pooled over the days the mean is
between -30% and -70% with a 95% interval below zero; "buy +15 min, sell +15 min" (the original's one row reaching
zero) is negative pooled. The kill stands on many days.

RESULT (2026-10-08, logs/meme_days.txt): THE KILL STANDS ON OTHER DAYS. 98 real graduates (glitches out) from 7 days
    (2026-09-23 .. 09-29; the collector's later days had too few fetchable pools in the sample), net of 2%: buy +1 min /
    sell +1h -66.9% [-81%, -50%], 0 of 7 days positive; +1 min / +6h -92.5%; +15 min / +15 min -7.1% [-15%, +2%] (the
    original's least-bad row again); wait-for-proof -82.9%. Predictions: every day negative at +1h - right; pooled
    -30..-70% with the interval below zero - right (-66.9%); +15/+15 negative pooled - right in sign, its interval
    reaches +2%.

    python -m backtest.meme_days            (fetches; ~40 min at the free rate limit, resumable)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import meme_grad as MG  # noqa: E402

LOG = ROOT / "logs" / "meme_days.txt"
CACHE = MG.OUT / "ohlcv_days"
PER_DAY = 25


def window(pool, t_seen):
    """Minute candles from just before graduation to ~13h after, oldest first (cached)."""
    f = CACHE / f"{pool}.json"
    if f.exists():
        return json.load(open(f))
    CACHE.mkdir(parents=True, exist_ok=True)
    before = int(t_seen) + 13 * 3600
    d = MG.get(MG.GT.format(pool) + f"&before_timestamp={before}", {"User-Agent": "Mozilla/5.0"}, pause=10)
    time.sleep(6.5)
    rows = (((d or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
    rows = sorted({r[0]: r for r in rows}.values())
    # keep only candles from the graduation on: the pool cannot trade before it exists, but guard anyway
    rows = [r for r in rows if r[0] >= int(t_seen) - 3600]
    json.dump(rows, open(f, "w"))
    return rows


def main():
    g = pd.read_csv(ROOT / "logs" / "meme_graduates.csv", parse_dates=["seen_utc"])
    g = g[g.pool.notna()].drop_duplicates("mint")
    g["day"] = g.seen_utc.dt.strftime("%Y-%m-%d")
    days = sorted(d for d in g.day.unique() if "2026-09-23" <= d <= "2026-10-06")
    rng = np.random.default_rng(0)
    pick = pd.concat([x.iloc[rng.permutation(len(x))[:PER_DAY]] for d, x in g[g.day.isin(days)].groupby("day")])
    res = []
    for k, r in enumerate(pick.itertuples()):
        t_seen = pd.Timestamp(r.created_ms, unit="ms").timestamp() if np.isfinite(r.created_ms) else r.seen_utc.timestamp()
        try:
            rows = window(r.pool, max(t_seen, r.seen_utc.timestamp() - 3600))
        except MG.Throttled:
            print("throttled - rerun to resume", flush=True)
            break
        o = MG.outcome(rows)
        if o:
            res.append(dict(o, day=r.day, symbol=r.symbol))
        if k % 25 == 0:
            print(f"  {k}/{len(pick)} fetched", flush=True)
    R = pd.DataFrame(res)
    R = R[(R.real == True) & (R.glitch == False)]  # noqa: E712
    lines = [f"backtest/meme_days.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; {len(R)} real graduates (glitches out) from "
             f"{R.day.nunique()} days {days[0]} .. {days[-1]}, up to {PER_DAY} a day; net of 2%", ""]
    cols = [("e1_15m", "buy +1 min, sell +15 min"), ("e1_1h", "buy +1 min, sell +1h"), ("e1_6h", "buy +1 min, sell +6h"),
            ("e15_15m", "buy +15 min, sell +15 min"), ("e15_1h", "buy +15 min, sell +1h"), ("e15_6h", "buy +15 min, sell +6h"),
            ("w60_h360", "wait for proof (alive at +1h), hold 6h")]
    for c, nm in cols:
        if c not in R:
            continue
        x = R[c].dropna().to_numpy() - MG.COST
        if len(x) < 10:
            continue
        lo, hi = MG.boot_ci(x)
        byday = R.groupby("day")[c].mean() - MG.COST
        lines.append(f"  {nm:40} n {len(x):4d} | mean {x.mean() * 100:+6.1f}% [{lo * 100:+.0f}%, {hi * 100:+.0f}%] | median "
                     f"{np.median(x) * 100:+6.1f}% | win {(x > 0).mean() * 100:3.0f}% | days with a positive mean "
                     f"{(byday > 0).sum()}/{byday.notna().sum()}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
