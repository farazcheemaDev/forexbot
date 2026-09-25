"""EVERY 1-MINUTE CANDLE PATTERN AT HIS MOMENTS - the chart he watches, read the way a 1-minute trader reads it.

The user, 2026-09-26: "he does [it] on 1 minute I guess". Already tested on 1-minute candles: the last closed
candle's body and wicks, hammer and engulfing vs other days (his_candles.py), the rejection wick vs the same
20 minutes (his_local.py), trend-pause-resume as a rule (his_micro.py), SMC and indicators (his_ta.py). Not
yet: the full candlestick set, and the candle that is FORMING when he clicks (~18 s into the minute).

Flags, sign-aligned to his direction (k = the last closed 1-minute candle, from USTECm mid ticks):
  pinbar      k's wick against him >= 60% of its range, body <= 30%, close in his half
  engulf      k his way, k-1 against, k's body covers k-1's body
  inside      k inside k-1's range
  doji        k's body <= 10% of its range
  outside     k's range covers k-1's and k closes his way
  three       k, k-1, k-2 all his way (momentum)
  pull1       k against him after k-1 and k-2 his way (the first pullback candle)
  pull2       k and k-1 against him after k-2 and k-3 his way (a two-candle pullback)
  star        k-2 against with a body >= its range's half, k-1 small (body <= 30%), k his way with body >= half
  tweezer     k's and k-1's extremes against him within 0.5 points (a 1-minute double bottom / top)
  brk_prev    k closed beyond k-1's extreme in his direction
  cur_sweep   the FORMING candle has already gone beyond k's extreme against him and is back inside at his click
  cur_against the forming candle is against him at his click (price vs its open)
STAGE A: his clean entries vs ~80 moments of the same day within 20 minutes, same direction, AT THE SAME
SECOND OF THE MINUTE as his entry (so the forming candle is equally old). Poisson-binomial, Holm over 13.
STAGE B: all tick days, random minutes, entered at 18 s past (his median second), both directions: mid race
and NET race (break-even 50%) with the flag on vs off, by half.

REGISTERED PREDICTION (2026-09-26, before running): pinbar at ~1.5-2x the nearby rate (the hammer / wick
again, p ~0.05) and cur_against high (he buys the dip inside the candle, §25), pull1 ~1.5x; nothing survives
Holm over 13. In B no flag gets the net race above 40%.

    python -m backtest.his_1m
"""
from __future__ import annotations

import pickle
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_local import race  # noqa: E402
from backtest.his_predictors import race_net  # noqa: E402
from backtest.his_ta import candles  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0
FLAGS = ("pinbar", "engulf", "inside", "doji", "outside", "three", "pull1", "pull2", "star", "tweezer", "brk_prev",
         "cur_sweep", "cur_against")


def flags(ts, mid, B, t, s):
    k = int(t // 60) - 1
    if k < 4 or k >= len(B["c"]):
        return None
    o, h, l, c = B["o"], B["h"], B["l"], B["c"]
    body = lambda j: s * (c[j] - o[j])  # noqa: E731
    rng = lambda j: h[j] - l[j]  # noqa: E731
    if rng(k) <= 0 or rng(k - 1) <= 0:
        return None
    against_w = (min(o[k], c[k]) - l[k]) if s == 1 else (h[k] - max(o[k], c[k]))
    his_half = ((c[k] - l[k]) / rng(k) >= 0.5) if s == 1 else ((h[k] - c[k]) / rng(k) >= 0.5)
    ext = lambda j: l[j] if s == 1 else h[j]  # noqa: E731    extreme against him
    i0 = np.searchsorted(ts, (k + 1) * 60.0)
    i1 = np.searchsorted(ts, t, side="right")
    if i1 <= i0:
        return None
    cur = mid[i0:i1]
    p = cur[-1]
    beyond = (cur.min() < l[k]) if s == 1 else (cur.max() > h[k])
    back = (p > l[k]) if s == 1 else (p < h[k])
    return dict(
        pinbar=against_w / rng(k) >= 0.6 and abs(body(k)) <= 0.3 * rng(k) and his_half,
        engulf=body(k) > 0 and body(k - 1) < 0 and body(k) >= -body(k - 1),
        inside=h[k] <= h[k - 1] and l[k] >= l[k - 1],
        doji=abs(body(k)) <= 0.1 * rng(k),
        outside=h[k] >= h[k - 1] and l[k] <= l[k - 1] and body(k) > 0,
        three=body(k) > 0 and body(k - 1) > 0 and body(k - 2) > 0,
        pull1=body(k) < 0 and body(k - 1) > 0 and body(k - 2) > 0,
        pull2=body(k) < 0 and body(k - 1) < 0 and body(k - 2) > 0 and body(k - 3) > 0,
        star=(rng(k - 2) > 0 and body(k - 2) < 0 and -body(k - 2) >= 0.5 * rng(k - 2)
              and abs(body(k - 1)) <= 0.3 * max(rng(k - 1), 1e-9) and body(k) >= 0.5 * rng(k)),
        tweezer=abs(ext(k) - ext(k - 1)) <= 0.5,
        brk_prev=(c[k] > h[k - 1]) if s == 1 else (c[k] < l[k - 1]),
        cur_sweep=bool(beyond and back),
        cur_against=s * (p - cur[0]) < 0)


def pz(z):
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def main():
    cache = pickle.loads(TICKS.read_bytes())
    days = [d for d in sorted(cache) if cache[d] is not None]
    BB = {}
    def bars(d):
        if d not in BB:
            BB[d] = candles(cache[d][0], cache[d][1], 60)
        return BB[d]
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-01"]
    rng = np.random.default_rng(18)
    obs, ps, his = {k: 0 for k in FLAGS}, {k: [] for k in FLAGS}, []
    for r in x.itertuples():
        et = pd.Timestamp(r.utc).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        d = et.normalize()
        if d not in cache or cache[d] is None:
            continue
        ts, mid, _ = cache[d]
        B = bars(d)
        t0 = (et - (d + pd.Timedelta(hours=9, minutes=30))).total_seconds()
        s = 1 if r.side == "BUY" else -1
        mine = flags(ts, mid, B, t0, s)
        if mine is None:
            continue
        near = []
        for _ in range(300):
            m = int(rng.integers(1, 21)) * int(rng.choice((-1, 1)))      # whole minutes away: same second of the minute
            f = flags(ts, mid, B, t0 + 60 * m, s)
            if f is not None:
                near.append(f)
            if len(near) >= 80:
                break
        N = pd.DataFrame(near)
        for k in FLAGS:
            obs[k] += mine[k]
            ps[k].append(N[k].mean())
        his.append(mine | {"et": et, "side": r.side, "net": r.net})
    n = len(his)
    pA = {}
    rows = []
    for k in FLAGS:
        p_ = np.array(ps[k])
        e, var = p_.sum(), (p_ * (1 - p_)).sum()
        pA[k] = pz((obs[k] - e) / sqrt(var)) if var > 0 else 1.0
        rows.append((k, obs[k], p_.mean() * 100, obs[k] / e if e else np.nan))
    order = sorted(pA, key=pA.get)
    holm = {k: min(1.0, max(pA[j] * (len(pA) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in pA}
    out = [f"STAGE A - his {n} clean entries vs ~80 moments of the same day within 20 min, same direction, same second "
           f"of the minute", f"  {'flag':<12}{'his':>8}{'nearby':>9}{'ratio':>7}{'p':>7}{'Holm':>7}"]
    for k, o_, nr, ratio in rows:
        out.append(f"  {k:<12}{o_:>3} /{n:>3}{nr:>8.1f}%{ratio:>7.2f}{pA[k]:>7.3f}{holm[k]:>7.3f}")

    P = []
    for d in days:
        ts, mid, spr = cache[d]
        B = bars(d)
        for m in rng.integers(30, 390, 40):
            t = m * 60 + 18.0
            for s in (1, -1):
                f = flags(ts, mid, B, t, s)
                o = race(ts, mid, t, s)
                if f is None or o is None:
                    continue
                P.append(f | {"o": o, "on": race_net(ts, mid, spr, t, s), "day": d})
    P = pd.DataFrame(P)
    mid_day = days[len(days) // 2]
    w = lambda g, c="o": g[c].dropna().mean() * 100 if len(g) else np.nan  # noqa: E731
    out.append(f"\nSTAGE B - {len(P)} random minutes x direction on {P.day.nunique()} days, entered 18 s past the minute; "
               f"mid race base {w(P):.1f}%, NET race base {w(P, 'on'):.1f}% (break-even 50%)")
    out.append(f"  {'flag':<12}{'off':>8}{'on':>8}{'diff':>7}{'1st half':>9}{'2nd half':>9}{'net on':>9}{'n on':>7}")
    for k in FLAGS:
        on, off = P[k].astype(bool), ~P[k].astype(bool)
        h1, h2 = P.day < mid_day, P.day >= mid_day
        out.append(f"  {k:<12}{w(P[off]):>7.1f}%{w(P[on]):>7.1f}%{w(P[on]) - w(P[off]):>+7.1f}"
                   f"{w(P[on & h1]) - w(P[off & h1]):>+9.1f}{w(P[on & h2]) - w(P[off & h2]):>+9.1f}{w(P[on], 'on'):>8.1f}%{int(on.sum()):>7}")
    out.append("\nHIS ENTRIES (1 = present)")
    for r in his:
        out.append(f"  {r['et']:%Y-%m-%d %H:%M:%S} {r['side']:<4} ${r['net']:>8.2f}  " +
                   " ".join(f"{k} {int(r[k])}" for k in FLAGS))
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_1m.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
