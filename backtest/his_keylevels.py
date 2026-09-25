"""THE DAY'S KEY LEVELS AT HIS MOMENTS - what his charts show by eye, tested against the rest of his sitting.

Looking at his 25 clean trades drawn on his broker's scale (his_look.py, logs/his_look/) shows him trading AT
levels: the day's open and yesterday's high as support (04-06, bought +12.5, then sold into 24,300), 29,800 bought
twice and the bounce's top sold (06-05), yesterday's close as the target (04-02), the break of 30,000 at the day's
high (07-10). The 75-feature model (his_model.py) had round numbers (via the NQ basis) and the last hour's range,
but NOT these levels. Levels (all from the same USTECm series, so basis-free, except round numbers):
  yesterday's high / low / close (09:30-16:00), today's 09:30 open, the first-15-minute high / low, and the
  day's high / low so far; round 100s and 50s on HIS scale (the offset his own fills give that day)
Features at a moment (p = mid now), for his direction s:
  dist_key    points to the nearest key level
  support     a key level on the far side of p within 10 points (below a buy / above a sell): trading off it
  room        points to the next key level in his direction (where a target would sit)
  d100 / d50  points to the nearest 100 / 50 on his scale
STAGE A: his 25 clean entries vs the 40 same-sitting moments at whole-minute offsets within 20 minutes (same second
of the minute, same direction, none within 60 s of another entry). Continuous by rank (0.50 ordinary), the flag by
rate; Holm over 5. STAGE B (key levels only - round numbers need his scale): all other tick days, random moments:
does "support within 10 points" or closeness to a key level move the 7-point race?

REGISTERED PREDICTION (2026-09-26, before running): his entries sit closer to key levels than the rest of his
sitting (dist_key rank <= 0.40, support flag ~1.5x) - the chart impression - but nothing survives Holm on 25
trades, and in B trading off a nearby key level moves the 7-point race by at most +3 points.

    python -m backtest.his_keylevels
"""
from __future__ import annotations

import pickle
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_race_curve import race2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0


def at(ts, mid, t):
    return mid[max(np.searchsorted(ts, t, side="right") - 1, 0)]


def keys(cache, tdays, d, ts, mid, t):
    prev = [x for x in tdays if x < d]
    lv = []
    if prev:
        pts, pm, _ = cache[prev[-1]]
        k = pts < 23400
        if k.any():
            lv += [pm[k].max(), pm[k].min(), pm[k][-1]]
    lv.append(mid[0])
    o15 = ts < 900
    if t > 900:
        lv += [mid[o15].max(), mid[o15].min()]
    past = ts < t - 1
    if past.sum() > 10:
        lv += [mid[past].max(), mid[past].min()]
    return np.array(lv)


def feats(cache, tdays, d, t, s, b):
    ts, mid, _ = cache[d]
    p = at(ts, mid, t)
    L = keys(cache, tdays, d, ts, mid, t)
    rel = s * (L - p)                         # + = in his direction (ahead), - = behind him
    ahead = rel[rel > 0.5]
    f = dict(dist_key=np.abs(L - p).min(), support=float(((rel <= 0) & (rel >= -10)).any()),
             room=ahead.min() if len(ahead) else 200.0)
    if b is not None:
        q = p + b
        f["d100"] = abs(q - np.round(q / 100) * 100)
        f["d50"] = abs(q - np.round(q / 50) * 50)
    return f


def main():
    cache = pickle.loads(TICKS.read_bytes())
    tdays = sorted(d for d in cache if cache[d] is not None)
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    for c in ("open_time", "close_time"):
        x[c[:-5]] = (x[c] - pd.Timedelta(hours=GMT)).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x[x.open_time - pd.Timedelta(hours=GMT) >= "2026-04-01"]
    x["d"] = x.open.dt.normalize()
    x["t"] = (x.open - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    x["tc"] = (x.close - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    x = x[x.d.isin(tdays) & (x.t > 960)]
    B = {}
    for d, g in x.groupby("d"):
        ts, mid, _ = cache[d]
        B[d] = np.median([((r.open_price - at(ts, mid, r.t)) + (r.close_price - at(ts, mid, r.tc))) / 2 for r in g.itertuples()])
    FE = ("dist_key", "support", "room", "d100", "d50")
    ranks, fl_obs, fl_ps = [], 0, []
    for r in x.itertuples():
        s = 1 if r.side == "BUY" else -1
        mine = feats(cache, tdays, r.d, r.t, s, B[r.d])
        others = x[x.d == r.d].t.to_numpy()
        near = []
        for m in list(range(-20, 0)) + list(range(1, 21)):
            t = r.t + 60 * m
            if t < 960 or np.min(np.abs(others - t)) < 60:
                continue
            near.append(feats(cache, tdays, r.d, t, s, B[r.d]))
        N = pd.DataFrame(near)
        ranks.append({k: (N[k] < mine[k]).mean() + 0.5 * (N[k] == mine[k]).mean() for k in FE if k != "support"}
                     | {"raw_" + k: mine[k] for k in FE})
        fl_obs += mine["support"]
        fl_ps.append(N.support.mean())
    R = pd.DataFrame(ranks)
    pz = lambda z: 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))  # noqa: E731
    p = {k: pz((R[k].mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(R)))) for k in ("dist_key", "room", "d100", "d50")}
    ps = np.array(fl_ps)
    p["support"] = pz((fl_obs - ps.sum()) / np.sqrt((ps * (1 - ps)).sum()))
    order = sorted(p, key=p.get)
    holm = {k: min(1.0, max(p[j] * (len(p) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in p}
    out = [f"STAGE A - his {len(R)} clean entries (after 09:46 ET) vs the same-sitting moments at the same second "
           f"(rank: share of those moments with a SMALLER value; low = his are closer)"]
    for k in ("dist_key", "room", "d100", "d50"):
        out.append(f"  {k:<9} rank {R[k].mean():.2f}   his median {R['raw_' + k].median():6.1f} pts   p {p[k]:.3f}  Holm {holm[k]:.3f}")
    out.append(f"  support   his {int(fl_obs)} / {len(R)}  vs the sitting's rate {ps.mean()*100:.0f}%  ratio {fl_obs / ps.sum():.2f}"
               f"   p {p['support']:.3f}  Holm {holm['support']:.3f}")

    rng = np.random.default_rng(24)
    his_days = set(x.d)
    rows = []
    for d in tdays:
        if d in his_days:
            continue
        ts, mid, spr = cache[d]
        for t in rng.uniform(1800, 22800, 40):
            for s in (1, -1):
                o = race2(ts, mid, t, s, 600, 7, 7)
                if o is None:
                    continue
                rows.append(feats(cache, tdays, d, t, s, None) | {"o": o, "day": d})
    P = pd.DataFrame(rows)
    ds = sorted(P.day.unique())
    md = ds[len(ds) // 2]
    w = lambda g: g.o.mean() * 100  # noqa: E731
    out.append(f"\nSTAGE B - {len(P)} random moment x direction pairs on {len(ds)} other days; 7-point race base {w(P):.1f}%")
    on, off = P.support.astype(bool), ~P.support.astype(bool)
    out.append(f"  support within 10 pts: on {w(P[on]):.1f}% (n {int(on.sum())}) vs off {w(P[off]):.1f}%;  halves "
               f"{w(P[on & (P.day < md)]) - w(P[off & (P.day < md)]):+.1f} / {w(P[on & (P.day >= md)]) - w(P[off & (P.day >= md)]):+.1f}")
    for k in ("dist_key", "room"):
        lo, hi = P[k].quantile(1 / 3), P[k].quantile(2 / 3)
        out.append(f"  {k:<9} near third {w(P[P[k] <= lo]):.1f}%  far third {w(P[P[k] >= hi]):.1f}%")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_keylevels.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
