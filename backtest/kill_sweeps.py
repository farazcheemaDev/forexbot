"""THE RE-TESTED KILLS, SWEPT OVER THEIR PARAMETERS (2026-10-09).

docs/21-graveyard-audit.md re-tested each thin / moderate kill, but mostly at ONE setting (or a handful). A kill that holds
at one setting can hide a working neighbour, so each is swept here over the parameters that define it:
    --sweep   ICT sweep-and-reclaim of the prior day's / prior WEEK's low (and the short mirror): target 1 / 2 / 3% x
              hold 12 / 24 / 48h x level day / week = 18 per side (36). Judged as a TRADE: net a trade > 0 on both halves.
    --vwap    VWAP reversion on daily bars: VWAP window 10 / 20 / 50 x entry 1.5 / 2 / 2.5 / 3 ATR under x max hold
              5 / 12 / 20 days = 36, each as an ACCOUNT (8 slots 1x, marked, 10 orders) on day boundary 00 UTC; any with a
              positive holdout account is re-run at 08 / 16.
    --carry   funding carry MN: funding window 3 / 7 / 14 / 30 days x short-leg exit none / +50% / +100% x basket 10 / 20%
              = 24, each on all 7 rebalance weekdays.
    --pairs   crypto pairs: formation 60 / 90 / 180 days x entry z 1.5 / 2 / 2.5 x stop 4 / none = 18.
    --meta    meta-labelling on the daily book: logistic / gradient-boosted trees x keep the top half / top 30% = 4.
    --xs      the market-neutral book ranked by RSI(14), RSI(7), MACD histogram, ROC(14), Stochastic %K(14), CCI(20),
              Bollinger %b(20) - and momentum/RSI blends at 25 / 50 / 75% RSI - all on 7 weekdays with the +50% exit.
    --grid    grid bots at 4% / 5% spacing (plain and range-gated) on all 20 coins (the 5 original + 15).
REGISTERED BEFORE RUNNING: sweep - no setting is positive a trade on both halves (the information is real, smaller than
fees everywhere); vwap - no setting has a positive holdout ACCOUNT at all three boundaries; carry - no setting reaches a
holdout Sharpe of +0.6 on the mean of 7 weekdays; pairs - every setting negative on at least one half; meta - all 4 fail
the line; xs - momentum + RSI at 50% stays the best blend, no single indicator beats it on both halves; grid - wider
spacings lose less but under a quarter of the 80 make money.

    python -m backtest.kill_sweeps --sweep --vwap --carry --meta --xs --grid
    python -m backtest.kill_sweeps --pairs        (slow, ~1 hour)
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / ("kill_sweeps_" + "_".join(sorted(a[2:] for a in sys.argv if a.startswith("--"))) + ".txt")
_L: list = []


def out(s):
    _L.append(s)
    print(s, flush=True)
    LOG.write_text("\n".join(_L) + "\n")


def sweep():
    from backtest import pair_lab as pl
    from backtest.capitulation_wide import funding_cum
    H = pl.HOLDOUT
    data = []
    for s, hh in pl.hourly_all().items():
        t = hh.time.to_numpy("datetime64[ns]")
        o, h, l, c = (hh[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        fc = funding_cum(s, hh.time.to_numpy(), hh)
        ym = pd.DatetimeIndex(t).strftime("%Y-%m").to_numpy()
        data.append((s, t, o, h, l, c, fc, ym, pl.universe()[s]))
    out(f"--sweep: PIT top-40 hourly, net a trade (12bp + funding) tune / holdout (split {H:%Y-%m-%d}); first signal per coin "
        f"per period")
    for level, side, tp, hold in itertools.product(("day", "week"), (1, -1), (0.01, 0.02, 0.03), (12, 24, 48)):
        nets = []
        for s, t, o, h, l, c, fc, ym, el in data:
            per = pd.DatetimeIndex(t).floor("D") if level == "day" else pd.DatetimeIndex(t).to_period("W").start_time
            ref = pd.Series(l if side > 0 else h, index=t).groupby(per).agg("min" if side > 0 else "max")
            prev = ref.shift(1).reindex(per).to_numpy()
            sig = ((l < prev) & (c > prev)) if side > 0 else ((h > prev) & (c < prev))
            seen = set()
            n = len(c)
            for i in np.flatnonzero(sig):
                if i < 200 or i + hold + 2 >= n or ym[i] not in el or per[i] in seen:
                    continue
                seen.add(per[i])
                e, stop = o[i + 1], (l[i] if side > 0 else h[i])
                if (side > 0 and stop >= e) or (side < 0 and stop <= e):
                    continue
                r = None
                for j in range(i + 1, i + hold + 1):
                    if (l[j] <= stop) if side > 0 else (h[j] >= stop):
                        x = min(o[j], stop) if side > 0 else max(o[j], stop)
                        r = side * (x / e - 1) - 0.0012 - side * (fc[j] - fc[i + 1]) / e
                        break
                    if (h[j] >= e * (1 + tp)) if side > 0 else (l[j] <= e * (1 - tp)):
                        r = tp - 0.0012 - side * (fc[j] - fc[i + 1]) / e
                        break
                if r is None:
                    j = i + hold
                    r = side * (c[j] / e - 1) - 0.0012 - side * (fc[j] - fc[i + 1]) / e
                nets.append((t[i + 1], r))
        T = pd.DataFrame(nets, columns=["t", "r"])
        a, b = T.r[T.t < H].mean(), T.r[T.t >= H].mean()
        out(f"  {'long ' if side > 0 else 'short'} {level:4} target {tp:.0%} hold {hold:2}h: n {len(T):6} | {a * 100:+.3f}% / "
            f"{b * 100:+.3f}% a trade {'<- POSITIVE BOTH' if a > 0 and b > 0 else ''}")


def vwap():
    from backtest import daily_combos as dc
    H = dc.HOLDOUT

    def trades(off, win, z, mh):
        rows = []
        for s, P in dc.panel(off).items():
            o, c, v, atr, fc, t, lo = P["o"], P["c"], P["v"], P["atr"], P["fc"], P["t"], P["l"]
            vw = pd.Series(c * v).rolling(win).sum().to_numpy() / np.where(
                pd.Series(v).rolling(win).sum().to_numpy() > 0, pd.Series(v).rolling(win).sum().to_numpy(), np.nan)
            sig = np.nan_to_num((c - vw) / atr <= -z).astype(bool)
            n, free = len(c), 0
            for i in np.flatnonzero(sig):
                if i < 60 or i < free or i + mh + 2 >= n or P["ym"][i] not in P["el"]:
                    continue
                e, worst = o[i + 1], 0.0
                for j in range(i + 1, i + mh + 1):
                    worst = max(worst, 1 - lo[j] / e)
                    if c[j] >= vw[j] or j == i + mh:
                        rows.append((s, t[i + 1], t[j + 1], o[j + 1] / e - 1 - dc.FEE - (fc[j + 1] - fc[i + 1]) / e, worst,
                                     [(t[i + 1], e)], "vwap", 0.0))
                        free = j + 1
                        break
        return pd.DataFrame(rows, columns=["coin", "t_in", "t_out", "net", "worst", "units", "why", "score"])

    def acct(T, off):
        r = [dc.stats(dc.curve(T, dc.allocate(T, s), off)) for s in dc.SEEDS]
        return {k: np.mean([x[k] for x in r]) for k in r[0]}

    out("--vwap: daily, PIT top-40, an ACCOUNT of 8 slots 1x marked, 10 orders; day boundary 00 UTC (others if the holdout "
        "account is positive)")
    for win, z, mh in itertools.product((10, 20, 50), (1.5, 2.0, 2.5, 3.0), (5, 12, 20)):
        T = trades(0, win, z, mh)
        a = acct(T, 0)
        extra = ""
        if a["hold"] > 0 and a["tune"] > 0:
            b8, b16 = acct(trades(8, win, z, mh), 8), acct(trades(16, win, z, mh), 16)
            extra = f" | 08: {b8['tune'] * 100:+.0f}/{b8['hold'] * 100:+.0f}  16: {b16['tune'] * 100:+.0f}/{b16['hold'] * 100:+.0f}"
            if b8["hold"] > 0 and b16["hold"] > 0 and b8["tune"] > 0 and b16["tune"] > 0:
                extra += "  <- POSITIVE ACCOUNT AT ALL 3"
        out(f"  VWAP({win}) {z} ATR under, max {mh}d: {len(T):5} trades, {T.net[T.t_in < H].mean() * 100:+.2f}% / "
            f"{T.net[T.t_in >= H].mean() * 100:+.2f}% a trade | account {a['tune'] * 100:+.0f}% / {a['hold'] * 100:+.0f}% a year, "
            f"fall {a['fall'] * 100:.0f}%{extra}")


def carry():
    from backtest import mn_combos as m
    out(f"--carry: funding carry MN on 7 rebalance weekdays, Sharpe tune / holdout mean (worst day)")
    for fw, ex, frac in itertools.product((3, 7, 14, 30), (None, 0.5, 1.0), (0.1, 0.2)):
        kw = dict(stop="short_only", short_stop=ex) if ex else {}
        st = [m.stats(m.mn_run(look=1, score="funding7", fwin=fw, frac=frac, start=o, **kw), 7) for o in range(7)]
        out(f"  window {fw:2}d, short exit {('+' + format(ex, '.0%')) if ex else 'none':>5}, basket {frac:.0%}: Sharpe "
            f"{np.mean([s['tune'] for s in st]):+.2f} / {np.mean([s['hold'] for s in st]):+.2f} (worst {min(s['tune'] for s in st):+.2f} / "
            f"{min(s['hold'] for s in st):+.2f}), falls {min(s['fall'] for s in st) * 100:.0f}-{max(s['fall'] for s in st) * 100:.0f}%")


def pairs():
    from backtest.bear_chop import pairs_book, per_month, tag
    from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel
    from backtest.wide_book import eligibility
    C, F, first = load_panel()
    F.index = C.index
    reg = btc_regime(C)
    e30 = drop_non_crypto(eligibility(30))
    out("--pairs: Engle-Granger pairs, PIT top-30, 10 pairs, next-close fills; %/month ALL / TUNE / HOLD")
    for win, zin, zs in itertools.product((60, 90, 180), (1.5, 2.0, 2.5), (4.0, 99.0)):
        daily, tr = pairs_book(C, F, first, e30, lag=1, win=win, z_in=zin, z_stop=zs)
        d = tag(pd.DataFrame(dict(t=daily.index, net=daily.to_numpy())), reg)
        pm = lambda x: per_month(x, "net", 1)  # noqa: E731
        out(f"  formation {win:3}d, entry z {zin}, stop {'none' if zs > 50 else zs}: {pm(d):+.2f}% / {pm(d[d.half == 'tune']):+.2f}% / "
            f"{pm(d[d.half == 'hold']):+.2f}% ({len(tr)} trades)")


def meta():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from backtest import daily_combos as dc
    feats = ("br", "rk", "vr", "atrp", "ext", "btc_r28", "fg")
    base, _ = dc.run(dc.BASE, dc.LEVS)

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in dc.SEEDS])

    out("--meta: walk-forward filters on the daily book (retrained each January on trades closed before it), vs bb's line")
    prepared = {}
    for off in dc.PHASES:
        PN, X = dc.panel(off), dc.features(off)
        T = dc.gen(off, dc.BASE)
        fr = []
        for r in T.itertuples():
            P, F_ = PN[r.coin], X[r.coin]
            i = int(np.searchsorted(P["t"], np.datetime64(r.t_in, "ns"))) - 1
            fr.append([F_[f][i] for f in feats] + [P["r"][i], P["c"][i] / F_["ema200"][i] - 1])
        prepared[off] = (T, np.nan_to_num(np.array(fr, float), nan=0.0, posinf=0.0, neginf=0.0))
    for mname, keep_q in itertools.product(("logistic", "boosted trees"), (0.5, 0.7)):
        ok, cells = True, []
        for off in dc.PHASES:
            T, Z = prepared[off]
            y = (T.net > 0).to_numpy()
            tin, tout = T.t_in.to_numpy("datetime64[ns]"), T.t_out.to_numpy("datetime64[ns]")
            keep = np.ones(len(T), bool)
            for yr in range(2021, 2027):
                st = np.datetime64(f"{yr}-01-01", "ns")
                tr, te = tout < st, (tin >= st) & (tin < np.datetime64(f"{yr + 1}-01-01", "ns"))
                if tr.sum() < 50 or not te.any():
                    continue
                mdl = (make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)) if mname == "logistic"
                       else HistGradientBoostingClassifier(max_depth=3, max_iter=150))
                mdl.fit(Z[tr], y[tr])
                thr = np.quantile(mdl.predict_proba(Z[tr])[:, 1], keep_q)
                keep[te] = mdl.predict_proba(Z[te])[:, 1] >= thr
            Tk = T[keep].reset_index(drop=True)
            res = [dc.stats(dc.curve(Tk, dc.allocate(Tk, s), off)) for s in dc.SEEDS]
            line = sorted((agg(base, off, "fall", lv), agg(base, off, "tune", lv), agg(base, off, "hold", lv)) for lv in dc.LEVS)
            fa = np.mean([x["fall"] for x in res])
            dt = np.mean([x["tune"] for x in res]) - np.interp(fa, [a for a, _, _ in line], [b for _, b, _ in line])
            dh = np.mean([x["hold"] for x in res]) - np.interp(fa, [a for a, _, _ in line], [c for _, _, c in line])
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
        out(f"  {mname:14} keep top {1 - keep_q:.0%}: {'  '.join(cells)} -> {'PASS' if ok else 'fail'}")


def xs():
    from backtest import mn_combos as m
    from backtest.moderate_retests import scored_run
    D = m.data()
    C = pd.DataFrame(D["X"])

    def rsi(n):
        d = C.diff()
        up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
        dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
        return (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()

    macd = C.ewm(span=12, adjust=False).mean() - C.ewm(span=26, adjust=False).mean()
    hist = ((macd - macd.ewm(span=9, adjust=False).mean()) / C).to_numpy()
    roc = (C / C.shift(14) - 1).to_numpy()
    lo14, hi14 = C.rolling(14).min(), C.rolling(14).max()
    stoch = ((C - lo14) / (hi14 - lo14).replace(0, np.nan)).to_numpy()
    tp = C
    cci = ((tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True))).to_numpy()
    ma, sd = C.rolling(20).mean(), C.rolling(20).std(ddof=0)
    pctb = ((C - (ma - 2 * sd)) / (4 * sd).replace(0, np.nan)).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    scores = {"momentum 30d (the book)": mom, "RSI(14)": rsi(14), "RSI(7)": rsi(7), "MACD histogram": hist, "ROC(14)": roc,
              "Stochastic %K(14)": stoch, "CCI(20)": cci, "Bollinger %b(20)": pctb}
    out("--xs: the MN book ranked by each score, +50% short-leg exit, 7 rebalance weekdays: Sharpe tune / holdout mean (worst day)")
    series = {}
    for nm, sc in scores.items():
        ss = [scored_run(sc, start=o, stop="short_only", short_stop=0.5) for o in range(7)]
        series[nm] = ss
        st = [m.stats(x, 7) for x in ss]
        out(f"  {nm:24} {np.mean([s['tune'] for s in st]):+.2f} / {np.mean([s['hold'] for s in st]):+.2f} "
            f"({min(s['tune'] for s in st):+.2f} / {min(s['hold'] for s in st):+.2f}), falls "
            f"{min(s['fall'] for s in st) * 100:.0f}-{max(s['fall'] for s in st) * 100:.0f}%")
    for w in (0.25, 0.5, 0.75):
        st = []
        for o in range(7):
            a, b = series["momentum 30d (the book)"][o], series["RSI(14)"][o]
            idx = a.index.union(b.index)
            st.append(m.stats((1 - w) * a.reindex(idx).fillna(0) + w * b.reindex(idx).fillna(0), 7))
        out(f"  blend momentum / RSI(14) at {w:.0%} RSI: {np.mean([s['tune'] for s in st]):+.2f} / {np.mean([s['hold'] for s in st]):+.2f} "
            f"({min(s['tune'] for s in st):+.2f} / {min(s['hold'] for s in st):+.2f})")


def grid():
    from backtest import grid_bot as G
    coins = G.COINS + ("ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT", "DOTUSDT", "BNBUSDT", "TRXUSDT", "BCHUSDT", "NEARUSDT",
                       "UNIUSDT", "ATOMUSDT", "FILUSDT", "ETCUSDT", "AAVEUSDT", "XLMUSDT")
    out("--grid: 4% / 5% spacing, plain and range-gated, 20 coins; %/yr of one side's ladder capital")
    W = []
    for sym in coins:
        h = G.load(sym)
        cells = []
        for s, g in itertools.product((0.04, 0.05), (False, True)):
            a = G.stats(G.run(h, s, g))["ann"]
            W.append(a)
            cells.append(f"{s:.0%}{'g' if g else ''} {a:+.0f}%")
        out(f"  {sym:9} " + "  ".join(cells))
    W = np.array(W)
    out(f"  {(W > 0).sum()} of {len(W)} make money; median {np.median(W):+.0f}%/yr")


def main():
    for flag, fn in (("--sweep", sweep), ("--vwap", vwap), ("--carry", carry), ("--meta", meta), ("--xs", xs),
                     ("--grid", grid), ("--pairs", pairs)):
        if flag in sys.argv:
            fn()
            out("")


if __name__ == "__main__":
    main()
