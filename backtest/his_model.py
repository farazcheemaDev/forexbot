"""CAN A MODEL SEE WHAT HE SEES? Every feature at once, his moment against the other moments of his sitting.

The user, 2026-09-26: "that's on us to figure out". his_race_curve.py showed his pick is real - direction over the
next 1-5 minutes, 10 of 12 days at +-7 (t 5.8) - and every single feature tested one at a time (§17-32) came out
ordinary. What one-at-a-time tests cannot see is a COMBINATION: a quiet candle AND a dip of a certain depth AND a
certain recent path, each ordinary alone. So this puts ~75 features into one model at once:
  his_microstructure (9: move, straightness, dip, retracement, last 5 s, quiet, steps, freshness)
  his_local.extra (4: last candle's wick and body, distance to a 25 level, tick rate)
  his_ta (16: EMAs, RSI, Stochastic, MACD, Bollinger, discount, 5-min trend, FVG, sweep, BOS)
  his_1m (13: pin bar, inside, engulfing, doji, ..., the forming candle)
  his_generals (8: the eight biggest NASDAQ stocks ahead of the index, the dollar, bitcoin)
  NEW: the raw path - the mid's move in each 5-s slice of the last 60 s (12) and each 30-s slice of the last
       5 min (10); where the price sits in the last closed candle's range; the Fibonacci depth of the pullback
       from the last 15-minute leg; the dip in points from the 5-minute extreme
TASK: tell his moment from the 40 moments of the same day at whole-minute offsets within 20 minutes (the SAME
second of the minute, same direction; none within 60 s of any of his entries). Two models (L2 logistic,
random forest). Scored ONLY on days the model never saw (leave-one-day-out): the percentile of his moment
among its 41 (0.50 = chance). Null: the same pipeline with a random other moment of each group labelled as
"his", 100 times. Then the model trained on all his days scores random moments on the OTHER ~106 days: does a
high score win the 7-point NASDAQ race (and the net race)?

REGISTERED PREDICTION (2026-09-26, before running): no model finds him. Out-of-fold percentile <= 0.60 for both,
permutation p > 0.1; on the other days the top-decile score wins the 7-point race within +-4 points of base and
nets < 40%.

    python -m backtest.his_model            # the test
    python -m backtest.his_model --power    # can it find a planted pattern?
"""
from __future__ import annotations

import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_1m import flags as pat_flags  # noqa: E402
from backtest.his_generals import CACHE as GCACHE, OTHER, STOCKS, feats as gen_feats, ndx_sec  # noqa: E402
from backtest.his_levels import daily_basis  # noqa: E402
from backtest.his_local import extra  # noqa: E402
from backtest.his_microstructure import feats as micro  # noqa: E402
from backtest.his_predictors import race_net  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402
from backtest.his_ta import candles, feats as ta_feats  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0


class Day:
    def __init__(self, d, tick, basis, gc):
        self.ts, self.mid, self.spr = tick
        self.B1, self.B5 = candles(self.ts, self.mid, 60), candles(self.ts, self.mid, 300)
        self.basis = basis
        self.G = None
        if gc is not None and all(gc[s].get(d) is not None for s in STOCKS):
            self.G = {s: gc[s][d].astype(np.float64) for s in STOCKS}
            for s in OTHER:
                self.G[s] = gc[s][d].astype(np.float64) if gc[s].get(d) is not None else None
            self.G["ndx"] = ndx_sec(self.ts, self.mid)

    def at(self, t):
        return self.mid[max(np.searchsorted(self.ts, t, side="right") - 1, 0)]


def allf(D, t, s):
    a = micro(D.ts, D.mid, t, s)
    b = extra(D.ts, D.mid, t, s, D.basis if np.isfinite(D.basis) else 0.0)
    c = ta_feats((D.ts, D.mid, D.B1, D.B5), t, s)
    e = pat_flags(D.ts, D.mid, D.B1, t, s)
    if a is None or b is None or c is None or e is None:
        return None
    f = a | b | c | e
    if not np.isfinite(D.basis):
        f["lvl25"] = np.nan
    g = gen_feats(D.G, t, s) if D.G is not None and 300 <= t < 23400 else None
    for k in ("lead_30", "lead_120", "lead_300", "gmove_120", "breadth_60", "nvda_lead_120", "dxy_120", "btc_120"):
        f[k] = g[k] if g is not None else np.nan
    p = D.at(t)
    for j in range(1, 13):
        f[f"r5_{j}"] = s * (D.at(t - 5 * (j - 1)) - D.at(t - 5 * j))
    for j in range(1, 11):
        f[f"r30_{j}"] = s * (D.at(t - 30 * (j - 1)) - D.at(t - 30 * j))
    k = int(t // 60) - 1
    h, l = D.B1["h"], D.B1["l"]
    rg = h[k] - l[k]
    f["pos_prev"] = ((p - l[k]) / rg if s == 1 else (h[k] - p) / rg) if rg > 0 else np.nan
    lo, hi = max(0, k - 14), k + 1
    if s == 1:
        iH = lo + int(np.argmax(h[lo:hi]))
        H, L = h[iH], l[lo:iH + 1].min()
        f["fib"] = (H - p) / (H - L) if H > L else np.nan
    else:
        iL = lo + int(np.argmin(l[lo:hi]))
        L, H = l[iL], h[lo:iL + 1].max()
        f["fib"] = (p - L) / (H - L) if H > L else np.nan
    i5 = np.searchsorted(D.ts, t - 300)
    i1 = np.searchsorted(D.ts, t, side="right")
    seg = D.mid[i5:i1]
    f["dip_pts"] = (seg.max() - p if s == 1 else p - seg.min()) if len(seg) else np.nan
    return {k: float(v) for k, v in f.items()}


def models():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {
        "logistic": lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                          LogisticRegression(C=0.05, class_weight="balanced", max_iter=2000)),
        "forest": lambda: make_pipeline(SimpleImputer(strategy="median"),
                                        RandomForestClassifier(n_estimators=200, min_samples_leaf=5, max_features=0.3,
                                                               class_weight="balanced_subsample", n_jobs=-1, random_state=0)),
    }


def cv_percentile(X, y, grp, day, make):
    """leave-one-day-out; mean percentile of the positive within its own group"""
    pct = []
    for d in np.unique(day):
        tr, te = day != d, day == d
        m = make().fit(X[tr], y[tr])
        sc = m.predict_proba(X[te])[:, 1]
        g, yy = grp[te], y[te]
        for gg in np.unique(g):
            k = g == gg
            pos = sc[k][yy[k] == 1]
            neg = sc[k][yy[k] == 0]
            if len(pos) == 1 and len(neg):
                pct.append((neg < pos[0]).mean() + 0.5 * (neg == pos[0]).mean())
    return np.array(pct)


def build():
    cache = pickle.loads(TICKS.read_bytes())
    basis = daily_basis()
    gc = pickle.loads(GCACHE.read_bytes()) if GCACHE.exists() else None
    DAYS = {}
    def day(d):
        if d not in DAYS:
            DAYS[d] = Day(d, cache[d], float(basis.get(d, np.nan)), gc)
        return DAYS[d]
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["et"] = (x.open_time - pd.Timedelta(hours=GMT)).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x[x.open_time - pd.Timedelta(hours=GMT) >= "2026-04-01"]
    x["d"] = x.et.dt.normalize()
    x["t"] = (x.et - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    rows = []
    for gi, r in enumerate(x.itertuples()):
        if r.d not in cache or cache[r.d] is None:
            continue
        D = day(r.d)
        s = 1 if r.side == "BUY" else -1
        mine = allf(D, r.t, s)
        if mine is None:
            continue
        others = x[x.d == r.d].t.to_numpy()
        rows.append(mine | {"y": 1, "g": gi, "day": r.d})
        for m in list(range(-20, 0)) + list(range(1, 21)):
            t = r.t + 60 * m
            if np.min(np.abs(others - t)) < 60:
                continue
            f = allf(D, t, s)
            if f is not None:
                rows.append(f | {"y": 0, "g": gi, "day": r.d})
    T = pd.DataFrame(rows)
    return T, cache, day


def main():
    T, cache, day = build()
    feat_cols = [c for c in T.columns if c not in ("y", "g", "day")]
    X, y, grp, dd = T[feat_cols].to_numpy(float), T.y.to_numpy(), T.g.to_numpy(), T.day.to_numpy()
    out = [f"{int(y.sum())} of his clean entries, {int((y == 0).sum())} same-day comparison moments (same second of the minute), "
           f"{len(np.unique(dd))} days, {len(feat_cols)} features"]
    rng = np.random.default_rng(21)
    M = models()
    for name, make in M.items():
        pct = cv_percentile(X, y, grp, dd, make)
        null = []
        n_perm = 100 if name == "logistic" else 40
        for _ in range(n_perm):
            yp = np.zeros_like(y)
            for gg in np.unique(grp):
                idx = np.flatnonzero((grp == gg) & (y == 0))
                if len(idx):
                    yp[rng.choice(idx)] = 1
            keep = y == 0
            null.append(cv_percentile(X[keep], yp[keep], grp[keep], dd[keep], make).mean())
        null = np.array(null)
        out.append(f"\n{name}: his moment's out-of-fold percentile among its group: mean {pct.mean():.3f} (median {np.median(pct):.2f}; "
                   f"top 10% in {np.mean(pct >= 0.9)*100:.0f}% of groups)")
        out.append(f"  null (a random other moment labelled his, {n_perm}x): mean {null.mean():.3f}, 95th pct {np.percentile(null, 95):.3f}; "
                   f"p = {np.mean(null >= pct.mean()):.3f}")

    # the model trained on all his days, scoring random moments on the OTHER days
    his_days = set(np.unique(dd))
    other = [d for d in sorted(cache) if cache[d] is not None and d not in his_days]
    B = []
    for d in other:
        D = day(d)
        for t in rng.uniform(1800, 22800, 40):
            for s in (1, -1):
                f = allf(D, t, s)
                o = race2(D.ts, D.mid, t, s, 600, 7, 7)
                if f is None or o is None:
                    continue
                B.append(f | {"o": o, "on": race_net(D.ts, D.mid, D.spr, t, s), "day": d})
    B = pd.DataFrame(B)
    mid_day = other[len(other) // 2]
    w = lambda g, c="o": g[c].dropna().mean() * 100 if len(g) else np.nan  # noqa: E731
    out.append(f"\nOTHER DAYS: {len(B)} random moment x direction pairs on {B.day.nunique()} days he did not trade; "
               f"7-point race base {w(B):.1f}%, net base {w(B, 'on'):.1f}% (break-even 50%)")
    for name, make in M.items():
        m = make().fit(X, y)
        sc = m.predict_proba(B[feat_cols].to_numpy(float))[:, 1]
        q9, q67 = np.quantile(sc, 0.9), np.quantile(sc, 2 / 3)
        top, t3, bot = B[sc >= q9], B[sc >= q67], B[sc <= np.quantile(sc, 1 / 3)]
        out.append(f"  {name:<9} top 10%: race {w(top):.1f}% (halves {w(top[top.day < mid_day]):.1f} / {w(top[top.day >= mid_day]):.1f}), "
                   f"net {w(top, 'on'):.1f}%  |  top third {w(t3):.1f}%  bottom third {w(bot):.1f}%")
        if name == "forest":
            imp = pd.Series(m[-1].feature_importances_, index=feat_cols).sort_values(ascending=False).head(12)
            out.append("  forest's most-used features: " + ", ".join(f"{k} {v:.3f}" for k, v in imp.items()))
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_model.txt").write_text(txt, encoding="utf-8")


def power():
    """Can this pipeline find a planted pattern at all? In each group, relabel as 'his' the moment that maximises a
    hidden 2-3 feature rule plus noise, and see what out-of-fold percentile the same models recover."""
    T, _, _ = build()
    feat_cols = [c for c in T.columns if c not in ("y", "g", "day")]
    X, grp, dd = T[feat_cols].to_numpy(float), T.g.to_numpy(), T.day.to_numpy()
    Z = (X - np.nanmean(X, 0)) / np.where(np.nanstd(X, 0) > 0, np.nanstd(X, 0), 1)
    Z = np.nan_to_num(Z)
    ix = {c: i for i, c in enumerate(feat_cols)}
    rules = {"wick + dip + low in candle": Z[:, ix["c_wick"]] - Z[:, ix["f_dip"]] - Z[:, ix["pos_prev"]],
             "30-s move + NVDA lead": Z[:, ix["r30_1"]] + Z[:, ix["nvda_lead_120"]]}
    rng = np.random.default_rng(22)
    out = ["POWER CHECK - a hidden rule picks one 'his' moment per group (rule + noise); what does the pipeline recover?",
           f"  {'rule':<28}{'noise':>6}{'plant rank on rule':>20}{'logistic':>10}{'forest':>8}"]
    M = models()
    for name, r in rules.items():
        for sig in (0.5, 1.5, 3.0):
            y = np.zeros(len(T), int)
            rk = []
            for gg in np.unique(grp):
                idx = np.flatnonzero(grp == gg)
                pick = idx[np.argmax(r[idx] + sig * rng.standard_normal(len(idx)))]
                y[pick] = 1
                others = r[idx[idx != pick]]
                rk.append((others < r[pick]).mean())
            res = [cv_percentile(X, y, grp, dd, M[m]).mean() for m in ("logistic", "forest")]
            out.append(f"  {name:<28}{sig:>6.1f}{np.mean(rk):>20.2f}{res[0]:>10.3f}{res[1]:>8.3f}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_model_power.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    if "--power" in sys.argv:
        power()
    else:
        main()
