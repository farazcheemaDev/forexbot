"""WHAT WOULD AN FX VETERAN WATCH? - Treasury, FX, oil, gold and equity futures before his clicks (real CME data).

WHY (the user: "a person with 20 years of forex experience"; his_strategy.md s42)
    His edge is a genuine read of the next 1-5 minutes (s42: the real NQ contract moved +10.97 points his way between
    his seconds). It is not in NQ's own price, tape, book or futures-cash gap. An FX veteran's screen is built around
    RATES and RISK: Treasury futures (yields drive tech), the yen (risk-on / risk-off), the euro, oil, gold. s32 tested
    the S&P, Dow, mega-caps, dollar index, gold, USDJPY and bitcoin on Exness CFD ticks. Never tested: Treasury
    futures at all, and none of these on the real exchange feed.

DATA: Databento GLBX.MDP3 bbo-1s (mid each second), continuous front-volume contracts:
      ZN (10-year note), ZB (30-year bond), ES, RTY, 6E (euro), 6J (yen), GC (gold), CL (oil);
      the same 31 windows around his entries (his_tape.windows), priced before download, raw data local.

AT EACH MOMENT (his entries; the same-sitting moments) the symbol's return over the prior 30 / 60 / 120 / 300 s.
    A. agreement: sign(return) vs HIS side (two-sided binomial; Holm over every symbol x window)
    B. timing: |return| at his moment ranked among the sitting's moments
    C. at the sitting's moments, a top-decile move: does following its sign win the NQ +-7 race?

REGISTERED PREDICTIONS (2026-10-04, before any data is fetched)
    1. Nothing survives Holm in A; every agreement lies within 35-65%.
    2. If anything shows, it is ZN or ZB (rates lead tech) - the yen and the euro next.
    3. B: ranks within 0.40-0.60.

    python -m backtest.his_crossfut
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "cross_bbo1s.pkl"
SYMS = ("ZN.v.0", "ZB.v.0", "ES.v.0", "RTY.v.0", "6E.v.0", "6J.v.0", "GC.v.0", "CL.v.0")
W = (30, 60, 120, 300)


def series():
    C = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    wins = TP.windows(TP.entries())
    need = [(s, a, b) for s in SYMS for a, b in wins if (s, str(a)) not in C]
    if need:
        cl = TP.client()
        usd = sum(float(cl.metadata.get_cost(dataset=TP.DATASET, symbols=[s], schema="bbo-1s", stype_in=TP.STYPE,
                                             start=a.isoformat() + "Z", end=b.isoformat() + "Z")) for s, a, b in need)
        print(f"fetching {len(need)} symbol-windows of bbo-1s: estimated ${usd:.2f}", flush=True)
        if usd > 5:
            sys.exit("over $5 - stopped")
        for s, a, b in need:
            try:
                df = cl.timeseries.get_range(dataset=TP.DATASET, symbols=[s], schema="bbo-1s", stype_in=TP.STYPE,
                                             start=a.isoformat() + "Z", end=b.isoformat() + "Z").to_df().reset_index()
            except Exception as e:  # noqa: BLE001
                print(f"  {s} {a}: {type(e).__name__}", flush=True)
                C[(s, str(a))] = pd.Series(dtype=float)
                continue
            tcol = "ts_recv" if "ts_recv" in df.columns else df.columns[0]
            t = pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None).dt.floor("s")
            m = ((df.bid_px_00 + df.ask_px_00) / 2).to_numpy(float)
            C[(s, str(a))] = pd.Series(m, index=t)
        CACHE.write_bytes(pickle.dumps(C))
    out = {}
    for s in SYMS:
        parts = [v for (k, _), v in C.items() if k == s and len(v)]
        if parts:
            v = pd.concat(parts)
            v = v[~v.index.duplicated(keep="last") & np.isfinite(v) & (v > 0)].sort_index()
            out[s] = v
    return out


def main():
    from scipy.stats import binomtest, wilcoxon
    S = series()
    x = TP.entries()
    ticks = pickle.loads(TP.TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None or r.t < 960:
            continue
        ts, mid, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if r.t + 60 * m > 960 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            T = base + pd.Timedelta(seconds=float(t))
            row = dict(entry=r.Index, who=who, s=r.s, race_up=race2(ts, mid, t, 1, 600, 7, 7))
            for sym, v in S.items():
                k = v.index.searchsorted(T, side="right") - 1
                if k < 0 or (T - v.index[k]).total_seconds() > 5:
                    continue
                for w in W:
                    j = v.index.searchsorted(T - pd.Timedelta(seconds=w), side="right") - 1
                    if j >= 0:
                        row[f"{sym[:-4]}_{w}"] = np.log(v.iat[k] / v.iat[j]) * 1e4
            rows.append(row)
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    cells = []
    for sym in S:
        for w in W:
            k = f"{sym[:-4]}_{w}"
            if k not in D:
                continue
            v = (np.sign(H[k]) * H.s).dropna()
            v = v[v != 0]
            if len(v) < 10:
                continue
            p = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue
            rk = []
            for e, g in D.groupby("entry"):
                h, n = g[g.who == "his"], g[g.who == "near"]
                if len(h) and len(n) >= 10 and np.isfinite(h[k].iat[0]):
                    rk.append((n[k].abs().dropna() < abs(h[k].iat[0])).mean())
            nv = N.dropna(subset=[k, "race_up"])
            nv = nv[nv[k] != 0]
            top = nv[nv[k].abs() >= nv[k].abs().quantile(0.9)]
            won = np.where(top[k] > 0, top.race_up, 1 - top.race_up).astype(float)
            cells.append(dict(k=k, n=len(v), agree=(v > 0).mean(), p=p, rank=np.mean(rk) if rk else np.nan,
                              rank_p=wilcoxon(np.array(rk) - 0.5).pvalue if len(rk) > 5 else np.nan,
                              follow=np.mean(won) if len(won) else np.nan))
    R = pd.DataFrame(cells)
    order = R.p.sort_values().index
    m = len(R)
    R["holm"] = np.nan
    run = 0.0
    for i, ix in enumerate(order):
        run = max(run, min(1.0, R.p[ix] * (m - i)))
        R.loc[ix, "holm"] = run
    out = [f"{len(H)} entries, {len(N)} sitting moments; {len(S)} futures on the real exchange feed (bbo-1s), "
           f"{m} symbol x window cells, Holm over all",
           f"\n  {'cell':>10}{'n':>4}{'his side':>10}{'p':>8}{'Holm':>7}{'|move| rank':>13}{'p':>7}{'follow wins':>13}"]
    for r in R.sort_values("p").itertuples():
        out.append(f"  {r.k:>10}{r.n:>4}{r.agree:>9.0%}{r.p:>8.3f}{r.holm:>7.3f}{r.rank:>12.2f}{r.rank_p:>8.3f}"
                   f"{r.follow:>12.0%}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_crossfut.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
