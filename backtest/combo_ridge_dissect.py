"""THE ONE CELL THAT SURVIVES A PER-CALL RE-SCORE: the direction-only ridge, top 5% - dissected before it is believed (2026-11-15)

combo_rowcheck.py re-scored 36 gate cells PER CALL (the gate averaged per UTC day + side, the repo's 'day-vote' trap) and found one that looks like an edge: G1 (1.2% stop / 2.4% target / 24h), a ridge on the 13 direction-aligned features, the top 5% of each
quarterly fold: selected +0.051R per call against -0.084R for all same-side calls = +0.135R (weekly-cluster t +3.1, circular shift-null p 0.002), selected +0.080 in 2023-24 and +0.019 in 2025-26. It was the BEST of 36 cells. The earlier control (all calls of the same side)
is NOT matched on quarter, hour of day or volatility, and the first rangerev result flipped sign when it was matched. So, before anyone calls it an edge:
  (1) the per-call numbers by half, year and quarter, with the best weeks removed (concentration);
  (2) selected vs unselected calls of the SAME side in the SAME quarter, and also the same hour of day and the same volatility tercile; the circular-shift null on that matched excess;
  (3) the PREDICTION-DECILE PROFILE: if the model has real skill the mean R rises across the whole range of its predictions, not only in the top 5%;
  (4) what the selection is: side mix, coins, hours, the ridge's coefficients and their sign stability over the 16 folds;
  (5) the per-call power check: a planted +0.10 / +0.05R-per-sd skill and a placebo through the same pipeline, scored per call (the bet-level gate could not see a planted +0.10R / sd; if the per-call score can, the instrument is fixed);
  (6) the other two brackets and fractions, for the consistency of the sign (not for another pick).
FAMILY: this is the best of 36 cells, themselves following 63 bet-level cells on the same candidates; the shift-null p of the best of 36 is multiplied by 36 here.

REGISTERED BEFORE THE FIRST RUN (2026-11-15; prior that the lead survives every check below: 10%)
  D1  The matched (quarter x side x hour x volatility) excess is at most 60% of the same-side excess (prior 60%).
  D2  The effect is concentrated: removing the best 10 weeks of the selected calls cuts the excess by more than half (prior 60%).
  D3  The prediction-decile profile is not monotone: the top 5% pops, the rest is flat or noisy (Spearman of decile vs mean R below +0.7; prior 60%).
  D4  The effect is mostly one side (more than 70% of the excess comes from one side; prior 55%).
  D5  The per-call planted-skill check recovers a +0.10R-per-sd skill with an excess of at least +0.10R (prior 70%).
  D6  The matched excess has a shift-null p above 0.01 (prior 55%).
  D7  More than half of the ridge's coefficients change sign across folds (prior 70%).

RESULT (2026-11-15, logs/combo_ridge_dissect.txt): the lead survives the checks that were meant to kill it and breaks on decay and on a new universe. Matched excess +0.149 (quarter x hour x volatility; D1 WRONG: not smaller), shift-null p 0.002 / 0.007 (D6 WRONG), prediction
deciles MONOTONE (Spearman +0.94; decile 10 +0.010R, decile 1 -0.180R; D3 WRONG), the ridge's coefficients are sign-stable (1 of 13 below 75% - D7 WRONG), the per-call power check recovers planted skills (+0.10R / sd -> +0.224R, t +4.9; +0.025 -> +0.136; placebo -0.008; D5 right).
WHAT IT IS: 85% shorts (88% of the excess) of coins that are weak against BTC over a week, RSI-low and below their Bollinger band = trend-CONTINUATION shorts, the 2023-26 alt bleed. WHERE IT BREAKS: the absolute selected mean is only +0.051R (= +6bp a trade after the 12bp fee), +0.080 in 2023-24
and +0.019 in 2025-26 (2026 -0.010R; 2026Q3 excess -0.20); the best 20 of 191 weeks removed leave -0.007R (D2 right - though removing the best weeks is itself a cherry-pick); G2 / G3 smaller (+0.091 / +0.045); and it is the best of 36 per-call cells (shift p 0.0025 x 36 = 0.09).

    python -m backtest.combo_ridge_dissect        writes logs/combo_ridge_dissect.txt
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import combo_direction as cd  # noqa: E402
from backtest import combo_meta as cm  # noqa: E402
from backtest import combo_rangerev as rr  # noqa: E402
from backtest import combo_rowcheck as rc  # noqa: E402
from backtest import combo_universe as cu  # noqa: E402

LOG = ROOT / "logs" / "combo_ridge_dissect.txt"
TOPFRAC = 0.05


def fold_coefficients(d: pd.DataFrame, Xd: pd.DataFrame) -> pd.DataFrame:
    """The ridge's standardised coefficients in every fold (the same fit as cm.fit_model('ridge'))."""
    from sklearn.linear_model import Ridge
    y = d.r_net.to_numpy()
    t_ms = d.made_ms.to_numpy()
    Xv = Xd.to_numpy(float)
    rows = []
    starts = cm.fold_starts(d.t)
    for a, b in zip(starts[:-1], starts[1:]):
        te = ((d.t >= a) & (d.t < b)).to_numpy()
        tr = t_ms + cm.EMBARGO_MS < int(a.timestamp() * 1000)
        if te.sum() == 0 or tr.sum() < cm.MIN_TRAIN:
            continue
        keep = cm.usable_columns(Xv[tr])
        p = cm.Prep().fit(Xv[tr][:, keep])
        m = Ridge(alpha=300.0).fit(p.transform(Xv[tr][:, keep]), np.clip(y[tr], cm.CLIP_LO, cm.CLIP_HI))
        c = pd.Series(np.nan, index=Xd.columns)
        c[np.array(Xd.columns)[keep]] = m.coef_
        rows.append(c.rename(a))
    return pd.DataFrame(rows)


def excess_weekly(x: pd.DataFrame, sel: pd.Series) -> pd.DataFrame:
    """Per-week sums of (selected call R - the same-side mean R) and call counts, for the concentration check."""
    s = x[sel]
    ctl = x.groupby("side").r_net.mean()
    e = s.r_net.to_numpy() - ctl.reindex(s.side).to_numpy()
    return pd.DataFrame({"e": e, "wk": s.t.dt.to_period("W").astype(str).to_numpy()}).groupby("wk").e.agg(["sum", "size"])


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    rng = np.random.default_rng(20261115)
    bars = {s: cm.load_bars(s) for s in cm.SYMS}
    feats = {s: cm.symbol_features(bars[s]) for s in cm.SYMS}
    mkt = cm.market_frame(feats)
    say(f"backtest/combo_ridge_dissect.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the direction-only ridge, top {int(TOPFRAC * 100)}% per fold, dissected; fixed brackets, 12bp")
    built = {}
    for gname, geom in cu.GEOMS.items():
        d = cu.candidate_frame(bars, geom)
        Xp = cm.call_features(d, feats, mkt)
        Xd = Xp[cd.direction_columns(Xp)]
        d["hour"] = ((d.made_ms // cm.H1) % 24).astype(int)
        d["atr"] = Xp.atr_pct.to_numpy(float)
        d["q"] = d.t.dt.to_period("Q").astype(str)
        d["atr_t"] = d.groupby("q").atr.transform(lambda v: pd.qcut(v, 3, labels=False, duplicates="drop"))
        wf = cm.walk_forward(d, Xd, "ridge")
        built[gname] = (d, Xd, wf)
    d, Xd, wf = built["G1"]
    x = d.join(wf)
    x = x[x.pred.notna()].copy()
    sel = cm.select(x, "pred", TOPFRAC)
    base = rc.per_call(x, sel)

    say()
    say(f"(1) G1 ridge D top {int(TOPFRAC * 100)}%: per-call selected {base['sel_r']:+.3f} vs same-side {base['ctl_r']:+.3f} = {base['diff']:+.3f} (weekly-cluster t {base['t']:+.1f}), n {base['n']}")
    for lab, m in (("2023-24", x.t < cm.HALF_SPLIT), ("2025-26", x.t >= cm.HALF_SPLIT)):
        b_ = rc.per_call(x[m], sel[m])
        say(f"    {lab}: selected {b_['sel_r']:+.3f} vs same-side {b_['ctl_r']:+.3f} = {b_['diff']:+.3f} (t {b_['t']:+.1f}), n {b_['n']}")
    for yr, m in x.groupby(x.t.dt.year):
        b_ = rc.per_call(x.loc[m.index], sel[m.index])
        say(f"    {yr}: selected {b_['sel_r']:+.3f} vs same-side {b_['ctl_r']:+.3f} = {b_['diff']:+.3f} (t {b_['t']:+.1f}), n {b_['n']}")
    qs = x.groupby("q")
    pos_q = 0
    nq = 0
    qrows = []
    for qn, g in qs:
        s_ = sel[g.index]
        if s_.sum() < 20:
            continue
        b_ = rc.per_call(g, s_)
        nq += 1
        pos_q += b_["diff"] > 0
        qrows.append(f"{qn} {b_['diff']:+.2f}({b_['n']})")
    say(f"    per quarter excess (n selected): " + "  ".join(qrows))
    say(f"    quarters with a positive excess: {pos_q} of {nq}")
    wk = excess_weekly(x, sel)
    tot_n, tot_e = wk["size"].sum(), wk["sum"].sum()
    for k in (5, 10, 20):
        top = wk.sort_values("sum", ascending=False).head(k)
        rest_e, rest_n = tot_e - top["sum"].sum(), tot_n - top["size"].sum()
        say(f"    best {k:>2} weeks removed ({int(top['size'].sum())} calls): excess {rest_e / rest_n:+.3f} (all weeks {tot_e / tot_n:+.3f}; {wk.shape[0]} weeks)")

    say()
    say("(2) MATCHED CONTROLS (selected vs unselected calls of the same side in the same stratum; weighted by selected calls)")
    x2 = x.assign(hour_bin=x.hour)
    matched = {}
    for lab, strata in (("same side only (above)", None), ("+ same quarter", ["q"]), ("+ quarter and hour of day", ["q", "hour_bin"]), ("+ quarter and volatility tercile", ["q", "atr_t"]), ("+ quarter, hour and volatility tercile", ["q", "hour_bin", "atr_t"])):
        if strata is None:
            say(f"    {lab:<42} excess {base['diff']:+.3f}")
            continue
        dm, nu = rr.matched_diff(x2, sel, strata)
        matched[lab] = dm
        say(f"    {lab:<42} matched excess {dm:+.3f}  ({nu} selected calls)")
    full = matched["+ quarter, hour and volatility tercile"]
    obs, p, sd = rr.shift_null(x, sel, rng)
    say(f"    circular-shift null on the same-side excess: observed {obs:+.3f}, null sd {sd:.3f}, p = {p:.3f}")
    # shift null for the matched excess: shift the selection flag and recompute the matched difference
    series = [np.flatnonzero(((x.symbol == s_) & (x.side == sd_)).to_numpy()) for s_ in x.symbol.unique() for sd_ in ("long", "short")]
    xs = x2.sort_values("made_ms", kind="stable")
    sel_sorted = sel.reindex(xs.index).to_numpy()
    series = [np.flatnonzero(((xs.symbol == s_) & (xs.side == sd_)).to_numpy()) for s_ in xs.symbol.unique() for sd_ in ("long", "short")]
    nulls = []
    for _ in range(150):
        k = int(rng.integers(10, 300)) * 4
        sh = np.zeros(len(xs), bool)
        for idx in series:
            sh[idx] = np.roll(sel_sorted[idx], k)
        nulls.append(rr.matched_diff(xs, pd.Series(sh, index=xs.index), ["q", "hour_bin", "atr_t"])[0])
    nulls = np.array(nulls)
    pm = float((1 + (nulls >= full).sum()) / (1 + len(nulls)))
    say(f"    circular-shift null on the fully matched excess: observed {full:+.3f}, null mean {np.nanmean(nulls):+.3f}, sd {np.nanstd(nulls):.3f}, p = {pm:.3f} (150 shifts); Bonferroni over the 36 cells: {min(1.0, 36 * pm):.2f}")

    say()
    say("(3) PREDICTION-DECILE PROFILE (G1, per-call mean R of ALL calls in each decile of the prediction within (fold, side))")
    key = pd.Series(list(zip(x.fold, x.side)), index=x.index)
    dec = np.ceil(x.pred.groupby(key).rank(pct=True, method="first") * 10).clip(1, 10).astype(int)
    prof = x.groupby(dec).r_net.agg(["mean", "std", "size"])
    for k, r_ in prof.iterrows():
        say(f"    decile {k:>2}: mean R {r_['mean']:+.3f} (se {r_['std'] / math.sqrt(r_['size']):.3f}, n {int(r_['size']):,})")
    say(f"    Spearman of decile vs mean R {sps.spearmanr(prof.index, prof['mean'])[0]:+.2f}; top 5% vs the 5-10% band below it:")
    top5 = x[sel]
    nxt = x[(cm.select(x, "pred", 0.10)) & ~sel]
    say(f"    top 5% {top5.r_net.mean():+.3f} (n {len(top5)}), next 5% {nxt.r_net.mean():+.3f} (n {len(nxt)}), the other 90% {x[~cm.select(x, 'pred', 0.10)].r_net.mean():+.3f}")

    say()
    say("(4) WHAT THE SELECTION IS")
    s_ = x[sel]
    say(f"    side mix: {s_.side.value_counts(normalize=True).round(3).to_dict()}; coins: {s_.symbol.value_counts(normalize=True).round(3).to_dict()}")
    say(f"    hours (UTC): {s_.hour.value_counts(normalize=True).sort_index().round(3).to_dict()}")
    ctl_side = x.groupby("side").r_net.mean()
    for sd_ in ("long", "short"):
        g = s_[s_.side == sd_]
        e = g.r_net.mean() - ctl_side[sd_]
        say(f"    {sd_:<5}: n {len(g)} selected {g.r_net.mean():+.3f} vs same-side {ctl_side[sd_]:+.3f} = {e:+.3f}; share of the total excess {(e * len(g)) / (base['diff'] * base['n']):.2f}")
    sel_feat = Xd.loc[s_.index].mean()
    all_feat = Xd.loc[x.index].mean()
    sdv = Xd.loc[x.index].std()
    say("    selected-call mean of each feature, in standard deviations from the all-call mean: " + ", ".join(f"{c} {((sel_feat[c] - all_feat[c]) / sdv[c]):+.2f}" for c in Xd.columns))
    coefs = fold_coefficients(d, Xd)
    stab = []
    for c in Xd.columns:
        v = coefs[c].dropna()
        stab.append((c, v.mean(), (np.sign(v) == np.sign(v.mean())).mean() if len(v) else float("nan")))
    say("    ridge coefficients (standardised), mean over folds and share of folds with the mean's sign: " + ", ".join(f"{c} {m:+.3f} ({s:.0%})" for c, m, s in stab))
    flips = sum(1 for _, _, s in stab if s < 0.75)
    say(f"    features whose sign is not the same in 75% of the folds: {flips} of {len(stab)}")

    say()
    say("(5) PER-CALL POWER CHECK (G1, ridge D, top 5%): planted skill +0.10 / +0.05 / +0.025R per sd of the rank-normal aligned 24h return, placebo (shuffled labels), real labels - scored per call vs the same-side mean")
    for lab, y in (("planted +0.10R / sd", cm.plant(d, Xd, 0.10)), ("planted +0.05R / sd", cm.plant(d, Xd, 0.05)), ("planted +0.025R / sd", cm.plant(d, Xd, 0.025)),
                   ("placebo (shuffled)", rng.permutation(d.r_net.to_numpy())), ("real labels", d.r_net.to_numpy())):
        d2 = d.copy()
        d2["r_net"] = y
        w2 = cm.walk_forward(d2, Xd, "ridge", y=y)
        x_ = d2.join(w2)
        x_ = x_[x_.pred.notna()]
        s2 = cm.select(x_, "pred", TOPFRAC)
        b_ = rc.per_call(x_, s2)
        say(f"    {lab:<24} selected {b_['sel_r']:+.3f} vs same-side {b_['ctl_r']:+.3f} = {b_['diff']:+.3f} (t {b_['t']:+.1f})")
    say("    a perfect sort on the planted feature would give the top 5% about +2.06 sd x the planted R: +0.21R at +0.10R / sd")

    say()
    say("(6) THE OTHER BRACKETS AND FRACTIONS (per call, ridge D; excess over same-side, halves' selected means)")
    for gname in ("G1", "G2", "G3"):
        dd, _, w = built[gname]
        xx = dd.join(w)
        xx = xx[xx.pred.notna()]
        for fr in (0.05, 0.10, 0.20):
            s2 = cm.select(xx, "pred", fr)
            b_ = rc.per_call(xx, s2)
            h1 = rc.per_call(xx[xx.t < cm.HALF_SPLIT], s2[xx.t < cm.HALF_SPLIT])
            h2 = rc.per_call(xx[xx.t >= cm.HALF_SPLIT], s2[xx.t >= cm.HALF_SPLIT])
            say(f"    {gname} top {int(fr * 100):>2}%: excess {b_['diff']:+.3f} (t {b_['t']:+.1f}); selected {b_['sel_r']:+.3f} (halves {h1['sel_r']:+.3f} / {h2['sel_r']:+.3f})")

    say()
    say(f"PREDICTIONS: D1 matched / same-side = {full / base['diff']:.2f}; D2 see the weeks-removed lines; D3 Spearman {sps.spearmanr(prof.index, prof['mean'])[0]:+.2f}; D5 see (5); D6 matched p {pm:.3f}; D7 sign-unstable features {flips} of {len(stab)}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
