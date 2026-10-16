"""PULLED LIQUIDITY ("spoof" cancellations) before his clicks - a proxy from cached data (2026-10-16)

The user's /goal, loophole 2: "does a massive cancellation of fake liquidity on one side trigger his 0.7-point pullback
entry?" The exact test needs order-by-order data (MBO cancel messages); the raw MBO was deleted after his_fullbook.py and
re-buying his 31 windows costs $5.55 (priced 2026-10-16, not bought). This is the free proxy:
DATA     NQ 10-level book sizes each second (nq_book_1s.pkl, his_book.py) + every trade with its aggressor
         (nq_trades_windows.pkl, his_tape.py), his 31 windows.
PROXY    per second, size that LEFT a side without trading:  pulled_ask = max(0, -d(ask depth) - buy-aggressor volume),
         pulled_bid = max(0, -d(bid depth) - sell-aggressor volume). (Price-level shifts add noise; real cancels of
         resting orders inside 10 levels are what it catches.)
FEATURES at each moment, over the last w = 1 / 2 / 3 / 5 / 10 / 30 s, signed his way:
         pull{w}   (pulled_ask - pulled_bid) / (pulled_ask + pulled_bid)  > 0 = offers vanished ahead of a buyer
         spike{w}  the same sign, but only seconds whose total pulled size is in the top 5% of the window ("massive")
TESTS    A his side vs the sign; B his moment ranked in his sitting; C at the sittings' moments, trade the sign of a
         top-quintile reading - both ways reported (no use of his side) -> +-7 race on the Exness mid.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. A within 35-65% for every feature; 2. B within 0.40-0.60; 3. C within 42-58%.
    LEAD LINE: A >= 75% (p < 0.01) or B >= 0.65 (p < 0.01), AND a rule >= 60%.

RESULT (2026-10-16, logs/his_cancel_proxy.txt) - CLOSED (as a proxy); predictions 2-3 right, 1 'wrong' on tiny cells.
    82,187 book seconds, 46 entries, 1,585 sitting moments. Pulled-liquidity imbalance over 1-30 s agrees with his side
    38-60% (all p >= 0.36), ranks 0.47-0.55. The 'massive pull' cells read 67-86% on 3 / 5 / 7 entries (p >= 0.125): a
    top-5% pull came in the 3 s before only 7 of his 46 clicks - about the 6-7 that chance gives - so it cannot be what
    triggers the other 39. Trading with or against a big pull at the sittings' moments wins 45-55%. The exact MBO cancel
    test ($5.55 for his 31 windows) was priced, not bought.

    python -m backtest.his_cancel_proxy
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
LOG = ROOT / "logs" / "his_cancel_proxy.txt"
W = (1, 2, 3, 5, 10, 30)


def per_second():
    B = pickle.loads((DATA / "nq_book_1s.pkl").read_bytes())
    T = pickle.loads((DATA / "nq_trades_windows.pkl").read_bytes())
    parts = []
    for k, b in B.items():
        idx = pd.date_range(b.index.min(), b.index.max(), freq="s")
        b = b.reindex(idx).ffill()
        ask = b[[c for c in b if c.startswith("ask")]].sum(axis=1)
        bid = b[[c for c in b if c.startswith("bid")]].sum(axis=1)
        t = T.get(k)
        sec = pd.to_datetime(t.ns).dt.floor("s")
        buy = t["size"].where(t.aggr > 0, 0).groupby(sec).sum().reindex(idx, fill_value=0)
        sell = t["size"].where(t.aggr < 0, 0).groupby(sec).sum().reindex(idx, fill_value=0)
        pa = np.maximum(0, -ask.diff() - buy).fillna(0)
        pb = np.maximum(0, -bid.diff() - sell).fillna(0)
        tot = pa + pb
        big = tot >= tot.quantile(0.95)
        parts.append(pd.DataFrame({"pa": pa, "pb": pb, "spa": pa.where(big, 0), "spb": pb.where(big, 0)}, index=idx))
    F = pd.concat(parts).sort_index()
    F = F[~F.index.duplicated()]
    return F


def main():
    from scipy.stats import binomtest, wilcoxon
    warnings.filterwarnings("ignore")
    F = per_second()
    cs = F.cumsum()
    x = TP.entries()
    ticks = pickle.loads(TP.TICKS.read_bytes())

    def window_sum(col, at, w):
        a = cs[col].asof(at - pd.Timedelta(seconds=1))
        b = cs[col].asof(at - pd.Timedelta(seconds=1 + w))
        return a - b if np.isfinite(a) and np.isfinite(b) else np.nan

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
            if at < F.index[0]:
                continue
            f = {}
            for w in W:
                a, b = window_sum("pa", at, w), window_sum("pb", at, w)
                f[f"raw_pull{w}"] = (a - b) / (a + b) if a + b > 0 else 0.0
                a, b = window_sum("spa", at, w), window_sum("spb", at, w)
                f[f"raw_spike{w}"] = (a - b) / (a + b) if a + b > 0 else 0.0
            f = {**f, **{k[4:]: r.s * v for k, v in f.items()}}
            rows.append(dict(entry=r.Index, who=who, s=r.s, up=race2(ts, mid, t, 1, 600, 7, 7), **f))
    D = pd.DataFrame(rows).dropna(subset=[f"pull{W[0]}"])
    H, N = D[D.who == "his"], D[D.who == "near"].dropna(subset=["up"])
    out = [f"backtest/his_cancel_proxy.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(F):,} book seconds, "
           f"{len(H)} of his entries, {len(N)} sitting moments", "",
           f"  {'feature':>8}{'agree':>8}{'p':>8}{'rank':>8}{'p':>8}{'with':>7}{'against':>9}{'n':>6}"]
    res = {}
    for k in [c for c in D.columns if c.startswith(("pull", "spike"))]:
        v = H[k][H[k] != 0]
        ag = (v > 0).mean() if len(v) else np.nan
        pa = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue if len(v) else np.nan
        rk = []
        for _, g in D.groupby("entry"):
            h, n = g[g.who == "his"], g[g.who == "near"]
            if len(h) and len(n) >= 10:
                rk.append((n[k] < h[k].iat[0]).mean() + 0.5 * (n[k] == h[k].iat[0]).mean())
        rk = np.array(rk)
        pb = wilcoxon(rk - 0.5).pvalue if len(rk) > 5 and np.any(rk != 0.5) else np.nan
        raw = N["raw_" + k]
        big = N[(raw.abs() >= raw.abs().quantile(0.8)) & (raw != 0)]
        sg = np.sign(big["raw_" + k])
        wth = np.where(sg == big.s, big.up, 1 - big.up).mean() if len(big) else np.nan
        res[k] = (ag, pa, rk.mean(), pb, wth)
        out.append(f"  {k:>8}{ag * 100:>7.0f}%{pa:>8.3f}{rk.mean():>8.2f}{pb:>8.3f}{wth * 100:>6.0f}%{100 - wth * 100:>8.0f}%{len(big):>6}")
    A = [v[0] for v in res.values() if np.isfinite(v[0])]
    B = [v[2] for v in res.values()]
    C = [x_ for v in res.values() for x_ in (v[4], 1 - v[4]) if np.isfinite(v[4])]
    lead = [k for k, v in res.items() if ((v[0] >= .75 and v[1] < .01) or (v[2] >= .65 and v[3] < .01)) and max(v[4], 1 - v[4]) >= .60]
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 A 35-65%: {min(A) * 100:.0f}..{max(A) * 100:.0f}% -> {'RIGHT' if min(A) >= .35 and max(A) <= .65 else 'WRONG'}",
            f"  2 B 0.40-0.60: {min(B):.2f}..{max(B):.2f} -> {'RIGHT' if min(B) >= .4 and max(B) <= .6 else 'WRONG'}",
            f"  3 C 42-58% (both ways): {min(C) * 100:.0f}..{max(C) * 100:.0f}% -> {'RIGHT' if min(C) >= .42 and max(C) <= .58 else 'WRONG'}",
            f"  LEAD LINE: {lead if lead else 'not hit'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
