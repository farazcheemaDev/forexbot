"""REAL-TIME OR HINDSIGHT? Where his entry and exit prices sit among the prices around them.

§32-33: his entries carry real information about NASDAQ's next 1-5 minutes (10 of 12 days, t 5.8) that no
recorded data holds, even in combination (a model with planted-pattern power finds nothing). Two explanations
fit that: foresight (he sees something we cannot record), or a record whose trades were not decided in real
time - and §25 already found his broker's January-March fills earning moves the market never offered. They
leave different fingerprints in the EXIT, which carries no forecasting skill for a trader with a fixed target:
  - a real-time trader exits on a 7-point target at its FIRST TOUCH; whether the price then goes higher is luck,
    so the exit is often not the best price of the minutes around it;
  - a record written with hindsight exits at (or near) the best price around, again and again.
For each of his 25 clean trades (USTECm mid, sign-aligned, 1 = the best price in the window):
  entry_60 / entry_300   where his entry second's price ranks among the prices within +-60 s / +-300 s
  exit_60 / exit_300     the same for his exit
CONTROLS, same days and directions: (a) random moments within 20 minutes as entries; (b) the FIRST TOUCH of
+his points after each such random entry as exits (a mechanical target exit, the fair control for his exits).

REGISTERED PREDICTION (2026-09-26, before running): his entries rank ~0.7-0.8 (a dip buyer, not the exact low);
his exits rank like first-touch target exits (~0.7-0.8, within 0.1 of the control). If his exits sit >= 0.2
above the control, at the best price of the surrounding 5 minutes, that is the hindsight fingerprint.

    python -m backtest.his_extremes
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


def at(ts, mid, t):
    return mid[max(np.searchsorted(ts, t, side="right") - 1, 0)]


def rank_in(ts, mid, t, s, w, entry):
    """share of 1-s prices within +-w of t that are WORSE than the price at t (1 = t is the best).
    For an entry the best is the lowest (buy) / highest (sell); for an exit the highest (buy) / lowest (sell)."""
    grid = np.arange(t - w, t + w + 1, 1.0)
    p = np.array([at(ts, mid, g) for g in grid])
    v = at(ts, mid, t)
    good = -s if entry else s
    return np.mean(good * (p - v) < 0) + 0.5 * np.mean(p == v)


def first_touch(ts, mid, t, s, pts, W=3600):
    i = np.searchsorted(ts, t, side="right") - 1
    j1 = np.searchsorted(ts, t + W, side="right")
    hit = np.flatnonzero(s * (mid[i + 1:j1] - mid[i]) >= pts)
    return ts[i + 1 + hit[0]] if len(hit) else None


def main():
    cache = pickle.loads(TICKS.read_bytes())
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    for c in ("open_time", "close_time"):
        x[c[:-5]] = (x[c] - pd.Timedelta(hours=GMT)).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x[x.open_time - pd.Timedelta(hours=GMT) >= "2026-04-01"]
    rng = np.random.default_rng(23)
    H, C = [], []
    for r in x.itertuples():
        d = r.open.normalize()
        if d not in cache or cache[d] is None:
            continue
        ts, mid, _ = cache[d]
        o0 = d + pd.Timedelta(hours=9, minutes=30)
        t, tc = (r.open - o0).total_seconds(), (r.close - o0).total_seconds()
        if t < 300 or tc > ts[-1] - 300:
            continue
        s = 1 if r.side == "BUY" else -1
        pts = max(s * (r.close_price - r.open_price), 1.0)
        H.append(dict(entry_60=rank_in(ts, mid, t, s, 60, True), entry_300=rank_in(ts, mid, t, s, 300, True),
                      exit_60=rank_in(ts, mid, tc, s, 60, False), exit_300=rank_in(ts, mid, tc, s, 300, False),
                      after_60=s * (at(ts, mid, tc + 60) - at(ts, mid, tc)), won=r.net > 0))
        for _ in range(30):
            tt = t + rng.uniform(30, 1200) * rng.choice((-1, 1))
            if tt < 300:
                continue
            tx = first_touch(ts, mid, tt, s, pts)
            if tx is None or tx > ts[-1] - 300:
                continue
            C.append(dict(entry_60=rank_in(ts, mid, tt, s, 60, True), entry_300=rank_in(ts, mid, tt, s, 300, True),
                          exit_60=rank_in(ts, mid, tx, s, 60, False), exit_300=rank_in(ts, mid, tx, s, 300, False),
                          after_60=s * (at(ts, mid, tx + 60) - at(ts, mid, tx))))
    Hd, Cd = pd.DataFrame(H), pd.DataFrame(C)
    out = [f"{len(Hd)} of his clean trades; control: {len(Cd)} random same-day entries in his direction, exited at the FIRST "
           f"touch of his points (a mechanical target exit)", "",
           f"  {'':<12}{'his mean':>10}{'his median':>12}{'control mean':>14}{'diff':>7}{'p':>8}{'his >= 0.95':>13}{'control':>9}"]
    for k in ("entry_60", "entry_300", "exit_60", "exit_300"):
        a, b = Hd[k], Cd[k]
        z = (a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
        out.append(f"  {k:<12}{a.mean():>10.2f}{a.median():>12.2f}{b.mean():>14.2f}{a.mean() - b.mean():>+7.2f}{p:>8.3f}"
                   f"{np.mean(a >= 0.95)*100:>12.0f}%{np.mean(b >= 0.95)*100:>8.0f}%")
    out.append(f"\n  the price 60 s after the exit, his way: his median {Hd.after_60.median():+.2f} (share higher "
               f"{np.mean(Hd.after_60 > 0)*100:.0f}%), control median {Cd.after_60.median():+.2f} "
               f"(share higher {np.mean(Cd.after_60 > 0)*100:.0f}%)")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_extremes.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
