"""REAL ORDER FLOW AROUND HIS PAUSES: aggressive buying vs selling on Binance's QQQ perp.

SUPERSEDED - this API version never ran: Binance's aggTrades API answers 400 for history. The test was run
from the downloaded daily archives instead: his_orderflow_archive.py and his_orderflow_check.py
(his_strategy.md s27).

The Exness NASDAQ feed has no book (his_microstructure.py: fixed 1.12-point spread, bid and ask move
together). Binance lists QQQUSDT (a Nasdaq-100 ETF perp) from 2026-04-06, and its public aggTrades
mark every trade's AGGRESSOR (isBuyerMaker true = a seller hit the bid). That is real buying/selling
pressure to the millisecond - Binance traders' pressure, not the CME's, so a proxy, but the only free
one. For each of his clean entries from 2026-04-06 on:
  imb_W = (aggressive buy volume - aggressive sell volume) / total, over the last W seconds (10/30/60/300),
          SIGN-ALIGNED (+ = pressure in his direction), and the same over the 60 s AFTER entry;
  n_W   = number of aggregated trades in the window (activity).
Each ranked against the same clock second on 20 other days (0.50 = ordinary).

REGISTERED PREDICTION (2026-09-26, before running): during his 30-s dip the aggressive flow is NOT
against him (imb_30 rank >= 0.5 while the price dipped): the dip is buyers stepping back, not sellers
pushing - the classic "absorption" a book reader buys. Weak: p ~ 0.1, nothing surviving Holm over 8.

    python -m backtest.his_orderflow
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GMT = 5.0
URL = "https://fapi.binance.com/fapi/v1/aggTrades?symbol=QQQUSDT&startTime={}&endTime={}&limit=1000"


def trades(t0, t1):
    """All aggTrades in [t0, t1) (UTC Timestamps), paging within the window."""
    out, a = [], int(t0.value // 10**6)
    b = int(t1.value // 10**6)
    while a < b:
        for k in range(4):
            try:
                d = json.load(urllib.request.urlopen(URL.format(a, b), timeout=20)); break
            except Exception:
                time.sleep(1 + k); d = None
        if not d:
            break
        out += d
        if len(d) < 1000:
            break
        a = d[-1]["T"] + 1
        time.sleep(0.05)
    if not out:
        return None
    x = pd.DataFrame(out)
    return pd.DataFrame({"T": x["T"].astype("int64"), "q": x["q"].astype(float) * x["p"].astype(float),
                         "sell": x["m"].astype(bool)})


def feats(tr, t, s):
    tm = int(t.value // 10**6)
    f = {}
    for w in (10, 30, 60, 300):
        g = tr[(tr["T"] >= tm - w * 1000) & (tr["T"] < tm)]
        tot = g.q.sum()
        f[f"imb_{w}"] = s * (g.q[~g.sell].sum() - g.q[g.sell].sum()) / tot if tot > 0 else np.nan
        f[f"n_{w}"] = len(g)
    g = tr[(tr["T"] >= tm) & (tr["T"] < tm + 60000)]
    tot = g.q.sum()
    f["imb_after60"] = s * (g.q[~g.sell].sum() - g.q[g.sell].sum()) / tot if tot > 0 else np.nan
    return f


def main():
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-07"]
    rng = np.random.default_rng(5)
    rows = []
    for r in x.itertuples():
        s = 1 if r.side == "BUY" else -1
        tr = trades(r.utc - pd.Timedelta(seconds=310), r.utc + pd.Timedelta(seconds=65))
        if tr is None or len(tr) < 5:
            continue
        mine = feats(tr, r.utc, s)
        C = []
        for k in rng.permutation(np.r_[np.arange(-45, 0), np.arange(1, 46)]):
            ct = r.utc + pd.Timedelta(days=int(k))
            if ct.weekday() >= 5 or ct < pd.Timestamp("2026-04-07") or ct > pd.Timestamp("2026-09-24"):
                continue
            ctr = trades(ct - pd.Timedelta(seconds=310), ct + pd.Timedelta(seconds=65))
            if ctr is not None and len(ctr) >= 5:
                C.append(feats(ctr, ct, s))
            if len(C) >= 20:
                break
        C = pd.DataFrame(C)
        rows.append({k: (C[k].dropna() < v).mean() + 0.5 * (C[k].dropna() == v).mean() for k, v in mine.items()
                     if not np.isnan(v)} | {f"raw_{k}": v for k, v in mine.items()})
    R = pd.DataFrame(rows)
    print(f"{len(R)} clean entries with QQQUSDT trades (from 2026-04-07); each ranked against the same clock second on "
          f"~20 other days. imb = aggressive buy minus sell volume, SIGN-ALIGNED (+ = pressure his way); 0.50 = ordinary.\n")
    ps = {}
    for k in ("imb_10", "imb_30", "imb_60", "imb_300", "n_30", "n_60", "n_300", "imb_after60"):
        v = R[k].dropna()
        z = (v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))
        ps[k] = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
        raw = R[f"raw_{k}"].dropna()
        print(f"  {k:<12} mean rank {v.mean():.2f}  (top third {np.mean(v > 2/3)*100:3.0f}%)  p {ps[k]:.3f}   "
              f"raw median {raw.median():+.3f}")
    order = sorted(ps, key=ps.get)
    print("  Holm: " + ", ".join(f"{k} {min(1.0, max(ps[j] * (len(ps) - i) for i, j in enumerate(order[:order.index(k) + 1]))):.3f}"
                               for k in order))
    R.to_csv(ROOT / "logs" / "his_orderflow_ranks.csv", index=False)


if __name__ == "__main__":
    main()
