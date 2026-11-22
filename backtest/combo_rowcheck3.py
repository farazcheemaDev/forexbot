"""PER-CALL RE-SCORE OF THE DESK'S OWN CALLS, with a stop-width-matched control (2026-11-15, /goal round 3b)

THE USER (2026-11-15, /goal): "find an edge that gives good signals - a perfect combination of every signal, or everything you have so far, including the forward data from the Analyst desk."
combo_meta.py scored 12 cells on the desk's 10,081 replay crypto calls (ridge / boosting on 55 candle features, and on those plus the panel's 91 daily signals) with the bet-level gate, and its raw rank IC (+0.20..+0.25) turned out to be the fee / stop-width tie-break: the losers end near
-(1 + fee / stop), so a model that prefers wide stops ranks 'well' without skill. combo_rowcheck.py / combo_rowcheck2.py showed the bet-level gate is the wrong instrument; the desk's calls were the one set never re-scored per call. Here: the 12 cells, per CALL, against the unselected calls of the SAME
stratum (quarter x rule x side x stop-width tercile within the rule) - so a model that merely likes wide stops, or one rule, or one side, earns no credit - with a weekly-cluster t, and the selected mean R in both halves. The calls are not on a fixed grid (the desk draws its own levels), so no shift-null.
THE BAR (fixed before the run): matched excess >= +0.08R, weekly-cluster t >= 3.0, selected mean >= +0.05R in BOTH halves (2023-24, 2025-26).

REGISTERED BEFORE THE FIRST RUN (2026-11-15; prior that any cell clears the bar: 3%)
  M1  No cell has a per-call selected mean >= +0.05R in both halves (prior 95%).
  M2  The best matched excess among the 12 is below +0.10R (prior 80%).
  M3  The matched excess is much smaller than the plain excess over all calls (the stop-width / rule tie-break was most of the earlier look of skill; the mean ratio below 0.5 in the cells whose plain excess is positive; prior 80%).

RESULT (2026-11-15, logs/combo_rowcheck3.txt): 0 of 12 cells have a per-call selected mean >= +0.05R in both halves (M1 right: every selected mean is NEGATIVE, -0.12..-0.18R); the best matched excess is +0.052R (hgb P+E top 33%, t +1.6) (M2 right); against all calls the cells show a plain
excess of +0.03..+0.07R, and the stop-width / rule / side matched excess is on average 0.06 of it (M3 right): what looked like ranking skill on the desk's calls (raw IC +0.20..+0.25) is the model preferring wide stops and the rules whose losers are cheaper. No lead.

    python -m backtest.combo_rowcheck3        writes logs/combo_rowcheck3.txt
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import combo_meta as cm  # noqa: E402

LOG = ROOT / "logs" / "combo_rowcheck3.txt"
MIN_EXCESS, MIN_T, MIN_SEL = 0.08, 3.0, 0.05


def matched_per_call(x: pd.DataFrame, sel: pd.Series, strata: list) -> dict:
    """Each selected call's R minus the mean R of the UNSELECTED calls in its stratum (strata with fewer than 5 unselected calls are skipped); the mean difference with a weekly-cluster standard error."""
    d = x.assign(sel=sel.to_numpy())
    un = d[~d.sel].groupby(strata).r_net.agg(["mean", "size"])
    s = d[d.sel].merge(un, left_on=strata, right_index=True, how="left")
    s = s[s["size"] >= 5]
    if len(s) < 20:
        return dict(n=len(s), sel_r=float("nan"), diff=float("nan"), t=float("nan"))
    diffs = (s.r_net - s["mean"]).to_numpy()
    wk = s.t.dt.to_period("W").astype(str).to_numpy()
    blocks = pd.Series(diffs).groupby(wk).sum()
    cnt = pd.Series(np.ones(len(s))).groupby(wk).sum()
    m = diffs.mean()
    se = math.sqrt(((blocks - m * cnt) ** 2).sum()) / len(s)
    return dict(n=len(s), sel_r=float(s.r_net.mean()), diff=float(m), t=float(m / se) if se > 1e-12 else float("nan"))


def plain_excess(x: pd.DataFrame, sel: pd.Series) -> float:
    return float(x[sel].r_net.mean() - x.r_net.mean())


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    calls = cm.load_replay_calls()
    Xp, Xe = cm.build_table(calls, extend=False)
    sets = cm.feature_sets(Xp, Xe)
    models = cm.run_models(calls, sets)
    say(f"backtest/combo_rowcheck3.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; per-CALL re-score of combo_meta's 12 cells on the desk's {len(calls):,} replay crypto calls, control = unselected calls of the same quarter x rule x side x stop tercile; 12bp in R")
    rows = []
    say()
    for mname, (sub, wf) in models.items():
        x = sub.join(wf)
        x = x[x.pred.notna()].copy()
        x["q"] = x.t.dt.to_period("Q").astype(str)
        x["stop_t"] = x.groupby("method").stop_pct.transform(lambda v: pd.qcut(v, 3, labels=False, duplicates="drop"))
        for fr in cm.FRACS:
            sel = cm.select(x, "pred", fr)
            full = matched_per_call(x, sel, ["q", "method", "side", "stop_t"])
            h1 = matched_per_call(x[x.t < cm.HALF_SPLIT], sel[x.t < cm.HALF_SPLIT], ["q", "method", "side", "stop_t"])
            h2 = matched_per_call(x[x.t >= cm.HALF_SPLIT], sel[x.t >= cm.HALF_SPLIT], ["q", "method", "side", "stop_t"])
            pe = plain_excess(x, sel)
            rows.append((mname, fr, full, h1, h2, pe, len(x)))
            say(f"  {mname:<9} top {int(fr * 100):>2}%  n {full['n']:>5}  selected {full['sel_r']:+.3f}  matched excess {full['diff']:+.3f} (t {full['t']:+.1f})  plain excess over all calls {pe:+.3f};  halves selected {h1['sel_r']:+.3f} / {h2['sel_r']:+.3f}")
    n_sel = sum(1 for r in rows if r[3]["sel_r"] >= MIN_SEL and r[4]["sel_r"] >= MIN_SEL)
    leads = [r for r in rows if r[2]["diff"] >= MIN_EXCESS and r[2]["t"] >= MIN_T and r[3]["sel_r"] >= MIN_SEL and r[4]["sel_r"] >= MIN_SEL]
    best = max(rows, key=lambda r: r[2]["diff"] if np.isfinite(r[2]["diff"]) else -9)
    pos = [r for r in rows if r[5] > 0 and np.isfinite(r[2]["diff"])]
    ratio = float(np.mean([r[2]["diff"] / r[5] for r in pos])) if pos else float("nan")
    say()
    say(f"  cells with a per-call selected mean >= +{MIN_SEL:.2f}R in BOTH halves: {n_sel} of {len(rows)}; cells that clear the bar: {len(leads)}")
    say(f"  best matched excess {best[2]['diff']:+.3f} ({best[0]} top {int(best[1] * 100)}%, t {best[2]['t']:+.1f}); mean matched / plain excess over the {len(pos)} cells with a positive plain excess: {ratio:.2f}")
    say()
    say(f"PREDICTIONS: M1 cells with selected >= +0.05 in both halves = {n_sel} of {len(rows)}; M2 best matched excess {best[2]['diff']:+.3f}; M3 ratio {ratio:.2f}; leads {len(leads)}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
