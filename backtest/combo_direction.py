"""THE COMBINATION TEST, DIRECTION FEATURES ONLY: strip out everything that is a regime LEVEL and keep only what points one way (2026-11-15)

THE USER (2026-11-15, /goal): "find an edge that gives good signals - a perfect combination of every signal, or everything you have so far, including the forward data from the Analyst desk."
combo_screen.py (screened ridge, 18 cells) found nothing, and its power check showed why a null there is weak: with a planted +0.10R-per-sd skill the screened ridge picked only +0.025R of the ~+0.17R a perfect sort would give. The screen
kept side / atr_pct / bb_w in 16 of 16 folds - REGIME LEVEL features that say how often a fixed 2:1 bracket decides, not which way price goes; they carry quarter-specific noise that flips out of sample and drowns a small direction skill.
A signal combination is a claim about DIRECTION, so this file gives the models ONLY the direction-aligned features (the sign of each already flips with the side of the trade): rsi_aligned, d_rsi_aligned and the eleven a_* features
(a_ret24, a_ret168, a_d_ma1000, a_bb_z, a_rng_pos24, a_d_sma50, a_d_ret7, a_rel_btc24, a_rel_btc168, a_btc_ret24, a_mkt_ret24) = 13 features, no `side`, no volatility, no calendar. Everything else is combo_universe's: a FIXED trade at every 6th
hour on BTC ETH SOL XRP BNB, both sides, brackets G1 1.2% / 2.4% / 24h, G2 1.2% / 3.6% / 24h, G3 2% / 4% / 48h, 12bp, quarterly walk-forward from 2023-01, 72h embargo, the combo_meta gate (selected bets minus all bets, Welch t >= 2; selected R/bet
>= +0.05 and > 0 in BOTH halves; difference > 0 in both; hit above the same-side same-quarter random-entry hit rate in both; >= 150 bets; Holm). Models: a ridge (alpha 300) and gradient boosting on the 13, x 3 brackets x top 5 / 10 / 20% = 18 cells.
FAMILY SIZE: combo_universe 27 + combo_screen 18 + these 18 = 63 cells on the same candidates; the Bonferroni figure over 63 is printed beside Holm over these 18.
FIRST THE POWER CHECK: a planted +0.10 / +0.05 / +0.025R-per-sd skill on the rank-normal aligned 24h return, a shuffled-label placebo, and the real labels.
DIAGNOSTICS (not in the gate, not counted): the single aligned features as the whole 'model' - momentum (a_ret24) and reversal (-a_ret24), range position, Bollinger z - top 10% in G1.

REGISTERED BEFORE THE FIRST RUN (2026-11-15; prior that at least one of the 18 cells passes: 3%)
  W1  The direction-only ridge recovers a planted +0.10R-per-sd skill (selected minus all >= +0.08R, Welch t >= 2) and +0.05R-per-sd at t >= 1.5; the shuffled placebo does not pass. (priors 85% / 60%)
  W2  No cell of the 18 passes.
  W3  Selected R/bet is negative in 2025-26 in most cells (the regime decay combo_universe and combo_screen showed).
  W4  The single-feature diagnostics are all inside +-2 se of zero on the real labels; the best of them is not the same sign in both halves.
  W5  On the desk's 92 live forward calls the picks stay indistinguishable from all calls (|t| < 2).

RESULT (2026-11-15, logs/combo_direction.txt): 0 of 18 cells pass at the bet level (smallest p 0.0071; Bonferroni over the 63 cells tried on these candidates 0.446); selected R/bet negative in 2025-26 in 18 of 18. The bet-level power check still failed (ridge: planted
+0.10R / sd read +0.014, t +0.5; hgb -0.010) - W1 WRONG. The post-hoc DIAGNOSTIC '-a_rng_pos24' (selected +0.051 vs all -0.097 = +0.147, t +4.5, both halves) was an ARTIFACT - W4 WRONG: the feature is not centred, so the selection was short-only and was compared with an all-sides
baseline, and the bet (day + side) mean is a day-vote mean; per call it is -0.157R vs -0.096R with a shift-null p of 0.983 (combo_rangerev.py). W2, W3 right; W5 right at the bet level (live |t| <= 0.5). The same 13-feature ridge, scored PER CALL, is the one lead in combo_rowcheck.py.

    python -m backtest.combo_direction        writes logs/combo_direction.txt          tests: tests/test_combo_wide.py (direction_columns)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import combo_meta as cm  # noqa: E402
from backtest import combo_universe as cu  # noqa: E402

LOG = ROOT / "logs" / "combo_direction.txt"
KINDS = ("ridge", "hgb")
DIRECTION = ["rsi_aligned", "d_rsi_aligned", "a_ret24", "a_ret168", "a_d_ma1000", "a_bb_z", "a_rng_pos24", "a_d_sma50", "a_d_ret7", "a_rel_btc24", "a_rel_btc168", "a_btc_ret24", "a_mkt_ret24"]
FAMILY = 27 + 18 + 18


def direction_columns(X: pd.DataFrame) -> list:
    """The direction-aligned columns, in a fixed order; every name must exist."""
    missing = [c for c in DIRECTION if c not in X.columns]
    assert not missing, f"missing direction features: {missing}"
    return list(DIRECTION)


def single_feature_cells(d: pd.DataFrame, Xd: pd.DataFrame, frac: float = 0.10) -> list:
    """A single aligned feature as the whole model, scored by the same cell (the prediction is the feature, or minus it for the reversal reading). Diagnostics only."""
    rows = []
    for name, col, sgn in (("momentum  a_ret24", "a_ret24", 1.0), ("reversal -a_ret24", "a_ret24", -1.0), ("range pos  a_rng_pos24", "a_rng_pos24", 1.0), ("range pos -a_rng_pos24", "a_rng_pos24", -1.0),
                           ("bollinger a_bb_z", "a_bb_z", 1.0), ("bollinger -a_bb_z", "a_bb_z", -1.0), ("trend a_d_sma50", "a_d_sma50", 1.0), ("trend -a_d_sma50", "a_d_sma50", -1.0)):
        x = d[d.t >= cm.FIRST_OOS].copy()
        x["pred"] = sgn * Xd.loc[x.index, col].to_numpy(float)
        x["fold"] = x.t.dt.to_period("Q").dt.start_time
        rows.append((name, cm.cell(x, "pred", frac)))
    return rows


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    rng = np.random.default_rng(20261115)
    bars = {s: cm.load_bars(s) for s in cm.SYMS}
    feats = {s: cm.symbol_features(bars[s]) for s in cm.SYMS}
    mkt = cm.market_frame(feats)
    say(f"backtest/combo_direction.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; direction-aligned features only ({len(DIRECTION)}), fixed brackets, 5 markets, both sides, every 6th hour; walk-forward quarterly folds from {cm.FIRST_OOS:%Y-%m-%d}; 12bp")

    results, cells = {}, []
    for gname, geom in cu.GEOMS.items():
        d = cu.candidate_frame(bars, geom)
        Xp = cm.call_features(d, feats, mkt)
        Xd = Xp[direction_columns(Xp)]
        models = {}
        for kind in KINDS:
            models[f"{kind} D"] = (d, cm.walk_forward(d, Xd, kind))
        results[gname] = (d, Xp, Xd, models)
        say()
        say(f"=== {gname}: stop {geom[0] * 100:.1f}% / target {geom[1] * 100:.1f}% / {geom[2]}h: {len(d):,} candidates, all-candidate mean R {d[d.t >= cm.FIRST_OOS].r_net.mean():+.3f} out of sample")
        for m, (s_, w_) in models.items():
            x = s_.join(w_)
            x = x[x.pred.notna()]
            say(f"    {m:<8} fee-free IC {sps.spearmanr(x.pred, x.r_net + cu.FEE / geom[0])[0]:+.3f}; IC vs R 2023-24 {sps.spearmanr(x[x.t < cm.HALF_SPLIT].pred, x[x.t < cm.HALF_SPLIT].r_net)[0]:+.3f}, "
                f"2025-26 {sps.spearmanr(x[x.t >= cm.HALF_SPLIT].pred, x[x.t >= cm.HALF_SPLIT].r_net)[0]:+.3f}")
        cells += [(gname,) + r for r in cu.cells_for(d, models)]

    adj = cm.holm([r[3]["p"] for r in cells])
    say()
    say("THE 18 CELLS (selected = top fraction by predicted R in each fold; difference = selected bets' mean R minus all bets' mean R; Holm over these 18)")
    npass = 0
    for (g, m, fr, c, _), a in zip(cells, adj):
        ok = cm.passes(c, float(a))
        npass += ok
        f, h1, h2 = c["full"], c["h1"], c["h2"]
        say(f"  {g} {m:<8} top {int(fr * 100):>2}%  n {f['n']:>6} bets {f['bets']:>4}/{f['all_bets']}  selected {f['sel_r']:+.3f} vs all {f['all_r']:+.3f} = {f['diff']:+.3f} (t {f['t']:+.1f})  hit {f['hit'] * 100:4.1f}% vs {f['base'] * 100:4.1f}%  "
            f"halves diff {h1['diff']:+.3f} / {h2['diff']:+.3f}, selected {h1['sel_r']:+.3f} / {h2['sel_r']:+.3f}  Holm {a:.3f}  {'PASS' if ok else 'no'}")
    pmin = min(r[3]["p"] for r in cells)
    say(f"  cells passing: {npass} of {len(cells)}; smallest p {pmin:.4f}; Bonferroni over the {FAMILY} cells tried on these candidates = {min(1.0, FAMILY * pmin):.3f}")
    say(f"  selected R/bet negative in 2025-26 in {sum(1 for r in cells if r[3]['h2']['sel_r'] < 0)} of {len(cells)} cells")

    say()
    say("POWER CHECK (G1, top 10%): planted skills of +0.10 / +0.05 / +0.025R per sd of the rank-normal direction-aligned 24h return, shuffled labels, and the real labels; the direction-only ridge and the direction-only gradient boosting")
    d, Xp, Xd, _ = results["G1"]
    for kind in KINDS:
        for lab, y in (("planted +0.10R / sd", cm.plant(d, Xd, 0.10)), ("planted +0.05R / sd", cm.plant(d, Xd, 0.05)), ("planted +0.025R / sd", cm.plant(d, Xd, 0.025)),
                       ("placebo (shuffled labels)", rng.permutation(d.r_net.to_numpy())), ("no plant (the real labels)", d.r_net.to_numpy())):
            d2 = d.copy()
            d2["r_net"] = y
            wf = cm.walk_forward(d2, Xd, kind, y=y)
            cc = cm.cell(d2.join(wf), "pred", 0.10)
            f = cc["full"]
            say(f"  {kind:<5} {lab:<28} selected {f['sel_r']:+.3f} vs all {f['all_r']:+.3f} = {f['diff']:+.3f} (Welch t {f['t']:+.1f}), halves {cc['h1']['diff']:+.3f} / {cc['h2']['diff']:+.3f}")
    say(f"  a perfect sort by the planted feature would give the top 10% a mean uplift of about +1.75 sd x the planted R: +0.175R at +0.10R / sd")

    say()
    say("DIAGNOSTICS, not gate cells: one aligned feature as the whole model (G1, top 10%, whole walk-forward period)")
    for name, c in single_feature_cells(d, Xd):
        f, h1, h2 = c["full"], c["h1"], c["h2"]
        say(f"  {name:<24} selected {f['sel_r']:+.3f} vs all {f['all_r']:+.3f} = {f['diff']:+.3f} (t {f['t']:+.1f})  halves diff {h1['diff']:+.3f} / {h2['diff']:+.3f}")

    say()
    say("THE LIVE FORWARD CALLS (the desk's 92 resolved crypto calls, never seen by any fit): direction-only models trained on ALL candidates of each bracket up to 2026-10-25, applied to the live calls' own features")
    live = cm.load_live_calls()
    Xl, _ = cm.build_table(live, extend=True)
    live["fold"] = 0
    for gname in cu.GEOMS:
        d, Xp, Xd, _ = results[gname]
        tr = d.made_ms.to_numpy() + cm.EMBARGO_MS < int(pd.Timestamp("2026-10-26").timestamp() * 1000)
        Xlive = Xl.reindex(columns=Xd.columns).to_numpy(float)
        for kind in KINDS:
            live["p"] = cm.fit_model(kind, Xd.to_numpy(float)[tr], d.r_net.to_numpy()[tr])(Xlive)
            for fr in (0.33, 0.50):
                st_ = cm.half_stats(live, cm.select(live, "p", fr))
                say(f"  {gname} {kind:<5} top {int(fr * 100)}%: n {st_['n']} bets {st_['bets']}  selected {st_['sel_r']:+.2f} vs all {st_['all_r']:+.2f} = {st_['diff']:+.2f} (Welch t {st_['t']:+.1f})  hit {st_['hit'] * 100:.0f}% vs random {st_['base'] * 100:.0f}%")
    say()
    say(f"PREDICTIONS (registered before the run): W2 cells passing {npass} of {len(cells)}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
