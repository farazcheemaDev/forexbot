"""THE FULL CME ORDER BOOK (every resting order, every level) at his clicks - the last untested part of his market (2026-10-14)

WHY      his_book.py read 10 levels a side (~2.5 NASDAQ points). A pasted write-up: premium depth tools (Bookmap / MBO) show
         large resting orders far from the price - "walls" or icebergs - and price is drawn to them (or bounces off them).
         Any such wall 5-40 points away was invisible to every test so far.

DATA     Databento GLBX.MDP3 `mbo` (market by order), NQ.v.0, from 00:00 UTC (the only point that carries a full-book
         snapshot) to the end of his last window, on each of his 30 trading days - $39.09 of the user's credit, with their
         OK. Raw files in strategy_analysis/data/nq_mbo/ (gitignored, licensed). The book is rebuilt order by order:
         add / modify set an order's price and size, cancel / fill reduce it, a clear ends every order.
AT EACH MOMENT (his clicks; his sittings' moments +-1..20 min as before), signed by the side (> 0 = his way):
    imb5 / imb10 / imb20 / imb40   (resting bids - asks) / (bids + asks) within 5 / 10 / 20 / 40 points of the mid
    wall_ahead / wall_behind       the largest single price level on the side he trades INTO (asks above a buy) /
                                   the side behind him (bids below a buy), within 40 points, over the median level size
    wall_ratio                     log(wall_ahead / wall_behind)
TESTS    A his side vs the sign (binomial); B his moment ranked in his sitting (mid-ranks, Wilcoxon); C a rule at the
         sittings' moments: trade with a top-quintile reading (+-7 race on Exness mid).

REGISTERED BEFORE ANY DATA IS FETCHED (2026-10-14)
    1. A: every feature agrees with his side 35-65%.
    2. B: ranks 0.40-0.60.
    3. C: every rule wins 42-58% of races.
    LEAD LINE: a feature with A >= 75% (p < 0.01) or B >= 0.65 (p < 0.01), AND its rule >= 60% -> the deep book carries
    his side, and a bot can read it.

RESULT (2026-10-15, logs/his_fullbook.txt; 29 of 30 days - 2026-09-14 kept timing out at Databento, the user said run on
    29) - THE DEEP BOOK IS RULED OUT. 39 entries, 1,321 sitting moments, books of 2.6-14.4 million order states a day.
    A: 38-56% agreement (every p >= 0.20); B: ranks 0.44-0.50. C read 54-59% and so "WRONG" against 42-58% - but the
    rule trades HIS side at his sittings' moments, where his side wins 55.1% anyway (the sittings' drift; 1,304
    moments); a book leaning AGAINST him still wins 52.5%. The full book adds ~0-4 points over that drift.

    python -m backtest.his_fullbook --cost      price only
    python -m backtest.his_fullbook             fetch (once) and test
"""
from __future__ import annotations

import argparse
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

RAW = ROOT / "strategy_analysis" / "data" / "nq_mbo"
FEAT_CACHE = ROOT / "strategy_analysis" / "data" / "nq_mbo_features.pkl"
LOG = ROOT / "logs" / "his_fullbook.txt"
FEATS = ["imb5", "imb10", "imb20", "imb40", "wall_ahead", "wall_behind", "wall_ratio"]
ACT = {"A": 0, "M": 1, "C": 2, "F": 3, "T": 4, "R": 5, "N": 6}


def day_requests(x):
    ends = {}
    for a, b in TP.windows(x):
        d = a.normalize()
        ends[d] = max(ends.get(d, b), b)
    return sorted(ends.items())


def fetch(cl, reqs):
    RAW.mkdir(parents=True, exist_ok=True)
    for i, (d, b) in enumerate(reqs, 1):
        f = RAW / f"{d:%Y-%m-%d}.dbn.zst"
        if f.exists() and f.stat().st_size > 0:
            continue
        tmp = f.with_suffix(".part")
        import time
        for attempt in range(1, 6):                                  # the gateway times out now and then (504)
            try:
                if tmp.exists():                                     # a half-written file blocks the next attempt
                    tmp.unlink()
                cl.timeseries.get_range(dataset="GLBX.MDP3", symbols=["NQ.v.0"], schema="mbo", stype_in="continuous",
                                        start=d.isoformat() + "Z", end=b.isoformat() + "Z", path=str(tmp))
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 5:
                    raise
                print(f"  {d:%Y-%m-%d}: {type(e).__name__} - retry {attempt} in {30 * attempt} s", flush=True)
                time.sleep(30 * attempt)
        tmp.rename(f)
        print(f"  fetched {i}/{len(reqs)} {d:%Y-%m-%d} ({f.stat().st_size / 1e6:.0f} MB)", flush=True)


def load_day(f):
    import databento as db
    store = db.DBNStore.from_file(str(f))
    parts = []
    for df in store.to_df(price_type="float", pretty_ts=False, map_symbols=False, count=2_000_000):
        parts.append(pd.DataFrame({
            "ts": df["ts_event"].to_numpy(np.int64) if "ts_event" in df else df.index.to_numpy(np.int64),
            "oid": df["order_id"].to_numpy(np.uint64), "act": df["action"].map(ACT).fillna(6).to_numpy(np.int8),
            "side": np.where(df["side"].to_numpy() == "B", 1, np.where(df["side"].to_numpy() == "A", -1, 0)).astype(np.int8),
            "px": df["price"].to_numpy(np.float64), "sz": df["size"].to_numpy(np.int64), "iid": df["instrument_id"].to_numpy(np.int64)}))
    m = pd.concat(parts, ignore_index=True)
    main_iid = m.loc[m.act <= 3, "iid"].value_counts().idxmax()
    return m[(m.iid == main_iid) | (m.act == 5)].reset_index(drop=True)


def states(m):
    """one row per (order, message): the order's price / side / remaining size from this message until the next one."""
    r_times = np.sort(m.loc[m.act == 5, "ts"].to_numpy())
    o = m[(m.act <= 3) & (m.oid != 0)].copy()
    o["seq"] = np.arange(len(o))
    o = o.sort_values(["oid", "seq"], kind="stable")
    setv = o.act.isin([0, 1]).to_numpy()
    seg = np.cumsum(setv | (o.oid.to_numpy() != np.r_[0, o.oid.to_numpy()[:-1]]))
    o["seg"] = seg
    base = o.sz.where(setv)
    o["base"] = base.groupby(o.seg).transform("first")
    o["bpx"] = o.px.where(setv).groupby(o.seg).transform("first")
    o["bside"] = o.side.where(setv).groupby(o.seg).transform("first")
    dec = np.where(setv, 0, o.sz.to_numpy())
    o["rem"] = o.base.to_numpy() - pd.Series(dec, index=o.index).groupby(o.seg).cumsum().to_numpy()
    o.loc[o.act == 2, "rem"] = 0                                         # a cancel ends the order (CME cancels are full)
    nxt = o.groupby("oid").ts.shift(-1).to_numpy()
    nxt = np.where(np.isnan(nxt), np.inf, nxt)
    if len(r_times):
        k = np.searchsorted(r_times, o.ts.to_numpy(), "right")
        nr = np.where(k < len(r_times), r_times[np.minimum(k, len(r_times) - 1)], np.inf)
        nxt = np.minimum(nxt, nr)
    S = pd.DataFrame({"t0": o.ts.to_numpy(np.float64), "t1": nxt, "px": o.bpx.to_numpy(), "side": o.bside.to_numpy(),
                      "rem": o.rem.to_numpy()})
    S = S[(S.rem > 0) & S.side.isin([1, -1]) & np.isfinite(S.px)]
    return S.sort_values("t0", kind="stable").reset_index(drop=True)


def book_at(S, t):
    a = S[(S.t0 <= t) & (S.t1 > t)]
    if a.empty:
        return None
    bids = a[a.side == 1].groupby("px").rem.sum()
    asks = a[a.side == -1].groupby("px").rem.sum()
    if bids.empty or asks.empty:
        return None
    return bids, asks


def feats(bids, asks, s):
    bb, ba = bids.index.max(), asks.index.min()
    mid = (bb + ba) / 2
    f = {}
    for w in (5, 10, 20, 40):
        b = bids[bids.index >= mid - w].sum()
        a = asks[asks.index <= mid + w].sum()
        f[f"imb{w}"] = s * (b - a) / max(b + a, 1)
    b40, a40 = bids[bids.index >= mid - 40], asks[asks.index <= mid + 40]
    med = np.median(np.r_[b40.to_numpy(), a40.to_numpy()]) or 1
    ahead, behind = (a40, b40) if s > 0 else (b40, a40)
    f["wall_ahead"] = ahead.max() / med if len(ahead) else np.nan
    f["wall_behind"] = behind.max() / med if len(behind) else np.nan
    f["wall_ratio"] = np.log(max(f["wall_ahead"], 1e-9) / max(f["wall_behind"], 1e-9))
    return f


def main(argv=None):
    from scipy.stats import binomtest, wilcoxon
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost", action="store_true")
    ap.add_argument("--no-fetch", action="store_true", help="test the days already on disk")
    a_ = ap.parse_args(argv)
    x = TP.entries()
    reqs = day_requests(x)
    cl = TP.client()
    if a_.cost:
        tot = sum(float(cl.metadata.get_cost(dataset="GLBX.MDP3", symbols=["NQ.v.0"], schema="mbo", stype_in="continuous",
                                             start=d.isoformat() + "Z", end=b.isoformat() + "Z")) for d, b in reqs)
        print(f"{len(reqs)} days of MBO from 00:00 UTC: ${tot:.2f}")
        return
    if a_.no_fetch:
        reqs = [(d, b) for d, b in reqs if (RAW / f"{d:%Y-%m-%d}.dbn.zst").exists()]
    else:
        fetch(cl, reqs)
    ticks = pickle.loads(TP.TICKS.read_bytes())
    cache = pickle.loads(FEAT_CACHE.read_bytes()) if FEAT_CACHE.exists() else {}
    rows = []
    for d, _ in reqs:
        day_x = x[x.utc.dt.normalize() == d]
        key = f"{d:%Y-%m-%d}"
        if key not in cache:
            S = states(load_day(RAW / f"{key}.dbn.zst"))
            day_rows = []
            for r in day_x.itertuples():
                tday = ticks.get(r.d)
                others = x[x.d == r.d].t.to_numpy()
                starts = [("his", r.t)] + [("near", r.t + 60 * k) for k in list(range(-20, 0)) + list(range(1, 21))
                                           if r.t + 60 * k > 960 and np.min(np.abs(others - (r.t + 60 * k))) >= 60]
                base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).value
                for who, t in starts:
                    if who == "his" and r.t < 960:
                        t = r.t
                    bk = book_at(S, base + int(t * 1e9))
                    if bk is None:
                        continue
                    up = race2(tday[0], tday[1], t, 1, 600, 7, 7) if tday is not None else None
                    day_rows.append(dict(entry=r.Index, who=who, s=r.s, up=up, **feats(*bk, r.s)))
            cache[key] = day_rows
            FEAT_CACHE.write_bytes(pickle.dumps(cache))
            print(f"  {key}: {len(day_rows)} moments, {len(S):,} order states", flush=True)
        rows += cache[key]
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    out = [f"backtest/his_fullbook.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; CME NQ full order book (MBO, rebuilt from the "
           f"00:00 UTC snapshot) on {len(reqs)} days; {len(H)} of his entries, {len(N)} sitting moments", "",
           f"  {'feature':>12}{'agree':>8}{'p':>8}{'rank':>8}{'p':>8}{'rule':>8}{'n':>6}   (signed his way; rule = trade with a top-quintile reading)"]
    res = {}
    for k in FEATS:
        centre = 0.0 if k.startswith("imb") or k == "wall_ratio" else N[k].median()
        v = (H[k] - centre).dropna()
        v = v[v != 0]
        ag = (v > 0).mean() if len(v) else np.nan
        pa = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue if len(v) else np.nan
        rk = []
        for _, g in D.groupby("entry"):
            h, n = g[g.who == "his"], g[g.who == "near"]
            if len(h) and len(n) >= 10 and np.isfinite(h[k].iat[0]):
                nv = n[k].dropna().to_numpy()
                rk.append((nv < h[k].iat[0]).mean() + 0.5 * (nv == h[k].iat[0]).mean())
        pb = wilcoxon(np.array(rk) - 0.5).pvalue if len(rk) > 5 else np.nan
        u = N.dropna(subset=["up", k])
        # the reading is signed by HIS side at the near moments; unsign it to trade it: side = s if reading high
        hi = u[u[k] >= u[k].quantile(0.8)]
        rule = np.where(hi.s > 0, hi.up, 1 - hi.up).mean() if len(hi) else np.nan
        res[k] = (ag, pa, np.mean(rk), pb, rule)
        out.append(f"  {k:>12}{ag * 100:>7.0f}%{pa:>8.3f}{np.mean(rk):>8.2f}{pb:>8.3f}{rule * 100:>7.0f}%{len(hi):>6}")
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 A within 35-65%: " + ", ".join(f"{v[0] * 100:.0f}" for v in res.values()) + " -> " +
            ("RIGHT" if all(0.35 <= v[0] <= 0.65 for v in res.values()) else "WRONG"),
            f"  2 B within 0.40-0.60: " + ", ".join(f"{v[2]:.2f}" for v in res.values()) + " -> " +
            ("RIGHT" if all(0.40 <= v[2] <= 0.60 for v in res.values()) else "WRONG"),
            f"  3 C within 42-58%: " + ", ".join(f"{v[4] * 100:.0f}" for v in res.values()) + " -> " +
            ("RIGHT" if all(0.42 <= v[4] <= 0.58 for v in res.values()) else "WRONG")]
    lead = [k for k, v in res.items() if ((v[0] >= 0.75 and v[1] < 0.01) or (v[2] >= 0.65 and v[3] < 0.01)) and v[4] >= 0.60]
    out.append(f"  LEAD LINE: {', '.join(lead) if lead else 'not hit'}")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
