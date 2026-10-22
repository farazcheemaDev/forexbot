"""EVERY MARKET'S RECENT MOVES -> THE NEXT HOUR: a machine-learning search across forex, gold and the US indices (2026-10-22)

THE USER (2026-10-22): "test every possible thing ... I want a crazy good strategy". The rule families (fx_intraday_pub.py,
fx_daily_families.py, cfd_scalp.py) each test one idea. This lets a model look at ALL of them at once - the kind of
cross-market lead-lag a desk would look for (NASDAQ moving before AUDUSD, gold before USDJPY, the dollar across pairs) - on
15 years of HistData minute bars (histdata_1m.py), so a small, real effect has the data to show itself.

GRID      5-minute closes, UTC, 2011-01 .. 2026-09; a bar counts if the instrument traded in it (else forward-filled, and
          its own returns are not used as a target there)
FEATURES  for each of EURUSD GBPUSD USDJPY AUDUSD USDCAD USDCHF NZDUSD gold NASDAQ S&P: log returns over the last 1, 3, 12
          and 48 bars (5 min .. 4 h); hour of day and weekday (sin / cos); 42-ish columns
TARGETS   the next 12 bars' log return (one hour) of EURUSD, USDJPY, AUDUSD, gold, NASDAQ
MODELS    ridge (standardised, alpha 10) and a gradient-boosted tree (sklearn HistGradientBoosting, 200 iterations, depth 4)
          fit on 2011-2018, scored on 2019-2026 (never seen); the tree on every 4th row (memory)
TRADE     on the test years, every hour on the hour: if |prediction| is above the 80th percentile of the TRAINING
          predictions' |prediction|, take the predicted side for one hour; net of the Exness spread (+0.5bp)
PASS      net > 0 with t >= 2 on both halves of the test period (2019-2022 / 2023-2026), Holm over the 10 model-targets

REGISTERED BEFORE THE RUN (2026-10-22)
  M1 test-period IC (correlation of prediction and outcome) is positive for every target but under 0.03 everywhere.
  M2 the forex targets lose after the spread at every model; gold and NASDAQ gross positive, net within +-1bp a trade.
  M3 nothing passes.

RESULT (2026-10-22, logs/fx_ml_leadlag.txt) - the models see a little and it is under the spread; 0 of 10 pass.
  Test-period IC -0.007..+0.028 (NASDAQ highest, USDJPY ridge negative - M1 WRONG on its sign), gross -0.08..+1.33bp a
  trade, net -1.9..+0.06bp; every forex target t -6..-14. M2, M3 RIGHT.

    python -m backtest.fx_ml_leadlag
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HD = ROOT / "strategy_analysis" / "data" / "histdata"
LOG = ROOT / "logs" / "fx_ml_leadlag.txt"
INS = {"EURUSD": 1.39, "GBPUSD": 1.48, "USDJPY": 1.29, "AUDUSD": 1.6, "USDCAD": 1.8, "USDCHF": 1.8, "NZDUSD": 2.0,
       "XAUUSD": 1.22, "NSXUSD": 0.77, "SPXUSD": 0.38}
TARGETS = ["EURUSD", "USDJPY", "AUDUSD", "XAUUSD", "NSXUSD"]
LAGS = (1, 3, 12, 48)
H = 12
SPLIT, MID = pd.Timestamp("2019-01-01"), pd.Timestamp("2023-01-01")


def grid():
    cols, live = {}, {}
    for s in INS:
        p = HD / f"{s}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        t = pd.to_datetime(d.t, unit="ms")
        c = pd.Series(d.c.to_numpy(), index=t)
        b = c.resample("5min").last()
        cols[s] = b
    C = pd.DataFrame(cols)
    C = C[(C.index >= "2011-01-01") & (C.index < "2026-10-01")]
    live = C.notna()
    C = C.ffill()
    keep = live.sum(axis=1) >= 6                      # skip weekend / holiday dead bars
    return C[keep], live[keep]


def features(C):
    lc = np.log(C)
    F = {}
    for s in C.columns:
        for k in LAGS:
            F[f"{s}_r{k}"] = lc[s] - lc[s].shift(k)
    h = C.index.hour + C.index.minute / 60
    F["hs"], F["hc"] = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
    F["ds"], F["dc"] = np.sin(2 * np.pi * C.index.dayofweek / 7), np.cos(2 * np.pi * C.index.dayofweek / 7)
    return pd.DataFrame(F, index=C.index)


def tt(x):
    x = np.asarray(x, float)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std(ddof=1) > 0 else 0.0


def main():
    from scipy.stats import norm
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    C, live = grid()
    X = features(C)
    lc = np.log(C)
    L = [f"backtest/fx_ml_leadlag.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; 5-minute grid {C.index[0]:%Y-%m-%d}.."
         f"{C.index[-1]:%Y-%m-%d}, {len(C):,} bars, {X.shape[1]} features ({', '.join(C.columns)}); train < {SPLIT:%Y}, test after",
         "", f"   {'target':<8}{'model':<7}{'IC test':>8}{'trades':>8}{'gross bp':>9}{'net bp':>8}{'t':>7}"
         f"{'2019-22 bp':>11}{'t':>6}{'2023-26 bp':>11}{'t':>6}{'won':>6}"]
    cells = []
    for tg in TARGETS:
        if tg not in C.columns:
            continue
        y = lc[tg].shift(-H) - lc[tg]
        ok = X.notna().all(axis=1) & y.notna() & live[tg] & live[tg].shift(-H, fill_value=False)
        Xo, yo = X[ok], y[ok]
        tr, te = Xo.index < SPLIT, Xo.index >= SPLIT
        sc = StandardScaler().fit(Xo[tr])
        Xtr, Xte = sc.transform(Xo[tr]), sc.transform(Xo[te])
        ytr = yo[tr].clip(*yo[tr].quantile([0.001, 0.999]))
        models = {"ridge": Ridge(alpha=10.0).fit(Xtr, ytr),
                  "trees": HistGradientBoostingRegressor(max_iter=200, max_depth=4, learning_rate=0.05,
                                                         random_state=0).fit(Xtr[::4], ytr.iloc[::4])}
        for mn, m in models.items():
            ptr = m.predict(Xtr)
            pte = pd.Series(m.predict(Xte), index=Xo.index[te])
            ic = np.corrcoef(pte, yo[te])[0, 1]
            thr = np.quantile(np.abs(ptr), 0.8)
            hourly = pte[(pte.index.minute == 0)]
            sel = hourly[hourly.abs() > thr]
            g = np.sign(sel) * yo[te].reindex(sel.index)
            net = g - (INS[tg] + 0.5) / 1e4
            a, b = net[net.index < MID], net[net.index >= MID]
            cells.append(dict(tg=tg, m=mn, t=tt(net), ta=tt(a), tb=tt(b), ma=a.mean() if len(a) else 0, mb=b.mean() if len(b) else 0))
            L.append(f"   {tg:<8}{mn:<7}{ic:>+8.3f}{len(net):>8}{g.mean() * 1e4:>+9.2f}{net.mean() * 1e4:>+8.2f}{tt(net):>+7.2f}"
                     f"{a.mean() * 1e4:>+11.2f}{tt(a):>+6.2f}{b.mean() * 1e4:>+11.2f}{tt(b):>+6.2f}{(g > 0).mean() * 100:>5.0f}%")
        if tg == TARGETS[0]:
            co = pd.Series(models["ridge"].coef_, index=X.columns).abs().sort_values(ascending=False)
            L.append(f"   ({tg} ridge's biggest weights: {', '.join(co.index[:5])})")
    D = pd.DataFrame(cells)
    D["p"] = [2 * (1 - norm.cdf(abs(t))) for t in D.t]
    o = np.argsort(D.p.to_numpy())
    run, holm = 0.0, np.empty(len(D))
    for k, i in enumerate(o):
        run = max(run, (len(D) - k) * D.p.iloc[i])
        holm[i] = min(run, 1.0)
    D["holm"] = holm
    D["pass"] = (D.ma > 0) & (D.mb > 0) & (D.ta >= 2) & (D.tb >= 2) & (D.holm < 0.05)
    fx = D[D.tg.isin(["EURUSD", "USDJPY", "AUDUSD"])]
    L += ["", f"   passes: {int(D['pass'].sum())} of {len(D)}", "", "REGISTERED PREDICTIONS",
          "  M1 IC positive everywhere, under 0.03 -> see the IC column",
          f"  M2 forex targets lose net at every model -> {'RIGHT' if (fx.t < 0).all() else 'WRONG'}",
          f"  M3 nothing passes -> {'RIGHT' if not D['pass'].any() else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
