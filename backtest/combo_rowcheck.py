"""PER-TRADE RE-CHECK OF THE WHOLE COMBINATION FAMILY: the gate averaged per DAY; money is made per TRADE (2026-11-15)

combo_rangerev.py found that the 'edge' printed by combo_direction.py's diagnostics (+0.147R, t +4.5) was two artifacts: a short-only selection measured against a baseline that is half longs, and a DAY-VOTE mean - the selected shorts at the top of the
range cluster on the same few market-wide days, lose together, and one vote per (day, side) lets quiet one-call days outvote them: per call the selected mean was -0.157R against -0.096R for all same-side candidates (a SHIFT-null p of 0.983: worse than random),
while per bet it read -0.038R. That is the repo's own trap (CLAUDE.md s3, 'A day-vote mean read as money') and the combo_* gate (combo_meta.half_stats) uses exactly that bet mean. This file re-scores every gate cell of combo_screen (18) and combo_direction (18)
PER CALL: the selected calls' mean R against the mean R of ALL calls of the SAME side(s) the selection contains, the t over weekly blocks (calls of a week are one unit: clusters across days and coins), and a shift-null p for the best cells.
The gate's verdicts stand if no cell shows a per-call excess with t >= 2 and a positive per-call mean in both halves; a cell that did pass would need this file's numbers beside it before it was believed.

REGISTERED BEFORE THE FIRST RUN (2026-11-15)
  K1  No cell has a per-call selected mean R >= +0.05 in both halves (prior 95%).
  K2  The per-call excess over the same-side control is smaller than the per-bet excess in most of the 36 cells (the gate was lenient: the day-vote direction of the artifact; prior 65%).
  K3  The best cell by per-call excess has a weekly-block t below 2 and a shift-null p above 0.05 (prior 85%).

RESULT (2026-11-15, logs/combo_rowcheck.txt): per CALL, 0 of 36 cells have a selected mean >= +0.05R in BOTH halves (K1 right); the per-call excess is LARGER than the per-bet excess in 32 of 36 cells (K2 WRONG: here the day-vote gate was strict, not lenient - it hid the lead
instead of inventing one); the best cell is G1, a ridge on the 13 direction features, top 5%: +0.051R selected vs -0.084R same-side = +0.135R (weekly-cluster t +3.1), halves selected +0.080 / +0.019, shift-null p 0.002 (K3 WRONG). Dissected in combo_ridge_dissect.py, tested on unseen
coins in combo_wide.py: it does not transfer. Tests: tests/test_combo_wide.py.

    python -m backtest.combo_rowcheck        writes logs/combo_rowcheck.txt
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import combo_direction as cd  # noqa: E402
from backtest import combo_meta as cm  # noqa: E402
from backtest import combo_rangerev as rr  # noqa: E402
from backtest import combo_universe as cu  # noqa: E402

LOG = ROOT / "logs" / "combo_rowcheck.txt"


def per_call(d: pd.DataFrame, sel: pd.Series) -> dict:
    """Selected calls vs ALL calls of the same side mix, per CALL; t over weekly blocks of the per-call difference r_i - mean R of that call's side."""
    s = d[sel]
    if len(s) < 20:
        return dict(n=len(s), sel_r=float("nan"), ctl_r=float("nan"), diff=float("nan"), t=float("nan"))
    ctl_side = d.groupby("side").r_net.mean()
    diffs = s.r_net.to_numpy() - ctl_side.reindex(s.side).to_numpy()
    wk = s.t.dt.to_period("W").astype(str).to_numpy()
    blocks = pd.Series(diffs).groupby(wk).sum()                          # a week's selected calls are one cluster; its weight is the number of calls
    cnt = pd.Series(np.ones(len(s))).groupby(wk).sum()
    # mean of the per-call differences with a cluster-robust se (clusters = weeks)
    m = diffs.mean()
    resid = blocks - m * cnt
    se = math.sqrt((resid ** 2).sum()) / len(s) if len(s) > 0 else float("nan")
    return dict(n=len(s), sel_r=float(s.r_net.mean()), ctl_r=float((ctl_side.reindex(s.side)).mean()), diff=float(m), t=(float(m / se) if se > 1e-12 else float("nan")))


def cell_rows(d: pd.DataFrame, wf: pd.DataFrame, frac: float) -> dict:
    x = d.join(wf)
    x = x[x.pred.notna()]
    sel = cm.select(x, "pred", frac)
    a, b = x.t < cm.HALF_SPLIT, x.t >= cm.HALF_SPLIT
    return dict(full=per_call(x, sel), h1=per_call(x[a], sel[a]), h2=per_call(x[b], sel[b]), bet=cm.half_stats(x, sel), x=x, sel=sel)


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    rng = np.random.default_rng(20261115)
    bars = {s: cm.load_bars(s) for s in cm.SYMS}
    feats = {s: cm.symbol_features(bars[s]) for s in cm.SYMS}
    mkt = cm.market_frame(feats)
    say(f"backtest/combo_rowcheck.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; per-CALL re-score of combo_screen (sridge on P, P+E) and combo_direction (ridge, hgb on the 13 direction features); fixed brackets, 12bp")
    rows = []
    for gname, geom in cu.GEOMS.items():
        d = cu.candidate_frame(bars, geom)
        Xp = cm.call_features(d, feats, mkt)
        Xe = cm.panel_features(d)
        sets = cm.feature_sets(Xp, Xe)
        Xd = Xp[cd.direction_columns(Xp)]
        variants = []
        for sname in ("P", "P+E"):
            sub = d if sname == "P" else d[d.t < cm.PANEL_CALLS_UNTIL]
            variants.append((f"sridge {sname}", sub, cm.walk_forward(sub, sets[sname].loc[sub.index], "sridge")))
        for kind in cd.KINDS:
            variants.append((f"{kind} D", d, cm.walk_forward(d, Xd, kind)))
        for name, sub, wf in variants:
            for fr in cu.FRACS:
                c = cell_rows(sub, wf, fr)
                rows.append((gname, name, fr, c))
    say()
    say("PER-CALL RESULTS (selected = top fraction by predicted R per fold; excess = selected calls' mean R minus the mean R of all calls of the same side(s); t over weekly clusters; 'bet' = the gate's per-(day, side) excess for comparison)")
    npos = 0
    smaller = 0
    for g, name, fr, c in rows:
        f, h1, h2, b = c["full"], c["h1"], c["h2"], c["bet"]
        both = (h1["sel_r"] >= 0.05) and (h2["sel_r"] >= 0.05)
        npos += both
        smaller += f["diff"] < b["diff"]
        say(f"  {g} {name:<10} top {int(fr * 100):>2}%  n {f['n']:>5}  per-call selected {f['sel_r']:+.3f} vs same-side {f['ctl_r']:+.3f} = {f['diff']:+.3f} (t {f['t']:+.1f}); halves selected {h1['sel_r']:+.3f} / {h2['sel_r']:+.3f}   bet-level excess {b['diff']:+.3f} (t {b['t']:+.1f})")
    say(f"  cells with a per-call selected mean >= +0.05R in BOTH halves: {npos} of {len(rows)}; cells where the per-call excess is smaller than the per-bet excess: {smaller} of {len(rows)}")
    best = max(rows, key=lambda r: r[3]["full"]["diff"] if np.isfinite(r[3]["full"]["diff"]) else -9)
    g, name, fr, c = best
    obs, p, sd = rr.shift_null(c["x"], c["sel"], rng)
    say(f"  best cell by per-call excess: {g} {name} top {int(fr * 100)}%: {c['full']['diff']:+.3f} (t {c['full']['t']:+.1f}); shift-null observed {obs:+.3f}, null sd {sd:.3f}, p = {p:.3f}")
    worst = min(rows, key=lambda r: r[3]["full"]["diff"] if np.isfinite(r[3]["full"]["diff"]) else 9)
    say(f"  worst cell by per-call excess: {worst[0]} {worst[1]} top {int(worst[2] * 100)}%: {worst[3]['full']['diff']:+.3f} (t {worst[3]['full']['t']:+.1f})")
    say()
    say(f"PREDICTIONS: K1 cells with per-call selected >= +0.05 in both halves = {npos} of {len(rows)}; K2 per-call < per-bet in {smaller} of {len(rows)}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
