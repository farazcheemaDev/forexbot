"""THE LAST MICRO-STRUCTURE LOOPHOLES - ES leading NQ by seconds, and a sub-second CME sweep before his fill (2026-10-16)

The user's /goal ("final forensic audit"), three loopholes. Two are testable on data already cached:
  L1  ES LEADS NQ: does the S&P future move (or move AHEAD of NQ) his way in the 1-5 s before his click?  s44
      (his_crossfut.py) read ES only over 30-300 s. Data: Databento ES bbo-1s mids (cross_bbo1s.pkl) and NQ bbo-1s
      (nq_bbo1s.pkl), his 31 windows. Features at each moment, signed his way (> 0 = his way):
        es{k}    ES % return over the last k = 1 / 2 / 3 / 5 s
        lead{k}  ES % return minus NQ % return over k s (ES ran ahead, NQ has not followed yet)
      A his side vs the sign; B his moment ranked in his sitting; C at the sittings' moments, trade the sign of a
      top-quintile |lead| reading (no use of his side) -> +-7 race on the Exness mid.
  L3  A LATENCY-ARB SCANNER (CME sweep, his CFD quote stale for 100-400 ms): then the real contract must have JUMPED
      his way in the second(s) before / of his stamped entry, and his fill must be better than the live CME print.
      Data: every real NQ print 5 s before to 6 s after each entry (nq_fill_prints.pkl, his_fills.py, ns timestamps).
        seg      signed CME move over each 1-s segment [T-5..T+1) (T = his stamped second; the click is inside [T, T+1))
        jump     the largest 400-ms move his way inside [T-2, T+1) against the same inside [T-5, T-2) (control)
      his_fills.py already measured the fill: entries a median +0.12 points better than the real print of that second,
      better in 51% (neutral).

REGISTERED BEFORE THE RUN (2026-10-16)
    1. L1 A: every es / lead feature agrees with his side 35-65%; B ranks 0.40-0.60; C rules win 42-58% of races.
    2. L3: median signed CME move in [T-1, T+1) within +-0.5 points; it is his way in 35-65% of entries; the 400-ms jump
       before his click is no bigger than in the control seconds (median difference within +-0.5).
    LEAD LINE (a loophole is OPEN): L1 A >= 75% (p < 0.01) with C >= 60%; or L3 median move >= +1.5 points his way in
    [T-1, T+1) with >= 75% of entries his way.

RESULT (2026-10-16, logs/his_loopholes.txt) - BOTH LOOPHOLES CLOSED; both predictions right.
    L1 (46 entries, 1,585 sitting moments): ES's 1-5 s move agrees with his side 35-49%, ES-ahead-of-NQ 45-59% (every p
    >= 0.12); ranks 0.43-0.57; trading the sign of a big ES lead at the sittings' moments wins 50-54%. Not ES top-of-book
    or ES aggressor flow (not cached: ES trades for his windows cost $1.80, not bought) - but ES's PRICE leading NQ by 1-5
    s, which any ES flow that mattered would have to show, does not point his way.
    L3 (46 entries, real NQ prints, ms timestamps): the CME contract moved AGAINST him in [T-2, T-1) (median -0.25, 57%
    against - his pullback), flat in [T-1, T) (35% his way), and his way only inside his own second [T, T+1) (+0.25,
    54%) - after the click. The largest 400-ms jump his way before the click equals the control seconds' (1.25 vs 1.25).
    With his_fills.py (entry fills a median +0.12 points vs the live print, better in 51%): no stale-quote fills, no
    sweep before. A latency scanner would show both. And his trades last a median 1.3 minutes for +7 - not sub-second.

    python -m backtest.his_loopholes
"""
from __future__ import annotations

import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "his_loopholes.txt"
K = (1, 2, 3, 5)


def series_1s(d, prefix=None):
    out = []
    for k, v in d.items():
        if prefix is not None and k[0] != prefix:
            continue
        out.append(v)
    s = pd.concat(out).sort_index()
    return s[~s.index.duplicated()]


def l1(x, ticks, out):
    from scipy.stats import binomtest, wilcoxon
    es = series_1s(pickle.loads((DATA / "cross_bbo1s.pkl").read_bytes()), "ES.v.0")
    nq = series_1s(pickle.loads((DATA / "nq_bbo1s.pkl").read_bytes()))
    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None:
            continue
        ts, mid, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            at = base + pd.Timedelta(seconds=int(np.floor(t)))
            f = {}
            for k in K:
                try:
                    e0, e1 = es.asof(at - pd.Timedelta(seconds=k)), es.asof(at)
                    n0, n1 = nq.asof(at - pd.Timedelta(seconds=k)), nq.asof(at)
                except KeyError:
                    e0 = e1 = n0 = n1 = np.nan
                re, rn = (e1 / e0 - 1) * 1e4, (n1 / n0 - 1) * 1e4
                f[f"es{k}"] = r.s * re
                f[f"lead{k}"] = r.s * (re - rn)
                f[f"raw_lead{k}"] = re - rn
            rows.append(dict(entry=r.Index, who=who, s=r.s, up=race2(ts, mid, t, 1, 600, 7, 7), **f))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"].dropna(subset=["up"])
    out += ["L1  ES LEADING NQ (1-s mids, bp; > 0 = his way)", f"    {len(H)} of his entries, {len(N)} sitting moments", "",
            f"    {'feature':>8}{'agree':>8}{'p':>8}{'rank':>8}{'p':>8}{'rule C':>9}{'n':>6}"]
    res = {}
    for k in [c for c in D.columns if c.startswith(("es", "lead"))]:
        v = H[k].dropna()
        v = v[v != 0]
        ag = (v > 0).mean() if len(v) else np.nan
        pa = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue if len(v) else np.nan
        rk = []
        for _, g in D.groupby("entry"):
            h, n = g[g.who == "his"][k].dropna(), g[g.who == "near"][k].dropna()
            if len(h) and len(n) >= 10:
                rk.append((n < h.iat[0]).mean() + 0.5 * (n == h.iat[0]).mean())
        rk = np.array(rk)
        pb = wilcoxon(rk - 0.5).pvalue if len(rk) > 5 and np.any(rk != 0.5) else np.nan
        raw = N["raw_" + k] if ("raw_" + k) in N else N[k] * N.s
        raw = raw.dropna()
        big = N.loc[raw.index][(raw.abs() >= raw.abs().quantile(0.8)) & (raw != 0)]
        sgn = np.sign(raw.loc[big.index])
        rule = np.where(sgn == big.s, big.up, 1 - big.up).mean() if len(big) else np.nan
        res[k] = (ag, pa, rk.mean() if len(rk) else np.nan, pb, rule)
        out.append(f"    {k:>8}{ag * 100:>7.0f}%{pa:>8.3f}{res[k][2]:>8.2f}{pb:>8.3f}{rule * 100:>8.0f}%{len(big):>6}")
    return res


def l3(x, out):
    P = pickle.loads((DATA / "nq_fill_prints.pkl").read_bytes())
    rows = []
    for r in x.itertuples():
        T = r.utc.floor("s")
        key = [k for k in P if k[1] == f"{T:%Y-%m-%d %H:%M:%S}"]
        if not key:
            continue
        p = P[key[0]].sort_values("t", kind="stable")
        tt, px = p.t.to_numpy(), p.px.to_numpy()

        def at(u):
            i = np.searchsorted(tt, np.datetime64(u), "right") - 1
            return px[i] if i >= 0 else np.nan

        seg = {f"seg{a}": r.s * (at(T + pd.Timedelta(seconds=a + 1)) - at(T + pd.Timedelta(seconds=a))) for a in range(-5, 1)}

        def jump(a, b):
            lo, hi = np.datetime64(T + pd.Timedelta(seconds=a)), np.datetime64(T + pd.Timedelta(seconds=b))
            m = (tt >= lo) & (tt < hi)
            best = 0.0
            for i in np.flatnonzero(m):
                j = np.searchsorted(tt, tt[i] - np.timedelta64(400, "ms"), "left")
                if j < i:
                    best = max(best, r.s * (px[i] - px[j:i].min() if r.s > 0 else px[i] - px[j:i].max()) * (1 if r.s > 0 else 1))
            return best
        rows.append(dict(**seg, pre=r.s * (at(T + pd.Timedelta(seconds=1)) - at(T - pd.Timedelta(seconds=1))),
                         jump=jump(-2, 1), ctrl=jump(-5, -2)))
    D = pd.DataFrame(rows)
    out += ["", "L3  A SUB-SECOND CME SWEEP BEFORE HIS FILL (real NQ prints, points his way)", f"    {len(D)} entries with prints", ""]
    for a in range(-5, 1):
        v = D[f"seg{a}"].dropna()
        out.append(f"    [T{a:+d}, T{a + 1:+d}) s   median {v.median():+.2f}  mean {v.mean():+.2f}  his way {(v > 0).mean() * 100:.0f}%  "
                   f"against {(v < 0).mean() * 100:.0f}%")
    v = D.pre.dropna()
    out += [f"    [T-1, T+1)       median {v.median():+.2f}  mean {v.mean():+.2f}  his way {(v > 0).mean() * 100:.0f}%  against "
            f"{(v < 0).mean() * 100:.0f}%",
            f"    largest 400-ms move his way: [T-2, T+1) median {D.jump.median():.2f}, control [T-5, T-2) {D.ctrl.median():.2f}; "
            f"paired difference median {(D.jump - D.ctrl).median():+.2f}"]
    return D


def main():
    warnings.filterwarnings("ignore")
    x = TP.entries()
    ticks = pickle.loads(TP.TICKS.read_bytes())
    out = [f"backtest/his_loopholes.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", ""]
    res = l1(x, ticks, out)
    D = l3(x, out)
    A = [v[0] for v in res.values() if np.isfinite(v[0])]
    B = [v[2] for v in res.values() if np.isfinite(v[2])]
    C = [v[4] for v in res.values() if np.isfinite(v[4])]
    v = D.pre.dropna()
    lead1 = [k for k, r in res.items() if r[0] >= 0.75 and r[1] < 0.01 and r[4] >= 0.60]
    lead3 = v.median() >= 1.5 and (v > 0).mean() >= 0.75
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 L1 A 35-65%: {min(A) * 100:.0f}..{max(A) * 100:.0f}%; B 0.40-0.60: {min(B):.2f}..{max(B):.2f}; C 42-58%: "
            f"{min(C) * 100:.0f}..{max(C) * 100:.0f}% -> "
            f"{'RIGHT' if min(A) >= .35 and max(A) <= .65 and min(B) >= .4 and max(B) <= .6 and min(C) >= .42 and max(C) <= .58 else 'WRONG'}",
            f"  2 L3 median [T-1,T+1) {v.median():+.2f} (within +-0.5), his way {(v > 0).mean() * 100:.0f}% (35-65), jump diff "
            f"{(D.jump - D.ctrl).median():+.2f} (within +-0.5) -> "
            f"{'RIGHT' if abs(v.median()) <= .5 and .35 <= (v > 0).mean() <= .65 and abs((D.jump - D.ctrl).median()) <= .5 else 'WRONG'}",
            f"  LEAD LINE: L1 {lead1 if lead1 else 'closed'}; L3 {'OPEN' if lead3 else 'closed'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
