"""THE COMBINATION TEST, CLEAN VERSION: a FIXED trade at every candidate hour, everything the repo can see as the signal (2026-11-15)

THE USER (2026-11-15, /goal): "find an edge that gives good signals - a perfect combination of every signal, or everything you have so far, including the forward data from the Analyst desk."
combo_meta.py asked it of the desk's own calls and found no edge - but its power check showed WHY that test is weak: every desk call has its own bracket, so the fee / stop-width differences between calls (a loser's R runs from -1.04 to -1.4 with the stop's
width) swamp everything, and a planted +0.25R-per-sd skill was recovered only at t +1.8. This file removes the confound. It asks the question in its cleanest form:
  at EVERY candidate hour, for each of 5 markets and both sides, a trade with a FIXED bracket (identical payoff structure for every candidate); can a model that sees everything available at that moment tell the winners from the losers?
  The model's only job is WHEN to enter. ~70,000 candidates per bracket, so the power is far higher than combo_meta's.

CANDIDATES  BTC ETH SOL XRP BNB, every 6th hour (00 / 06 / 12 / 18 UTC), long and short; the signal reads the last CLOSED 1h bar (as the desk does), the entry is the OPEN of the next hour, the bracket is fixed in percent of the entry,
            scored on 1h candles exactly like the replay (a bar touching both stop and target = a loss; a timeout exits at the horizon's close; 12bp fee). Three brackets:  G1 stop 1.2% / target 2.4% / 24h,  G2 stop 1.2% / target 3.6% / 24h,
            G3 stop 2.0% / target 4.0% / 48h.
FEATURES    combo_meta's: the P set (55 candle features: returns, ATR, RSI, Bollinger, position in the 24h range, distance to the 1000h / daily means, BTC's state, relative strength, breadth, hour, weekday; direction-aligned versions) and the E set
            (the panel's 91 daily signals at the previous day: funding, positioning, taker flow, OI, news, tone, unlocks, size / age, fuel, breadth, fear & greed). The bracket's own numbers are constants (dropped per fold).
MODELS      Ridge and a regularised gradient-boosted tree on P, and the tree on P + E (the panel ends 2026-09-09, so P + E candidates stop there) = 3 models. Walk-forward quarterly folds from 2023-01-01, a fold trains only on candidates made >= 72h before it.
SELECTION   in each fold the top 5% / 10% / 20% of candidates by predicted R are taken: 3 brackets x 3 models x 3 fractions = 27 cells.
GATE        (combo_meta's amended gate) selected bets' mean R minus the mean R of ALL bets in the same period (a bet = UTC day + side), Welch t >= 2; selected R/bet >= +0.05 and > 0 in BOTH halves (2023-24, 2025-26); the difference > 0 in both halves;
            the selected candidates' hit rate above the hit rate of ALL candidates of the same side in the same quarter, in both halves; >= 150 selected bets; Holm over the 27 cells.
            Then the same models are applied to the desk's LIVE forward calls (descriptive: 92 calls).
POWER       the same pipeline on (a) labels with a planted skill (+0.10R per sd of a rank-normal direction-aligned 24h return) and (b) shuffled labels, for the first bracket and the ridge model.

REGISTERED BEFORE THE FIRST RUN (2026-11-15; prior that at least one of the 27 cells passes: 3%)
  U1  No cell passes.
  U2  The mean R of ALL candidates is negative for every bracket (about -0.05 .. -0.25R: the fee plus a coin-flip's bracket).
  U3  The fee-free out-of-sample rank IC of every model is within +-0.03, and adding the E set lifts it by under 0.01.
  U4  The best cell's selected R/bet is lower in 2025-26 than in 2023-24 (decay) or negative.
  U5  The planted +0.10R-per-sd skill IS recovered (selected - all >= +0.05R, Welch t >= 2) and the shuffled placebo is not: with fixed payoffs and ~70k candidates this test can see what combo_meta could not.

RESULT (2026-11-15; logs/combo_universe.txt) - 0 of 27 cells pass.
    70,350 candidates per bracket (55,760 out of sample): the mean R of ALL candidates is -0.103 (G1), -0.096 (G2), -0.058 (G3); long and short about alike; the same in 2023-24 and 2025-26. Fee-free out-of-sample rank IC +0.023 .. +0.055 (every model small and positive,
    none tradable); the E set adds +0.008 (G2) and loses 0.003 / 0.015 (G1 / G3). The 18 P-set cells: differences -0.035 .. +0.057, Welch t -1.3 .. +1.4, selected R/bet negative in 2025-26 in 17 of 18. The 9 tree cells with the panel's signals (P+E): FOUR reach t +2.2 .. +2.3 (G1 top 5%: +0.098R, selected +0.021 / -0.024; and
    G2 top 5 / 10 / 20%: differences +0.111 / +0.088 / +0.075, selected +0.061 .. +0.074R a bet in 2023-24 and -0.026 .. -0.107R in 2025-26; Holm 0.26 .. 0.37) - the funding / positioning signals helped in 2023-24 and not since, the shape of every decayed lead in this repo.
    Best cell by difference: G2 tree P+E top 5%: +0.111R (t +2.2). POWER CHECK (G1 ridge, top 10%): a planted +0.10R-per-sd skill is NOT recovered (selected +0.017R above all, Welch t +0.6), +0.05R per sd gives -0.055R, the placebo +0.026R (t +1.1): a model with 55 correlated features learns
    regime noise as large as a modest real skill, so 'no cell passes' excludes combination skills of roughly +0.25R per sd and larger, not small ones. LIVE forward calls (92): top 33% / 50% under the G1-G3 models +0.28 .. -0.16R a bet vs all -0.04, every |t| <= 0.8.
    Predictions: U1 right; U2 right; U3 half (IC +0.02..+0.055, above the +-0.03 I wrote for 8 of 9 models; the E lift under 0.01 right); U4 right (the best cell +0.061 then -0.026); U5 WRONG (the planted +0.10R per sd is not seen).
    Tests 11 (tests/test_combo_universe.py); planted bugs 15 of 15 (the one first survivor, entry price = previous close, was a gap in my tests: opens never gapped), control survived.

    python -m backtest.combo_universe        writes logs/combo_universe.txt          tests: python tests/test_combo_universe.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import combo_meta as cm  # noqa: E402

LOG = ROOT / "logs" / "combo_universe.txt"
FEE = 0.0012
H1 = cm.H1
HOURS = (0, 6, 12, 18)                                  # UTC hours at which a candidate is made
GEOMS = {"G1": (0.012, 0.024, 24), "G2": (0.012, 0.036, 24), "G3": (0.020, 0.040, 48)}
KINDS = (("ridge", "P"), ("hgb", "P"), ("hgb", "P+E"))
FRACS = (0.05, 0.10, 0.20)


# ------------------------------------------------------------------ candidates and their outcomes

def score_fixed(o, h, l, c, j, side: int, stop: float, target: float, hours: int):
    """Outcome of a trade entered at the OPEN of bar j with stop / target in percent of the entry, scored like the replay: the bars j .. j+hours-1 are scanned in order; a bar that touches BOTH is a loss; a trade neither
    level touches exits at the close of bar j+hours-1. Vectorised over the entry bars j. Returns (r, status) with status 0 LOSS, 1 WIN, 2 EXPIRED."""
    j = np.asarray(j)
    H = hours
    e = o[j]
    wh, wl = sliding_window_view(h, H)[j], sliding_window_view(l, H)[j]
    if side > 0:
        hs, ht = wl <= (e * (1 - stop))[:, None], wh >= (e * (1 + target))[:, None]
    else:
        hs, ht = wh >= (e * (1 + stop))[:, None], wl <= (e * (1 - target))[:, None]
    fs = np.where(hs.any(1), hs.argmax(1), H)
    ft = np.where(ht.any(1), ht.argmax(1), H)
    lose, win = (fs <= ft) & (fs < H), ft < fs
    r_to = (side * (c[j + H - 1] / e - 1) - FEE) / stop
    r = np.where(win, (target - FEE) / stop, np.where(lose, -(stop + FEE) / stop, r_to))
    status = np.where(win, 1, np.where(lose, 0, 2))
    return r, status


def candidate_frame(bars: dict, geom: tuple) -> pd.DataFrame:
    """Every candidate hour for every symbol and side, with the outcome of the fixed bracket."""
    stop, target, hours = geom
    rows = []
    for sym, b in bars.items():
        t = b.index.to_numpy()
        o, h, l, c = (b[k].to_numpy(float) for k in ("o", "h", "l", "c"))
        hod = (t // H1) % 24
        j = np.flatnonzero(np.isin(hod, HOURS))
        j = j[(j >= 1) & (j + hours <= len(t))]                    # a closed bar before the entry bar, and the whole horizon observed
        for side, name in ((1, "long"), (-1, "short")):
            r, st = score_fixed(o, h, l, c, j, side, stop, target, hours)
            rows.append(pd.DataFrame(dict(symbol=sym, side=name, made_ms=t[j].astype("int64"), r_net=r, st=st, entry=o[j])))
    d = pd.concat(rows, ignore_index=True).sort_values(["made_ms", "symbol", "side"], kind="stable").reset_index(drop=True)
    d["status"] = np.array(["LOSS", "WIN", "EXPIRED"])[d.st.to_numpy()]
    d["method"], d["stop_pct"], d["target_pct"], d["rr"], d["hours"] = "SR", stop, target, target / stop, hours
    d = cm.finish_calls(d)
    # the random-entry odds = the hit rate of ALL candidates of the same side in the same quarter (a time-varying baseline)
    q = d.t.dt.to_period("Q").astype(str)
    d["base_p"] = d.groupby([q, d.side]).win.transform("mean")
    return d


# ------------------------------------------------------------------ the run

def cells_for(d: pd.DataFrame, models: dict) -> list:
    rows = []
    for mname, (sub, wf) in models.items():
        x = sub.join(wf)
        for fr in FRACS:
            rows.append((mname, fr, cm.cell(x, "pred", fr)))
    adj = cm.holm([r[2]["p"] for r in rows])
    return [(m, fr, c, float(a)) for (m, fr, c), a in zip(rows, adj)]


def fee_free_ic(sub: pd.DataFrame, wf: pd.DataFrame, geom: tuple) -> float:
    d = sub.join(wf)
    d = d[d.pred.notna()]
    return float(sps.spearmanr(d.pred, d.r_net + FEE / geom[0])[0])


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    rng = np.random.default_rng(20261115)
    bars = {s: cm.load_bars(s) for s in cm.SYMS}
    for s, b in bars.items():
        assert (np.diff(b.index.to_numpy()) == H1).all(), f"{s}: hourly bars are not contiguous"
    feats = {s: cm.symbol_features(bars[s]) for s in cm.SYMS}
    mkt = cm.market_frame(feats)
    say(f"backtest/combo_universe.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; fixed brackets at every 6th hour, 5 markets, both sides; walk-forward quarterly folds from {cm.FIRST_OOS:%Y-%m-%d}; 12bp fee")
    results = {}
    all_cells = []
    for gname, geom in GEOMS.items():
        d = candidate_frame(bars, geom)
        Xp = cm.call_features(d, feats, mkt)
        Xe = cm.panel_features(d)
        sets = cm.feature_sets(Xp, Xe)
        models = {}
        for kind, sname in KINDS:
            sub = d if sname == "P" else d[d.t < cm.PANEL_CALLS_UNTIL]
            wf = cm.walk_forward(sub, sets[sname].loc[sub.index], kind)
            models[f"{kind} {sname}"] = (sub, wf)
        results[gname] = (d, Xp, models)
        oos = d[d.t >= cm.FIRST_OOS]
        say()
        say(f"=== {gname}: stop {geom[0] * 100:.1f}% / target {geom[1] * 100:.1f}% / {geom[2]}h: {len(d):,} candidates, win {d.win.mean() * 100:.1f}%, mean R {d.r_net.mean():+.3f} (out of sample {len(oos):,}: {oos.r_net.mean():+.3f}; "
            f"long {oos[oos.side == 'long'].r_net.mean():+.3f}, short {oos[oos.side == 'short'].r_net.mean():+.3f}); 2023-24 {oos[oos.t < cm.HALF_SPLIT].r_net.mean():+.3f}, 2025-26 {oos[oos.t >= cm.HALF_SPLIT].r_net.mean():+.3f}")
        say("  fee-free out-of-sample rank IC (prediction vs R + fee/stop): " + "   ".join(f"{m} {fee_free_ic(s_, w_, geom):+.3f}" for m, (s_, w_) in models.items()))
        for m, (s_, w_) in models.items():
            x = s_.join(w_)
            x = x[x.pred.notna()]
            say(f"    {m:<9} IC vs R {sps.spearmanr(x.pred, x.r_net)[0]:+.3f}; 2023-24 {sps.spearmanr(x[x.t < cm.HALF_SPLIT].pred, x[x.t < cm.HALF_SPLIT].r_net)[0]:+.3f}, "
                f"2025-26 {sps.spearmanr(x[x.t >= cm.HALF_SPLIT].pred, x[x.t >= cm.HALF_SPLIT].r_net)[0]:+.3f}")
        all_cells += [(gname,) + r for r in cells_for(d, models)]
    # Holm over ALL 27 cells (the per-geometry Holm in cells_for is only a placeholder)
    adj = cm.holm([r[3]["p"] for r in all_cells])
    say()
    say("THE 27 CELLS (selected = top fraction by predicted R in each fold; difference = selected bets' mean R minus all bets' mean R; Holm over all 27)")
    npass = 0
    for (g, m, fr, c, _), a in zip(all_cells, adj):
        ok = cm.passes(c, float(a))
        npass += ok
        f, h1, h2 = c["full"], c["h1"], c["h2"]
        say(f"  {g} {m:<9} top {int(fr * 100):>2}%  n {f['n']:>6} bets {f['bets']:>4}/{f['all_bets']}  selected {f['sel_r']:+.3f} vs all {f['all_r']:+.3f} = {f['diff']:+.3f} (t {f['t']:+.1f})  hit {f['hit'] * 100:4.1f}% vs {f['base'] * 100:4.1f}%  "
            f"halves diff {h1['diff']:+.3f} / {h2['diff']:+.3f}, selected {h1['sel_r']:+.3f} / {h2['sel_r']:+.3f}  Holm {a:.3f}  {'PASS' if ok else 'no'}")
    say(f"  cells passing: {npass} of {len(all_cells)}")
    best = max(all_cells, key=lambda r: r[3]["full"]["diff"] if np.isfinite(r[3]["full"]["diff"]) else -9)
    g, m, fr, c, _ = best
    say(f"  best cell by difference: {g} {m} top {int(fr * 100)}%: {c['full']['diff']:+.3f} (t {c['full']['t']:+.1f}); selected R/bet {c['h1']['sel_r']:+.3f} in 2023-24 and {c['h2']['sel_r']:+.3f} in 2025-26")

    # ---- power check on the first bracket
    say()
    say("POWER CHECK (G1, ridge P, top 10%): a planted skill of +0.10R per sd of the rank-normal direction-aligned 24h return, and shuffled labels")
    d, Xp, _ = results["G1"]
    for lab, y in (("planted +0.10R / sd", cm.plant(d, Xp, 0.10)), ("planted +0.05R / sd", cm.plant(d, Xp, 0.05)), ("placebo (shuffled labels)", rng.permutation(d.r_net.to_numpy()))):
        d2 = d.copy()
        d2["r_net"] = y
        wf = cm.walk_forward(d2, Xp, "ridge", y=y)
        cc = cm.cell(d2.join(wf), "pred", 0.10)
        f = cc["full"]
        say(f"  {lab:<26} selected {f['sel_r']:+.3f} vs all {f['all_r']:+.3f} = {f['diff']:+.3f} (Welch t {f['t']:+.1f}), halves {cc['h1']['diff']:+.3f} / {cc['h2']['diff']:+.3f}")

    # ---- the live forward calls under the same models
    say()
    say("THE LIVE FORWARD CALLS (the desk's own 92 resolved crypto calls, never seen by any fit): models trained on ALL candidates of each bracket up to 2026-10-25, applied to the live calls' own features")
    live = cm.load_live_calls()
    Xl, _ = cm.build_table(live, extend=True)
    live["fold"] = 0
    for gname, geom in GEOMS.items():
        d, Xp, _ = results[gname]
        tr = d.made_ms.to_numpy() + cm.EMBARGO_MS < int(pd.Timestamp("2026-10-26").timestamp() * 1000)
        for kind in ("ridge", "hgb"):
            p = cm.fit_model(kind, Xp.to_numpy(float)[tr], d.r_net.to_numpy()[tr])(Xl.reindex(columns=Xp.columns).to_numpy(float))
            live[f"p_{kind}"] = p
            for fr in (0.33, 0.50):
                sel = cm.select(live, f"p_{kind}", fr)
                st_ = cm.half_stats(live, sel)
                say(f"  {gname} {kind:<5} top {int(fr * 100)}%: n {st_['n']} bets {st_['bets']}  selected {st_['sel_r']:+.2f} vs all {st_['all_r']:+.2f} = {st_['diff']:+.2f} (Welch t {st_['t']:+.1f})  hit {st_['hit'] * 100:.0f}% vs random {st_['base'] * 100:.0f}%")
    say()
    say(f"PREDICTIONS (registered before the run): U1 cells passing {npass} of {len(all_cells)}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
