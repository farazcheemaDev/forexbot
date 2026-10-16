"""THE A+ SETUP SEARCH - does NASDAQ's own chart ever give a 90% call, at his rarity? 16 years of minute bars (2026-10-13)

WHY      The user: he trades alone, from his own chart, and says ~10% a month "is safer". The statement agrees: he trades
         to a ~10% monthly target and stops (April 7 trades -> +11.9% then nothing; June 3 trades in ONE day -> +11.1%), at
         60-180x notional with no stop. Needing 3-5 wins a month, he can wait for the clearest setups: ~5 NASDAQ trades in
         ~11,000 session minutes a month (~0.05%). Every earlier test compared him with the rest of his sitting, or looked
         for rules that fire often. If his edge is a chart read, it is a RARE setup - and 16 years of minute bars hold
         thousands of them. A model trained on the chart at every minute, judged only on its rarest, most confident calls,
         is the direct search for it.

DATA     HistData NSXUSD 1-minute bars (strategy_analysis/data/histdata/NSXUSD.parquet, 2010-11 .. 2026-09, New York clock
         with DST, histdata_1m.parse). Moments: every minute close 08:00-16:45 New York, weekdays (features built 05:00-16:45 for his entries).
TARGET   the race from the NEXT bar's open to +-0.024% of price (= +-7 points at 29,000; his target), resolved on the next
         15 one-minute bars; both barriers inside one bar = ambiguous (dropped from training, counted as a LOSS when scored).
FEATURES (chart only, at the bar close): moves over 1-240 minutes in units of recent volatility; position in the last
         15 / 30 / 60 / 240 minutes' range; distance to today's 09:30 open, today's high / low so far, the overnight high /
         low, yesterday's cash-session high / low / close; distance to the nearest 25 / 50 / 100-point level; the last bar's
         and the last 5 / 15 minutes' candle shape (body, wicks, range); volatility now vs the day; hour, minute, weekday.
MODEL    gradient-boosted trees, fit 2010-11 .. 2022-12; 2023-24 reported, never used to choose; TEST 2025-01 .. 2026-09.
         Calls ranked by confidence |p - 0.5|; each bucket trades the model's side.

REGISTERED BEFORE THE RUN (2026-10-13)
    1. TEST AUC <= 0.54.
    2. His rarity (top 0.05% most confident) wins <= 62% of races; no bucket from the top 10% to the top 0.01% reaches 70%.
    3. At his 2026 entries (the bar before his click): the model's confidence is not unusually high (median percentile
       <= 70) and its side agrees with his <= 60%.
    LEAD LINE: a bucket at >= 75% on the TEST years with >= 30 calls -> an A+ chart setup exists; then it goes to Exness
    ticks with the real spread.

RESULT (2026-10-13, logs/ndx_aplus.txt) - NO A+ CHART SETUP. All three predictions right; lead line not hit.
    1,366,143 training moments (2010-11..2022), TEST 216,315 (2025-01..2026-09). TEST AUC 0.506 (validation 0.510).
    The most confident calls, at his rarity: top 0.1% / 0.05% / 0.01% won 45.4 / 47.2 / 42.9% counting a both-barriers
    minute as a loss, 56.6 / 60.0 / 52.9% leaving those out; with an ambiguous minute as a coin flip, ~55-58% on TEST
    (~60% on 2023-24) - before a spread worth ~1-2 points of a 7-point race. His 45 entries: the model's confidence sits
    at a median 51st percentile (7% of them in its top 1%), and its side agrees with his 40%.
    Even searched at his rarity, over 16 years, NASDAQ's own chart offers no setup near his 88-95%.

    python -m backtest.ndx_aplus
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "ndx_aplus.txt"
B = 0.00024
HZ = 15


def load():
    d = pd.read_parquet(ROOT / "strategy_analysis" / "data" / "histdata" / "NSXUSD.parquet").sort_values("t", kind="stable")
    d = d.drop_duplicates("t").reset_index(drop=True)
    ny = pd.to_datetime(d.t, unit="ms", utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    d["ny"] = ny
    return d


def race(o, h, l):
    """from each bar i: enter at o[i+1]; +-B*price over bars i+1..i+HZ. 1 up, 0 down, nan unresolved / ambiguous."""
    n = len(o)
    e = np.r_[o[1:], np.nan]
    up_b, dn_b = e * (1 + B), e * (1 - B)
    res = np.full(n, np.nan)
    done = np.zeros(n, bool)
    for k in range(1, HZ + 1):
        hk = np.r_[h[k:], np.full(k, np.nan)]
        lk = np.r_[l[k:], np.full(k, np.nan)]
        u, dn = hk >= up_b, lk <= dn_b
        both = u & dn & ~done
        res[both] = -1                                   # ambiguous
        res[u & ~dn & ~done] = 1
        res[dn & ~u & ~done] = 0
        done |= (u | dn)
    return res


def features(d, mask):
    """chart features at each bar close, returned only for the rows in `mask` (float32). All causal: day levels are
    running values, the 09:30 open and yesterday's levels only once they exist."""
    o, h, l, c = (d[k].to_numpy() for k in "ohlc")
    lc = np.log(c)
    r1 = np.r_[0, np.diff(lc)]
    gap = np.r_[0, np.diff(d.t.to_numpy())] > 5 * 60_000                 # a break in the data
    r1[gap] = 0
    s = pd.Series(r1)
    vol30 = s.rolling(30, min_periods=10).std().to_numpy() + 1e-6
    vol240 = s.rolling(240, min_periods=60).std().to_numpy() + 1e-6
    F = {}

    def put(name, arr):
        F[name] = np.asarray(arr, dtype=np.float64)[mask].astype(np.float32)
    cs, hs, ls, os_ = pd.Series(c), pd.Series(h), pd.Series(l), pd.Series(o)
    for k in (1, 2, 3, 5, 10, 15, 30, 60, 120, 240):
        put(f"r{k}", (lc - np.log(cs.shift(k).to_numpy())) / (vol240 * np.sqrt(k)))
    for k in (15, 30, 60, 240):
        hi = hs.rolling(k, min_periods=2).max().to_numpy()
        lo = ls.rolling(k, min_periods=2).min().to_numpy()
        put(f"pos{k}", (c - lo) / np.maximum(hi - lo, 1e-9))
        put(f"rng{k}", (hi - lo) / c / (vol240 * np.sqrt(k)))
    put("volratio", vol30 / vol240)
    for k in (1, 5, 15):                                              # last bar, last 5, last 15 minutes as candles
        ok = np.log(os_.shift(k - 1).to_numpy()) if k > 1 else np.log(o)
        hk = hs.rolling(k, min_periods=1).max().to_numpy()
        lk = ls.rolling(k, min_periods=1).min().to_numpy()
        rg = np.maximum(np.log(hk) - np.log(lk), 1e-9)
        put(f"body{k}", (lc - ok) / rg)
        put(f"uw{k}", (np.log(hk) - np.maximum(lc, ok)) / rg)
        put(f"lw{k}", (np.minimum(lc, ok) - np.log(lk)) / rg)
        put(f"rg{k}", rg / (vol240 * np.sqrt(k)))
    ny = d.ny
    sd = (ny + pd.Timedelta(hours=6)).dt.normalize()                  # session date rolls at 18:00 New York
    tod = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
    cash = (tod >= 570) & (tod < 960)
    is_on = (tod < 570) | (tod >= 1080)
    g = pd.DataFrame({"sd": sd, "h": h, "l": l,
                      "onh": np.where(is_on, h, -np.inf), "onl": np.where(is_on, l, np.inf)})
    day_hi = g.groupby("sd").h.cummax().to_numpy()
    day_lo = g.groupby("sd").l.cummin().to_numpy()
    onh = g.groupby("sd").onh.cummax().to_numpy()                     # running overnight high / low
    onl = g.groupby("sd").onl.cummin().to_numpy()
    cs_day = pd.DataFrame({"sd": sd, "h": h, "l": l, "c": c})[cash].groupby("sd").agg(ch=("h", "max"), cl=("l", "min"),
                                                                                   cc=("c", "last"))
    prev = cs_day.shift(1)
    op = pd.DataFrame({"sd": sd, "o": o})[tod == 570].groupby("sd").o.first()
    m = pd.DataFrame({"sd": sd}).join(prev, on="sd").join(op.rename("op"), on="sd")
    dop = np.where(tod >= 570, m.op.to_numpy(), np.nan)                # today's open only after 09:30
    scale = c * vol240 * np.sqrt(30)
    for name, lv in (("dhi", day_hi), ("dlo", day_lo), ("onh", np.where(np.isfinite(onh), onh, np.nan)),
                     ("onl", np.where(np.isfinite(onl), onl, np.nan)), ("pdh", m.ch.to_numpy()), ("pdl", m.cl.to_numpy()),
                     ("pdc", m.cc.to_numpy()), ("dop", dop)):
        put(f"x_{name}", (c - lv) / scale)
    for rn in (25, 50, 100):
        put(f"rn{rn}", (c - np.round(c / rn) * rn) / scale)
    put("hour", ny.dt.hour.to_numpy())
    put("minute", ny.dt.minute.to_numpy())
    put("dow", ny.dt.dayofweek.to_numpy())
    F = pd.DataFrame(F)
    F.replace([np.inf, -np.inf], np.nan, inplace=True)
    return F


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    d = load()
    ny = d.ny
    tod_all = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
    base = (tod_all >= 300) & (tod_all < 1005) & (ny.dt.dayofweek < 5).to_numpy()   # 05:00-16:45, his hours
    y_all = race(*(d[k].to_numpy() for k in "ohl"))
    F = features(d, base)
    rows = np.flatnonzero(base)                                       # full index of each feature row
    y, nyb, tod = y_all[base], ny[base].reset_index(drop=True), tod_all[base]
    keep = (tod >= 480) & ~np.isnan(y)                                # moments 08:00-16:45
    tr = keep & (nyb < "2023-01-01").to_numpy() & (y >= 0)
    va = keep & (nyb >= "2023-01-01").to_numpy() & (nyb < "2025-01-01").to_numpy()
    te = keep & (nyb >= "2025-01-01").to_numpy()
    feats = list(F.columns)
    mdl = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=300,
                                         l2_regularization=1.0, random_state=0)
    mdl.fit(F.loc[tr, feats], y[tr])
    out = [f"backtest/ndx_aplus.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; NSXUSD 1m {ny.min():%Y-%m} .. {ny.max():%Y-%m}; "
           f"race +-{B * 100:.3f}% from the next open within {HZ} min; moments 08:00-16:45 NY",
           f"train {tr.sum():,} moments (2010-11..2022), validation {va.sum():,} (2023-24), TEST {te.sum():,} (2025-01..2026-09)", ""]
    res = {}
    for name, msk in (("validation 2023-24", va), ("TEST 2025-26", te)):
        p = mdl.predict_proba(F.loc[msk, feats])[:, 1]
        yy = y[msk]
        clean = yy >= 0
        auc = roc_auc_score(yy[clean], p[clean])
        conf = np.abs(p - 0.5)
        out.append(f"{name}: AUC {auc:.3f} on unambiguous races; up share {np.mean(yy[clean]):.3f}; ambiguous {np.mean(~clean) * 100:.1f}%")
        out.append(f"   {'bucket':>12}{'calls':>9}{'won':>8}{'won excl. ambiguous':>22}   (the model's side; ambiguous counted as a loss)")
        order = np.argsort(-conf)
        for q in (0.10, 0.01, 0.001, 0.0005, 0.0001):
            k = max(int(len(p) * q), 1)
            idx = order[:k]
            side = p[idx] > 0.5
            win = np.where(yy[idx] < 0, 0, (yy[idx] == 1) == side)
            cl = yy[idx] >= 0
            wx = np.mean(((yy[idx] == 1) == side)[cl]) if cl.any() else np.nan
            out.append(f"   {'top ' + f'{q * 100:g}%':>12}{k:>9,}{np.mean(win) * 100:>7.1f}%{wx * 100:>21.1f}%")
            if name.startswith("TEST"):
                res[q] = (k, np.mean(win))
        res[name] = auc
        out.append("")
    # HIS 2026 entries: the bar before his click
    import backtest.his_tape as TP
    x = TP.entries()
    tmin = (d.t.to_numpy() // 60_000)
    pt = mdl.predict_proba(F.loc[te, feats])[:, 1]
    conf_te = np.sort(np.abs(pt - 0.5))
    pct, agree = [], []
    for r in x.itertuples():
        um = int(pd.Timestamp(r.utc).value // 60_000_000_000) - 1                   # the last completed minute
        j = np.searchsorted(tmin, um)
        if j >= len(tmin) or tmin[j] != um:
            continue
        jj = np.searchsorted(rows, j)
        if jj >= len(rows) or rows[jj] != j:                          # outside 05:00-16:45 New York
            continue
        p1 = mdl.predict_proba(F.iloc[[jj]][feats])[:, 1][0]
        pct.append(np.searchsorted(conf_te, abs(p1 - 0.5)) / len(conf_te))
        agree.append((p1 > 0.5) == (r.s > 0))
    out.append(f"HIS {len(pct)} NASDAQ entries (2026, on the bar before his click): model confidence percentile median "
               f"{np.median(pct) * 100:.0f} (top 1%: {np.mean(np.array(pct) >= 0.99) * 100:.0f}% of his entries); model side "
               f"agrees with his {np.mean(agree) * 100:.0f}%")
    out.append("")
    top_rare = res[0.0005][1]
    out.append("REGISTERED PREDICTIONS")
    out.append(f"  1 TEST AUC {res['TEST 2025-26']:.3f} <= 0.54 -> {'RIGHT' if res['TEST 2025-26'] <= 0.54 else 'WRONG'}")
    out.append(f"  2 his rarity (top 0.05%) {top_rare * 100:.1f}% <= 62% and no bucket >= 70%: "
               + ", ".join(f"{q * 100:g}% {v[1] * 100:.1f}" for q, v in res.items() if isinstance(q, float))
               + f" -> {'RIGHT' if top_rare <= 0.62 and all(v[1] < 0.70 for q, v in res.items() if isinstance(q, float)) else 'WRONG'}")
    out.append(f"  3 his confidence percentile {np.median(pct) * 100:.0f} <= 70 and agreement {np.mean(agree) * 100:.0f}% <= 60% -> "
               f"{'RIGHT' if np.median(pct) <= 0.70 and np.mean(agree) <= 0.60 else 'WRONG'}")
    lead = [q for q, v in res.items() if isinstance(q, float) and v[0] >= 30 and v[1] >= 0.75]
    out.append(f"  LEAD LINE (>= 75% with >= 30 calls on TEST): {', '.join(f'top {q * 100:g}%' for q in lead) if lead else 'not hit'}")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
