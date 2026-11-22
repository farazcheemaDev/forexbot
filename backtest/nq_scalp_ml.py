"""CAN ANYTHING PREDICT NASDAQ'S NEXT 3-30 MINUTES? A walk-forward model on 16 years of NQ minute bars WITH VOLUME - the cleanest scalping test the data allows (2026-11-03)

The user, 2026-11-04: "this [the noise rule] is not a good strategy; I want something better, preferably scalping like he does." Every earlier scalping test on NASDAQ (cfd_scalp.py 1,368 rules, cfd_bigtarget.py 4,820, ustec_seconds.py, his_model.py's 75
features at HIS moments) either had no volume or no history. This uses the bought NQ bars (backtest/nq_fetch.py): 4,016 cash sessions, 5.46 million minute bars with volume.

THE QUESTION IS PURELY STATISTICAL: how much of the next h minutes' move can be predicted from what is known now, and is it more than the cost? NASDAQ moves ~20 points in 3 minutes at today's level, so a Exness round trip of ~2.2 points (0.77 bp) needs
a rank IC of only ~0.05 if you trade your best tenth (IC* = cost / (1.755 x sigma_h)) - far less than the crypto scalps needed (0.29), which is why this is worth a clean test.

DESIGN. Decision every 3 minutes from 10:00 to 15:57 New York (110 a session), enter at the next minute's open, exit h minutes later (h = 3, 5, 15, 30; 3 minutes is his +7/-7 race horizon). 17 features, all known at the decision close:
z-returns over 1 / 3 / 5 / 15 / 30 minutes and since the open, distance from the session VWAP, the gap, the position in the range, the range so far, the last 5 minutes' realised volatility (all in units of the recent
per-minute volatility), VOLUME features (the last 5 and 30 minutes' volume against the same minutes' average over the previous 14 sessions, and the signed-volume imbalance over 5 and 30 minutes), the time of day and the weekday.
WALK-FORWARD by year: train on every session BEFORE the test year (at least 3 years), predict the test year (2014-2026). Models: ridge (all four horizons) and gradient boosting (3 and 15 minutes). Reported: pooled and per-year rank IC, and
the economic test - trade only the strongest predictions (the top 10% / 2% / 0.5% of |prediction| within each test year), long if the prediction is positive, short if negative, net of the cost, with a day-clustered t.
Costs: 0.77 bp (Exness NASDAQ spread) and 0.25 bp (what a futures/micro-futures venue might cost - the question 'does a cheaper venue change the answer?').

REGISTERED BEFORE THE FIRST RUN (2026-11-04)
    N1  Pooled out-of-sample rank IC is below 0.03 for every model and horizon (positive perhaps, but economically small).
    N2  No (model, horizon, top-share) cell has a positive net expectancy with day-clustered t >= 3.0 at 0.77 bp.
    N3  At 0.25 bp at most two cells are positive and none has t >= 3.0 (a cheaper venue does not rescue it).
    N4  The volume features add nothing: the ridge IC with them is within 0.005 of the ridge IC without them.

RESULT (2026-11-04, logs/nq_scalp_ml.txt; 4,016 sessions, 441,760 decisions, 13 test years 2014-2026)
    A model on 17 price-and-volume features does not predict NASDAQ's next 3-30 minutes well enough to pay even a futures-sized cost. Pooled out-of-sample rank IC: ridge +0.012 / +0.007 / +0.003 / +0.010 at 3 / 5 / 15 / 30 minutes, boosting +0.016 (3 min)
    and +0.005 (15 min); the skill needed to beat 0.77 bp is 0.054 / 0.042 / 0.025 / 0.018 (0.018 / 0.014 / 0.008 / 0.006 at 0.25 bp). Boosting at 3 minutes is positive in all 13 years (+0.004..+0.036) - a real, tiny signal worth ~0.2 bp gross
    in its strongest tenth. Trading the strongest predictions: the top tenth nets -0.18..-0.53 bp at 0.77 bp (t down to -12); the best cells at 0.77 are ridge 30 min top 2% +1.08 bp (t 0.9), 5 min top 0.5% +0.31 (t 0.6): 0 of 18 reach t >= 3. At 0.25 bp 14 of 18 cells are
    nominally positive, the best ridge 5 min top 2% +0.59 bp (6,919 trades, t 2.3), ridge 30 min top 2% +1.60 (t 1.3): none reaches t 3, and one t of 2.3 among 36 looks is what chance gives. Volume features: ridge IC with / without +0.0118 / +0.0082, +0.0074 / +0.0054,
    +0.0033 / +0.0030, +0.0096 / +0.0109 - nothing. Predictions: N1, N2, N4 right; N3 half right (14 cells positive, not <= 2; none with t >= 3).
    Tests: 8; 21 planted bugs, all caught (19 on the first pass - the two survivors, the 30-minute volume ratio and the volatility-scale window, each got a hand-formula test).

    python -m backtest.nq_scalp_ml        writes logs/nq_scalp_ml.txt          tests: python tests/test_nq_scalp_ml.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.his_exit_shape import clustered_t  # noqa: E402
from backtest.know_when_not_to import _ratio_to_prior  # noqa: E402
from backtest.nq_noise import build_sessions, load_nq, vwap_array  # noqa: E402

DEC = tuple(range(30, 359, 3))
HORIZONS = (3, 5, 15, 30)
FEATS = ("z1", "z3", "z5", "z15", "z30", "z_open", "z_vwap", "gap_z", "pos", "rng_z", "rv5", "vol5", "vol30", "sv5", "sv30", "m", "dow")
VOLUME = ("vol5", "vol30", "sv5", "sv30")
QS = (0.10, 0.02, 0.005)
COSTS = (0.77, 0.25)
MIN_TRAIN_YEARS = 3


def required_ic(cost_bp, sigma_bp, top_share_mult=1.755):
    """IC* = cost / (1.755 x sigma_h): the rank IC at which the best tenth's average move equals the cost."""
    return cost_bp / (top_share_mult * sigma_bp)


def build(A, dates, prev):
    """(X, Y, sess, m): features at every (session, decision minute) and the h-minute forward returns in bp (entry at the next minute's open). X columns follow FEATS."""
    O, H, Lo, C, V = A["o"], A["h"], A["l"], A["c"], A["v"]
    n = C.shape[0]
    r1 = np.diff(C, axis=1) / C[:, :-1]
    scale = (pd.Series(np.std(r1, axis=1) * 1e4).rolling(20).mean().shift(1)).to_numpy()          # recent per-minute volatility in bp, known before the session
    O0 = O[:, 0]
    cumH, cumL = np.maximum.accumulate(H, axis=1), np.minimum.accumulate(Lo, axis=1)
    vw = vwap_array(A)
    cs_v = np.cumsum(V, axis=1)
    cs_s = np.cumsum(np.sign(C - O) * V, axis=1)
    gap = np.where(np.isfinite(prev), (O0 / prev - 1) * 1e4, 0.0)
    dow = dates.dayofweek.to_numpy().astype(float)

    def win(cs, m, k):
        return cs[:, m] - cs[:, m - k]

    Xs, Ys, S, M = [], {h: [] for h in HORIZONS}, [], []
    for m in DEC:
        f = {}
        for k in (1, 3, 5, 15, 30):
            f[f"z{k}"] = (C[:, m] / C[:, m - k] - 1) * 1e4 / (scale * np.sqrt(k))
        f["z_open"] = (C[:, m] / O0 - 1) * 1e4 / (scale * np.sqrt(m + 1))
        f["z_vwap"] = (C[:, m] / vw[:, m] - 1) * 1e4 / (scale * np.sqrt(30))
        f["gap_z"] = gap / (scale * np.sqrt(30))
        rng = cumH[:, m] - cumL[:, m]
        f["pos"] = (C[:, m] - cumL[:, m]) / np.maximum(rng, 1e-12)
        f["rng_z"] = rng / O0 * 1e4 / (scale * np.sqrt(m + 1))
        f["rv5"] = np.std(r1[:, m - 5:m], axis=1) * 1e4 / scale
        v5, v30 = win(cs_v, m, 5), win(cs_v, m, 30)
        f["vol5"], f["vol30"] = _ratio_to_prior(v5), _ratio_to_prior(v30)
        f["sv5"], f["sv30"] = win(cs_s, m, 5) / np.maximum(v5, 1.0), win(cs_s, m, 30) / np.maximum(v30, 1.0)
        f["m"], f["dow"] = np.full(n, float(m)), dow
        X = np.column_stack([f[c] for c in FEATS])
        for j, c in enumerate(FEATS):
            if c not in ("m", "dow", "pos"):
                X[:, j] = np.clip(X[:, j], -10, 10)
        Xs.append(X)
        for h in HORIZONS:
            Ys[h].append((O[:, m + 1 + h] / O[:, m + 1] - 1) * 1e4)
        S.append(np.arange(n))
        M.append(np.full(n, m))
    return np.vstack(Xs), {h: np.concatenate(v) for h, v in Ys.items()}, np.concatenate(S), np.concatenate(M)


def make_models():
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {"ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=3000.0)),
            "boosting": lambda: HistGradientBoostingRegressor(max_depth=3, max_iter=120, learning_rate=0.05, random_state=0)}


def walk_forward(X, y, year, make, cols, test_years):
    """Out-of-sample predictions: each test year is predicted by a model trained on every row of EARLIER years only."""
    pred = np.full(len(y), np.nan)
    ok = np.isfinite(X[:, cols]).all(axis=1) & np.isfinite(y)
    for ty in test_years:
        tr, te = ok & (year < ty), ok & (year == ty)
        if len(np.unique(year[tr])) < MIN_TRAIN_YEARS or te.sum() == 0:
            continue
        mdl = make()
        mdl.fit(X[tr][:, cols], y[tr])
        pred[te] = mdl.predict(X[te][:, cols])
    return pred


def rank_ic(a, b):
    from scipy.stats import spearmanr
    return float(spearmanr(a, b).statistic)


def top_trades(pred, y, year, q, cost_bp):
    """Rows traded: within each test year the top q share of |prediction|; net bp = side x forward return - cost."""
    sel = np.zeros(len(pred), bool)
    for ty in np.unique(year[np.isfinite(pred)]):
        m = np.isfinite(pred) & (year == ty)
        thr = np.quantile(np.abs(pred[m]), 1 - q)
        sel |= m & (np.abs(pred) >= thr)
    return sel, np.sign(pred[sel]) * y[sel] - cost_bp


def main():
    d = load_nq()
    A, dates, prev, roll = build_sessions(d)
    X, Y, sess, mm = build(A, dates, prev)
    year = dates.year.to_numpy()[sess]
    day = sess
    test_years = [yy for yy in sorted(set(year)) if yy >= 2014]
    cols_all = list(range(len(FEATS)))
    cols_novol = [i for i, c in enumerate(FEATS) if c not in VOLUME]
    lvl = 28000.0
    out = [f"backtest/nq_scalp_ml.py - {len(dates)} NQ cash sessions, {len(X):,} decision points (every 3 minutes, 10:00-15:57 New York); walk-forward test years {test_years[0]}-{test_years[-1]}; entry at the next minute's open",
           "\nHOW BIG THE MOVES ARE AND WHAT SKILL BEATING THE COST NEEDS (IC* = cost / (1.755 x sigma), trading the best tenth):",
           f"   {'horizon':>8}{'sigma bp':>9}{'sigma pts @28k':>15}{'IC* at 0.77 bp':>15}{'IC* at 0.25 bp':>15}"]
    for h in HORIZONS:
        s = np.nanstd(Y[h])
        out.append(f"   {h:>6} m{s:>9.1f}{s * lvl / 1e4:>15.1f}{required_ic(0.77, s):>15.3f}{required_ic(0.25, s):>15.3f}")
    models = make_models()
    res = {}
    out.append("\nOUT-OF-SAMPLE RANK IC (pooled over the test years; per-year range) and the strongest predictions' net expectancy (bp per trade, day-clustered t):")
    out.append(f"   {'model':<9}{'h':>3}{'IC':>8}{'IC by year min..max':>21}{'top':>6}{'trades':>8}{'gross bp':>9}{'net @0.77':>10}{'t':>6}{'net @0.25':>10}{'t':>6}")
    for name in ("ridge", "boosting"):
        for h in HORIZONS:
            if name == "boosting" and h not in (3, 15):
                continue
            pred = walk_forward(X, Y[h], year, models[name], cols_all, test_years)
            ok = np.isfinite(pred) & np.isfinite(Y[h])
            ic = rank_ic(pred[ok], Y[h][ok])
            yic = [rank_ic(pred[ok & (year == ty)], Y[h][ok & (year == ty)]) for ty in test_years if (ok & (year == ty)).sum() > 100]
            res[(name, h)] = dict(ic=ic)
            for q in QS:
                sel, net1 = top_trades(pred, Y[h], year, q, COSTS[0])
                _, net2 = top_trades(pred, Y[h], year, q, COSTS[1])
                gross = net1.mean() + COSTS[0]
                m1, t1 = clustered_t(net1, day[sel])
                m2, t2 = clustered_t(net2, day[sel])
                res[(name, h, q)] = dict(n=int(sel.sum()), net1=m1, t1=t1, net2=m2, t2=t2)
                out.append(f"   {name:<9}{h:>3}{ic:>+8.3f}{min(yic):>+11.3f}..{max(yic):>+6.3f}{q * 100:>5.1f}%{int(sel.sum()):>8}{gross:>+9.2f}{m1:>+10.2f}{t1:>+6.1f}{m2:>+10.2f}{t2:>+6.1f}")
    ics = [v["ic"] for k, v in res.items() if len(k) == 2]
    cells = {k: v for k, v in res.items() if len(k) == 3}
    pos1 = [k for k, v in cells.items() if v["net1"] > 0 and v["t1"] >= 3.0]
    pos2 = [k for k, v in cells.items() if v["net2"] > 0]
    pos2t = [k for k, v in cells.items() if v["net2"] > 0 and v["t2"] >= 3.0]
    out.append(f"\n   largest pooled IC over all models and horizons: {max(ics):+.3f}; cells with a positive net expectancy and t >= 3 at 0.77 bp: {len(pos1)} of {len(cells)}; positive at 0.25 bp: {len(pos2)} (with t >= 3: {len(pos2t)})")
    out.append("\nN4 - DO THE VOLUME FEATURES HELP? ridge IC with all 17 features vs without the 4 volume features:")
    for h in HORIZONS:
        pa = walk_forward(X, Y[h], year, models["ridge"], cols_all, test_years)
        pb = walk_forward(X, Y[h], year, models["ridge"], cols_novol, test_years)
        ok = np.isfinite(pa) & np.isfinite(pb) & np.isfinite(Y[h])
        out.append(f"   h = {h:>2} min: with volume {rank_ic(pa[ok], Y[h][ok]):+.4f}   without {rank_ic(pb[ok], Y[h][ok]):+.4f}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "nq_scalp_ml.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
