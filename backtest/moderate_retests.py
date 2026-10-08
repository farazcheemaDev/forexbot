"""PHASE 2, the MODERATE kills that docs/21-graveyard-audit.md rated but did not re-test (2026-10-09).

    --xs     "Cross-sectional versions of the 19 indicator families: best Sharpe +0.49, worse than price momentum's +1.09"
             (doc 02, early, ONE rebalance day, the measurement mn_combos.py showed can mislead). Re-run: the market-neutral
             book ranked by an indicator instead of 30-day return - RSI(14) and Bollinger %b(20) on daily closes, highest
             long / lowest short - on ALL 7 rebalance days, with and without the +50% short-leg exit, against momentum.
    --grid   "Grid bots: 28 of 30 configurations lose" (doc 11 s3; grid_bot.py on BTC ETH SOL XRP DOGE). Re-run on 15 MORE
             coins (ADA LINK AVAX LTC DOT BNB TRX BCH NEAR UNI ATOM FIL ETC AAVE XLM) at the same 4 spacings, plain and
             range-gated - 120 more configurations, grid_bot.run unchanged.

    --vwap   VWAP reversion (early table, PF 0.46-0.85): long 2 ATR under VWAP(20), daily and 4h, PIT top-40, vs random.
    --meta   meta-labelling (one early attempt): a walk-forward logistic filter on the daily book's trades.
    --wide   "breadth does not scale" (wide_book.py, OLD engine): the corrected engine on the PIT top-40 vs the 12 coins.

REGISTERED BEFORE RUNNING (--vwap / --meta / --wide written before they ran, after --xs / --grid had started):
    --vwap  negative a trade after costs on both timeframes, at best tying its random control: dead.
    --meta  fails the line on at least one boundary (it keeps ~half the trades; the daily book's money is in a few
            pumps a filter cannot pick out in advance).
    --wide  the PIT top-40's holdout stays under a third of the 12 coins' (the gap was far beyond what the engine fixes
            could close); the kill stands.
    --xs    both indicator rankings have a lower mean Sharpe than momentum on both halves across the 7 days (the kill
            stands); RSI-ranking is closest (it is a 14-day momentum in disguise).
    --grid  at least 85% of the 120 new configurations lose money (the kill stands across coins); the survivors are on
            the wide (3%) spacing.

    python -m backtest.moderate_retests --xs
    python -m backtest.moderate_retests --grid
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "moderate_retests.txt"


def out(lines, s):
    lines.append(s)
    print(s, flush=True)


def scored_run(score_mat, start=0, stop=None, short_stop=None):
    """mn_combos.mn_run's machinery with the ranking taken from score_mat's row i (known at close i). With the
    30-day return as the score it reproduces mn_run - asserted in xs()."""
    from backtest import mn_combos as m
    Dd = m.ohl() if stop is not None else m.data()
    idx, X_, Fx, ff = Dd["idx"], Dd["X"], Dd["Fx"], Dd["ff"]
    hold, look, frac = 7, 30, 0.1
    rows, pl_, ps_ = [], set(), set()
    for i in range(look + 1 + start, len(idx) - hold - 1, hold):
        t0 = idx[i]
        ok = (Dd["Em"][Dd["months"][i]] & ((t0.value - Dd["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D)
              & np.isfinite(X_[i]) & np.isfinite(X_[i - look]))
        if ok.sum() < 20:
            continue
        cand = np.flatnonzero(ok)
        past = score_mat[i, cand]
        k = max(int(len(cand) * frac), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        sh, lo = order[:k], order[-k:]
        fwd = ff[i + hold] / X_[i] - 1
        if stop is not None:
            fwd = fwd.copy()
            for x in sh:
                lvl = X_[i, x] * (1 + short_stop)
                for dd in range(i + 1, i + hold + 1):
                    if np.isfinite(Dd["Hi"][dd, x]) and Dd["Hi"][dd, x] >= lvl:
                        fwd[x] = max(Dd["Op"][dd, x], lvl) / X_[i, x] - 1
                        break
        fnd = Fx[i + 1:i + hold + 1].sum(axis=0)
        gross = 0.5 * fwd[lo].mean() - 0.5 * fwd[sh].mean()
        carry = 0.5 * (-fnd[lo].mean()) + 0.5 * fnd[sh].mean()
        L_, S_ = {Dd["cols"][x] for x in lo}, {Dd["cols"][x] for x in sh}
        cost = m.FEE * min((len(L_ ^ pl_) + len(S_ ^ ps_)) / (4 * k), 1.0)
        pl_, ps_ = L_, S_
        rows.append((t0 + pd.Timedelta(days=hold), gross + carry - cost))
    return pd.Series([r for _, r in rows], index=pd.DatetimeIndex([t for t, _ in rows])).groupby(level=0).sum()


def xs():
    from backtest import mn_combos as m
    D = m.data()
    X = D["X"]
    C = pd.DataFrame(X)
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    D["RSI"] = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    ma, sd = C.rolling(20).mean(), C.rolling(20).std(ddof=0)
    D["PCTB"] = ((C - (ma - 2 * sd)) / (4 * sd).replace(0, np.nan)).to_numpy()

    lines = [f"backtest/moderate_retests.py --xs, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-60, weekly, 1x; 7 rebalance days; "
             f"Sharpe tune / holdout (split {m.HOLDOUT:%Y-%m-%d})"]
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    ref, mine = m.mn_run(start=3), scored_run(mom, start=3)
    common = ref.index.intersection(mine.index)
    assert len(common) > 300 and float((ref[common] - mine[common]).abs().max()) < 1e-9, "the indicator machinery != mn_run"
    out(lines, f"  CHECK: with momentum as the score it reproduces mn_combos.mn_run on {len(common)} rebalances")
    for nm, sc in (("30-day momentum (the book)", mom), ("RSI(14) rank", D["RSI"]), ("Bollinger %b(20) rank", D["PCTB"])):
        for xn, kw in (("uncapped", {}), ("+50% short exit", dict(stop="short_only", short_stop=0.5))):
            st = [m.stats(scored_run(sc, start=o, **kw), 7) for o in range(7)]
            out(lines, f"  {nm:28} {xn:16} Sharpe mean {np.mean([s['tune'] for s in st]):+.2f} / {np.mean([s['hold'] for s in st]):+.2f}"
                       f", worst day {min(s['tune'] for s in st):+.2f} / {min(s['hold'] for s in st):+.2f} | falls "
                       f"{min(s['fall'] for s in st) * 100:.0f}-{max(s['fall'] for s in st) * 100:.0f}%")
    return lines


def grid():
    from backtest import grid_bot as G
    coins = ("ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT", "DOTUSDT", "BNBUSDT", "TRXUSDT", "BCHUSDT", "NEARUSDT",
             "UNIUSDT", "ATOMUSDT", "FILUSDT", "ETCUSDT", "AAVEUSDT", "XLMUSDT")
    lines = [f"backtest/moderate_retests.py --grid, {pd.Timestamp.now():%Y-%m-%d %H:%M}; grid_bot.run unchanged, 15 more coins x "
             f"{len(G.SPACINGS)} spacings x plain / range-gated; %/yr of one side's ladder capital"]
    n, win = 0, []
    for sym in coins:
        try:
            h = G.load(sym)
        except FileNotFoundError:
            out(lines, f"  {sym}: no data")
            continue
        cells = []
        for s in G.SPACINGS:
            for gated in (False, True):
                st = G.stats(G.run(h, s, gated))
                n += 1
                win.append((sym, s, gated, st["ann"]))
                cells.append(f"{s:.1%}{'g' if gated else ''} {st['ann']:+.0f}%")
        out(lines, f"  {sym:9} " + "  ".join(cells))
    W = pd.DataFrame(win, columns=["coin", "spacing", "gated", "ann"])
    out(lines, f"  {(W.ann > 0).sum()} of {n} configurations make money; by spacing: "
               + ", ".join(f"{s:.1%} {(g.ann > 0).sum()}/{len(g)}" for s, g in W.groupby("spacing"))
               + f"; median {W.ann.median():+.0f}%/yr")
    return lines


def vwap():
    """VWAP reversion (doc 02's first table, PF 0.46-0.85, early, no universe recorded): long when the close sits 2 ATR
    under its 20-bar volume-weighted average price; out at the next open after a close back at or above it, or after
    12 bars. Control: a random bar of the same coin and month with the same exits. Daily and 4h, PIT top-40."""
    from backtest import capit_combos as cc
    from backtest import daily_combos as dc
    H = dc.HOLDOUT
    rng = np.random.default_rng(0)
    lines = [f"backtest/moderate_retests.py --vwap, {pd.Timestamp.now():%Y-%m-%d %H:%M}; long 2 ATR under VWAP(20), out at VWAP "
             f"or 12 bars; 12bp + funding; control = random bar, same coin-month, same exits; t by distinct day"]

    def trade(i, P, vw):
        o, c, fc = P["o"], P["c"], P["fc"]
        n = len(c)
        e = o[i + 1]
        for j in range(i + 1, min(i + 13, n - 1)):
            if c[j] >= vw[j] or j == i + 12:
                return o[j + 1] / e - 1 - 0.0012 - (fc[j + 1] - fc[i + 1]) / e
        return None

    for tf, PN in (("daily", dc.panel(0)), ("4h", cc.panel4(0))):
        rows = []
        for s, P in PN.items():
            c, v, atr = P["c"], P["v"], P["atr"]
            pv = pd.Series(c * v).rolling(20).sum().to_numpy()
            vv = pd.Series(v).rolling(20).sum().to_numpy()
            vw = pv / np.where(vv > 0, vv, np.nan)
            sig = np.nan_to_num((c - vw) / atr <= -2.0).astype(bool)
            ym, el, t = P["ym"], P["el"], P["t"]
            by_m = pd.Series(np.arange(len(c))).groupby(ym).apply(lambda x: x.to_numpy())
            free = 0
            for i in np.flatnonzero(sig):
                if i < 60 or i < free or i + 14 >= len(c) or ym[i] not in el:
                    continue
                r = trade(i, P, vw)
                pool = by_m[ym[i]]
                pool = pool[(pool > 60) & (pool + 14 < len(c))]
                if not len(pool):
                    continue
                k = int(rng.choice(pool))
                rc = trade(k, P, vw)
                if r is None or rc is None:
                    continue
                rows.append((t[i + 1], r, rc))
                free = i + 13
        T = pd.DataFrame(rows, columns=["t", "net", "ctrl"])
        T["day"] = pd.DatetimeIndex(T.t).floor("D")
        cells, ok = [], True
        for half, x in (("tune", T[T.t < H]), ("holdout", T[T.t >= H])):
            d = (x.net - x.ctrl).groupby(x.day).mean()
            tt = d.mean() / d.std(ddof=1) * np.sqrt(len(d))
            ok = ok and x.net.mean() > 0 and tt > 2
            cells.append(f"{half}: n {len(x)}, {x.net.mean() * 100:+.2f}% a trade vs control {x.ctrl.mean() * 100:+.2f}% "
                         f"(excess t {tt:+.1f})")
        out(lines, f"  {tf:5}: " + " | ".join(cells) + f" -> {'ALIVE' if ok else 'dead'}")
    return lines


def meta():
    """Meta-labelling (doc 02: "ML filter on signals ... didn't save it", one early attempt): a logistic model on the
    daily book's entry features, retrained each January on trades CLOSED before it, keeps the trades it scores above
    the training median. Judged like daily_combos.py: the base's leverage line, both halves, 3 day boundaries."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from backtest import daily_combos as dc
    feats = ("br", "rk", "vr", "atrp", "ext", "btc_r28", "fg")
    lines = [f"backtest/moderate_retests.py --meta, {pd.Timestamp.now():%Y-%m-%d %H:%M}; walk-forward logistic filter on the daily "
             f"book (features {', '.join(feats)}, RSI, distance to EMA200)"]
    keep_sets = {}
    for off in dc.PHASES:
        PN, X = dc.panel(off), dc.features(off)
        T = dc.gen(off, dc.BASE)
        fr = []
        for r in T.itertuples():
            P, F = PN[r.coin], X[r.coin]
            i = int(np.searchsorted(P["t"], np.datetime64(r.t_in, "ns"))) - 1
            fr.append([F[f][i] for f in feats] + [P["r"][i], P["c"][i] / F["ema200"][i] - 1])
        Z = np.nan_to_num(np.array(fr, float), nan=0.0, posinf=0.0, neginf=0.0)
        y = (T.net > 0).to_numpy()
        tin, tout = T.t_in.to_numpy("datetime64[ns]"), T.t_out.to_numpy("datetime64[ns]")
        keep = np.ones(len(T), bool)
        for yr in range(2021, 2027):
            start = np.datetime64(f"{yr}-01-01", "ns")
            tr = tout < start
            te = (tin >= start) & (tin < np.datetime64(f"{yr + 1}-01-01", "ns"))
            if tr.sum() < 50 or te.sum() == 0:
                continue
            mdl = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(Z[tr], y[tr])
            thr = np.median(mdl.predict_proba(Z[tr])[:, 1])
            keep[te] = mdl.predict_proba(Z[te])[:, 1] >= thr
        keep_sets[off] = (T, keep)
    base, _ = dc.run(dc.BASE, dc.LEVS)

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in dc.SEEDS])

    cells, ok = [], True
    for off in dc.PHASES:
        T, keep = keep_sets[off]
        Tk = T[keep].reset_index(drop=True)
        res = {s: dc.stats(dc.curve(Tk, dc.allocate(Tk, s), off)) for s in dc.SEEDS}
        line = sorted((agg(base, off, "fall", lv), agg(base, off, "tune", lv), agg(base, off, "hold", lv)) for lv in dc.LEVS)
        fa = np.mean([res[s]["fall"] for s in dc.SEEDS])
        dt = np.mean([res[s]["tune"] for s in dc.SEEDS]) - np.interp(fa, [a for a, _, _ in line], [b for _, b, _ in line])
        dh = np.mean([res[s]["hold"] for s in dc.SEEDS]) - np.interp(fa, [a for a, _, _ in line], [c for _, _, c in line])
        ok = ok and dt > 0 and dh > 0
        cells.append(f"boundary {off:02d}: kept {keep.mean() * 100:.0f}% of {len(T)} trades, fall {fa * 100:.0f}%, vs line "
                     f"{dt * 100:+.0f} / {dh * 100:+.0f}")
    out(lines, "  " + " | ".join(cells) + f" -> {'PASS' if ok else 'fail'}")
    return lines


def wide():
    """"Breadth does not scale" (doc 02, wide_book.py: the hourly trend engine on the PIT top-30/60/100 earned <= +0.75 %/mo
    on the holdout against +6.56 on the 12 coins) - measured on the OLD engine and never re-scored. Re-run on the
    corrected engine (engine_rescore2.walk2, real entry times, entry-sized, 12 slots, 1000h gate, 10 orderings), longs
    only, with BOTH universes loaded the same way (capitulation_wide.hourly, the fixed loader) and no funding on either
    (funding only lowers a long book, so leaving it out cannot hide a gap that is there): the 12 BOOK coins vs the PIT
    top-40 (dead coins in, a row kept only if its entry month was in the coin's top-40 months). Main and triple rules."""
    from backtest import blend
    from backtest import engine_rescore2 as E
    from backtest import graveyard_rescore as G
    from backtest.bear_side import sleeve_sided
    from backtest.bull_boost import regimes
    from backtest.capitulation_wide import hourly
    from backtest.causal_t0 import real_t0
    from backtest.engine_variants import break_map
    from backtest.timeframes import resample
    from backtest.wide_book import eligibility
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    el = eligibility(40)
    lines = [f"backtest/moderate_retests.py --wide, {pd.Timestamp.now():%Y-%m-%d %H:%M}; corrected engine, longs only, no funding "
             f"on either side, tune < {cut:%Y-%m-%d} <= holdout; %/mo is CAGR/3"]
    for cfg_nm, kw in (("MAIN", {}), ("TRIPLE", dict(tight=True, time_stop=(100, 2.0), max_units=7))):
        res = {}
        for uni_nm, coins in (("12 BOOK coins", list(blend.BOOK)), ("PIT top-40", sorted(s for s, m in el.items() if m))):
            rows = []
            for s in coins:
                h = hourly(s)
                if h is None:
                    continue
                h = h.rename(columns={"qvol": "volume"})
                for rule in ("1h", "4h", "12h"):
                    df = resample(h, rule)
                    if len(df) < 300:
                        continue
                    k2 = {k: v for k, v in kw.items() if k != "tight"}
                    rr = E.walk2(df, rule, s, tb=break_map(df, rule) if kw.get("tight") else None, **k2)
                    if uni_nm.startswith("PIT"):
                        rr = [r for r in rr if pd.Timestamp(r["t0"]).strftime("%Y-%m") in el[s]]
                    rows += rr
            rows = real_t0(rows)
            S = G.score(rows, bear, cut)
            res[uni_nm] = S
            out(lines, f"  {cfg_nm:6} {uni_nm:14} {len(rows):6} trades | tune {S['tune'][:, 0].mean():+6.2f}%/mo DD "
                       f"{S['tune'][:, 1].mean():3.0f}% | holdout {S['hold'][:, 0].mean():+6.2f}%/mo DD {S['hold'][:, 1].mean():3.0f}%")
    return lines


def main():
    lines = []
    if "--xs" in sys.argv:
        lines += xs()
    if "--grid" in sys.argv:
        lines += grid()
    if "--vwap" in sys.argv:
        lines += vwap()
    if "--meta" in sys.argv:
        lines += meta()
    if "--wide" in sys.argv:
        lines += wide()
    prev = LOG.read_text() if LOG.exists() else ""
    LOG.write_text(prev + "\n".join(lines) + "\n\n")


if __name__ == "__main__":
    main()
