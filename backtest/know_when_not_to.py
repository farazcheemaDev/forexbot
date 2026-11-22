"""HE KNOWS WHEN NOT TO: can the rare disaster of a small-profit / no-stop trade be seen coming from what is known at entry? (2026-11-03)

The user, 2026-11-03: "he does kinda this [small profits] but with very good accuracy, meaning he knows when not to". his_exit_shape.py / small_profit_scalp.py: a +7-point no-stop trade wins 93-96% from random entries, the rare loser
averages -126..-151 points, and the break-even win rate is only 1-2 points above what random entries get. So a modest skill at skipping the disasters would flip the sign - THAT is what 'knowing when not to' is worth, and it is
testable without knowing his side: predict the DISASTER (the target is never touched before the close), not the direction.

DATA / TRADE. NASDAQ 1-minute bars 2010-11..2026-09 (HistData via fx_intraday_pub.session, 3,686 sessions). Decision minutes 30, 60, ..., 360 (10:00-15:30 New York) x both sides = 24 entries a session; entry at the next minute's
open; target +2.5 bp (= 7 points at today's 28,000); NO stop; held to the 16:00 print if the target is never touched (the target is touched when a later minute's high / low reaches it); costs 0.77 bp a trade (the quoted spread;
the same convention as his_exit_shape.py). Outcome in basis points net of cost; 'disaster' = target not touched.
FEATURES, all known at the decision close (no bar after it is read): the time of day; the session's range so far and the last 30 minutes' volatility, each relative to the same clock time over the previous 14 sessions; the move
since the open, the last 30 minutes' move, the gap and the previous day's return, each in the trade's direction; where the price sits in the range so far (the trade's direction); the weekday.
MODELS. A standardised logistic regression and a small gradient-boosting classifier (depth 3, 150 rounds), trained on the first 60% of sessions only, scored on the last 40% (2020-2026). The entries are then RANKED by predicted
disaster risk and only the safest fraction kept (50%, 20%, 10%, 5%, 1% - 'he takes ~5 trades a month out of ~500 moments'); expectancy, win rate and a day-clustered t are read on the held-out sessions.

REGISTERED BEFORE THE FIRST RUN (2026-11-03)
    D1  The held-out AUC for 'disaster' is modest (<= 0.65) for both models (the time of day alone tells a late entry from an early one, so it is not 0.5).
    D2  No (model, keep) cell has a positive expectancy with t >= 2.8 on the held-out sessions (Holm over 2 models x 5 keeps = 10); keeping the safest entries shrinks the loser rate but not enough, or the sample of DAYS
        becomes too thin to read.
    D3  The best cell beats the all-entries baseline by less than +1 bp a trade.

RESULT (2026-11-03; logs/know_when_not_to.txt; 88,464 entries, train before 2019-12-17, 35,256 test entries)
    D1 RIGHT: held-out AUC for 'disaster' 0.612 (logistic) / 0.627 (boosting). D2 RIGHT: 0 of 10 (model, keep) cells has a positive expectancy; the all-entries baseline is win 94.5%, -1.25 bp a trade (t -12).
    D3 RIGHT: the best cell (boosting, safest 5%) is -1.02 bp, +0.23 better than the baseline. Keeping only the safest entries DOES raise the win rate (96.2-96.3% at 50%, 97.1-97.6% at 10%, up to 98.0% at 5%) -
    and the average loser that remains grows from about -80 bp (keep 50%) to -140..-180 bp (keep 5% / 1%): the model removes the ordinary disasters (a late entry that simply runs out of time before the close, a small
    loss) and leaves the catastrophic ones (crash and trend-reversal days), which none of these features sees. A 98% win rate with a loser of ~55x the target still loses.
    Reading: 'knowing when not to' in the form of a skip filter built from market features (time, volatility, range, trend, gap) does not rescue a small-profit / no-stop trade. What he avoids is the CATASTROPHIC loser;
    that is a crash prediction, and nothing readable here makes one.

    python -m backtest.know_when_not_to        writes logs/know_when_not_to.txt          tests: python tests/test_know_when_not_to.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import session  # noqa: E402
from backtest.his_exit_shape import clustered_t  # noqa: E402

T_BP = 2.5
COST_BP = 0.77
DEC = tuple(range(30, 361, 30))
KEEPS = (0.5, 0.2, 0.1, 0.05, 0.01)
FEATS = ("m", "rng_ratio", "vol_ratio", "ret_bp", "mom30_bp", "pos_side", "gap_bp", "abs_gap_bp", "prev_ret_bp", "dow")


def _ratio_to_prior(x):
    """x / the mean of the same quantity over the previous 14 sessions (NaN until 14 sessions exist)."""
    typ = pd.Series(x).rolling(14).mean().shift(1).to_numpy()
    return x / typ


def build(A, prev, dates, t_bp=T_BP, cost_bp=COST_BP):
    """One row per (session, decision minute, side): features known at the decision close, the outcome in bp net of cost, the disaster flag, the session index."""
    O, H, Lo, C = A["o"], A["h"], A["l"], A["c"]
    n, L = C.shape
    O0 = O[:, 0]
    cumH, cumL = np.maximum.accumulate(H, axis=1), np.minimum.accumulate(Lo, axis=1)
    futH = np.maximum.accumulate(H[:, ::-1], axis=1)[:, ::-1]           # max of H[j:]
    futL = np.minimum.accumulate(Lo[:, ::-1], axis=1)[:, ::-1]
    r1 = np.diff(C, axis=1) / C[:, :-1]                                  # r1[:, k] = the return of minute k + 1
    close = C[:, -1]
    prev_ret = np.full(n, np.nan)
    prev_ret[2:] = close[1:-1] / close[:-2] - 1
    gap = O0 / prev - 1
    dow = dates.dayofweek.to_numpy()
    rows = []
    for m in DEC:
        rng = _ratio_to_prior((cumH[:, m] - cumL[:, m]) / O0)
        vol = _ratio_to_prior(np.std(r1[:, m - 30:m], axis=1))
        ret = C[:, m] / O0 - 1
        mom = C[:, m] / C[:, m - 30] - 1
        pos = (C[:, m] - cumL[:, m]) / np.maximum(cumH[:, m] - cumL[:, m], 1e-12)
        e = O[:, m + 1]
        for s in (1, -1):
            hit = (futH[:, m + 1] >= e * (1 + t_bp / 1e4)) if s == 1 else (futL[:, m + 1] <= e * (1 - t_bp / 1e4))
            out = np.where(hit, t_bp - cost_bp, s * (close / e - 1) * 1e4 - cost_bp)
            F = np.column_stack([np.full(n, m), rng, vol, s * ret * 1e4, s * mom * 1e4, pos if s == 1 else 1 - pos, s * gap * 1e4, np.abs(gap) * 1e4, s * prev_ret * 1e4, dow])
            rows.append((F, out, ~hit, np.arange(n), np.full(n, s)))
    F = np.vstack([r[0] for r in rows])
    return F, np.concatenate([r[1] for r in rows]), np.concatenate([r[2] for r in rows]), np.concatenate([r[3] for r in rows]), np.concatenate([r[4] for r in rows])


def split_sessions(valid_idx, frac=0.6):
    """First `frac` of the usable sessions (in time order) = train, the rest = test."""
    v = np.sort(np.unique(valid_idx))
    cut = v[int(len(v) * frac)]
    return cut


def masks(day, ok, frac=0.6):
    """(train, test) row masks: rows with every feature, split at the first `frac` of the usable sessions; the two never share a session."""
    cut = split_sessions(day[ok], frac)
    return ok & (day < cut), ok & (day >= cut)


def keep_safest(p, keep):
    """Indices of the `keep` fraction with the LOWEST predicted disaster probability."""
    return np.argsort(p, kind="stable")[: max(1, int(keep * len(p)))]


def evaluate(F, out, dis, day, models, frac=0.6):
    from sklearn.metrics import roc_auc_score
    ok = np.isfinite(F).all(axis=1)
    tr, te = masks(day, ok, frac)
    res = {"baseline": dict(ev=out[te].mean(), win=(~dis[te]).mean() * 100, n=int(te.sum()), t=clustered_t(out[te], day[te])[1])}
    for name, mk in models.items():
        mdl = mk()
        mdl.fit(F[tr], dis[tr])
        p = mdl.predict_proba(F[te])[:, 1]
        res[name] = dict(auc=roc_auc_score(dis[te], p), keeps={})
        for k in KEEPS:
            idx = keep_safest(p, k)
            x, d = out[te][idx], day[te][idx]
            ev, t = clustered_t(x, d)
            res[name]["keeps"][k] = dict(n=len(x), days=len(np.unique(d)), win=(~dis[te][idx]).mean() * 100, loser=x[x < 0].mean() if (x < 0).any() else 0.0, ev=ev, t=t)
    return res


def make_models():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {"logistic": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=500)),
            "boosting": lambda: HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.08, random_state=0)}


def main():
    A, dates, prev = session("NASDAQ")
    F, out, dis, day, side = build(A, prev, dates)
    res = evaluate(F, out, dis, day, make_models())
    ok = np.isfinite(F).all(axis=1)
    cut = split_sessions(day[ok])
    L = [f"backtest/know_when_not_to.py - {len(dates)} sessions {dates[0]:%Y-%m}..{dates[-1]:%Y-%m}; {len(out):,} entries ({int(ok.sum()):,} with all features); +{T_BP} bp target, no stop, held to the close, {COST_BP} bp cost; train before {dates[cut]:%Y-%m-%d}, test after",
         f"   all test entries: win {res['baseline']['win']:.1f}%, expectancy {res['baseline']['ev']:+.2f} bp a trade (t {res['baseline']['t']:+.1f}), n {res['baseline']['n']:,}",
         f"   {'model':<10}{'AUC':>6}{'keep safest':>12}{'n':>8}{'days':>6}{'win %':>7}{'avg loser bp':>13}{'EV bp':>8}{'t':>6}"]
    best = None
    for name in ("logistic", "boosting"):
        for k, v in res[name]["keeps"].items():
            L.append(f"   {name:<10}{res[name]['auc']:>6.3f}{k * 100:>11.0f}%{v['n']:>8}{v['days']:>6}{v['win']:>7.1f}{v['loser']:>+13.1f}{v['ev']:>+8.2f}{v['t']:>+6.1f}")
            if best is None or v["ev"] > best[2]["ev"]:
                best = (name, k, v)
    pos = [(n, k) for n in ("logistic", "boosting") for k, v in res[n]["keeps"].items() if v["ev"] > 0 and v["t"] >= 2.8]
    L.append(f"\n   cells with a positive expectancy and t >= 2.8: {len(pos)} of 10; best: {best[0]} keeping the safest {best[1] * 100:.0f}% -> {best[2]['ev']:+.2f} bp (t {best[2]['t']:+.1f}, {best[2]['n']} entries on {best[2]['days']} days) vs the all-entries {res['baseline']['ev']:+.2f}")
    txt = "\n".join(L)
    print(txt)
    (ROOT / "logs" / "know_when_not_to.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
