"""IS THE ORDER-FLOW SIGNAL REAL - lead/lag, price-move control, the spread, and the "sellers stopped" pause.

his_orderflow_archive.py found, on 24 days, that the Binance QQQ perp's aggressor imbalance over the last
10 s predicts the 3-minute NASDAQ mid race by +11.7 points (top vs bottom third; +14.6 / +8.8 by half) -
3-4x the size I registered. A result that large gets the bug hunt first:
  1. LEAD/LAG: correlate 1-second returns of Binance QQQ (trade prices) and USTECm (Exness mid) at lags
     -20..+20 s. If Binance's clock runs AHEAD of Exness's tick clock, "the last 10 s" on Binance is
     partly the future on Exness, and the signal is look-ahead.
  2. PRICE CONTROL: the perp is thin (20-75 trades a minute; arbitrageurs lift it after NASDAQ moves), so
     imb_10 may only restate NASDAQ's own last-10-s move, which the Exness chart shows anyway. Within
     terciles of USTECm's own 10-s move, does imb_10 still split the race?
  3. THE SPREAD: net race (enter at the quote, +7 / -7 on the exit side, 180 s) by imb_10 decile, both
     halves. Break-even is 50%; random entries net ~42% (his_predictors.py).
  4. THE PAUSE: in A1 his entries had the 30-s flow AGAINST him (imb_30 rank 0.38, p 0.057) but the last
     10 s ordinary (0.47). "Sellers hit, then stopped" - turn = imb_10 - imb_30, and stop5 = notional in
     the last 5 s / notional in the last 30 s (low = the aggression went quiet). Ranked as in A1.

REGISTERED PREDICTIONS (2026-09-26, before running):
  1. peak correlation at lag 0 or +1 s (Binance at most a second behind or level); no Binance lead >= 2 s.
  2. inside USTECm's own-move terciles imb_10 keeps +3 to +6 points: some of it is price, not all.
  3. no imb_10 decile nets >= 50% on both halves; the top decile nets 44-48%.
  4. his entries rank >= 0.6 on turn and <= 0.4 on stop5 (p ~0.05); in B neither beats +3 points.

    python -m backtest.his_orderflow_check
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
from backtest.his_orderflow_archive import QDIR, TICKS, feats, load_day, pval, rank  # noqa: E402
from backtest.his_predictors import race_net  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GMT = 5.0


def off_ms(d):
    et0 = d + pd.Timedelta(hours=9, minutes=30)
    return int(pd.Timestamp(et0).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).value // 10**6)


def extra(q, tm, s):
    T = q["T"]
    i30, i10, i5, i1 = (np.searchsorted(T, tm - w * 1000) for w in (30, 10, 5, 0))
    n30, n5 = q["n"][i30:i1].sum(), q["n"][i5:i1].sum()
    return dict(stop5=n5 / n30 if n30 > 0 else np.nan)


def main():
    days = sorted(pd.Timestamp(f.stem.split("-aggTrades-")[1]) for f in QDIR.glob("*.csv"))
    Q = {d: load_day(d) for d in days}
    ticks = pickle.loads(TICKS.read_bytes())
    days = [d for d in days if d in ticks and ticks[d] is not None]

    # 1. lead / lag on a 1-second grid, 09:30-16:00 ET
    lags = range(-20, 21)
    xs = {k: [] for k in lags}
    for d in days:
        ts, mid, _ = ticks[d]
        g = np.arange(0, 23400)
        u = mid[np.clip(np.searchsorted(ts, g, side="right") - 1, 0, None)]
        T, px = Q[d]["T"], Q[d]["px"]
        b = px[np.clip(np.searchsorted(T, off_ms(d) + g * 1000, side="right") - 1, 0, None)]
        ru, rb = np.diff(np.log(u)), np.diff(np.log(b))
        for k in lags:                                   # k > 0: Binance at t vs Exness at t + k (Binance leads)
            a, c = (rb[:len(rb) - k], ru[k:]) if k >= 0 else (rb[-k:], ru[:len(ru) + k])
            xs[k].append(np.corrcoef(a, c)[0, 1])
    cc = {k: np.nanmean(v) for k, v in xs.items()}
    best = max(cc, key=cc.get)
    print("1. LEAD/LAG - corr(Binance QQQ 1-s return at t, USTECm 1-s return at t+k), mean over", len(days), "days")
    print("   " + "  ".join(f"{k:+d}:{cc[k]:.3f}" for k in range(-5, 8)))
    print(f"   peak at k = {best:+d} s ({cc[best]:.3f});  k > 0 means Binance moves FIRST")

    # sample moments: every day, 10:00-16:00 ET, 150 random seconds x both directions
    rng = np.random.default_rng(16)
    rows = []
    for d in days:
        ts, mid, spr = ticks[d]
        o0 = off_ms(d)
        for t in rng.uniform(1800, 23400, 150):
            tm = o0 + int(t * 1000)
            k = np.searchsorted(ts, t, side="right") - 1
            k10 = np.searchsorted(ts, t - 10, side="right") - 1
            if k10 < 0:
                continue
            for s in (1, -1):
                o, on = race(ts, mid, t, s), race_net(ts, mid, spr, t, s)
                if o is None:
                    continue
                f = feats(Q[d], tm, s) | extra(Q[d], tm, s)
                f["turn"] = f["imb_10"] - f["imb_30"]
                rows.append(f | {"o": o, "on": on, "day": d, "u10": s * (mid[k] - mid[k10])})
    B = pd.DataFrame(rows)
    mid_day = days[len(days) // 2]
    h1, h2 = B.day < mid_day, B.day >= mid_day
    w = lambda g, c="o": g[c].dropna().mean() * 100 if len(g) else np.nan  # noqa: E731

    print(f"\n2. PRICE CONTROL - {len(B)} pairs; mid race, imb_10 top vs bottom third INSIDE terciles of USTECm's own 10-s move")
    q = B.dropna(subset=["imb_10"])
    lo, hi = q.imb_10.quantile(1 / 3), q.imb_10.quantile(2 / 3)
    print(f"   overall: imb_10 {w(q[q.imb_10 >= hi]) - w(q[q.imb_10 <= lo]):+.1f};  USTECm's own 10-s move top vs bottom third "
          f"{w(q[q.u10 >= q.u10.quantile(2/3)]) - w(q[q.u10 <= q.u10.quantile(1/3)]):+.1f}")
    for lab, m in zip(("against", "flat", "his way"), pd.qcut(q.u10.rank(method="first"), 3, labels=False).pipe(lambda z: [z == i for i in range(3)])):
        g = q[m]
        a, b = w(g[g.imb_10 >= hi]), w(g[g.imb_10 <= lo])
        a1 = w(g[(g.imb_10 >= hi) & h1]) - w(g[(g.imb_10 <= lo) & h1])
        a2 = w(g[(g.imb_10 >= hi) & h2]) - w(g[(g.imb_10 <= lo) & h2])
        print(f"   USTECm 10-s move {lab:<8} n {len(g):>5}: imb_10 high {a:5.1f}%  low {b:5.1f}%  diff {a - b:+5.1f}  "
              f"(halves {a1:+.1f} / {a2:+.1f})")

    print("\n3. THE SPREAD - net race win % (enter at the quote, +7/-7 on the exit side, 180 s) by imb_10 decile; break-even 50%")
    q = B.dropna(subset=["imb_10", "on"]).copy()
    q["dec"] = pd.qcut(q.imb_10.rank(method="first"), 10, labels=False)
    print(f"   all moments {w(q, 'on'):.1f}%  ({len(q)})")
    print("   decile  " + "".join(f"{i:>7}" for i in range(10)))
    for lab, m in (("all", q.day.notna()), ("1st half", q.day < mid_day), ("2nd half", q.day >= mid_day)):
        print(f"   {lab:<8}" + "".join(f"{w(q[m & (q.dec == i)], 'on'):>7.1f}" for i in range(10)))
    print("   decile imb_10 lower edge: " + " ".join(f"{q[q.dec == i].imb_10.min():+.2f}" for i in range(10)))

    # 4. the pause: his entries on turn and stop5
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-07"]
    rr = []
    for r in x.itertuples():
        d = r.utc.normalize()
        if Q.get(d) is None:
            continue
        s = 1 if r.side == "BUY" else -1
        tm = int(r.utc.value // 10**6)
        def ff(t):
            f = feats(Q[d], t, s) | extra(Q[d], t, s)
            f["turn"] = f["imb_10"] - f["imb_30"]
            return f
        mine = ff(tm)
        N = pd.DataFrame([ff(tm + int(rng.uniform(30, 1200) * 1000) * rng.choice((-1, 1))) for _ in range(80)])
        rr.append({k: rank(mine[k], N[k].to_numpy()) for k in ("turn", "stop5")} | {"stop5_raw": mine["stop5"]})
    R = pd.DataFrame(rr)
    print(f"\n4. THE PAUSE - his {len(R)} clean entries ranked among same-day moments +-20 min (0.50 = ordinary)")
    for k in ("turn", "stop5"):
        v = R[k].to_numpy()
        g = B.dropna(subset=[k])
        lo, hi = g[k].quantile(1 / 3), g[k].quantile(2 / 3)
        print(f"   {k:<6} his rank {np.nanmean(v):.2f}  p {pval(v):.3f}   |  B: mid race high third {w(g[g[k] >= hi]):.1f}%  "
              f"low third {w(g[g[k] <= lo]):.1f}%  diff {w(g[g[k] >= hi]) - w(g[g[k] <= lo]):+.1f}")
    print(f"   his stop5 raw median {R.stop5_raw.median():.2f} (share of the last 30 s's notional traded in the last 5 s)")


if __name__ == "__main__":
    main()
