"""IS THE ENTRY-RUNNER EDGE WORTH MORE? - harder sizing, more features, a stronger model,
and the one that matters: sizing COMBINED with the tight-exit rule, then levered to today's
drawdown.

Builds on entry_runner.py (runner predictable at entry, holdout AUC 0.675 full / 0.591
position-only; linear +-90% sizing beat matched-DD uniform by ~+1.5-2%/mo). Four questions:

  1. MORE FEATURES. Add breadth (how many signals fired across the book in the last 24h -
     a market-wide breakout is a trend day) and BTC volatility expansion. Does OOS AUC rise?
  2. STRONGER MODEL. Gradient boosting vs logistic, strictly OOS. Does AUC rise, or overfit?
  3. HARDER SIZING. Convex tilt and a hard bottom-decile cut vs the linear tilt, each against
     a uniform bet at the SAME drawdown (the only honest control - bull_boost.py).
  4. STACK THE TWO EDGES. Sizing (return) + the BTC-4h-break tight exit (drawdown), then the
     leverage headline: run the combination at the risk that returns drawdown to today's 64%,
     and see the return. That is what "leverage it more" actually means.

Everything is fit on the first 60% of dates and judged only on the last 40%. Sizing keeps
mean risk constant, so a win is skill, not leverage, until section 4 deliberately adds
leverage against a matched-drawdown yardstick.

    python -m backtest.runner_leverage
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.btc_exit import btc_trail  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.runner_id import auc, btc_context  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

RULES = ["1h", "4h", "12h"]
RUN_R = 50.0
BASE_FEATS = ["atr_expand", "ext_ma", "coin_30", "coin_90", "brk", "vsurge"]
AUG_FEATS = BASE_FEATS + ["breadth", "btc_atr_expand"]


def walk(df, s, a, feat_arrays, tb, coin, rule):
    """ONE position at a time (deployed behaviour). tb=None -> deployed 20xATR trail;
    tb given -> tighten to 5xATR for good once a BTC break is active after entry. Records
    entry features, exit R, peak. Returns list of position dicts."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    t = pd.DatetimeIndex(df["time"])
    fee = FEE_BP / 1e4
    out, pos = [], None
    for i in range(1, len(df)):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            pos = dict(risk=blend.SL_MULT * a[i - 1], stop=o[i] - blend.SL_MULT * a[i - 1],
                       best=o[i], bar=i, ents=[o[i]], nxt=1, peak=0.0, tight=False,
                       armed=(tb is None or not tb[i]),
                       feat=feat_arrays(i))
        if pos is None:
            continue
        risk = pos["risk"]; e0 = pos["ents"][0]
        pos["peak"] = max(pos["peak"], sum(h[i] - e for e in pos["ents"]) / risk)
        if tb is not None and i > pos["bar"]:
            if not tb[i]:
                pos["armed"] = True
            elif pos["armed"]:
                pos["tight"] = True
        if lo[i] <= pos["stop"]:
            R = (sum(pos["stop"] - e for e in pos["ents"])
                 - sum(fee * e for e in pos["ents"])) / risk
            out.append({**pos["feat"], "coin": coin, "rule": rule, "t0": t[pos["bar"]],
                        "t1": t[i], "R": float(R), "peak": float(pos["peak"])})
            pos = None
            continue
        if len(pos["ents"]) < blend.MAX_UNITS and (h[i] - e0) / risk >= pos["nxt"] * blend.ADD_EVERY:
            pos["ents"].append(e0 + pos["nxt"] * blend.ADD_EVERY * risk); pos["nxt"] += 1
        pos["best"] = max(pos["best"], h[i])
        tm = 5.0 if pos["tight"] else blend.LONG_TRAIL
        cand = pos["best"] - tm * a[i - 1]
        if (pos["best"] - e0) / risk >= blend.BE_AT:
            cand = max(cand, e0)
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None:
        R = (sum(c[-1] - e for e in pos["ents"]) - sum(fee * e for e in pos["ents"])) / pos["risk"]
        out.append({**pos["feat"], "coin": coin, "rule": rule, "t0": t[pos["bar"]],
                    "t1": t[-1], "R": float(R), "peak": float(pos["peak"])})
    return out


def build():
    btc = btc_context()
    bd = blend.load("BTCUSDT")
    b4 = resample(bd, "4h")
    ba = atr_ind(b4, 14).to_numpy(float)
    ba_avg = pd.Series(ba).rolling(60).mean().to_numpy()
    btc_ax = pd.Series(np.where((ba_avg > 0), ba / ba_avg, 1.0),
                       index=pd.DatetimeIndex(b4["time"]))
    breaks = btc_trail(5)                                   # 4h break flags
    dep_rows, tight_rows, shorts, sig_times = [], [], [], []
    for rule in RULES:
        _tr, stops = sleeve_sided(rule)
        shorts += [dict(t0=a_, t1=b_, R=r, sf=stops.get(c_, 0.05), adds=[a_], side="short",
                        coin=c_, rule=rule) for a_, b_, r, _ru, c_, side in _tr if side == "short"]
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            s = signals(df, "long", "all").to_numpy()
            c = df["close"].to_numpy(float); v = df["volume"].to_numpy(float)
            a = atr_ind(df, 14).to_numpy(float)
            t = pd.DatetimeIndex(df["time"])
            ma200 = pd.Series(c).rolling(200).mean().to_numpy()
            mabb = pd.Series(c).rolling(30).mean().to_numpy()
            sdbb = pd.Series(c).rolling(30).std(ddof=0).to_numpy()
            aavg = pd.Series(a).rolling(60).mean().to_numpy()
            vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
            sig_times += [t[i] for i in range(1, len(df)) if s[i] == Action.BUY]

            def feat_arrays(i, t=t, c=c, v=v, a=a, ma200=ma200, mabb=mabb, sdbb=sdbb,
                            aavg=aavg, vavg=vavg):
                j = i - 1
                try:
                    bx = float(btc_ax.asof(t[i]))
                except Exception:
                    bx = 1.0
                return dict(
                    atr_expand=float(a[j] / aavg[j]) if aavg[j] and aavg[j] > 0 else 1.0,
                    ext_ma=float(c[j] / ma200[j]) if np.isfinite(ma200[j]) and ma200[j] > 0 else 1.0,
                    coin_30=float(c[j] / c[j - 30] - 1) if j >= 30 else 0.0,
                    coin_90=float(c[j] / c[j - 90] - 1) if j >= 90 else 0.0,
                    brk=float((c[j] - (mabb[j] + 1.5 * sdbb[j])) / a[j]) if a[j] > 0 else 0.0,
                    vsurge=float(v[j] / vavg[j]) if vavg[j] and vavg[j] > 0 else 1.0,
                    btc_atr_expand=bx)

            starts = t if rule == "1h" else t - pd.Timedelta(rule)
            tb = breaks.reindex(breaks.index.union(starts)).ffill().reindex(starts)\
                .fillna(False).to_numpy(bool)
            dep_rows += walk(df, s, a, feat_arrays, None, coin, rule)
            tight_rows += walk(df, s, a, feat_arrays, tb, coin, rule)

    def finish(rows):
        D = pd.DataFrame(rows).sort_values("t0").reset_index(drop=True)
        D["runner"] = (D["peak"] >= RUN_R).astype(int)
        return D
    Ddep, Dtight = finish(dep_rows), finish(tight_rows)
    # breadth: BUY signals across the whole book in the prior 24h (causal), from ALL
    # signals whether taken or not; attached to each position by its entry time
    st = np.sort(np.array(sig_times, dtype="datetime64[ns]"))
    win = np.timedelta64(24, "h")
    for D in (Ddep, Dtight):
        tt = D["t0"].to_numpy().astype("datetime64[ns]")
        D["breadth"] = (np.searchsorted(st, tt, "right")
                        - np.searchsorted(st, tt - win, "left")).astype(float)
    return Ddep, Dtight, shorts


def fit(tr, te, feats, gb=False):
    from sklearn.preprocessing import StandardScaler
    Xtr, Xte = tr[feats].to_numpy(float), te[feats].to_numpy(float)
    ytr = tr["runner"].to_numpy()
    if gb:
        from sklearn.ensemble import HistGradientBoostingClassifier
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=120,
                                           learning_rate=0.05, l2_regularization=1.0,
                                           min_samples_leaf=60, random_state=0)
        m.fit(Xtr, ytr)
        return m.predict_proba(Xte)[:, 1]
    from sklearn.linear_model import LogisticRegression
    sc = StandardScaler().fit(Xtr)
    m = LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced").fit(sc.transform(Xtr), ytr)
    return m.predict_proba(sc.transform(Xte))[:, 1]


def curve(rows, bear, cut, spread=0.0, mode="linear", drop_frac=0.0, uniform=1.0, seeds=(0,)):
    """Holdout return/DD, AVERAGED over `seeds` random orderings of simultaneous entries
    (that ordering alone swings the result +-several %/mo). spread/mode/drop_frac define the
    model sizing on longs (mean risk ~constant); uniform is a flat multiplier."""
    hpm, dd, wm = [], [], []
    for sd in seeds:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        ordered = [rows[i] for i in sorted(range(len(rows)),
                                           key=lambda i: (rows[i]["t0"], tie[i]))]
        out = []
        for r in ordered:
            f = uniform
            if r["side"] == "long" and spread > 0:
                rank = r["_rank"]
                if mode == "linear":
                    f *= 1.0 + spread * (rank - 0.5) * 2
                elif mode == "convex":
                    f *= 1.0 + spread * np.sign(rank - 0.5) * (abs(rank - 0.5) * 2) ** 2
                if drop_frac and rank < drop_frac:
                    f = 0.0
            out.append(dict(r, R=r["R"] * f))
        s = evaluate(out, bear, t_from=cut)
        hpm.append(s["hpm"]); dd.append(s["dd"]); wm.append(s["worst_mo"])
    return dict(hpm=float(np.mean(hpm)), dd=float(np.mean(dd)), worst_mo=float(np.mean(wm)))


def rank_field(rows, field):
    vals = [r.get(field) for r in rows if r["side"] == "long" and r.get(field) is not None]
    ser = pd.Series(vals).rank(pct=True)
    k = 0
    for r in rows:
        if r["side"] == "long" and r.get(field) is not None:
            r["_rank"] = float(ser.iloc[k]); k += 1
        else:
            r["_rank"] = 0.5


def rowset(D, shorts, key, med):
    rows = [dict(coin=r.coin, rule=r.rule, t0=r.t0, t1=r.t1, R=r.R, side="long",
                 sf=0.05, adds=[r.t0], p=key.get((r.t0, r.coin, r.rule), med))
            for r in D.itertuples()]
    rows += [dict(r, p=med) for r in shorts]
    rows.sort(key=lambda r: r["t0"])
    rank_field(rows, "p")
    return rows


def main():
    Ddep, Dtight, shorts = build()
    cut = Ddep["t0"].quantile(0.6)
    tr, te = Ddep[Ddep.t0 < cut], Ddep[Ddep.t0 >= cut]
    yte = te["runner"].to_numpy()
    print(f"deployed book {len(Ddep):,} longs | tight book {len(Dtight):,} longs | "
          f"{len(shorts):,} shorts | runner peak>= {RUN_R:.0f}R")
    print(f"tune {len(tr):,} ({tr.runner.mean()*100:.1f}%)  holdout {len(te):,} "
          f"({te.runner.mean()*100:.1f}%)")

    print("\n1+2. OOS AUC on the deployed book (fit on tune, scored on holdout)")
    print(f"  {'model':<36}{'holdout AUC':>12}")
    combos = [("logistic, position-only (baseline)", BASE_FEATS, False),
              ("logistic, + breadth + BTC vol", AUG_FEATS, False),
              ("grad boosting, + breadth + BTC vol", AUG_FEATS, True)]
    best_auc, best_feats, best_gb, best_name = 0.0, BASE_FEATS, False, combos[0][0]
    for name, feats, gb in combos:
        A = auc(*(lambda p: (p[yte == 1], p[yte == 0]))(fit(tr, te, feats, gb)))
        print(f"  {name:<36}{A:>12.3f}")
        if A > best_auc:
            best_auc, best_feats, best_gb, best_name = A, feats, gb, name

    bear = regimes()[1000]
    p_dep = fit(tr, Ddep, best_feats, best_gb)
    p_tig = fit(tr, Dtight, best_feats, best_gb)
    med = float(np.median(p_dep))
    kdep = {(r.t0, r.coin, r.rule): pv for r, pv in zip(Ddep.itertuples(), p_dep)}
    ktig = {(r.t0, r.coin, r.rule): pv for r, pv in zip(Dtight.itertuples(), p_tig)}
    rows_dep = rowset(Ddep, shorts, kdep, med)
    rows_tig = rowset(Dtight, shorts, ktig, med)
    print(f"\n  best model: {best_name} (AUC {best_auc:.3f})")

    SEEDS = (0, 1, 2, 3, 4)

    def uni(rows):
        pts = sorted((curve(rows, bear, cut, uniform=m, seeds=SEEDS)["dd"],
                      curve(rows, bear, cut, uniform=m, seeds=SEEDS)["hpm"])
                     for m in np.linspace(1.0, 2.6, 17))
        return np.array([x[0] for x in pts]), np.array([x[1] for x in pts])
    ud_dep, ud_tig = uni(rows_dep), uni(rows_tig)

    def show(lab, rows, ud, **kw):
        s = curve(rows, bear, cut, seeds=SEEDS, **kw)
        u = float(np.interp(s["dd"], ud[0], ud[1]))
        print(f"  {lab:<42}{s['hpm']:>+9.2f}%{s['dd']:>6.0f}%{s['worst_mo']:>+9.1f}%"
              f"{u:>+11.2f}%{s['hpm']-u:>+7.2f}%")
        return s

    print("\n3. HARDER SIZING on the deployed book, each vs a uniform bet at the SAME drawdown")
    print(f"  {'scheme':<42}{'/mo':>9}{'DD':>6}{'worst mo':>9}{'uniform@DD':>11}{'edge':>7}")
    dep_flat = show("flat (deployed today)", rows_dep, ud_dep)
    show("linear +-90%", rows_dep, ud_dep, spread=0.9, mode="linear")
    show("convex +-90%", rows_dep, ud_dep, spread=0.9, mode="convex")
    show("drop bottom 20% + linear 90%", rows_dep, ud_dep, spread=0.9, drop_frac=0.2)
    show("drop bottom 30% + linear 90%", rows_dep, ud_dep, spread=0.9, drop_frac=0.3)

    print("\n4. STACK: tight exit + sizing, each vs uniform at the SAME drawdown")
    print(f"  {'scheme':<42}{'/mo':>9}{'DD':>6}{'worst mo':>9}{'uniform@DD':>11}{'edge':>7}")
    show("tight exit, flat", rows_tig, ud_tig)
    show("tight exit, linear +-90%", rows_tig, ud_tig, spread=0.9, mode="linear")
    show("tight exit, drop bottom 20% + lin90", rows_tig, ud_tig, spread=0.9, drop_frac=0.2)

    target = dep_flat["dd"]
    print(f"\n  THE LEVERAGE HEADLINE (holdout, {len(SEEDS)} orderings averaged)")
    print(f"  today's book (deployed exit, flat): {dep_flat['hpm']:+.2f}%/mo at {target:.0f}% DD")
    for lab, rows, kw in (("tight exit, flat", rows_tig, {}),
                          ("tight exit + convex-90 sizing", rows_tig,
                           dict(spread=0.9, mode="convex"))):
        best = None
        for m in np.linspace(1.0, 3.0, 41):
            s = curve(rows, bear, cut, uniform=m, seeds=SEEDS, **kw)
            if s["dd"] <= target:
                best = (m, s)
        if best:
            m, s = best
            print(f"  {lab} levered to {target:.0f}% DD (x{m:.2f}): {s['hpm']:+.2f}%/mo, "
                  f"worst mo {s['worst_mo']:+.1f}%  -> {s['hpm']-dep_flat['hpm']:+.2f}%/mo vs today")
        else:
            print(f"  {lab}: even at x1 its DD exceeds today's {target:.0f}% - cannot lever to match")


if __name__ == "__main__":
    main()
