"""IS THE 87% SOLID? His moment's edge across targets, stops, paths - and his broker's clock to the second.

The user, 2026-09-26: "must be something that tells them apart - he sees what we don't". Every search since
§26 rests on one number: from his clean entries, NASDAQ goes +7 before -7 (mid, 180 s) in 87% (20/23),
against 54% for the other moments of the same 20 minutes. The repo's rule is to attack a good result before
building on it, and there is already a crack: NET of the spread (+8.1 / -5.9 on mid) his entries win 42%,
the same as random. A real informational edge should not vanish when the race shifts by one point.
  A  the symmetric race at T = 2..15 points (180 s and 600 s): his vs the same-day nearby moments
  B  target 7 with stops 3..20: where does his advantage live?
  C  the median sign-aligned path after his entries vs nearby, 0..300 s
  D  his BROKER's clock/feed vs the real market at 1-second resolution: for shifts d = -20..+20 s, the
     real move over [open+d, close+d] against the points he banked (basis-free). A broker quoting the
     market late (or early) - something he would see and we would not - shows as a best d away from 0.
     §25 looked at -600..+600 s and found 0, but only to about +-10 s.

REGISTERED PREDICTION (2026-09-26, before running): the edge is fragile. A: his advantage peaks near T = 6-8
and is <= +10 points at T <= 4. B: with stops <= 5 his win rate is within 10 points of nearby; the
advantage needs a stop >= 7 (his entries dip 5-7 points first). C: the median path goes against him for
the first 10-30 s, then turns. D: best shift within +-2 s of 0 - no broker lag.

    python -m backtest.his_race_curve
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0


def race2(ts, mid, t, s, W, tgt, stp):
    i = np.searchsorted(ts, t, side="right") - 1
    if i < 0:
        return None
    j1 = np.searchsorted(ts, t + W, side="right")
    p = s * (mid[i + 1:j1] - mid[i])
    up = np.flatnonzero(p >= tgt)
    dn = np.flatnonzero(p <= -stp)
    if not len(up) and not len(dn):
        return None
    if not len(dn):
        return 1
    if not len(up):
        return 0
    return int(up[0] < dn[0])


def at(ts, mid, t):
    return mid[max(np.searchsorted(ts, t, side="right") - 1, 0)]


def main():
    cache = pickle.loads(TICKS.read_bytes())
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    for c in ("open_time", "close_time"):
        x[c + "_et"] = (x[c] - pd.Timedelta(hours=GMT)).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x[x.open_time - pd.Timedelta(hours=GMT) >= "2026-04-01"]
    rng = np.random.default_rng(19)
    E = []
    for r in x.itertuples():
        d = r.open_time_et.normalize()
        if d not in cache or cache[d] is None:
            continue
        o0 = d + pd.Timedelta(hours=9, minutes=30)
        E.append(dict(d=d, t=(r.open_time_et - o0).total_seconds(), tc=(r.close_time_et - o0).total_seconds(),
                      s=1 if r.side == "BUY" else -1, pts=(1 if r.side == "BUY" else -1) * (r.close_price - r.open_price)))
    near = {i: [e["t"] + rng.uniform(30, 1200) * rng.choice((-1, 1)) for _ in range(80)] for i, e in enumerate(E)}
    out = [f"{len(E)} clean entries in the tick cache; nearby = 80 moments each, same day, 30 s - 20 min away, same direction"]

    def rate(tgt, stp, W):
        h, n = [], []
        for i, e in enumerate(E):
            ts, mid, _ = cache[e["d"]]
            o = race2(ts, mid, e["t"], e["s"], W, tgt, stp)
            if o is not None:
                h.append(o)
            n += [v for v in (race2(ts, mid, t, e["s"], W, tgt, stp) for t in near[i]) if v is not None]
        return np.mean(h) * 100, len(h), np.mean(n) * 100

    out.append("\nA. SYMMETRIC RACE +T before -T (mid)")
    out.append(f"  {'T':>4} | {'180 s: his':>11}{'nearby':>8}{'edge':>7} | {'600 s: his':>11}{'nearby':>8}{'edge':>7}")
    for T in (2, 3, 4, 5, 6, 7, 8, 10, 12, 15):
        a, na, b = rate(T, T, 180)
        c, nc, dd = rate(T, T, 600)
        out.append(f"  {T:>4} | {a:>8.0f}% ({na:>2}){b:>6.0f}%{a - b:>+7.0f} | {c:>8.0f}% ({nc:>2}){dd:>6.0f}%{c - dd:>+7.0f}")
    out.append("\nB. TARGET +7, STOP -S (mid, 600 s)")
    for S in (3, 4, 5, 6, 7, 8, 10, 15, 20):
        a, na, b = rate(7, S, 600)
        out.append(f"  stop {S:>3}: his {a:>4.0f}% ({na:>2})   nearby {b:>4.0f}%   edge {a - b:>+4.0f}")

    grid = np.array([0, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300])
    def path(ts, mid, t, s):
        base = at(ts, mid, t)
        return s * (np.array([at(ts, mid, t + g) for g in grid]) - base)
    H = np.array([path(*cache[e["d"]][:2], e["t"], e["s"]) for e in E])
    N = np.array([path(*cache[e["d"]][:2], t, e["s"]) for i, e in enumerate(E) for t in near[i]])
    out.append("\nC. MEDIAN PATH, points his way (mid), after his entry vs nearby moments")
    out.append("  seconds  " + "".join(f"{g:>6}" for g in grid))
    out.append("  his      " + "".join(f"{v:>+6.1f}" for v in np.median(H, axis=0)))
    out.append("  nearby   " + "".join(f"{v:>+6.1f}" for v in np.median(N, axis=0)))
    out.append("  his share his way " + "".join(f"{v:>5.0f}%" for v in (H > 0).mean(axis=0) * 100))
    mae = [min(0.0, H_i[:grid.searchsorted(60) + 1].min()) for H_i in H]
    out.append(f"  his worst point in the first 60 s: median {np.median(mae):+.1f}, quartiles {np.percentile(mae, 25):+.1f} / {np.percentile(mae, 75):+.1f}")

    out.append("\nD. HIS BROKER vs THE REAL MARKET: points he banked vs the real mid move over [open+d, close+d]")
    res = []
    for dsh in range(-20, 21):
        dif = np.array([e["s"] * (at(*cache[e["d"]][:2], e["tc"] + dsh) - at(*cache[e["d"]][:2], e["t"] + dsh)) - e["pts"] for e in E])
        k = np.median(dif)
        res.append((dsh, k, np.sqrt(np.mean((dif - k) ** 2)), np.median(np.abs(dif - k))))
    best = min(res, key=lambda z: z[2])
    for dsh, k, rmse, mad in res:
        if dsh % 2 == 0 or abs(dsh) <= 3:
            out.append(f"  d {dsh:>+3} s: offset {k:+.2f} pts  rmse {rmse:5.2f}  median abs {mad:5.2f}{'   <- best' if dsh == best[0] else ''}")
    # E (added after A-D ran): his 26 entries fall on 12 days and same-day trades are not independent - count by day
    out.append("\nE. BY DAY (same-day entries are not independent): symmetric race, 600 s, his day rate minus nearby")
    for T in (4, 7, 10):
        rec = []
        for i, e in enumerate(E):
            ts, mid, _ = cache[e["d"]]
            h = race2(ts, mid, e["t"], e["s"], 600, T, T)
            nn = [v for v in (race2(ts, mid, t, e["s"], 600, T, T) for t in near[i]) if v is not None]
            if h is not None and nn:
                rec.append((e["d"], h, np.mean(nn)))
        R = pd.DataFrame(rec, columns=["d", "h", "n"]).groupby("d").mean()
        ed = (R.h - R.n) * 100
        se = ed.std(ddof=1) / np.sqrt(len(ed))
        out.append(f"  T {T:>2}: {len(ed)} days, his day above nearby on {int((ed > 0).sum())}, mean day edge {ed.mean():+.1f} "
                   f"points, se {se:.1f}, t {ed.mean() / se:.2f}")

    # F (added after A-D ran): the real price in the seconds around his entry and his exit
    D = np.arange(-6, 7)
    EN = np.array([[e["s"] * (at(*cache[e["d"]][:2], e["t"] + k) - at(*cache[e["d"]][:2], e["t"])) for k in D] for e in E])
    EX = np.array([[e["s"] * (at(*cache[e["d"]][:2], e["tc"] + k) - at(*cache[e["d"]][:2], e["tc"])) for k in D] for e in E])
    out.append("\nF. THE REAL PRICE AROUND HIS ENTRY AND EXIT SECONDS (mid, his way, relative to that second)")
    out.append("  seconds          " + "".join(f"{k:>+6d}" for k in D))
    out.append("  entry, median    " + "".join(f"{v:>+6.1f}" for v in np.median(EN, 0)))
    out.append("  entry, share > 0 " + "".join(f"{v:>5.0f}%" for v in (EN > 0).mean(0) * 100))
    out.append("  exit, median     " + "".join(f"{v:>+6.1f}" for v in np.median(EX, 0)))
    out.append("  exit, share > 0  " + "".join(f"{v:>5.0f}%" for v in (EX > 0).mean(0) * 100))
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_race_curve.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
