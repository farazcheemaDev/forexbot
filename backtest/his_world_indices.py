"""Do ASIAN or EUROPEAN index futures move first, before the NASDAQ trader's clicks? (2026-11-14)

THE USER: "check asian european". His newest sitting (2026-11-12) was at 04:38-05:00 New York - US pre-market, when Europe is trading and Asia
has just closed - so a lead from those markets is a natural source he could watch. Tested before only for DAX / STOXX at his first clicks
(his_pasted_ideas.py, s60: 36-53%); Nikkei, Hang Seng, ASX, FTSE and CAC never. Outside data only: Exness CFD ticks via MT5 (2026-01 on).

INDICES  JP225m (Nikkei), HK50m (Hang Seng), AUS200m (ASX), DE30m (DAX), STOXX50m, UK100m (FTSE), FR40m (CAC); USTECm for the lead-lag.
CLICKS   his 53 NASDAQ entries (46 statement + 7 new; statement clock UTC+4 before 2026-03-29, UTC+5 after - his_fade_stretch.entries()).
MEASURE  at click t, from mids BEFORE t: his-way move of each index over 10 / 30 / 60 / 120 s (side x change; all these indices move with NASDAQ,
         so 'his way' = the same sign as his NASDAQ side), as a fraction of the index (bp), ranked against the same second of the minute
         1-20 minutes away (none within 60 s of a click). 0.5 = ordinary.
RULE     at the sittings' moments: take NASDAQ's side from each index's last 30 s; the +-7 NASDAQ race on the mid. Win rate.
LEAD-LAG pooled over the windows: corr(index 1-s change at s, NASDAQ 1-s change at s + k), k = -5..+5 (k > 0 = the index first).

REGISTERED BEFORE THE RUN (2026-11-14)
  W1  No index x horizon (28 cells) has a mean rank above 0.65 with Holm p < 0.05.                                         (85%)
  W2  Following any index's last 30 s wins the NASDAQ race 45-56%.                                                         (85%)
  W3  Every index's strongest lead-lag correlation is at k <= 0 (moves with or after NASDAQ); none leads with |corr| > 0.05. (75%)
  The 3 pre-market clicks of 2026-11-12 are reported apart (too few to test).

RESULT (2026-11-14, logs/his_world_indices.txt) - NOTHING; W1-W3 right. Before his 53 clicks every index's his-way move ranks 0.41-0.56 at
  10-120 s (smallest raw p 0.05, FTSE 120 s at 0.41 = AGAINST him; Holm 1.00). Taking NASDAQ's side from any index's last 30 s wins the race
  46.7-48.8% (1,288-1,797 moments each). Lead-lag: every index moves in the same second as NASDAQ (corr +0.29..+0.63) and NASDAQ leads all of them
  by a second (k = -1: +0.04..+0.20); no index leads (k > 0 all <= 0.012). The 3 pre-market clicks of 2026-11-12: no index consistently his way.

    python -m backtest.his_world_indices
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "his_world_indices.txt"
IDX = {"JP225m": "Nikkei", "HK50m": "Hang Seng", "AUS200m": "ASX", "DE30m": "DAX", "STOXX50m": "STOXX50", "UK100m": "FTSE", "FR40m": "CAC"}
HOR = (10, 30, 60, 120)


def mids(mt5, sym, a, b):
    tk = mt5.copy_ticks_range(sym, a.tz_localize("UTC").to_pydatetime(), b.tz_localize("UTC").to_pydatetime(), mt5.COPY_TICKS_ALL)
    if tk is None or len(tk) < 20:
        return None
    s = pd.Series((tk["bid"] + tk["ask"]) / 2, index=pd.to_datetime(tk["time_msc"], unit="ms"))
    s = s[~s.index.duplicated(keep="last")]
    return s.resample("1s").last().ffill()


def at(s, t):
    i = s.index.searchsorted(t, "right") - 1
    return s.iloc[i] if i >= 0 else np.nan


def feats(s, t, side):
    v0 = at(s, t - pd.Timedelta(seconds=1))
    return {n: side * (v0 / at(s, t - pd.Timedelta(seconds=n + 1)) - 1) * 1e4 for n in HOR}


def race(nq, t, side, k=7.0, horizon=240):
    w = nq[t:t + pd.Timedelta(seconds=horizon)]
    if len(w) < 30:
        return np.nan
    p = side * (w.to_numpy() - w.iloc[0])
    up, dn = np.flatnonzero(p >= k), np.flatnonzero(p <= -k)
    if not len(up) and not len(dn):
        return np.nan
    return 1.0 if len(up) and (not len(dn) or up[0] < dn[0]) else 0.0


def main():
    import MetaTrader5 as mt5
    from backtest.his_fade_stretch import entries
    assert mt5.initialize(), mt5.last_error()
    for s in list(IDX) + ["USTECm"]:
        mt5.symbol_select(s, True)
    X = entries()
    X = X[X.mk == "USTECm"].reset_index(drop=True)
    ct = X.utc.astype("datetime64[ns]").astype("int64").to_numpy()
    rows, rule, lags = [], {k: [] for k in IDX}, {k: {j: [] for j in range(-5, 6)} for k in IDX}
    for day, g in X.groupby(X.utc.dt.date):
        a, b = g.utc.min() - pd.Timedelta(minutes=25), g.utc.max() + pd.Timedelta(minutes=25)
        nq = mids(mt5, "USTECm", a, b)
        S = {k: mids(mt5, k, a, b) for k in IDX}
        if nq is None:
            continue
        for k, s in S.items():
            if s is None:
                continue
            j = pd.concat([s.rename("x"), nq.rename("n")], axis=1).ffill().dropna().diff().dropna()
            if len(j) > 300 and j.x.std() > 0:
                for lag in range(-5, 6):
                    lags[k][lag].append(j.x.corr(j.n.shift(-lag)))
        for r in g.itertuples():
            for k, s in S.items():
                if s is None:
                    continue
                me = feats(s, r.utc, r.s)
                if not np.all(np.isfinite(list(me.values()))):
                    continue
                C = []
                for m in range(1, 21):
                    for sg in (-1, 1):
                        u = r.utc + pd.Timedelta(minutes=sg * m)
                        if u - pd.Timedelta(seconds=125) < a or u + pd.Timedelta(seconds=240) > b or np.min(np.abs(ct - u.value)) < 60e9:
                            continue
                        f = feats(s, u, r.s)
                        if np.all(np.isfinite(list(f.values()))):
                            C.append(f)
                            mv = at(s, u - pd.Timedelta(seconds=1)) - at(s, u - pd.Timedelta(seconds=31))
                            if mv != 0:
                                rule[k].append(race(nq, u, int(np.sign(mv))))
                if len(C) < 8:
                    continue
                C = pd.DataFrame(C)
                rows.append(dict(idx=k, t=r.utc, s=r.s, pre=r.utc.date() == pd.Timestamp("2026-11-12").date(),
                                 **{f"r{n}": (np.sum(C[n] < me[n]) + 0.5 * np.sum(C[n] == me[n])) / len(C) for n in HOR},
                                 **{f"v{n}": me[n] for n in HOR}))
    mt5.shutdown()
    R = pd.DataFrame(rows)
    L = [f"backtest/his_world_indices.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {X.shape[0]} NASDAQ clicks; Exness ticks; same-second controls 1-20 min away", "",
         "RANK OF THE INDEX'S HIS-WAY MOVE BEFORE HIS CLICK (0.5 ordinary)"]
    cells = []
    for k, g in R.groupby("idx", sort=False):
        line = f"  {IDX[k]:<10} n {len(g):>2} "
        for n in HOR:
            v = g[f"r{n}"].dropna().to_numpy()
            p = stats.wilcoxon(v - 0.5).pvalue if len(v) > 5 and np.any(v != 0.5) else 1.0
            cells.append((k, n, v.mean(), p))
            line += f"  {n:>3}s {v.mean():.2f} (p {p:.2f})"
        pm = g[g.pre]
        line += "   | 11-12 pre-market 60s ranks: " + ", ".join(f"{z:.2f}" for z in pm.r60) if len(pm) else ""
        L.append(line)
    ps = np.array([c[3] for c in cells])
    order = np.argsort(ps)
    holm = np.empty(len(ps))
    run = 0.0
    for i, o in enumerate(order):
        run = max(run, min(1.0, ps[o] * (len(ps) - i)))
        holm[o] = run
    best = int(np.argmin(holm))
    L += [f"  smallest Holm p: {IDX[cells[best][0]]} {cells[best][1]}s rank {cells[best][2]:.2f}, raw p {cells[best][3]:.3f}, Holm {holm[best]:.2f}", "",
          "RULE: NASDAQ side from the index's last 30 s, +-7 NASDAQ race at the sittings' moments:"]
    wr = {}
    for k, v in rule.items():
        v = np.array([z for z in v if np.isfinite(z)])
        wr[k] = v.mean() if len(v) else np.nan
        L.append(f"  {IDX[k]:<10} won {wr[k] * 100:5.1f}% of {len(v)}")
    L += ["", "LEAD-LAG corr(index change at s, NASDAQ change at s + k), mean over days (k > 0 = the index first):"]
    lead = {}
    for k, d in lags.items():
        m = {j: np.nanmean(v) if v else np.nan for j, v in d.items()}
        lead[k] = (max(m, key=lambda j: abs(m[j]) if np.isfinite(m[j]) else -1), max(abs(m[j]) for j in m if j > 0 and np.isfinite(m[j])))
        L.append(f"  {IDX[k]:<10} " + " ".join(f"{j:+d}:{m[j]:+.3f}" for j in range(-5, 6)))
    w1 = [(IDX[c[0]], c[1]) for c, h in zip(cells, holm) if c[2] > 0.65 and h < 0.05]
    w3 = [IDX[k] for k, (bk, lv) in lead.items() if bk > 0 or lv > 0.05]
    L += ["", "PREDICTIONS",
          f"  W1 no cell > 0.65 with Holm p < 0.05 (found: {w1 or 'none'}) -> {'RIGHT' if not w1 else 'WRONG'}",
          f"  W2 every index's rule wins 45-56% ({', '.join(f'{IDX[k]} {v * 100:.0f}%' for k, v in wr.items())}) -> "
          f"{'RIGHT' if all(0.45 <= v <= 0.56 for v in wr.values() if np.isfinite(v)) else 'WRONG'}",
          f"  W3 no index leads NASDAQ (leading: {w3 or 'none'}) -> {'RIGHT' if not w3 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
