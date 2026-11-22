"""THE COMBINATION TEST WITH A SCREENED MODEL: can a few well-chosen signals see what 55-146 correlated ones could not? (2026-11-15)

THE USER (2026-11-15, /goal): "find an edge that gives good signals - a perfect combination of every signal, or everything you have so far, including the forward data from the Analyst desk."
combo_meta.py and combo_universe.py found nothing (0 of 12, 0 of 27) - but their power check showed the cause of a weak null: a ridge on 55-146 correlated features learns regime noise as large as a modest real skill, so it could not recover a planted
+0.10R-per-sd skill. This file applies the standard remedy that never touches the test data: inside EVERY training fold, screen the features by |correlation| with the (clipped) outcome, keep the K = 8 strongest, and fit a small ridge on those
(combo_meta.fit_model 'sridge'). Everything else is combo_universe's: a FIXED trade at every 6th hour on BTC ETH SOL XRP BNB, both sides, three fixed brackets (G1 1.2% / 2.4% / 24h, G2 1.2% / 3.6% / 24h, G3 2% / 4% / 48h), 12bp, ~70,000
candidates per bracket, quarterly walk-forward from 2023-01 with a 72-hour embargo, the gate of combo_meta (selected bets' mean R minus all bets' mean R, Welch t >= 2; selected R/bet >= +0.05 and > 0 in BOTH halves; difference > 0 in both; hit rate above
the all-candidates hit rate of the same side and quarter in both; >= 150 bets; Holm). 2 models (the screened ridge on the P set and on P + E) x 3 brackets x 3 fractions (top 5 / 10 / 20%) = 18 new cells; Holm is reported over these 18 and over all 45
(the 27 of combo_universe plus these).
FIRST THE POWER CHECK (the point of this file): the same pipeline on labels with a planted skill of +0.10 / +0.05 / +0.025R per sd of a rank-normal direction-aligned 24h return, and on shuffled labels. A null is only worth reading if the planted skill shows.

REGISTERED BEFORE THE FIRST RUN (2026-11-15; prior that at least one of the 18 cells passes: 3%)
  V1  The screened ridge recovers a planted +0.10R-per-sd skill (selected minus all >= +0.05R, Welch t >= 2) and a planted +0.05R-per-sd skill at t >= 1.5; the shuffled placebo does not pass. (priors 80% / 55%)
  V2  No cell of the 18 passes.
  V3  The screened models' selected R/bet is negative in 2025-26 in most cells (the regime decay combo_universe showed).
  V4  The screen is unstable: most features are kept in fewer than half of the folds; the ones kept most often are market-regime features (BTC / breadth / market returns), not coin-specific ones.
  V5  On the desk's 92 live forward calls the picks stay indistinguishable from all calls (|t| < 2).

RESULT (2026-11-15, logs/combo_screen.txt): 0 of 18 cells pass (smallest p 0.084); selected R/bet negative in 2025-26 in 18 of 18. POWER CHECK: the screened ridge recovers a planted +0.10R / sd skill only as +0.025R (bet-level Welch t +0.8; a perfect sort would
give +0.175R) - V1 WRONG. The screen keeps REGIME-LEVEL features (side, atr_pct, bb_w in 16 of 16 folds; 15 distinct features, 7 of them in under half of the folds), which flip out of sample; with the skill planted a_ret24 is kept in 16 of 16 folds yet the level features
still dominate the selection. V2, V3, V5 right (live |t| <= 0.3); V4 half right (unstable, but the most-kept features are volatility / side, not market-regime ones). SUPERSEDED IN PART: the bet-level gate (a day-vote mean) was the wrong instrument - combo_rowcheck.py re-scores per call.

    python -m backtest.combo_screen        writes logs/combo_screen.txt          tests: python tests/test_combo_meta.py (screen_top, fit_model 'sridge'), tests/test_combo_wide.py (screened_names)
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import combo_meta as cm  # noqa: E402
from backtest import combo_universe as cu  # noqa: E402

LOG = ROOT / "logs" / "combo_screen.txt"
KINDS = (("sridge", "P"), ("sridge", "P+E"))


def screened_names(X: pd.DataFrame, calls: pd.DataFrame, y: np.ndarray | None = None) -> list:
    """For every fold, the names of the K features the screen keeps (the same steps as fit_model)."""
    y = calls.r_net.to_numpy() if y is None else y
    t_ms = calls.made_ms.to_numpy()
    starts = cm.fold_starts(calls.t)
    Xv = X.to_numpy(float)
    out = []
    for a, b in zip(starts[:-1], starts[1:]):
        te = ((calls.t >= a) & (calls.t < b)).to_numpy()
        tr = t_ms + cm.EMBARGO_MS < int(a.timestamp() * 1000)
        if te.sum() == 0 or tr.sum() < cm.MIN_TRAIN:
            continue
        keep = cm.usable_columns(Xv[tr])
        Xk = Xv[tr][:, keep]
        Z = cm.Prep().fit(Xk).transform(Xk)
        top = cm.screen_top(Z, np.clip(y[tr], cm.CLIP_LO, cm.CLIP_HI), cm.SCREEN_K)
        names = np.array(X.columns)[keep][top]
        out.append(list(names))
    return out


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    rng = np.random.default_rng(20261115)
    bars = {s: cm.load_bars(s) for s in cm.SYMS}
    feats = {s: cm.symbol_features(bars[s]) for s in cm.SYMS}
    mkt = cm.market_frame(feats)
    say(f"backtest/combo_screen.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the screened ridge (K = {cm.SCREEN_K}) on fixed-bracket candidates, 5 markets, both sides, every 6th hour; walk-forward quarterly folds from {cm.FIRST_OOS:%Y-%m-%d}; 12bp")

    results = {}
    cells = []
    for gname, geom in cu.GEOMS.items():
        d = cu.candidate_frame(bars, geom)
        Xp = cm.call_features(d, feats, mkt)
        Xe = cm.panel_features(d)
        sets = cm.feature_sets(Xp, Xe)
        models = {}
        for kind, sname in KINDS:
            sub = d if sname == "P" else d[d.t < cm.PANEL_CALLS_UNTIL]
            wf = cm.walk_forward(sub, sets[sname].loc[sub.index], kind)
            models[f"{kind} {sname}"] = (sub, wf)
        results[gname] = (d, Xp, sets, models)
        say()
        say(f"=== {gname}: stop {geom[0] * 100:.1f}% / target {geom[1] * 100:.1f}% / {geom[2]}h: {len(d):,} candidates, all-candidate mean R {d[d.t >= cm.FIRST_OOS].r_net.mean():+.3f} out of sample")
        for m, (s_, w_) in models.items():
            x = s_.join(w_)
            x = x[x.pred.notna()]
            say(f"    {m:<11} fee-free IC {sps.spearmanr(x.pred, x.r_net + cu.FEE / geom[0])[0]:+.3f}; IC vs R 2023-24 {sps.spearmanr(x[x.t < cm.HALF_SPLIT].pred, x[x.t < cm.HALF_SPLIT].r_net)[0]:+.3f}, "
                f"2025-26 {sps.spearmanr(x[x.t >= cm.HALF_SPLIT].pred, x[x.t >= cm.HALF_SPLIT].r_net)[0]:+.3f}")
        cells += [(gname,) + r for r in cu.cells_for(d, models)]

    adj18 = cm.holm([r[3]["p"] for r in cells])
    say()
    say("THE 18 CELLS (selected = top fraction by predicted R in each fold; difference = selected bets' mean R minus all bets' mean R; Holm over these 18)")
    npass = 0
    for (g, m, fr, c, _), a in zip(cells, adj18):
        ok = cm.passes(c, float(a))
        npass += ok
        f, h1, h2 = c["full"], c["h1"], c["h2"]
        say(f"  {g} {m:<11} top {int(fr * 100):>2}%  n {f['n']:>6} bets {f['bets']:>4}/{f['all_bets']}  selected {f['sel_r']:+.3f} vs all {f['all_r']:+.3f} = {f['diff']:+.3f} (t {f['t']:+.1f})  hit {f['hit'] * 100:4.1f}% vs {f['base'] * 100:4.1f}%  "
            f"halves diff {h1['diff']:+.3f} / {h2['diff']:+.3f}, selected {h1['sel_r']:+.3f} / {h2['sel_r']:+.3f}  Holm {a:.3f}  {'PASS' if ok else 'no'}")
    say(f"  cells passing: {npass} of {len(cells)}; with the 27 cells of combo_universe the family is 45 cells (the smallest p here is {min(r[3]['p'] for r in cells):.4f}; Bonferroni over 45 = {min(1.0, 45 * min(r[3]['p'] for r in cells)):.3f})")
    neg = sum(1 for r in cells if r[3]["h2"]["sel_r"] < 0)
    say(f"  selected R/bet negative in 2025-26 in {neg} of {len(cells)} cells")

    # ---- the power check
    say()
    say("POWER CHECK (G1, screened ridge on P, top 10%): planted skills of +0.10 / +0.05 / +0.025R per sd of the rank-normal direction-aligned 24h return, and shuffled labels")
    d, Xp, sets, _ = results["G1"]
    pw = {}
    for lab, y in (("planted +0.10R / sd", cm.plant(d, Xp, 0.10)), ("planted +0.05R / sd", cm.plant(d, Xp, 0.05)), ("planted +0.025R / sd", cm.plant(d, Xp, 0.025)),
                   ("placebo (shuffled labels)", rng.permutation(d.r_net.to_numpy())), ("no plant (the real labels)", d.r_net.to_numpy())):
        d2 = d.copy()
        d2["r_net"] = y
        wf = cm.walk_forward(d2, Xp, "sridge", y=y)
        cc = cm.cell(d2.join(wf), "pred", 0.10)
        f = cc["full"]
        pw[lab] = f
        say(f"  {lab:<28} selected {f['sel_r']:+.3f} vs all {f['all_r']:+.3f} = {f['diff']:+.3f} (Welch t {f['t']:+.1f}), halves {cc['h1']['diff']:+.3f} / {cc['h2']['diff']:+.3f}")
    names = screened_names(Xp, d)
    cnt = Counter(n for fold in names for n in fold)
    stable = [(n, k) for n, k in cnt.most_common()]
    say(f"  the screen over {len(names)} folds (G1, P): {len(cnt)} distinct features kept; most often: " + ", ".join(f"{n} {k}/{len(names)}" for n, k in stable[:10]))
    say(f"  kept in fewer than half of the folds: {sum(1 for _, k in stable if k < len(names) / 2)} of {len(cnt)}")
    ya = cm.plant(d, Xp, 0.10)
    namesp = screened_names(Xp, d, ya)
    cntp = Counter(n for fold in namesp for n in fold)
    say(f"  with the +0.10R / sd skill planted, a_ret24 is kept in {cntp.get('a_ret24', 0)} of {len(namesp)} folds")

    # ---- the live forward calls
    say()
    say("THE LIVE FORWARD CALLS (the desk's 92 resolved crypto calls, never seen by any fit): the screened ridge trained on ALL candidates of each bracket up to 2026-10-25, applied to the live calls' own features")
    live = cm.load_live_calls()
    Xl, _ = cm.build_table(live, extend=True)
    live["fold"] = 0
    for gname, geom in cu.GEOMS.items():
        d, Xp, _, _ = results[gname]
        tr = d.made_ms.to_numpy() + cm.EMBARGO_MS < int(pd.Timestamp("2026-10-26").timestamp() * 1000)
        live["p"] = cm.fit_model("sridge", Xp.to_numpy(float)[tr], d.r_net.to_numpy()[tr])(Xl.reindex(columns=Xp.columns).to_numpy(float))
        for fr in (0.33, 0.50):
            st_ = cm.half_stats(live, cm.select(live, "p", fr))
            say(f"  {gname} top {int(fr * 100)}%: n {st_['n']} bets {st_['bets']}  selected {st_['sel_r']:+.2f} vs all {st_['all_r']:+.2f} = {st_['diff']:+.2f} (Welch t {st_['t']:+.1f})  hit {st_['hit'] * 100:.0f}% vs random {st_['base'] * 100:.0f}%")
    say()
    say(f"PREDICTIONS (registered before the run): V2 cells passing {npass} of {len(cells)}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
