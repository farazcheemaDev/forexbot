"""DARK-POOL PRINTS BEFORE HIS CLICKS - off-exchange trades in QQQ and the 8 NASDAQ mega-caps (2026-10-16)

A pasted write-up: "a premium dark-pool feed - a huge off-exchange print hits the tape and the futures reprice seconds
later". Off-exchange (ATS / dark pool / internalised) trades in Nasdaq-listed stocks are printed through the FINRA/Nasdaq
Trade Reporting Facilities, which Databento's Nasdaq Basic carries (venues FINN Carteret, FINC Chicago).
DATA     XNAS.BASIC `trades`, QQQ NVDA MSFT AAPL AMZN GOOGL META AVGO TSLA, his 31 windows (22 min before to 20 min after
         each NASDAQ click) - $6.07 of the user's credit, with their OK; raw kept in the gitignored data folder.
SIGNAL   only FINN / FINC prints. Side by the tick rule against the symbol's previous print (any venue): up-tick = buy.
         Notional in $ (QQQ and stocks together). Over 15 / 30 / 60 / 120 s before T: signed dark notional (his way > 0),
         and the signed notional of BLOCK prints only (>= $1M each).
TESTS    A his side vs the sign (binomial); B his moment ranked in his sitting (mid-ranks); C rule at the sittings' moments:
         trade with a top-quintile reading (+-7 race on the Exness mid) - against the sittings' 55% drift for his side.

REGISTERED BEFORE ANY DATA IS FETCHED (2026-10-16)
    1. A within 35-65% for every feature; 2. B within 0.40-0.60; 3. C within 5 points of the same moments' baseline.
    LEAD LINE: A >= 75% (p < 0.01) or B >= 0.65 (p < 0.01), AND the rule beats the baseline by >= 10 points.

RESULT (2026-10-16, logs/his_darkpool.txt) - RULED OUT as his source; one real footprint, and it is his pullback.
    17.9M prints, 13.5M off-exchange ($176.5bn, 7,594 blocks >= $1M). Dark flow over 15-120 s agrees with his side 43-57%.
    BLOCKS over the last 2 minutes point AGAINST him: 9 of 39 his way (23%, p 0.001; rank 0.40, p 0.007) - predictions
    1-2 "wrong" on that cell. But the tick rule signs a print by the price's direction, so blocks against him = the price
    came back against him: his known pullback entry (s34, s64), seen through dark prints. And it carries no information:
    at his sittings' moments, trading WITH or AGAINST the top-quintile block flow wins 49% / 51% (317 moments).

    python -m backtest.his_darkpool
"""
from __future__ import annotations

import pickle
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

SYMS = ["QQQ", "NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "AVGO", "TSLA"]
CACHE = ROOT / "strategy_analysis" / "data" / "nasdaq_basic_trades.pkl"
LOG = ROOT / "logs" / "his_darkpool.txt"
W = (15, 30, 60, 120)


def call(f, **k):
    last = None
    for i in range(6):
        try:
            return f(**k)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(10 * (i + 1))
    raise last


def fetch(cl, wins):
    C = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    for i, (a, b) in enumerate(wins, 1):
        k = (str(a), str(b))
        if k in C:
            continue
        st = call(cl.timeseries.get_range, dataset="XNAS.BASIC", symbols=SYMS, schema="trades",
                  start=a.isoformat() + "Z", end=b.isoformat() + "Z")
        df = st.to_df(pretty_ts=False, map_symbols=True).reset_index()
        tcol = "ts_event" if "ts_event" in df else df.columns[0]
        C[k] = pd.DataFrame({"ns": df[tcol].to_numpy(np.int64), "sym": df["symbol"].astype(str).to_numpy(),
                             "pub": df["publisher_id"].to_numpy(np.int64), "px": df["price"].to_numpy(float),
                             "sz": df["size"].to_numpy(np.int64)})
        CACHE.write_bytes(pickle.dumps(C))
        print(f"  fetched {i}/{len(wins)} ({len(df):,} prints)", flush=True)
    return pd.concat(C.values()).drop_duplicates().sort_values("ns", kind="stable").reset_index(drop=True)


def main():
    from scipy.stats import binomtest, wilcoxon
    warnings.filterwarnings("ignore")
    x = TP.entries()
    wins = TP.windows(x)
    cl = TP.client()
    dark_ids = {p["publisher_id"] for p in call(cl.metadata.list_publishers)
                if p["dataset"] == "XNAS.BASIC" and p["venue"] in ("FINN", "FINC")}
    T = fetch(cl, wins)
    T["sign"] = 0
    for s, g in T.groupby("sym"):
        d = np.sign(np.diff(np.r_[g.px.iat[0], g.px.to_numpy()]))
        d = pd.Series(np.where(d == 0, np.nan, d)).ffill().fillna(0).to_numpy()
        T.loc[g.index, "sign"] = d
    T["notional"] = T.px * T.sz
    D_ = T[T.pub.isin(dark_ids)].reset_index(drop=True)
    ns = D_.ns.to_numpy()
    flow = np.r_[0.0, np.cumsum(D_.sign * D_.notional)]
    blk = np.r_[0.0, np.cumsum(np.where(D_.notional >= 1e6, D_.sign * D_.notional, 0.0))]
    ticks = pickle.loads(TP.TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None:
            continue
        ts, mid, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).value
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            at = base + int(t * 1e9)
            j = np.searchsorted(ns, at, "right")
            f = {}
            for w in W:
                i = np.searchsorted(ns, at - w * 10**9, "right")
                f[f"dark{w}"] = r.s * (flow[j] - flow[i])
                f[f"block{w}"] = r.s * (blk[j] - blk[i])
            rows.append(dict(entry=r.Index, who=who, s=r.s, up=race2(ts, mid, t, 1, 600, 7, 7), **f))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    nb = N.dropna(subset=["up"])
    base = np.where(nb.s > 0, nb.up, 1 - nb.up).mean()
    out = [f"backtest/his_darkpool.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(T):,} prints in {len(wins)} windows, "
           f"{len(D_):,} off-exchange (FINN/FINC, {D_.notional.sum() / 1e9:.1f} $bn, {int((D_.notional >= 1e6).sum()):,} blocks >= $1M); "
           f"{len(H)} of his entries, {len(N)} sitting moments", f"baseline: his side at the sittings' moments wins {base * 100:.1f}%", "",
           f"  {'feature':>9}{'agree':>8}{'p':>8}{'rank':>8}{'p':>8}{'rule':>8}{'n':>6}"]
    res = {}
    for k in [c for c in D.columns if c.startswith(("dark", "block"))]:
        v = H[k][H[k] != 0]
        ag = (v > 0).mean() if len(v) else np.nan
        pa = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue if len(v) else np.nan
        rk = []
        for _, g in D.groupby("entry"):
            h, n = g[g.who == "his"], g[g.who == "near"]
            if len(h) and len(n) >= 10:
                rk.append((n[k] < h[k].iat[0]).mean() + 0.5 * (n[k] == h[k].iat[0]).mean())
        pb = wilcoxon(np.array(rk) - 0.5).pvalue if len(rk) > 5 and np.any(np.array(rk) != 0.5) else np.nan
        hi = nb[nb[k] >= nb[k].quantile(0.8)]
        hi = hi[hi[k] > 0]
        rule = np.where(hi.s > 0, hi.up, 1 - hi.up).mean() if len(hi) else np.nan
        # unsigned rules at the sittings' moments (no use of his side): with / against the flow's own sign, top quintile |flow|
        raw = nb[k] * nb.s
        big = nb[(raw.abs() >= raw.abs().quantile(0.8)) & (raw != 0)]
        rb = big[k] * big.s
        w_with = np.where(rb > 0, big.up, 1 - big.up).mean() if len(big) else np.nan
        res[k] = (ag, pa, np.mean(rk), pb, rule)
        out.append(f"  {k:>9}{ag * 100:>7.0f}%{pa:>8.3f}{np.mean(rk):>8.2f}{pb:>8.3f}{rule * 100:>7.0f}%{len(hi):>6}"
                   f"   (n {len(v)}; any side: WITH the flow {w_with * 100:.0f}%, AGAINST {100 - w_with * 100:.0f}% of {len(big)})")
    lead = [k for k, v in res.items() if ((v[0] >= 0.75 and v[1] < 0.01) or (v[2] >= 0.65 and v[3] < 0.01)) and v[4] - base >= 0.10]
    A = [v[0] for v in res.values() if np.isfinite(v[0])]
    B = [v[2] for v in res.values()]
    Cc = [v[4] for v in res.values() if np.isfinite(v[4])]
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 A within 35-65%: {min(A) * 100:.0f}..{max(A) * 100:.0f}% -> {'RIGHT' if min(A) >= 0.35 and max(A) <= 0.65 else 'WRONG'}",
            f"  2 B within 0.40-0.60: {min(B):.2f}..{max(B):.2f} -> {'RIGHT' if min(B) >= 0.40 and max(B) <= 0.60 else 'WRONG'}",
            f"  3 C within 5 points of {base * 100:.0f}%: {min(Cc) * 100:.0f}..{max(Cc) * 100:.0f}% -> "
            f"{'RIGHT' if all(abs(c - base) <= 0.05 for c in Cc) else 'WRONG'}",
            f"  LEAD LINE: {', '.join(lead) if lead else 'not hit'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
