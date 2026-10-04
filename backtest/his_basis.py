"""DOES HE TRADE THE FUTURES-CASH GAP? - real NQ futures against the cash index at his moments.

WHY (his_strategy.md s39)
    His side is not in either price's history (s36, s39). But he trades a FUTURES-priced NASDAQ (quarter-point grid,
    a basis that rolls down into each expiry) while Exness quotes the CASH index. Index traders watch the gap between
    them: when the futures run ahead of cash, or lag it, the gap mean-reverts within minutes, and the direction of
    that snap-back is information that sits in NEITHER series alone. Never tested here.

DATA (both already local - no new download)
    real NQ futures: the last trade price each second from the Databento trades cache (his_tape.py)
    cash index: Exness USTECm mid each second from the tick cache
    gap(t) = futures - cash; dev_w(t) = gap(t) - mean(gap over the previous w seconds), w = 60 / 300 / 900

TESTS
    A. Does the gap's deviation agree with HIS side? A buy should come when futures are CHEAP against their recent
       gap (dev < 0) if he trades the snap-back.
    B. Is the deviation larger at his moments than at the sitting's other moments? (|dev| rank)
    C. At the sitting's moments, trade the snap-back of a top-decile deviation: does it win the +-7 race?
    D. First, how much the gap moves at all - if Exness derives its cash price from the futures, it barely will.

REGISTERED PREDICTIONS (2026-10-04, before running)
    1. D: the gap's within-window standard deviation is under 1.5 points - Exness USTECm is a CFD priced off the
       futures, so there is little gap to trade.
    2. A: agreement 45-55%; B: ranks 0.45-0.55; C: 48-55%.

    python -m backtest.his_basis
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_race_curve import race2  # noqa: E402
from backtest.his_tape import TICKS, entries  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
W = (60, 300, 900)


BBO = ROOT / "strategy_analysis" / "data" / "nq_bbo1s.pkl"


def futures_mid() -> pd.Series:
    """Real NQ futures mid each second (Databento bbo-1s, priced at $0.14 for these windows). The trades and book
    caches hold sizes only, so prices come from here. Cached locally (git-ignored)."""
    import backtest.his_tape as TP
    C = pickle.loads(BBO.read_bytes()) if BBO.exists() else {}
    wins = TP.windows(entries())
    need = [w for w in wins if (str(w[0]), str(w[1])) not in C]
    if need:
        cl = TP.client()
        usd = sum(float(cl.metadata.get_cost(dataset=TP.DATASET, symbols=[TP.SYMBOL], schema="bbo-1s",
                                             stype_in=TP.STYPE, start=a.isoformat() + "Z", end=b.isoformat() + "Z"))
                  for a, b in need)
        print(f"fetching {len(need)} windows of bbo-1s: estimated ${usd:.2f}", flush=True)
        if usd > 5:
            sys.exit("over $5 - stopped")
        for a, b in need:
            df = cl.timeseries.get_range(dataset=TP.DATASET, symbols=[TP.SYMBOL], schema="bbo-1s",
                                         stype_in=TP.STYPE, start=a.isoformat() + "Z",
                                         end=b.isoformat() + "Z").to_df().reset_index()
            tcol = "ts_recv" if "ts_recv" in df.columns else df.columns[0]
            t = pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None).dt.floor("s")
            C[(str(a), str(b))] = pd.Series(((df.bid_px_00 + df.ask_px_00) / 2).to_numpy(float), index=t)
        BBO.write_bytes(pickle.dumps(C))
    s = pd.concat(C.values())
    return s[~s.index.duplicated(keep="last")].sort_index()


def main():
    from scipy.stats import binomtest, wilcoxon
    fut = futures_mid()
    fut = fut[(fut > 1000) & np.isfinite(fut)]
    ticks = pickle.loads(TICKS.read_bytes())
    x = entries()
    rows, sds = [], []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None or r.t < 960:
            continue
        ts, mid, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        lo, hi = r.t - 22 * 60, r.t + 20 * 60
        secs = np.arange(max(lo, 0), hi, 1.0)
        cash = mid[np.clip(np.searchsorted(ts, secs, side="right") - 1, 0, None)]
        when = base + pd.to_timedelta(secs, unit="s")
        f = fut.reindex(when, method="ffill").to_numpy(float)
        gap = pd.Series(f - cash, index=secs)
        if gap.notna().sum() < 600:
            continue
        sds.append(float(gap.std()))
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if r.t + 60 * m > 960 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            row = dict(entry=r.Index, who=who, s=r.s, race_up=race2(ts, mid, t, 1, 600, 7, 7))
            g_now = gap.asof(t)
            for w in W:
                prev = gap[(gap.index > t - w) & (gap.index <= t)]
                row[f"dev{w}"] = g_now - prev.mean() if len(prev) > w / 2 else np.nan
            rows.append(row)
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    out = [f"{len(H)} entries, {len(N)} same-sitting moments; futures (Databento trades) vs Exness cash, per second",
           f"\nD. how much the futures-cash gap moves inside a 42-minute window: median sd {np.median(sds):.2f} pts "
           f"(range {np.min(sds):.2f} .. {np.max(sds):.2f})",
           "\nA. does the gap's deviation point HIS way? (a buy when futures are cheap: -dev signed by side > 0)",
           f"  {'window':>7}{'agrees':>9}{'p':>8}"]
    for w in W:
        v = (-H[f"dev{w}"] * H.s).dropna()
        v = v[v != 0]
        out.append(f"  {w:>6}s{(v > 0).mean():>8.0%}{binomtest(int((v > 0).sum()), len(v), 0.5).pvalue:>8.3f}")
    out.append("\nB. is |deviation| larger at his moments than at the sitting's others?")
    out.append(f"  {'window':>7}{'rank':>8}{'p':>8}")
    for w in W:
        rk = []
        for e, g in D.groupby("entry"):
            h, n = g[g.who == "his"], g[g.who == "near"]
            if len(h) and len(n) >= 10 and np.isfinite(h[f"dev{w}"].iat[0]):
                rk.append((n[f"dev{w}"].abs().dropna() < abs(h[f"dev{w}"].iat[0])).mean())
        out.append(f"  {w:>6}s{np.mean(rk):>8.2f}{wilcoxon(np.array(rk) - 0.5).pvalue:>8.3f}")
    out.append("\nC. trade the snap-back of a top-decile deviation at the sitting's moments")
    out.append(f"  {'window':>7}{'race won':>10}{'n':>6}")
    for w in W:
        v = N.dropna(subset=[f"dev{w}", "race_up"])
        top = v[v[f"dev{w}"].abs() >= v[f"dev{w}"].abs().quantile(0.9)]
        won = np.where(top[f"dev{w}"] < 0, top.race_up, 1 - top.race_up).astype(float)
        out.append(f"  {w:>6}s{np.mean(won):>9.0%}{len(won):>6}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_basis.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
