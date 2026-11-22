"""PER-CALL RE-SCORE OF ROUND 1's RICHER MODELS (candle + positioning / funding / news / panel features), then the out-of-universe test of the best (2026-11-15, /goal round 3)

THE USER (2026-11-15, /goal): "find an edge that gives good signals - a perfect combination of every signal, or everything you have so far, including the forward data from the Analyst desk."
combo_rowcheck.py re-scored 36 cells of the screened / direction-only models per call and found one relative lead that did not transfer (combo_wide.py). The 27 cells of combo_universe.py - a ridge on the 55 candle features (P), gradient boosting on P, and gradient boosting on P + the
panel's 91 daily signals (E: funding, crowd positioning, taker flow, open interest, news, unlock schedules ...) - were only ever scored by the bet-level (day + side) gate, which that re-score showed is the wrong instrument (a day-vote mean). The per-call instrument has now been validated by a power check
(a planted +0.10R / sd skill is recovered as +0.224R; the placebo -0.008). So: the same 27 cells, per call, same-side baseline, weekly-cluster t, circular-shift null, BEFORE any further model is built.
THE BAR (fixed before the run; the family is 36 + 27 = 63 per-call cells on these candidates): a cell is a LEAD only if its per-call excess over the same-side calls is >= +0.08R with weekly-cluster t >= 3.0, its selected mean R is >= +0.05 in BOTH halves, and its circular-shift p is below 0.01;
it is believed only if the SAME cell's frozen model (trained on the five majors only) has an excess >= +0.05R and a positive selected mean on the point-in-time top-40 perpetuals outside the five (combo_wide's universe). The best cell by excess is taken to that out-of-universe test whether or not it clears the first bar (E-set cells
only on the coins the panel covers, and only to 2026-09-09).

REGISTERED BEFORE THE FIRST RUN (2026-11-15; prior that any of the 27 cells is a lead that survives the out-of-universe test: 3%)
  L1  No cell has a per-call selected mean >= +0.05R in both halves (prior 93%).
  L2  The best per-call excess among the 27 is below the direction-only ridge's +0.135R (prior 70%).
  L3  Adding the panel signals (hgb P+E vs hgb P) does not lift the per-call excess: the paired difference over the nine matched cells is within +-0.03R on average (prior 70%).
  L4  Any cell with an excess >= +0.08R has a selected mean below +0.05R in 2025-26 (prior 80%).

RESULT (2026-11-15, logs/combo_rowcheck2.txt): per call, 0 of 27 cells have a selected mean >= +0.05R in both halves (L1 right); the best excess is +0.107R (G1 ridge on the 55 candle features, top 5%: selected +0.025R, halves +0.041 / +0.008, t +2.4, shift p 0.005 = 0.31
over 63) - not a lead, and below the direction-only ridge's +0.135 (L2 right); the mean excess over the 27 cells is +0.040R; ADDING THE PANEL SIGNALS (funding, crowd positioning, taker flow, open interest, news, unlocks) does nothing: hgb P+E minus hgb P over nine matched cells -0.001R
on average, range -0.073..+0.058 (L3 right); the one cell above +0.08R is below +0.05R in 2025-26 (L4 right). OUT OF UNIVERSE, the best cell frozen on the five majors and applied to 284 point-in-time perpetuals: excess +0.040R (t +1.6, shift p 0.010) but selected -0.034R (-0.117R after 10bp
of slippage; 87% shorts): a small RELATIVE tilt, negative in absolute terms. Not believed. Round 1's richer models carry no tradable edge when scored per call either.

    python -m backtest.combo_rowcheck2        writes logs/combo_rowcheck2.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import combo_meta as cm  # noqa: E402
from backtest import combo_rangerev as rr  # noqa: E402
from backtest import combo_rowcheck as rc  # noqa: E402
from backtest import combo_universe as cu  # noqa: E402
from backtest import combo_wide as cw  # noqa: E402

LOG = ROOT / "logs" / "combo_rowcheck2.txt"
KINDS = (("ridge", "P"), ("hgb", "P"), ("hgb", "P+E"))
MIN_EXCESS, MIN_T, MIN_SEL, MAX_P = 0.08, 3.0, 0.05, 0.01


def is_lead(c: dict, shift_p: float) -> bool:
    f, h1, h2 = c["full"], c["h1"], c["h2"]
    return bool(f["diff"] >= MIN_EXCESS and f["t"] >= MIN_T and h1["sel_r"] >= MIN_SEL and h2["sel_r"] >= MIN_SEL and shift_p < MAX_P)


def build_wide(say):
    from backtest import wide_book
    elig = {s: m for s, m in wide_book.eligibility(cw.TOPN).items() if m and s not in cm.SYMS}
    wbars = {s: b for s in elig if (b := cw.load_perp(s)) is not None}
    wfeats = {s: cm.symbol_features(b) for s, b in wbars.items()}
    say(f"  wide universe: {len(wbars)} perpetuals outside the five")
    return elig, wbars, wfeats


def wide_test(say, rng, g: str, kind: str, sname: str, frac: float, d5: pd.DataFrame, X5: pd.DataFrame, bars5: dict, feats5: dict, mkt: pd.DataFrame):
    geom = cu.GEOMS[g]
    elig, wbars, wfeats = build_wide(say)
    dw = cw.wide_candidates(wbars, elig, geom)
    allfeats = dict(feats5)
    allfeats.update(wfeats)
    Xw = cm.call_features(dw, allfeats, mkt)
    train, Xtrain = d5, X5
    if sname == "P+E":
        z = np.load(cm.PANEL, allow_pickle=True)
        covered = set(map(str, z["coins"]))
        dw = dw[dw.symbol.isin(covered) & (dw.t < cm.PANEL_CALLS_UNTIL)]
        Xw = pd.concat([Xw.loc[dw.index], cm.panel_features(dw)], axis=1)
        train = d5[d5.t < cm.PANEL_CALLS_UNTIL]
        Xtrain = X5.loc[train.index]
        say(f"  P+E: restricted to {dw.symbol.nunique()} coins the panel covers and to dates before {cm.PANEL_CALLS_UNTIL:%Y-%m-%d}")
    else:
        Xw = Xw.loc[dw.index]
    Xw = Xw.reindex(columns=Xtrain.columns)
    wf = cw.frozen_predictions(train, Xtrain, dw, Xw, kind)
    old = cw.FRAC
    cw.FRAC = frac
    try:
        return cw.report(say, f"frozen {kind} {sname} {g} top {int(frac * 100)}%", dw, wf, rng)
    finally:
        cw.FRAC = old


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    rng = np.random.default_rng(20261115)
    bars = {s: cm.load_bars(s) for s in cm.SYMS}
    feats = {s: cm.symbol_features(bars[s]) for s in cm.SYMS}
    mkt = cm.market_frame(feats)
    say(f"backtest/combo_rowcheck2.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; per-CALL re-score of combo_universe's 27 cells (ridge P, hgb P, hgb P+E x 3 brackets x top 5 / 10 / 20%); fixed brackets, 12bp")
    rows, keep = [], {}
    for gname, geom in cu.GEOMS.items():
        d = cu.candidate_frame(bars, geom)
        Xp = cm.call_features(d, feats, mkt)
        Xe = cm.panel_features(d)
        sets = cm.feature_sets(Xp, Xe)
        keep[gname] = (d, Xp, sets)
        for kind, sname in KINDS:
            sub = d if sname == "P" else d[d.t < cm.PANEL_CALLS_UNTIL]
            wf = cm.walk_forward(sub, sets[sname].loc[sub.index], kind)
            for fr in cu.FRACS:
                rows.append((gname, kind, sname, fr, rc.cell_rows(sub, wf, fr)))
    say()
    say("PER-CALL RESULTS (excess = selected calls' mean R minus the mean R of all calls of the same side(s); t over weekly clusters; 'bet' = the old gate's per-(day, side) excess)")
    n_sel = 0
    for g, kind, sname, fr, c in rows:
        f, h1, h2, b = c["full"], c["h1"], c["h2"], c["bet"]
        n_sel += (h1["sel_r"] >= MIN_SEL) and (h2["sel_r"] >= MIN_SEL)
        say(f"  {g} {kind:<5} {sname:<4} top {int(fr * 100):>2}%  n {f['n']:>5}  selected {f['sel_r']:+.3f} vs same-side {f['ctl_r']:+.3f} = {f['diff']:+.3f} (t {f['t']:+.1f}); halves selected {h1['sel_r']:+.3f} / {h2['sel_r']:+.3f}   bet-level excess {b['diff']:+.3f}")
    say(f"  cells with a per-call selected mean >= +{MIN_SEL:.2f}R in BOTH halves: {n_sel} of {len(rows)}")
    best_i = max(range(len(rows)), key=lambda i: rows[i][4]["full"]["diff"] if np.isfinite(rows[i][4]["full"]["diff"]) else -9)
    ex = [r[4]["full"]["diff"] for r in rows]
    say(f"  best per-call excess: {ex[best_i]:+.3f} ({rows[best_i][0]} {rows[best_i][1]} {rows[best_i][2]} top {int(rows[best_i][3] * 100)}%); mean excess over the 27 cells {np.nanmean(ex):+.3f}; cells with excess >= +{MIN_EXCESS:.2f}: {sum(1 for v in ex if v >= MIN_EXCESS)}")
    # L3: paired hgb P+E minus hgb P
    pe = {(g, fr): c["full"]["diff"] for g, k, s, fr, c in rows if k == "hgb" and s == "P+E"}
    pp = {(g, fr): c["full"]["diff"] for g, k, s, fr, c in rows if k == "hgb" and s == "P"}
    dd = np.array([pe[k] - pp[k] for k in pe])
    say(f"  panel signals added (hgb P+E minus hgb P, nine matched cells): mean {dd.mean():+.3f}, range {dd.min():+.3f}..{dd.max():+.3f}")
    # shift-null for every cell with an excess >= +0.08 and the best cell
    cand = sorted({i for i, r in enumerate(rows) if r[4]["full"]["diff"] >= MIN_EXCESS} | {best_i})
    leads = []
    say()
    say("SHIFT-NULL for the cells with excess >= +0.08R and for the best cell")
    for i in cand:
        g, kind, sname, fr, c = rows[i]
        obs, p, sd = rr.shift_null(c["x"], c["sel"], rng, shifts=200)
        ok = is_lead(c, p)
        if ok:
            leads.append(i)
        say(f"  {g} {kind} {sname} top {int(fr * 100)}%: excess {c['full']['diff']:+.3f} (t {c['full']['t']:+.1f}), halves selected {c['h1']['sel_r']:+.3f} / {c['h2']['sel_r']:+.3f}; shift p {p:.3f} (Bonferroni over 63: {min(1.0, 63 * p):.2f})  {'LEAD' if ok else 'not a lead'}")
    say()
    g, kind, sname, fr, c = rows[best_i]
    say(f"OUT-OF-UNIVERSE TEST of the best cell: {g} {kind} {sname} top {int(fr * 100)}% - the model frozen on the five majors, applied to the point-in-time top-40 outside them")
    d, Xp, sets = keep[g]
    res = wide_test(say, rng, g, kind, sname, fr, d, sets[sname], bars, feats, mkt)
    believed = bool(leads and best_i in leads and res["base"]["diff"] >= 0.05 and res["base"]["sel_r"] > 0)
    say()
    say(f"PREDICTIONS: L1 cells with selected >= +0.05 in both halves = {n_sel} of {len(rows)}; L2 best excess {ex[best_i]:+.3f} vs +0.135; L3 panel gain {dd.mean():+.3f}; "
        f"L4 see the table; leads {len(leads)}; out-of-universe excess {res['base']['diff']:+.3f}, selected {res['base']['sel_r']:+.3f} -> {'BELIEVED' if believed else 'not believed'}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
