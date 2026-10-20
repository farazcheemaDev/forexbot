"""EVERYTHING WE MEASURED ABOUT HIS TRADES, TOGETHER - any correlation? (2026-10-20, his_strategy.md s71)

The user: "if we combine this with previous stats we have on him, can we discover any correlation". Each NASDAQ trade
gets, on the corrected clock (his_clock_exits.trades(), Exness USTECm mid ticks around every trade, cached):
OUTCOMES   race7 (+7 before -7 within 30 min), mfe60 / mae60 and mfe300 / mae300 (best / worst excursion his way in the
           first 1 / 5 minutes), t7 (seconds to +7, if reached), pts (his own points, clock-free)
CONDITIONS gamma (his_gex_trades.csv): positive-gamma moment, distance to the nearest wall and its session rank,
           distance to the flip and its rank, side toward the magnet, side away from the nearer wall; the day: VXN level,
           the session's move from the open to his click and whether he traded WITH it, hour (New York), first trade of a
           sitting vs follow-up; the market just before him: the 30-s and 5-min move his way (his "dip"), 60-s tick rate
TWO QUESTIONS
    (a) which conditions go with his BETTER trades? Spearman of every condition with every outcome, Holm across all
    (b) do the conditions TOGETHER predict his SIDE? logistic regression, leave-one-out accuracy vs 50% and vs the best
        single rule ("trade with the session's move")
The older 20-minute marker ranks (his_local_ranks.csv) carry no timestamps and are not joined. TICK (12 trades) is left
to his_tick.py.

REGISTERED BEFORE THE RUN (2026-10-20)
    R1 no condition-outcome correlation survives Holm.
    R2 negative-gamma moments go with larger 5-minute runs his way (Spearman of 'positive gamma' with mfe300 < 0).
    R3 the conditions together predict his side at <= 60% leave-one-out.

    python -m backtest.his_combine
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "his_combine.txt"
NY = "America/New_York"


def holm(p: np.ndarray) -> np.ndarray:
    o = np.argsort(p)
    adj = np.empty_like(p)
    run = 0.0
    for k, i in enumerate(o):
        run = max(run, (len(p) - k) * p[i])
        adj[i] = min(run, 1.0)
    return adj


def main():
    from backtest.his_clock_exits import at, exness_ticks, trades
    from backtest.his_gex import qqq_1m, DATA
    T = trades()
    ex = exness_ticks(T)
    N = T[T.kind == "NASDAQ"].copy()
    G = pd.read_csv(ROOT / "logs" / "his_gex_trades.csv", parse_dates=["t"])
    G["t"] = pd.to_datetime(G.t, utc=True)
    vxn = pd.read_csv(DATA / "vxn.csv", header=[0, 1], index_col=0, parse_dates=True)[("Close", "^VXN")].astype(float)
    rows = []
    prev_t = None
    for i, r in N.sort_values("entry").iterrows():
        tp = ex.get(i)
        if tp is None:
            continue
        ts, px = tp
        t0 = r.entry.timestamp()
        p0 = at(ts, px, t0)
        if not np.isfinite(p0):
            continue
        s = r.s
        j = np.searchsorted(ts, t0, "right")
        path = s * (px[j:np.searchsorted(ts, t0 + 1800)] - p0)
        tt = ts[j:j + len(path)] - t0
        up, dn = np.flatnonzero(path >= 7), np.flatnonzero(path <= -7)
        race = 1.0 if len(up) and (not len(dn) or up[0] < dn[0]) else (0.0 if len(dn) else np.nan)
        w60, w300 = tt <= 60, tt <= 300
        e = pd.Timestamp(r.entry).tz_localize("UTC")
        g = G[(G.t - e).abs() <= pd.Timedelta(seconds=2)]
        q = qqq_1m(e.strftime("%Y-%m-%d"))
        day_move = np.nan
        if q is not None:
            t_open = pd.Timestamp(f"{e:%Y-%m-%d} 09:31").tz_localize(NY).tz_convert("UTC")
            a, b = q[q.index <= t_open], q[q.index <= e]
            if len(a) and len(b) and e > t_open:
                day_move = b.iloc[-1] / a.iloc[-1] - 1
        v = vxn[vxn.index < pd.Timestamp(e.date())]
        rows.append(dict(
            t=e, s=s, race7=race,
            mfe60=path[w60].max() if w60.any() else np.nan, mae60=-path[w60].min() if w60.any() else np.nan,
            mfe300=path[w300].max() if w300.any() else np.nan, mae300=-path[w300].min() if w300.any() else np.nan,
            t7=float(tt[up[0]]) if len(up) else np.nan, pts=s * (r.close_price - r.open_price),
            pre30=s * (p0 - at(ts, px, t0 - 30)), pre300=s * (p0 - at(ts, px, t0 - 300)),
            rate60=float(((ts > t0 - 60) & (ts <= t0)).sum()),
            hour_ny=e.tz_convert(NY).hour + e.tz_convert(NY).minute / 60,
            follow_up=int(prev_t is not None and (e - prev_t) < pd.Timedelta(minutes=45)),
            vxn=float(v.iloc[-1]) if len(v) else np.nan,
            day_move_his=s * day_move if np.isfinite(day_move) else np.nan,
            with_day=int(np.sign(day_move) == s) if np.isfinite(day_move) and day_move != 0 else np.nan,
            gamma_pos=float(g.pos.iloc[0]) if len(g) else np.nan,
            dwall=float(g.dwall.iloc[0]) if len(g) else np.nan, r_wall=float(g.r_wall.iloc[0]) if len(g) else np.nan,
            dflip=float(g.dflip.iloc[0]) if len(g) else np.nan, r_flip=float(g.r_flip.iloc[0]) if len(g) else np.nan,
            toward_magnet=float(g.toward.iloc[0]) if len(g) and g.toward.notna().iloc[0] else np.nan))
        prev_t = e
    D = pd.DataFrame(rows)
    OUT = ["race7", "mfe60", "mae60", "mfe300", "mae300", "t7", "pts"]
    CON = ["gamma_pos", "dwall", "r_wall", "dflip", "r_flip", "toward_magnet", "vxn", "day_move_his", "with_day",
           "hour_ny", "follow_up", "pre30", "pre300", "rate60"]
    lines = [f"backtest/his_combine.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(D)} NASDAQ trades on the corrected "
             f"clock (Exness mid ticks); race +-7 won {np.nanmean(D.race7):.0%}", "",
             "(a) WHICH CONDITIONS GO WITH HIS BETTER TRADES - Spearman, Holm across every pair",
             "   " + " " * 15 + "".join(f"{o:>9}" for o in OUT)]
    cells = []
    for c in CON:
        row = []
        for o in OUT:
            x = D[[c, o]].dropna()
            if len(x) < 10 or x[c].nunique() < 2 or x[o].nunique() < 2:
                row.append((np.nan, np.nan, 0))
                continue
            rr = spearmanr(x[c], x[o])
            row.append((rr.correlation, rr.pvalue, len(x)))
            cells.append((c, o, rr.correlation, rr.pvalue, len(x)))
        lines.append(f"   {c:<15}" + "".join(f"{v[0]:>+9.2f}" if np.isfinite(v[0]) else f"{'-':>9}" for v in row))
    P = np.array([c[3] for c in cells])
    A = holm(P)
    best = sorted(zip(cells, A), key=lambda z: z[0][3])[:6]
    lines += ["", f"   {len(cells)} tests; the smallest p-values (raw -> Holm):"]
    for (c, o, rho, p, n), a in best:
        lines.append(f"     {c:<14} x {o:<7} rho {rho:+.2f}  n {n:2d}  p {p:.4f} -> Holm {a:.3f}")
    surv = [z for z in zip(cells, A) if z[1] < 0.05]
    # (b) side prediction
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    X = D[["gamma_pos", "r_wall", "r_flip", "vxn", "hour_ny", "follow_up", "rate60"]].copy()
    X["day_move"] = D.day_move_his * D.s                      # the session's move (NOT signed by his side)
    X["pre30_raw"] = D.pre30 * D.s                             # the market's 30-s move (not his-side-signed)
    X["pre300_raw"] = D.pre300 * D.s
    ok = X.notna().all(axis=1)
    Xv, y = X[ok].to_numpy(float), (D.s[ok] > 0).astype(int).to_numpy()
    hits = []
    for k in range(len(y)):
        m = np.ones(len(y), bool)
        m[k] = False
        sc = StandardScaler().fit(Xv[m])
        lr = LogisticRegression(C=0.5, max_iter=1000).fit(sc.transform(Xv[m]), y[m])
        hits.append(int(lr.predict(sc.transform(Xv[k:k + 1]))[0] == y[k]))
    acc = float(np.mean(hits))
    wd = D.with_day.dropna()
    base_long = max(y.mean(), 1 - y.mean())
    lines += ["", "(b) DO THE CONDITIONS TOGETHER PREDICT HIS SIDE?",
              f"   logistic regression on {len(y)} trades, leave-one-out accuracy {acc:.0%} (always the majority side: {base_long:.0%})",
              f"   the single rule 'trade with the session's move from the open': {wd.mean():.0%} of {len(wd)} trades",
              f"   his side with the 30-s move before him: {np.nanmean(D.pre30 > 0):.0%} (the 'dip' he buys: against it {np.nanmean(D.pre30 < 0):.0%})"]
    r2 = spearmanr(D[["gamma_pos", "mfe300"]].dropna().gamma_pos, D[["gamma_pos", "mfe300"]].dropna().mfe300).correlation
    lines += ["", "REGISTERED PREDICTIONS",
              f"  R1 no correlation survives Holm -> {'RIGHT' if not surv else 'WRONG'} ({len(surv)} survive)",
              f"  R2 positive gamma x mfe300 negative: {r2:+.2f} -> {'RIGHT' if r2 < 0 else 'WRONG'}",
              f"  R3 side predicted at <= 60% leave-one-out: {acc:.0%} -> {'RIGHT' if acc <= 0.60 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    D.to_csv(ROOT / "logs" / "his_combine_trades.csv", index=False)
    print(txt)


if __name__ == "__main__":
    main()
