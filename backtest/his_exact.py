"""THE EXACT VERSIONS of loopholes 1 and 2 - ES top of book / aggressor / blocks, and NQ order cancellations (2026-10-16)

his_loopholes.py closed ES's PRICE lead and his_cancel_proxy.py closed a pulled-liquidity PROXY; the /goal asked for the
real thing. Bought for his 31 windows (22.8 hours), with the /goal as the instruction: ES `mbp-1` ($3.55: every top-of-
book change and every trade with its aggressor side) and NQ `mbo` ($5.55: every order add / cancel / modify, with price,
side and size; no full-book snapshot is needed to count cancels). Raw data stays local (licensed, gitignored).
FEATURES at each moment (his clicks; his sittings' moments +-1..20 min), signed his way (> 0 = his way), w = 1/2/3/5/10 s:
  ES  esimb      top-of-book (bid size - ask size) / (sum), the last state before the moment
      esflow{w}  (buy - sell aggressor volume) / total over the last w s
      esblock    signed volume of ES trades >= 50 contracts over the last 30 s
  NQ  cxl{w}     (ask-side cancelled size - bid-side cancelled size) / (sum), orders within 5 points of the mid
                 (> 0 = offers pulled ahead of a buyer)
      bigcxl{w}  the same, only single cancels >= 10 lots (the "fake wall" pulled)
      cratio{w}  his side's opposite-side cancel ratio: cancelled / added size within 5 points (ask side for a buy)
TESTS    A his side vs the sign; B his moment ranked in his sitting; C at the sittings' moments, trade the sign of a
         top-quintile reading (no use of his side) -> +-7 race on the Exness mid.

REGISTERED BEFORE ANY DATA IS FETCHED (2026-10-16)
    1. A within 35-65% for every feature (except tiny-n cells, n < 10, which are reported but not judged).
    2. B within 0.40-0.60.  3. C within 42-58%.
    LEAD LINE: A >= 75% (p < 0.01) or B >= 0.65 (p < 0.01), AND a rule >= 60% -> the loophole is OPEN.

RESULT (2026-10-16, logs/his_exact.txt) - LOOPHOLES 1 AND 2 CLOSED on the exact data; the lead line not hit.
    21.4M ES top-of-book rows (1.17M trades), 37.7M NQ order adds / cancels (17.1M cancels within 5 points of the mid);
    46 entries, 1,585 sitting moments. ES top of book agrees with his side 46%, ES aggressor flow 1-10 s 40-48%, ES blocks
    56% on 9; NQ cancel imbalance 38-46%, big single cancels 33-58% on 2-12; ranks 0.40-0.52. One cell stands out and
    points AGAINST him: cratio3 30% (p 0.011, rank 0.40) - before his buys, bids were being pulled relative to adds: his
    pullback seen in the book (as with the dark-pool blocks, s66); not Holm-significant over 22 features, rules 48-52%.
    Predictions 1 and 3 'wrong' only through that cell and ES flow's rule C: at ordinary moments, trading WITH 2-10 s of
    ES aggressor flow won NQ's +-7 MID race 55-60% - carried to money in backtest/es_flow_mended.py (it dies).
    First run of this file read 0 trades / 0 cancels: pandas stored the codes as StringDtype, not object - fixed in slim().
    Data: $9.10 of credit as priced (ES mbp-1 $3.55, NQ mbo $5.55), per-window caches in strategy_analysis/data/exact_*/.

    python -m backtest.his_exact
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

DATA = ROOT / "strategy_analysis" / "data"
ES_CACHE = DATA / "es_mbp1_windows.pkl"
MBO_CACHE = DATA / "nq_mbo_windows.pkl"
LOG = ROOT / "logs" / "his_exact.txt"
W = (1, 2, 3, 5, 10)


def call(f, **k):
    last = None
    for i in range(6):
        try:
            return f(**k)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(10 * (i + 1))
    raise last


ES_DIR, MBO_DIR = DATA / "exact_es", DATA / "exact_mbo"


def _name(k):
    return k[0].replace(":", "").replace(" ", "_") + ".pkl"


def migrate():
    """The first run kept every window in one pickle, rewritten after each window (slow): split it, once."""
    for big, d in ((ES_CACHE, ES_DIR), (MBO_CACHE, MBO_DIR)):
        if big.exists():
            d.mkdir(exist_ok=True)
            for k, v in pickle.loads(big.read_bytes()).items():
                (d / _name(k)).write_bytes(pickle.dumps(slim(v)))
            big.unlink()


def slim(v):
    v = v.copy()
    if not pd.api.types.is_integer_dtype(v["action"]):        # object OR pandas StringDtype
        v["action"] = v["action"].map(ACT).fillna(9).astype(np.int8)
        v["side"] = v["side"].map(SIDE).fillna(0).astype(np.int8)
    return v


def fetch(cl, wins):
    migrate()
    ES_DIR.mkdir(exist_ok=True)
    MBO_DIR.mkdir(exist_ok=True)
    if "--no-fetch" in sys.argv:                          # use only the windows already downloaded
        wins = [w for w in wins if (ES_DIR / _name((str(w[0]), str(w[1])))).exists()
                and (MBO_DIR / _name((str(w[0]), str(w[1])))).exists()]
    for i, (a, b) in enumerate(wins, 1):
        k = (str(a), str(b))
        fe, fm = ES_DIR / _name(k), MBO_DIR / _name(k)
        if not fe.exists():
            df = call(cl.timeseries.get_range, dataset="GLBX.MDP3", symbols=["ES.v.0"], stype_in="continuous", schema="mbp-1",
                      start=a.isoformat() + "Z", end=b.isoformat() + "Z").to_df(pretty_ts=False).reset_index()
            t = "ts_event" if "ts_event" in df else df.columns[0]
            fe.write_bytes(pickle.dumps(slim(pd.DataFrame({
                "ns": df[t].to_numpy(np.int64), "action": df["action"].astype(str).to_numpy(),
                "side": df["side"].astype(str).to_numpy(), "size": df["size"].to_numpy(np.int64),
                "bsz": df["bid_sz_00"].to_numpy(np.int64), "asz": df["ask_sz_00"].to_numpy(np.int64)}))))
        if not fm.exists():
            df = call(cl.timeseries.get_range, dataset="GLBX.MDP3", symbols=["NQ.v.0"], stype_in="continuous", schema="mbo",
                      start=a.isoformat() + "Z", end=b.isoformat() + "Z").to_df(pretty_ts=False, price_type="float").reset_index()
            t = "ts_event" if "ts_event" in df else df.columns[0]
            df = df[df["action"].isin(["A", "C"])]
            fm.write_bytes(pickle.dumps(slim(pd.DataFrame({
                "ns": df[t].to_numpy(np.int64), "action": df["action"].astype(str).to_numpy(),
                "side": df["side"].astype(str).to_numpy(), "px": df["price"].to_numpy(float),
                "size": df["size"].to_numpy(np.int64)}))))
        print(f"  window {i}/{len(wins)} ready", flush=True)
    E = {k: pickle.loads((ES_DIR / _name(k)).read_bytes()) for k in ((str(a), str(b)) for a, b in wins)}
    M = {k: pickle.loads((MBO_DIR / _name(k)).read_bytes()) for k in ((str(a), str(b)) for a, b in wins)}
    return lean(E), lean(M)


ACT = {"A": 0, "C": 1, "T": 2, "M": 3}
SIDE = {"B": 1, "A": -1}


def lean(C):
    """Windows are merged per day, so they never overlap: concatenate without de-duplication, strings -> int8 codes."""
    parts = []
    for v in C.values():
        parts.append(slim(v))
    C.clear()
    return pd.concat(parts, ignore_index=True).sort_values("ns", kind="stable").reset_index(drop=True)


def main():
    from scipy.stats import binomtest, wilcoxon
    warnings.filterwarnings("ignore")
    x = TP.entries()
    wins = TP.windows(x)
    E, M = fetch(TP.client(), wins)
    # ES
    tr = E[E.action == ACT["T"]]
    tns = tr.ns.to_numpy()
    # Databento side on a trade = the aggressor: 'B' buy, 'A' sell
    sg = tr.side.to_numpy().astype(np.int64) * tr["size"].to_numpy()
    cflow, cvol = np.r_[0, np.cumsum(sg)], np.r_[0, np.cumsum(np.abs(sg))]
    cblk = np.r_[0, np.cumsum(np.where(tr["size"].to_numpy() >= 50, sg, 0))]
    ens, ebs, eas = E.ns.to_numpy(), E.bsz.to_numpy(), E.asz.to_numpy()
    # NQ: mid each second from the cached 1-s bbo, cancels / adds within 5 points of it
    nq = pd.concat(pickle.loads((DATA / "nq_bbo1s.pkl").read_bytes()).values()).sort_index()
    nq = nq[~nq.index.duplicated()]
    mid = nq.reindex(pd.to_datetime(M.ns).dt.floor("s"), method="ffill").to_numpy()
    near = np.abs(M.px.to_numpy() - mid) <= 5
    mns = M.ns.to_numpy()
    sz = M["size"].to_numpy()
    isC, isA = (M.action == ACT["C"]).to_numpy() & near, (M.action == ACT["A"]).to_numpy() & near
    ask, bid = (M.side == -1).to_numpy(), (M.side == 1).to_numpy()
    cum = {n: np.r_[0, np.cumsum(np.where(m, sz, 0))] for n, m in
           (("cA", isC & ask), ("cB", isC & bid), ("aA", isA & ask), ("aB", isA & bid),
            ("bcA", isC & ask & (sz >= 10)), ("bcB", isC & bid & (sz >= 10)))}
    ticks = pickle.loads(TP.TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None:
            continue
        ts, mid_, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).value
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            at = base + int(np.floor(t)) * 10**9
            f = {}
            j = np.searchsorted(ens, at, "right") - 1
            f["raw_esimb"] = (ebs[j] - eas[j]) / max(ebs[j] + eas[j], 1) if j >= 0 and at - ens[j] < 5 * 10**9 else np.nan
            jt = np.searchsorted(tns, at, "right")
            for w in W:
                i0 = np.searchsorted(tns, at - w * 10**9, "right")
                v = cvol[jt] - cvol[i0]
                f[f"raw_esflow{w}"] = (cflow[jt] - cflow[i0]) / v if v > 0 else 0.0
            i0 = np.searchsorted(tns, at - 30 * 10**9, "right")
            f["raw_esblock"] = float(cblk[jt] - cblk[i0])
            jm = np.searchsorted(mns, at, "right")
            for w in W:
                i0 = np.searchsorted(mns, at - w * 10**9, "right")
                d = {n: c[jm] - c[i0] for n, c in cum.items()}
                s = d["cA"] + d["cB"]
                f[f"raw_cxl{w}"] = (d["cA"] - d["cB"]) / s if s > 0 else 0.0
                s = d["bcA"] + d["bcB"]
                f[f"raw_bigcxl{w}"] = (d["bcA"] - d["bcB"]) / s if s > 0 else 0.0
                rA = d["cA"] / d["aA"] if d["aA"] > 0 else np.nan
                rB = d["cB"] / d["aB"] if d["aB"] > 0 else np.nan
                f[f"raw_cratio{w}"] = rA - rB          # > 0: offers cancelled faster than bids, relative to adds
            f.update({k[4:]: r.s * v for k, v in list(f.items())})
            rows.append(dict(entry=r.Index, who=who, s=r.s, up=race2(ts, mid_, t, 1, 600, 7, 7), **f))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"].dropna(subset=["up"])
    out = [f"backtest/his_exact.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; ES mbp-1 {len(E):,} rows ({len(tr):,} trades), "
           f"NQ mbo {len(M):,} adds+cancels ({int(isC.sum()):,} cancels within 5 points); {len(H)} of his entries, {len(N)} sitting moments",
           "", f"  {'feature':>10}{'agree':>8}{'n':>5}{'p':>8}{'rank':>7}{'p':>8}{'with':>7}{'against':>9}"]
    res = {}
    for k in [c for c in D.columns if not c.startswith("raw_") and c not in ("entry", "who", "s", "up")]:
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
        raw = N["raw_" + k].dropna()
        big = N.loc[raw.index][(raw.abs() >= raw.abs().quantile(0.8)) & (raw != 0)]
        wth = np.where(np.sign(big["raw_" + k]) == big.s, big.up, 1 - big.up).mean() if len(big) else np.nan
        res[k] = (ag, pa, rk.mean() if len(rk) else np.nan, pb, wth, len(v))
        out.append(f"  {k:>10}{ag * 100:>7.0f}%{len(v):>5}{pa:>8.3f}{res[k][2]:>7.2f}{pb:>8.3f}{wth * 100:>6.0f}%{100 - wth * 100:>8.0f}%")
    J = {k: v for k, v in res.items() if v[5] >= 10}
    A = [v[0] for v in J.values()]
    B = [v[2] for v in res.values() if np.isfinite(v[2])]
    C = [z for v in res.values() if np.isfinite(v[4]) for z in (v[4], 1 - v[4])]
    lead = [k for k, v in res.items() if ((v[0] >= .75 and v[1] < .01) or (v[2] >= .65 and v[3] < .01)) and max(v[4], 1 - v[4]) >= .60]
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 A 35-65% (n >= 10): {min(A) * 100:.0f}..{max(A) * 100:.0f}% -> {'RIGHT' if min(A) >= .35 and max(A) <= .65 else 'WRONG'}",
            f"  2 B 0.40-0.60: {min(B):.2f}..{max(B):.2f} -> {'RIGHT' if min(B) >= .4 and max(B) <= .6 else 'WRONG'}",
            f"  3 C 42-58% (both ways): {min(C) * 100:.0f}..{max(C) * 100:.0f}% -> {'RIGHT' if min(C) >= .42 and max(C) <= .58 else 'WRONG'}",
            f"  LEAD LINE: {lead if lead else 'not hit - loopholes 1 and 2 CLOSED on the exact data'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
