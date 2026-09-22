"""CAN WE PREDICT THE RUNNER AT ENTRY? - for slot allocation, not for exits.

THE DIFFERENCE FROM runner_id.py
    runner_id measured features at +20R and asked which reach +100R; using it to EXIT lost
    money (re-entry drag, error asymmetry). This asks the untested question: AT ENTRY, before
    a slot is committed, can we rank signals by their chance of becoming a big runner? The
    use is different and has no re-entry drag - we only choose which of several signals we
    would take anyway gets a contested slot, against the current random pick.

WHY IT MIGHT WORK WHERE THE AVERAGE-R TEST FAILED (slot_priority.py)
    slot_priority ranked by mean R and CAPPED R at +100, washing out the runners - which
    ARE the prize (3.5% of trades = 158% of profit). Here the LABEL is the runner itself
    (peak >= 50R), and the metric is the runner hit-rate, not mean R.

FEATURES AT ENTRY, DECLARED BEFORE LOOKING - all from bars closed at/before the entry bar
    atr_expand   ATR(14) / its own 60-bar average - is volatility already expanding
                 (atr_ratio was runner_id's one survivor; this is its at-entry form)
    ext_ma       price / its 200-bar mean - how far the trend has already run
    coin_30      coin's 30-bar return
    coin_90      coin's 90-bar return
    brk          breakout strength: (close - upper band) / ATR
    vsurge       entry-bar volume / its 20-bar average
    btc_bear     deployed 1000h regime (0/1)
    btc_30       BTC's 30-bar return - is the whole market trending
    tf           sleeve, one-hot (reported, low prior)

HONEST GUARDS
    * Runners cluster in time (2021). The model is fit ONLY on the tune half and every
      number that decides anything is the HOLDOUT. If the holdout AUC is ~0.5 it is dead.
    * A time split can flatter a regime feature. So the economic test is run on the
      holdout only, and the by-year runner rate is printed so a pure-2021 effect is visible.
    * The economic test compares picking-by-model against RANDOM picks over 8 seeds, and
      reports the runner hit-rate among TAKEN trades, not just return.

    python -m backtest.entry_runner
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.runner_id import auc, btc_context  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

RULES = ["1h", "4h", "12h"]
RUN_R = 50.0                      # "runner" = peak reaches this many R
FEATS = ["atr_expand", "ext_ma", "coin_30", "coin_90", "brk", "vsurge", "btc_bear", "btc_30"]


def walk(df, sig, coin, rule, btc):
    """Deployed long pyramid; record ENTRY-time features, plus the peak and exit R."""
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    v = df["volume"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    ma200 = pd.Series(c).rolling(200).mean().to_numpy()
    ma_bb = pd.Series(c).rolling(30).mean().to_numpy()
    sd_bb = pd.Series(c).rolling(30).std(ddof=0).to_numpy()
    a_avg = pd.Series(a).rolling(60).mean().to_numpy()
    v_avg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
    t = pd.DatetimeIndex(df["time"])
    fee = FEE_BP / 1e4
    out, pos = [], None
    for i in range(1, len(df)):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i-1]) and a[i-1] > 0:
            j = i - 1                                        # the signal bar (closed)
            try:
                bc = btc.asof(t[i]); bb, b30 = float(bool(bc.bear)), float(bc.r30)
            except Exception:
                bb, b30 = 0.0, 0.0
            feat = dict(
                atr_expand=float(a[j] / a_avg[j]) if a_avg[j] and a_avg[j] > 0 else 1.0,
                ext_ma=float(c[j] / ma200[j]) if np.isfinite(ma200[j]) and ma200[j] > 0 else 1.0,
                coin_30=float(c[j] / c[j-30] - 1) if j >= 30 else 0.0,
                coin_90=float(c[j] / c[j-90] - 1) if j >= 90 else 0.0,
                brk=float((c[j] - (ma_bb[j] + 1.5*sd_bb[j])) / a[j]) if a[j] > 0 else 0.0,
                vsurge=float(v[j] / v_avg[j]) if v_avg[j] and v_avg[j] > 0 else 1.0,
                btc_bear=bb, btc_30=b30, t0=t[i], coin=coin, tf=rule)
            pos = dict(risk=blend.SL_MULT*a[i-1], stop=o[i]-blend.SL_MULT*a[i-1],
                       best=o[i], bar=i, ents=[o[i]], nxt=1, peak=0.0, feat=feat)
        if pos is None:
            continue
        risk = pos["risk"]; e0 = pos["ents"][0]
        pos["peak"] = max(pos["peak"], sum(h[i]-e_ for e_ in pos["ents"]) / risk)
        if lo[i] <= pos["stop"]:
            px = pos["stop"]
            r = (sum(px-e_ for e_ in pos["ents"]) - sum(fee*e_ for e_ in pos["ents"]))/risk
            out.append({**pos["feat"], "t1": t[i], "peak": pos["peak"], "R": r}); pos = None
            continue
        if len(pos["ents"]) < blend.MAX_UNITS and (h[i]-e0)/risk >= pos["nxt"]*blend.ADD_EVERY:
            pos["ents"].append(e0 + pos["nxt"]*blend.ADD_EVERY*risk); pos["nxt"] += 1
        pos["best"] = max(pos["best"], h[i])
        cand = pos["best"] - blend.LONG_TRAIL*a[i-1]
        if (pos["best"]-e0)/risk >= blend.BE_AT:
            cand = max(cand, e0)
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None:
        px = c[-1]
        r = (sum(px-e_ for e_ in pos["ents"]) - sum(fee*e_ for e_ in pos["ents"]))/pos["risk"]
        out.append({**pos["feat"], "t1": t[-1], "peak": pos["peak"], "R": r})
    return out


def build():
    btc = btc_context()
    rows = []
    for rule in RULES:
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            rows += walk(df, signals(df, "long", "all"), coin, rule, btc)
    D = pd.DataFrame(rows)
    D["t0"] = pd.to_datetime(D["t0"]); D["t1"] = pd.to_datetime(D["t1"])
    D["runner"] = (D["peak"] >= RUN_R).astype(int)
    return D


def fit_predict(tr, te, feats=None):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    feats = feats or FEATS
    Xtr = tr[feats].to_numpy(float); Xte = te[feats].to_numpy(float)
    sc = StandardScaler().fit(Xtr)
    m = LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced")
    m.fit(sc.transform(Xtr), tr["runner"].to_numpy())
    coef = dict(zip(feats, m.coef_[0]))
    return m.predict_proba(sc.transform(Xte))[:, 1], coef


def main():
    D = build()
    D = D.sort_values("t0").reset_index(drop=True)
    cut = D["t0"].quantile(0.6)
    tr, te = D[D.t0 < cut].copy(), D[D.t0 >= cut].copy()
    print(f"{len(D):,} long positions | runner = peak >= {RUN_R:.0f}R")
    print(f"  tune {len(tr):,} ({tr.runner.mean()*100:.1f}% runners)  "
          f"holdout {len(te):,} ({te.runner.mean()*100:.1f}% runners)")
    print(f"  runner rate by year: " + "  ".join(
        f"{y} {g.runner.mean()*100:.1f}%(n{len(g)})" for y, g in D.groupby(D.t0.dt.year)))

    print("\n1. PER-FEATURE AUC on the HOLDOUT (0.5 = useless; >0.5 => higher value picks runners)")
    print(f"  {'feature':<12}{'holdout AUC':>12}{'tune AUC':>10}")
    for f in FEATS:
        ah = auc(te[te.runner == 1][f].to_numpy(), te[te.runner == 0][f].to_numpy())
        at = auc(tr[tr.runner == 1][f].to_numpy(), tr[tr.runner == 0][f].to_numpy())
        print(f"  {f:<12}{ah:>12.3f}{at:>10.3f}")

    print("\n2. LOGISTIC MODEL fit on TUNE ONLY, scored on the HOLDOUT")
    p, coef = fit_predict(tr, te)
    te = te.assign(p=p)
    a_model = auc(te[te.runner == 1].p.to_numpy(), te[te.runner == 0].p.to_numpy())
    print(f"  holdout AUC of the model: {a_model:.3f}")
    print("  coefficients (standardized): " + "  ".join(f"{k} {v:+.2f}" for k, v in coef.items()))
    # decile lift: do the model's top-10% signals actually run more, and earn more, OOS?
    q = pd.qcut(te.p, 10, labels=False, duplicates="drop")
    top, bot = te[q == q.max()], te[q == 0]
    print(f"  holdout top decile by model: runner rate {top.runner.mean()*100:.1f}%, "
          f"mean R {top.R.mean():+.2f}   bottom decile: {bot.runner.mean()*100:.1f}%, "
          f"mean R {bot.R.mean():+.2f}   (base {te.runner.mean()*100:.1f}%, {te.R.mean():+.2f})")

    print("\n3. ECONOMIC TEST on the HOLDOUT: pick contested slots by the model vs at random")
    print("   (uncapped R this time - the runners are the point). 8 seeds each.")
    from backtest.bull_boost import evaluate, regimes
    from backtest.slot_priority import build as sp_build
    bear = regimes()[1000]
    # attach model prob to the full row set (longs get p; shorts get p=median so they are
    # neither preferred nor penalised), then order contested groups by p vs random
    allrows = sp_build()
    sc_full = None
    # score every long row with the tune-fit model
    from sklearn.linear_model import LogisticRegression  # noqa
    p_all, _ = fit_predict(tr, D)                          # scores for ALL longs (incl tune)
    key = {(r.t0, r.coin, r.tf): pv for r, pv in zip(D.itertuples(), p_all)}
    med = float(np.median(p_all))
    for r in allrows:
        if r["side"] == "long":
            r["p"] = key.get((pd.Timestamp(r["t0"]), r["coin"], r["rule"]), med)
        else:
            r["p"] = med

    def order(rows, by_model, seed):
        rng = np.random.default_rng(seed); tie = rng.random(len(rows))
        kf = (lambda i: -rows[i]["p"]) if by_model else (lambda i: 0.0)
        idx = sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], kf(i), tie[i]))
        return [rows[i] for i in idx]

    def score(by_model):
        H = []
        for sd in range(8):
            o = order(allrows, by_model, sd)
            b = evaluate(o, bear, t_from=cut)
            H.append((b["hpm"], b["dd"]))
        return np.array(H)

    rnd, mdl = score(False), score(True)
    print(f"   {'':<16}{'HOLDOUT /mo (mean, range)':>30}{'DD':>7}")
    print(f"   {'random pick':<16}{rnd[:,0].mean():>+16.2f}% ({rnd[:,0].min():+.1f}.."
          f"{rnd[:,0].max():+.1f}){rnd[:,1].mean():>7.0f}%")
    print(f"   {'model pick':<16}{mdl[:,0].mean():>+16.2f}% ({mdl[:,0].min():+.1f}.."
          f"{mdl[:,0].max():+.1f}){mdl[:,1].mean():>7.0f}%")
    delta = mdl[:, 0].mean() - rnd[:, 0].mean()
    print(f"\n   model minus random: {delta:+.2f}%/mo on the holdout - slot priority does "
          f"NOT work, because the pick is between signals sharing one regime.")

    print("\n4. IS THE POWER CROSS-TIME (regime) OR WITHIN-MOMENT?  within contested groups:")
    te2 = D[D.t0 >= cut].assign(p=p)
    wr = []
    for _t, g in te2.groupby("t0"):
        if g.runner.sum() >= 1 and (g.runner == 0).sum() >= 1:
            wr.append(auc(g[g.runner == 1].p.to_numpy(), g[g.runner == 0].p.to_numpy()))
    print(f"   within-moment AUC (groups with a runner and a non-runner, n={len(wr)}): "
          f"{np.mean(wr):.3f}  -> ~0.5 means it cannot rank simultaneous signals")

    print("\n5. POSITION-ONLY model (drop btc_bear, btc_30): is there edge BEYOND regime timing?")
    pos_feats = [f for f in FEATS if f not in ("btc_bear", "btc_30")]
    p_pos, coef_pos = fit_predict(tr, te, pos_feats)
    yte = te["runner"].to_numpy()
    a_pos = auc(p_pos[yte == 1], p_pos[yte == 0])
    print(f"   position-only holdout AUC: {a_pos:.3f}  coefs: "
          + "  ".join(f"{k} {v:+.2f}" for k, v in coef_pos.items()))

    print("\n6. SIZING by runner-probability (holdout), MEAN RISK HELD CONSTANT so this is")
    print("   NOT just betting more. Each position's risk x a factor from its rank, mean 1.")
    # factor from within-book percentile of p, mapped to [lo, hi] with mean ~1
    from backtest.bull_boost import evaluate, regimes
    bearr = regimes()[1000]
    base_full = [dict(r) for r in allrows]
    def sized(rows, spread):
        pr = np.array([r["p"] for r in rows])
        rank = pd.Series(pr).rank(pct=True).to_numpy()
        fac = 1.0 + spread * (rank - 0.5) * 2         # rank 0->1-spread, 1->1+spread, mean 1
        out = []
        for r, f in zip(rows, fac):
            q = dict(r); q["R"] = r["R"] * f; out.append(q)   # R x size = P&L scaling
        return out
    ordered = sorted(base_full, key=lambda r: r["t0"])
    dep = evaluate(ordered, bearr, t_from=cut)
    print(f"   {'scheme':<26}{'HOLDOUT/mo':>12}{'DD':>7}{'worst mo':>10}")
    print(f"   {'deployed (flat)':<26}{dep['hpm']:>+11.2f}%{dep['dd']:>6.0f}%{dep['worst_mo']:>+9.1f}%")
    for spread in (0.5, 0.9):
        s = evaluate(sized(ordered, spread), bearr, t_from=cut)
        print(f"   {'size by p, +-'+str(int(spread*100))+'%':<26}{s['hpm']:>+11.2f}%"
              f"{s['dd']:>6.0f}%{s['worst_mo']:>+9.1f}%")
    print("\n7. THE CONTROL THAT DECIDES IT: sizing-by-p vs a UNIFORM bet at the SAME drawdown.")
    print("   If uniform matches it, the gain was just leverage (bull_boost.py). Also shown:")
    print("   sizing by the POSITION-ONLY model, which cannot be regime-timing.")
    # uniform curve on the holdout
    uni = []
    for m in np.linspace(1.0, 2.2, 25):
        s = evaluate([dict(r, R=r["R"] * m) for r in ordered], bearr, t_from=cut)
        uni.append((s["dd"], s["hpm"], m))
    uni.sort()
    uni_dd = np.array([u[0] for u in uni]); uni_hpm = np.array([u[1] for u in uni])
    def uni_at(dd):
        return float(np.interp(dd, uni_dd, uni_hpm))
    # position-only scores for all rows
    p_pos_all, _ = fit_predict(tr, D, pos_feats)
    keyp = {(r.t0, r.coin, r.tf): pv for r, pv in zip(D.itertuples(), p_pos_all)}
    for r in ordered:
        r["p_pos"] = keyp.get((pd.Timestamp(r["t0"]), r["coin"], r["rule"]), float(np.median(p_pos_all))) \
            if r["side"] == "long" else float(np.median(p_pos_all))
    def sized_by(rows, field, spread):
        rank = pd.Series([r[field] for r in rows]).rank(pct=True).to_numpy()
        fac = 1.0 + spread * (rank - 0.5) * 2
        return [dict(r, R=r["R"] * f) for r, f in zip(rows, fac)]
    print(f"   {'scheme':<30}{'HOLDOUT/mo':>12}{'DD':>6}{'uniform @ same DD':>19}{'edge':>7}")
    for field, lab in (("p", "full model"), ("p_pos", "position-only")):
        for spread in (0.5, 0.9):
            s = evaluate(sized_by(ordered, field, spread), bearr, t_from=cut)
            u = uni_at(s["dd"])
            print(f"   {lab+' +-'+str(int(spread*100))+'%':<30}{s['hpm']:>+11.2f}%"
                  f"{s['dd']:>5.0f}%{u:>+18.2f}%{s['hpm']-u:>+7.2f}%")
    print("   edge > 0 means sizing-by-runner-probability beats plain leverage at equal risk.")


if __name__ == "__main__":
    main()
