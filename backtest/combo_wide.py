"""THE DIRECTION-ONLY COMBINATION ON COINS IT HAS NEVER SEEN: the point-in-time top-40 perpetuals, dead coins included (2026-11-15)

THE USER (2026-11-15, /goal): "find an edge that gives good signals - a perfect combination of every signal, or everything you have so far, including the forward data from the Analyst desk."
WHERE WE ARE (combo_rangerev, combo_rowcheck, combo_ridge_dissect): the bet-level (UTC day + side) gate used by combo_meta / combo_universe / combo_screen / combo_direction is a day-vote mean and hid the only per-call lead. Re-scored per call, ONE of 36 cells shows a
relative edge: a ridge on the 13 direction-aligned features (rsi_aligned, d_rsi_aligned, a_ret24, a_ret168, a_d_ma1000, a_bb_z, a_rng_pos24, a_d_sma50, a_d_ret7, a_rel_btc24, a_rel_btc168, a_btc_ret24, a_mkt_ret24), G1 = fixed 1.2% stop / 2.4% target / 24h trade at every
6th hour on BTC ETH SOL XRP BNB, top 5% of each quarterly fold: per-call selected +0.051R vs -0.084R for all same-side calls = +0.135R (weekly-cluster t +3.1; matched to quarter x hour x volatility +0.149; shift-null p 0.002 / 0.007; deciles monotone, Spearman +0.94;
85% of the selected are shorts of coins that are weak vs BTC and below their bands = trend-continuation shorts). BUT: absolute selected R is only +0.051 (= +6bp a trade after 12bp), +0.080 in 2023-24, +0.019 in 2025-26, 2026 -0.010, 2026Q3 excess -0.20; and it was the best of 36 cells.
THIS FILE is the out-of-universe test, written before it was run: the same G1 rule, the same top 5% per quarterly fold, on the 'wide' universe = every perpetual NOT in the five that was in the top 40 by the PRIOR month's volume (wide_book.eligibility(40): delisted coins included,
coin-months only while eligible), 1h candles from strategy_analysis/data/perps (2020-09 .. 2026-09-21). Two versions:
  (A) FROZEN: the ridge is trained ONLY on the five majors' candidates before each fold (exactly the model of the lead) and applied to the wide coins - a model that has never seen these coins;
  (B) NATIVE: a ridge trained walk-forward on the wide coins themselves (the same procedure, a new universe).
A candidate needs a contiguous hour grid: the previous 24 bars and the next H bars must be consecutive hours (a hole in a coin's history would otherwise shorten the 24-hour bracket). Same 12bp fee; funding is NOT charged (a 24h hold crosses three settlements: a few bp either way, less
for a long than a short, and every cell here is short-heavy - so it may flatter the shorts by about as much as funding pays them; flagged, not modelled). Per-call statistics only (the day-vote trap): selected calls vs all same-side calls, weekly-cluster t, the circular shift-null, absolute mean R.

REGISTERED BEFORE THE FIRST RUN (2026-11-15; prior that the lead is an edge worth running: 8%)
  E1  (A) the frozen model's top 5% has a per-call excess >= +0.05R on the wide coins (prior 45%): the relative signal transfers.
  E2  (A) and (B): the absolute selected mean R >= +0.05 in BOTH halves (2023-24, 2025-26) (prior 10%).
  E3  (B) the native excess is >= +0.05R with a weekly-cluster t >= 2 (prior 50%).
  E4  The absolute selected mean R is <= +0.02 in 2025-26 in both versions (prior 75%).
  E5  After 6bp of extra slippage per trade (alts are wider than the majors) the selected mean R is below zero in both versions (prior 85%).
  E6  The selection on the wide coins is again mostly short (> 70%).

RESULT (2026-11-15, logs/combo_wide.txt): the lead does NOT transfer. 360 perpetuals outside the five were in the PIT top 40 (343 with candidates: 553,006 candidates; 284 coins and 318,014 calls out of sample). (A) the ridge trained on the five majors only: selected -0.108R per call vs
-0.082R same-side = excess -0.026 (weekly-cluster t -1.1), 2023-24 -0.062 / 2025-26 -0.158, shift-null p 0.83. (B) a ridge trained on the wide coins themselves: selected -0.042R, excess +0.018 (t +0.6, p 0.124), 2025-26 -0.065. G2 / G3 frozen: excess -0.003 / +0.001; top 10% / 20%
+0.010 / +0.015. The same code path reproduces the majors' +0.051 / +0.135 (C). After 6bp of slippage the majors' own selected mean is +0.001 and the wide coins' -0.09 / -0.16. E1 WRONG, E2 right, E3 WRONG, E4 right, E5 right, E6 right (81% / 99% short). Funding not charged (flatters
the shorts by about what it pays them). Tests: tests/test_combo_wide.py (18; 37 of 37 non-equivalent planted bugs caught across combo_wide / rangerev / rowcheck / direction / screen, the no-op control survived; the one survivor is the redundant second length guard in load_perp).

    python -m backtest.combo_wide        writes logs/combo_wide.txt          tests: tests/test_combo_wide.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import combo_direction as cd  # noqa: E402
from backtest import combo_meta as cm  # noqa: E402
from backtest import combo_rangerev as rr  # noqa: E402
from backtest import combo_rowcheck as rc  # noqa: E402
from backtest import combo_universe as cu  # noqa: E402

LOG = ROOT / "logs" / "combo_wide.txt"
PERPS = ROOT / "strategy_analysis" / "data" / "perps"
H1 = cm.H1
TOPN = 40
FRAC = 0.05
PRE_BARS = 24


def load_perp(sym: str) -> pd.DataFrame | None:
    """1h candles of one perpetual indexed by open time (ms): the first continuous episode only (a gap over 48h = a relisting), zero closes dropped; None if too short."""
    f = PERPS / f"{sym}_1h.csv.gz"
    if not f.exists():
        return None
    d = pd.read_csv(f)
    t = pd.to_datetime(d["time"]).astype("datetime64[ns]").astype("int64") // 10 ** 6
    d = pd.DataFrame(dict(o=d.open.to_numpy(float), h=d.high.to_numpy(float), l=d.low.to_numpy(float), c=d.close.to_numpy(float)), index=t.to_numpy())
    d = d[(d.c > 0) & (d.o > 0)]
    d = d[~d.index.duplicated()].sort_index()
    if len(d) < 800:
        return None
    gap = np.diff(d.index.to_numpy()) / H1
    if (gap > 48).any():
        d = d.iloc[: int(np.argmax(gap > 48)) + 1]
    return d if len(d) >= 800 else None


def month_of(ms: np.ndarray) -> np.ndarray:
    return pd.to_datetime(ms, unit="ms").strftime("%Y-%m").to_numpy()


def contiguous_entries(t: np.ndarray, j: np.ndarray, hours: int, pre: int = PRE_BARS) -> np.ndarray:
    """Which entry positions j have `pre` consecutive hourly bars before them (the feature windows) and `hours` consecutive bars from j on (the bracket), judged on the TIMESTAMPS."""
    ok = (j >= pre) & (j + hours <= len(t))
    jj = np.clip(j, pre, len(t) - hours)
    ok &= (t[jj] - t[jj - pre]) == pre * H1
    ok &= (t[np.clip(j + hours - 1, 0, len(t) - 1)] - t[jj]) == (hours - 1) * H1
    return ok


def wide_candidates(bars: dict, elig: dict, geom: tuple) -> pd.DataFrame:
    """The fixed bracket at every 6th hour for every eligible coin-month of every coin, both sides, exactly combo_universe's scoring, plus the contiguity filter."""
    stop, target, hours = geom
    rows = []
    for sym, b in bars.items():
        t = b.index.to_numpy()
        o, h, l, c = (b[k].to_numpy(float) for k in ("o", "h", "l", "c"))
        hod = (t // H1) % 24
        j = np.flatnonzero(np.isin(hod, cu.HOURS))
        if len(j) == 0:
            continue
        j = j[np.isin(month_of(t[j]), list(elig.get(sym, ())))]
        if len(j) == 0:
            continue
        j = j[contiguous_entries(t, j, hours)]
        if len(j) == 0:
            continue
        for side, name in ((1, "long"), (-1, "short")):
            r, st = cu.score_fixed(o, h, l, c, j, side, stop, target, hours)
            rows.append(pd.DataFrame(dict(symbol=sym, side=name, made_ms=t[j].astype("int64"), r_net=r, st=st, entry=o[j])))
    d = pd.concat(rows, ignore_index=True).sort_values(["made_ms", "symbol", "side"], kind="stable").reset_index(drop=True)
    d["status"] = np.array(["LOSS", "WIN", "EXPIRED"])[d.st.to_numpy()]
    d["method"], d["stop_pct"], d["target_pct"], d["rr"], d["hours"] = "SR", stop, target, target / stop, hours
    d = cm.finish_calls(d)
    q = d.t.dt.to_period("Q").astype(str)
    d["base_p"] = d.groupby([q, d.side]).win.transform("mean")
    return d


def frozen_predictions(train: pd.DataFrame, Xtrain: pd.DataFrame, test: pd.DataFrame, Xtest: pd.DataFrame, kind: str = "ridge") -> pd.DataFrame:
    """For each quarterly fold: fit the ridge on the TRAIN universe's candidates before the fold (72h embargo) and predict the TEST universe's candidates inside it."""
    starts = cm.fold_starts(test.t)
    pred = np.full(len(test), np.nan)
    fold = np.full(len(test), np.datetime64("NaT"), dtype="datetime64[ns]")
    tr_ms = train.made_ms.to_numpy()
    ytr = train.r_net.to_numpy()
    Xt = Xtrain.to_numpy(float)
    Xe = Xtest.to_numpy(float)
    for a, b in zip(starts[:-1], starts[1:]):
        te = ((test.t >= a) & (test.t < b)).to_numpy()
        tr = tr_ms + cm.EMBARGO_MS < int(a.timestamp() * 1000)
        if te.sum() == 0 or tr.sum() < cm.MIN_TRAIN:
            continue
        pred[te] = cm.fit_model(kind, Xt[tr], ytr[tr])(Xe[te])
        fold[te] = np.datetime64(a)
    return pd.DataFrame({"pred": pred, "fold": fold}, index=test.index)


def report(say, name: str, d: pd.DataFrame, wf: pd.DataFrame, rng, shifts: bool = True) -> dict:
    x = d.join(wf)
    x = x[x.pred.notna()].copy()
    sel = cm.select(x, "pred", FRAC)
    base = rc.per_call(x, sel)
    h1 = rc.per_call(x[x.t < cm.HALF_SPLIT], sel[x.t < cm.HALF_SPLIT])
    h2 = rc.per_call(x[x.t >= cm.HALF_SPLIT], sel[x.t >= cm.HALF_SPLIT])
    say(f"  {name}: {len(x):,} out-of-sample calls on {x.symbol.nunique()} coins; selected {base['n']}: per-call mean R {base['sel_r']:+.3f} vs same-side {base['ctl_r']:+.3f} = excess {base['diff']:+.3f} (weekly-cluster t {base['t']:+.1f})")
    say(f"      halves: 2023-24 selected {h1['sel_r']:+.3f} (excess {h1['diff']:+.3f}, t {h1['t']:+.1f}, n {h1['n']});  2025-26 selected {h2['sel_r']:+.3f} (excess {h2['diff']:+.3f}, t {h2['t']:+.1f}, n {h2['n']})")
    yrs = []
    for yr, g in x.groupby(x.t.dt.year):
        b_ = rc.per_call(g, sel[g.index])
        yrs.append(f"{yr} {b_['sel_r']:+.3f}/{b_['diff']:+.3f}({b_['n']})")
    say("      by year, selected / excess (n): " + "  ".join(yrs))
    s_ = x[sel]
    say(f"      side mix of the selected: {s_.side.value_counts(normalize=True).round(3).to_dict()}; coins in the selection: {s_.symbol.nunique()} (the most frequent: {s_.symbol.value_counts().head(5).to_dict()})")
    slip = [f"{bp:.0f}bp: {base['sel_r'] - bp / 1e4 / x.stop_pct.iloc[0]:+.3f}" for bp in (0, 3, 6, 10)]
    say("      selected mean R after extra slippage per trade: " + ", ".join(slip))
    x["q"] = x.t.dt.to_period("Q").astype(str)
    x["hour_bin"] = ((x.made_ms // H1) % 24).astype(int)
    out = dict(base=base, h1=h1, h2=h2)
    if shifts:
        obs, p, sd = rr.shift_null(x, sel, rng, shifts=200)
        say(f"      circular-shift null on the same-side excess: observed {obs:+.3f}, null sd {sd:.3f}, p = {p:.3f} (200 shifts)")
        out["p"] = p
    return out


def run():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    from backtest import wide_book
    rng = np.random.default_rng(20261115)
    say(f"backtest/combo_wide.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the direction-only ridge (13 features) on the point-in-time top-{TOPN} perpetuals outside the five majors; G1 = 1.2% / 2.4% / 24h at every 6th hour, both sides, 12bp (no funding); top {int(FRAC * 100)}% per quarterly fold")
    elig = {s: m for s, m in wide_book.eligibility(TOPN).items() if m and s not in cm.SYMS}
    say(f"  {len(elig)} coins were ever in the top {TOPN} by the prior month's volume (the five majors excluded)")
    bars5 = {s: cm.load_bars(s) for s in cm.SYMS}
    feats5 = {s: cm.symbol_features(bars5[s]) for s in cm.SYMS}
    mkt = cm.market_frame(feats5)
    geom = cu.GEOMS["G1"]
    d5 = cu.candidate_frame(bars5, geom)
    X5 = cm.call_features(d5, feats5, mkt)[cd.DIRECTION]
    wbars = {}
    for s in elig:
        b = load_perp(s)
        if b is not None:
            wbars[s] = b
    say(f"  {len(wbars)} of them have a usable 1h history ({sum(len(b) for b in wbars.values()):,} bars)")
    wfeats = {s: cm.symbol_features(b) for s, b in wbars.items()}
    dw = wide_candidates(wbars, elig, geom)
    allfeats = dict(feats5)
    allfeats.update(wfeats)
    Xw = cm.call_features(dw, allfeats, mkt)[cd.DIRECTION]
    oos = dw[dw.t >= cm.FIRST_OOS]
    say(f"  wide candidates: {len(dw):,} ({dw.symbol.nunique()} coins, {dw.t.min():%Y-%m} to {dw.t.max():%Y-%m}); out of sample {len(oos):,}; all-candidate mean R long {oos[oos.side == 'long'].r_net.mean():+.3f}, short {oos[oos.side == 'short'].r_net.mean():+.3f}")
    say(f"  for reference the five majors' G1 all-candidate mean R long {d5[d5.t >= cm.FIRST_OOS][d5.side == 'long'].r_net.mean():+.3f}, short {d5[d5.t >= cm.FIRST_OOS][d5.side == 'short'].r_net.mean():+.3f}")

    say()
    say("(A) FROZEN: the ridge trained on the FIVE MAJORS only, applied to the wide coins")
    wf_a = frozen_predictions(d5, X5, dw, Xw)
    ra = report(say, "A frozen", dw, wf_a, rng)

    say()
    say("(B) NATIVE: a ridge trained walk-forward on the wide coins themselves")
    wf_b = cm.walk_forward(dw, Xw, "ridge")
    rb = report(say, "B native", dw, wf_b, rng)

    say()
    say("(C) FOR REFERENCE, the majors themselves with the SAME code path (should reproduce combo_ridge_dissect: selected +0.051, excess +0.135)")
    wf_c = cm.walk_forward(d5, X5, "ridge")
    report(say, "C majors", d5, wf_c, rng, shifts=False)

    say()
    say("(D) THE OTHER TWO BRACKETS AND TOP 10% ON THE WIDE COINS (frozen model retrained per bracket on the majors; consistency of sign only)")
    for gname in ("G2", "G3"):
        g_ = cu.GEOMS[gname]
        d5g = cu.candidate_frame(bars5, g_)
        X5g = cm.call_features(d5g, feats5, mkt)[cd.DIRECTION]
        dwg = wide_candidates(wbars, elig, g_)
        Xwg = cm.call_features(dwg, allfeats, mkt)[cd.DIRECTION]
        wfg = frozen_predictions(d5g, X5g, dwg, Xwg)
        report(say, f"A frozen {gname}", dwg, wfg, rng, shifts=False)
    x = dw.join(wf_a)
    x = x[x.pred.notna()]
    for fr in (0.10, 0.20):
        s2 = cm.select(x, "pred", fr)
        b_ = rc.per_call(x, s2)
        say(f"  A frozen G1 top {int(fr * 100)}%: selected {b_['sel_r']:+.3f} vs same-side {b_['ctl_r']:+.3f} = excess {b_['diff']:+.3f} (t {b_['t']:+.1f}), n {b_['n']}")

    say()
    ha, hb = ra["h2"], rb["h2"]
    say(f"PREDICTIONS: E1 frozen excess {ra['base']['diff']:+.3f}; E2 absolute selected halves frozen {ra['h1']['sel_r']:+.3f} / {ra['h2']['sel_r']:+.3f}, native {rb['h1']['sel_r']:+.3f} / {rb['h2']['sel_r']:+.3f}; "
        f"E3 native excess {rb['base']['diff']:+.3f} (t {rb['base']['t']:+.1f}); E4 2025-26 selected {ha['sel_r']:+.3f} / {hb['sel_r']:+.3f}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
