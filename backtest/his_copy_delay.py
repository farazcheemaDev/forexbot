"""IF WE CANNOT DECODE HIM, CAN WE COPY HIM? His edge after a delay, at a real broker's prices.

§32-34: his pick is real (10 of 12 days at a 7-point race, t 5.8), real-time (his exits look exactly like a
mechanical target, his_extremes.py), and not recoverable from any recorded data. For the goal - maximum return -
the question that matters is whether FOLLOWING him pays: someone copying his trades enters seconds after him.
His edge lives at 1-5 minutes, not in the first ticks (at +-4 points he is ordinary), so a delay may cost little.
For his 25 clean entries, entered d seconds late (d = 0, 5, 10, 20, 30, 60, 120) in his direction:
  mid race    +7 before -7 on USTECm mid (600 s)
  net race    entered at the Exness quote, +7 / -7 on the exit side (600 s)  - break-even 50%
  his exit    +7 target at the quote, no stop, closed at 30 minutes if never hit - points per trade net of the
              spread (the way he trades, copied)
Against the same for the same-sitting moments (whole-minute offsets within 20 minutes, same direction).

REGISTERED PREDICTION (2026-09-26, before running): his mid race stays >= 75% up to a 10-s delay and falls toward
the nearby rate by 60 s; net of the spread a 5-10 s copy still wins >= 60% of +-7 races and makes >= +3 points a
trade with his exit, where the same-sitting moments lose ~-2 to -3.

    python -m backtest.his_copy_delay
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_race_curve import race2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0
DELAYS = (0, 5, 10, 20, 30, 60, 120)


def net_race(ts, mid, spr, t, s, T=7, W=600):
    i = np.searchsorted(ts, t, side="right") - 1
    e = mid[i] + s * spr[i] / 2
    j1 = np.searchsorted(ts, t + W, side="right")
    p = s * ((mid[i + 1:j1] - s * spr[i + 1:j1] / 2) - e)
    up, dn = np.flatnonzero(p >= T), np.flatnonzero(p <= -T)
    if not len(up) and not len(dn):
        return None
    return int(len(up) > 0 and (not len(dn) or up[0] < dn[0]))


def his_exit(ts, mid, spr, t, s, T=7, W=1800):
    i = np.searchsorted(ts, t, side="right") - 1
    e = mid[i] + s * spr[i] / 2
    j1 = min(np.searchsorted(ts, t + W, side="right"), len(ts) - 1)
    p = s * ((mid[i + 1:j1] - s * spr[i + 1:j1] / 2) - e)
    hit = np.flatnonzero(p >= T)
    return float(T) if len(hit) else float(p[-1]) if len(p) else None


def main():
    cache = pickle.loads(TICKS.read_bytes())
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["et"] = (x.open_time - pd.Timedelta(hours=GMT)).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x[x.open_time - pd.Timedelta(hours=GMT) >= "2026-04-01"]
    x["d"] = x.et.dt.normalize()
    x["t"] = (x.et - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    res = {("his", d): [] for d in DELAYS} | {("near", d): [] for d in DELAYS}
    for r in x.itertuples():
        if r.d not in cache or cache[r.d] is None:
            continue
        ts, mid, spr = cache[r.d]
        s = 1 if r.side == "BUY" else -1
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if r.t + 60 * m > 60 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t0 in starts:
            for dl in DELAYS:
                t = t0 + dl
                res[(who, dl)].append((race2(ts, mid, t, s, 600, 7, 7), net_race(ts, mid, spr, t, s), his_exit(ts, mid, spr, t, s)))
    out = [f"his {len(res[('his', 0)])} clean entries entered d seconds late, vs the same-sitting moments; Exness quotes",
           f"  {'delay':>6} | {'mid race':>9}{'nearby':>8} | {'net race':>9}{'nearby':>8} | {'his exit, pts':>14}{'nearby':>8}{'his win%':>9}"]
    for dl in DELAYS:
        H, N = np.array(res[("his", dl)], dtype=object), np.array(res[("near", dl)], dtype=object)
        f = lambda A, i: np.mean([v for v in A[:, i] if v is not None])  # noqa: E731
        hx = [v for v in H[:, 2] if v is not None]
        out.append(f"  {dl:>5}s | {f(H, 0)*100:>8.0f}%{f(N, 0)*100:>7.0f}% | {f(H, 1)*100:>8.0f}%{f(N, 1)*100:>7.0f}% | "
                   f"{np.mean(hx):>+14.2f}{f(N, 2):>+8.2f}{np.mean(np.array(hx) >= 7)*100:>8.0f}%")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_copy_delay.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
