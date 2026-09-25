"""REAL ORDER FLOW AT HIS MOMENTS - Binance QQQUSDT aggressor-tagged trades (downloaded archives, user-approved).

The last ~30 of his ~33 points of 3-minute edge (his_strategy.md s26) are not in NASDAQ's price, pace, other
markets or news; the Exness feed has no book. Binance's QQQ perp (a Nasdaq-100 ETF perp, listed 2026-04-06)
tags every trade's aggressor. data.binance.vision daily aggTrades for his 10 clean trading days since
2026-04-28 and 14 comparison days (19 MB, downloaded 2026-09-26 with the user's approval) are in
strategy_analysis/data/binance_qqq/ (not committed). Binance traders' flow, not the CME's: a partial view.

FEATURES at a moment t for direction s (+ = s's way), from QQQ trades before t unless stated:
  imb_10/30/60/300   (aggressive buy - aggressive sell notional) / total, sign-aligned
  act_30             notional in the last 30 s / (30 x the per-second average of the prior 30 min)
  big_60             the largest single aggregated trade in the last 60 s / that day's 99th percentile
  mv_30              QQQ's own 30-s move, sign-aligned, in basis points
  absorb_30          -imb_30 minus the QQQ price's own sign-aligned 30-s move scaled to z: high = sellers
                     (for a buy) hit hard while the price barely fell - "absorption"
  after_60           imbalance in the 60 s AFTER t (does flow arrive his way right after he enters?)
A1: his moment ranked among the same day's moments within +-20 min, same direction (0.50 = ordinary).
A2: ranked against the same clock second on the 14 comparison days.
B:  on all 24 days, 40 random seconds a day x both directions, does each feature (top vs bottom third)
    predict the 3-minute NASDAQ mid race to +7/-7 (USTECm ticks)? Both halves of the days.

REGISTERED PREDICTION (2026-09-26, before running): at his moments the aggressive selling against him is
LOW for the dip that is happening - absorb_30 and imb_30 rank >= 0.6 in A1 - the dip is buyers pausing,
not sellers pushing. Weak: p ~0.05, nothing surviving Holm over 10; in B order flow predicts the next 3
minutes by +2 to +4 points at most.

RESULT - READ BEFORE TRUSTING PART B (his_strategy.md s27): B prints imb_10 +11.7 (+14.6 / +8.8) and imb_30
+8.2. That is ONE lucky sample of moments. 40 fresh samples of the same 24 days give imb_10 +0.8 (sd 3.8,
max +7.3), 150 moments a day give +0.5, and inside USTECm's own 10-s move the imbalance adds ~0
(his_orderflow_check.py). Binance's perp follows the NASDAQ price by up to a second; its flow is an echo.

    python -m backtest.his_orderflow_archive
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

ROOT = Path(__file__).resolve().parents[1]
QDIR = ROOT / "strategy_analysis" / "data" / "binance_qqq"
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0
FEATS = ("imb_10", "imb_30", "imb_60", "imb_300", "act_30", "big_60", "mv_30", "absorb_30", "after_60")


def load_day(d):
    f = QDIR / f"QQQUSDT-aggTrades-{d:%Y-%m-%d}.csv"
    if not f.exists():
        return None
    x = pd.read_csv(f)
    T = x.transact_time.to_numpy(np.int64)
    n = (x.price * x.quantity).to_numpy(float)
    sgn = np.where(x.is_buyer_maker.astype(str).str.lower() == "true", -1.0, 1.0)
    return dict(T=T, n=n, sn=sgn * n, px=x.price.to_numpy(float), p99=np.percentile(n, 99))


def feats(q, tm, s):
    """tm: UTC epoch ms."""
    T = q["T"]
    def win(a, b):
        return np.searchsorted(T, a), np.searchsorted(T, b)
    f = {}
    for w in (10, 30, 60, 300):
        i0, i1 = win(tm - w * 1000, tm)
        tot = q["n"][i0:i1].sum()
        f[f"imb_{w}"] = s * q["sn"][i0:i1].sum() / tot if tot > 0 else np.nan
    i0, i1 = win(tm - 30000, tm)
    j0, j1 = win(tm - 1830000, tm - 30000)
    base = q["n"][j0:j1].sum() / 1800.0
    f["act_30"] = (q["n"][i0:i1].sum() / 30.0) / base if base > 0 else np.nan
    k0, k1 = win(tm - 60000, tm)
    f["big_60"] = q["n"][k0:k1].max() / q["p99"] if k1 > k0 else 0.0
    if i1 - i0 >= 2 and i0 > 0:
        mv = s * (q["px"][i1 - 1] / q["px"][i0 - 1] - 1) * 1e4
    else:
        mv = np.nan
    f["mv_30"] = mv
    f["absorb_30"] = (-f["imb_30"] - (-mv) / 3.0) if np.isfinite(mv) and np.isfinite(f["imb_30"]) else np.nan
    a0, a1 = win(tm, tm + 60000)
    tot = q["n"][a0:a1].sum()
    f["after_60"] = s * q["sn"][a0:a1].sum() / tot if tot > 0 else np.nan
    return f


def rank(v, arr):
    arr = arr[np.isfinite(arr)]
    return np.nan if (not len(arr) or not np.isfinite(v)) else (arr < v).mean() + 0.5 * (arr == v).mean()


def pval(v):
    v = v[np.isfinite(v)]
    z = (v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def main():
    days = sorted(pd.Timestamp(f.stem.split("-aggTrades-")[1]) for f in QDIR.glob("*.csv"))
    Q = {d: load_day(d) for d in days}
    ticks = pickle.loads(TICKS.read_bytes())
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-07"]
    trade_days = {u.normalize() for u in x.utc}
    ctrl_days = [d for d in days if d not in trade_days]
    rng = np.random.default_rng(15)
    A1, A2 = [], []
    for r in x.itertuples():
        d = r.utc.normalize()
        q = Q.get(d)
        if q is None:
            continue
        s = 1 if r.side == "BUY" else -1
        tm = int(r.utc.value // 10**6)
        mine = feats(q, tm, s)
        near = [feats(q, tm + int(rng.uniform(30, 1200) * 1000) * rng.choice((-1, 1)), s) for _ in range(80)]
        N = pd.DataFrame(near)
        A1.append({k: rank(mine[k], N[k].to_numpy()) for k in FEATS})
        C = []
        for cd in ctrl_days:
            ct = int((cd + (r.utc - d)).value // 10**6)
            C.append(feats(Q[cd], ct, s))
        C = pd.DataFrame(C)
        A2.append({k: rank(mine[k], C[k].to_numpy()) for k in FEATS} | {f"raw_{k}": mine[k] for k in FEATS})
    R1, R2 = pd.DataFrame(A1), pd.DataFrame(A2)
    print(f"{len(R1)} clean entries on {len(trade_days)} trade days with QQQ trades; {len(ctrl_days)} comparison days.\n")
    ps1 = {k: pval(R1[k].to_numpy()) for k in FEATS}
    order = sorted(ps1, key=ps1.get)
    holm = {k: min(1.0, max(ps1[j] * (len(ps1) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in ps1}
    print(f"  {'feature':<10}{'A1 rank':>8}{'p':>7}{'Holm':>7}{'A2 rank':>9}{'p':>7}   his raw median")
    for k in FEATS:
        print(f"  {k:<10}{np.nanmean(R1[k]):>8.2f}{ps1[k]:>7.3f}{holm[k]:>7.3f}{np.nanmean(R2[k]):>9.2f}{pval(R2[k].to_numpy()):>7.3f}"
              f"   {np.nanmedian(R2['raw_' + k]):+.3f}")

    # B: do the features predict the 3-minute NASDAQ race on these 24 days?
    rows = []
    for d in days:
        if d not in ticks or ticks[d] is None:
            continue
        ts, mid, _ = ticks[d]
        et0 = d + pd.Timedelta(hours=9, minutes=30)
        off = pd.Timestamp(et0).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        for t in rng.uniform(1800, 23400, 60):
            tm = int((off + pd.Timedelta(seconds=float(t))).value // 10**6)
            for s in (1, -1):
                o = race(ts, mid, t, s)
                if o is None:
                    continue
                rows.append(feats(Q[d], tm, s) | {"o": o, "day": d})
    B = pd.DataFrame(rows)
    mid_day = days[len(days) // 2]
    print(f"\nB - {len(B)} moment x direction pairs on {B.day.nunique()} days: 3-min NASDAQ mid race by feature third "
          f"(base {B.o.mean()*100:.1f}%)")
    print(f"  {'feature':<10}{'low 1/3':>9}{'high 1/3':>10}{'diff':>7}{'1st half':>10}{'2nd half':>10}")
    for k in FEATS:
        q = B.dropna(subset=[k])
        lo, hi = q[k].quantile(1 / 3), q[k].quantile(2 / 3)
        w = lambda g: g.o.mean() * 100 if len(g) else np.nan  # noqa: E731
        d1 = w(q[(q[k] >= hi) & (q.day < mid_day)]) - w(q[(q[k] <= lo) & (q.day < mid_day)])
        d2 = w(q[(q[k] >= hi) & (q.day >= mid_day)]) - w(q[(q[k] <= lo) & (q.day >= mid_day)])
        print(f"  {k:<10}{w(q[q[k] <= lo]):>8.1f}%{w(q[q[k] >= hi]):>9.1f}%{w(q[q[k] >= hi]) - w(q[q[k] <= lo]):>+7.1f}"
              f"{d1:>+10.1f}{d2:>+10.1f}")
    R2.to_csv(ROOT / "logs" / "his_orderflow_archive.csv", index=False)


if __name__ == "__main__":
    main()
