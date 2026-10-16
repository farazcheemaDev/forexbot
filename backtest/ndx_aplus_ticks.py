"""THE A+ SEARCH AT TICK LEVEL - a "tick rhythm" setup, judged only on the rarest, most confident calls (2026-10-13)

WHY      A pasted write-up: a solo discretionary trader reads tick velocity / deceleration / absorption on the pullback by
         eye, and takes only the clearest ~5 a month. ndx_aplus.py searched for rare setups on 1-MINUTE bars (16 years:
         top 0.05% ~55-58%); ustec_burst_anatomy.py read tick features but judged direction over all bursts (AUC 0.513),
         never on the model's rarest calls. This closes that gap.

DATA     Exness USTECm ticks (strategy_analysis/data/ustec_tick_days.pkl, 181 days 2026-01..09-14, 09:30-19:30 New
         York), a 1-second grid; every 5th second is a moment. Features: ustec_burst_anatomy.day_frame's tick set (quote
         rate 5/30/300 s and ratios, absolute movement 5/30/300 s and ratios = velocity and deceleration, ranges, signed
         moves 1-300 s, up-minus-down seconds, spread, clock, the day's movement, time since the last burst) + position
         in the last 60 s / 15 min range and distance to that range's high / low (the level behind the pullback).
TARGET   +7 before -7 on the mid from that second, within 10 minutes (unresolved dropped).
MODEL    gradient-boosted trees, fit on the first 60% of days, judged on the last 40% only by the most confident calls
         (top 1% / 0.1% / 0.05% / 0.01%), on the mid and at the real spread. His 42 entries scored by the same model.

REGISTERED BEFORE THE RUN (2026-10-13)
    1. holdout AUC <= 0.55.
    2. top 0.05% / 0.01% win <= 65% on the mid; no bucket >= 75% with >= 30 calls; net of spread <= 0 in every bucket.
    3. his entries: confidence median percentile <= 75; side agreement <= 60%.
    LEAD LINE: a bucket >= 75% on the mid with >= 30 calls AND positive net of spread -> a tick-rhythm setup exists.

RESULT (2026-10-13, logs/ndx_aplus_ticks.txt, logs/ndx_aplus_ticks_check.txt) - NO TICK-RHYTHM SETUP. Lead line not hit.
    Holdout AUC 0.505. Top 1% / 0.1% / 0.05% / 0.01%: 58.1 / 69.9 / 55.1 / 46.2% won, net -0.02 / +2.79 / +0.71 / -0.54
    points at the spread. The top 0.1% (396 calls) is 7 EPISODES on 6 days (moments 5 s apart within one move; two on
    2026-09-07, US Labor Day), 6 of 7 won - p ~0.06 for 7 coin flips, and the stricter cuts fall back to 55% / 46%.
    Prediction 2 reads WRONG only on that clustered bucket. His 42 entries: confidence median 27th percentile (none in
    the top 1%), side agreement 57%.

    python -m backtest.ndx_aplus_ticks
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.ustec_burst_anatomy import day_frame, FEATS as BASE  # noqa: E402

LOG = ROOT / "logs" / "ndx_aplus_ticks.txt"
X, CAP, STEP = 7.0, 600, 5
FEATS = BASE + ["pos60", "pos900", "dhi900", "dlo900"]


def extra(F, gm):
    s = pd.Series(gm)
    for w in (60, 900):
        hi = s.rolling(w, min_periods=2).max().to_numpy()
        lo = s.rolling(w, min_periods=2).min().to_numpy()
        F[f"pos{w}"] = (gm - lo) / np.maximum(hi - lo, 1e-9)
        if w == 900:
            F["dhi900"], F["dlo900"] = hi - gm, gm - lo
    return F


def races(gm, gsp, idx):
    """mid race (1 up / 0 down / nan) and the spread-inclusive points for the up and down side, from each index."""
    up_mid, pts_up, pts_dn = np.full(len(idx), np.nan), np.full(len(idx), np.nan), np.full(len(idx), np.nan)
    n = len(gm)
    for k, i in enumerate(idx):
        j = min(i + CAP, n)
        p = gm[i + 1:j] - gm[i]
        u, d = np.flatnonzero(p >= X), np.flatnonzero(p <= -X)
        if len(u) or len(d):
            up_mid[k] = 1.0 if (len(u) and (not len(d) or u[0] < d[0])) else 0.0
        for side, arr in ((1, pts_up), (-1, pts_dn)):
            e = gm[i] + side * gsp[i] / 2
            q = side * ((gm[i + 1:j] - side * gsp[i + 1:j] / 2) - e)
            uu, dd = np.flatnonzero(q >= X), np.flatnonzero(q <= -X)
            if len(uu) and (not len(dd) or uu[0] < dd[0]):
                arr[k] = X
            elif len(dd):
                arr[k] = -X
            else:
                arr[k] = q[-1] if len(q) else 0.0
    return up_mid, pts_up, pts_dn


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    cache = pickle.loads((ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    frames, store = [], {}
    for d in days:
        F, (g, gm, gsp) = day_frame(*cache[d])
        F = extra(F, gm)
        idx = np.arange(900, len(F) - 1, STEP)
        y, pu, pdn = races(gm, gsp, idx)
        sub = F.iloc[idx][FEATS].copy()
        sub["y"], sub["pu"], sub["pd"], sub["day"] = y, pu, pdn, d
        frames.append(sub)
        store[d] = (F, g)
    D = pd.concat(frames, ignore_index=True)
    D = D[D.y.notna()]
    tr, te = D[D.day < cut], D[D.day >= cut]
    m = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=200,
                                       l2_regularization=1.0, random_state=0)
    m.fit(tr[FEATS], tr.y)
    p = m.predict_proba(te[FEATS])[:, 1]
    auc = roc_auc_score(te.y, p)
    conf = np.abs(p - 0.5)
    order = np.argsort(-conf)
    out = [f"backtest/ndx_aplus_ticks.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, holdout from {cut:%Y-%m-%d}; "
           f"moments every {STEP} s: train {len(tr):,}, holdout {len(te):,}; +-{X:g} race within {CAP} s", "",
           f"holdout AUC {auc:.3f}; up share {te.y.mean():.3f}", "",
           f"   {'bucket':>10}{'calls':>8}{'won (mid)':>11}{'net pts at spread':>19}"]
    res = {}
    yv, pu, pdn = te.y.to_numpy(), te.pu.to_numpy(), te.pd.to_numpy()
    for q in (0.01, 0.001, 0.0005, 0.0001):
        k = max(int(len(p) * q), 1)
        ix = order[:k]
        side_up = p[ix] > 0.5
        won = np.mean((yv[ix] == 1) == side_up)
        net = np.nanmean(np.where(side_up, pu[ix], pdn[ix]))
        res[q] = (k, won, net)
        out.append(f"   {'top ' + f'{q * 100:g}%':>10}{k:>8,}{won * 100:>10.1f}%{net:>+19.2f}")
    # his entries
    import backtest.his_tape as TP
    x = TP.entries()
    conf_sorted = np.sort(conf)
    pct, agree = [], []
    for r in x.itertuples():
        if r.d not in store:
            continue
        F, g = store[r.d]
        i = int(np.searchsorted(g, r.t, "right") - 1) - 1                  # the second before his click
        if i < 900 or i >= len(F):
            continue
        p1 = m.predict_proba(F.iloc[[i]][FEATS])[:, 1][0]
        pct.append(np.searchsorted(conf_sorted, abs(p1 - 0.5)) / len(conf_sorted))
        agree.append((p1 > 0.5) == (r.s > 0))
    out += ["", f"HIS {len(pct)} entries: confidence percentile median {np.median(pct) * 100:.0f} (top 1%: "
            f"{np.mean(np.array(pct) >= 0.99) * 100:.0f}%); the model's side agrees with his {np.mean(agree) * 100:.0f}%", "",
            "REGISTERED PREDICTIONS",
            f"  1 AUC {auc:.3f} <= 0.55 -> {'RIGHT' if auc <= 0.55 else 'WRONG'}",
            f"  2 top 0.05% / 0.01% {res[0.0005][1] * 100:.0f}% / {res[0.0001][1] * 100:.0f}% <= 65%, nets " +
            ", ".join(f"{v[2]:+.2f}" for v in res.values()) + " <= 0 -> " +
            ("RIGHT" if res[0.0005][1] <= 0.65 and res[0.0001][1] <= 0.65 and all(v[2] <= 0 for v in res.values())
             and not any(v[0] >= 30 and v[1] >= 0.75 for v in res.values()) else "WRONG"),
            f"  3 his percentile {np.median(pct) * 100:.0f} <= 75, agreement {np.mean(agree) * 100:.0f}% <= 60% -> "
            f"{'RIGHT' if np.median(pct) <= 0.75 and np.mean(agree) <= 0.60 else 'WRONG'}"]
    lead = [q for q, v in res.items() if v[0] >= 30 and v[1] >= 0.75 and v[2] > 0]
    out.append(f"  LEAD LINE: {', '.join(f'top {q * 100:g}%' for q in lead) if lead else 'not hit'}")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
