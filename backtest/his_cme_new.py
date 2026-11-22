"""The CME NQ book and tape at his 7 NEW NASDAQ clicks (October 8 / 13 and the pre-market sitting of November 12) (2026-11-13)

THE USER: "Yes, pull it" (USD 0.99 of Databento credit, GLBX.MDP3 mbp-10, NQ.v.0, three windows 22 min before to 20 min after his entries).
Every earlier CME test used his first 46 trades (his_tape / his_book / his_fullbook / his_cme_scan ...: nothing). These 7 are new, out of sample,
and three are in the PRE-MARKET (04:38-05:00 New York), where the book is thin and big resting orders stand out - never looked at.

FEATURES at his click second t, from data before t only, SIGN-ALIGNED to his side (+ = points his way):
  flow5 / flow10 / flow30 / flow60   signed aggressor volume (buyer-initiated minus seller-initiated contracts) over the last 5 / 10 / 30 / 60 s
  imb1 / imb5 / imb10                book imbalance (bid size - ask size) / (bid + ask) over the best 1 / 5 / 10 levels, last snapshot before t
  dimb5_10                           change of imb5 over the last 10 s
  mv10 / mv30 / mv60                 mid move over the last 10 / 30 / 60 s
  big30                              signed volume of trades of >= 5 contracts over the last 30 s
CONTROL: the same features at the same second of the minute, 1-20 whole minutes before / after (his_local.py), inside the window, same side,
none within 60 s of any of his clicks. Rank of his value among them (0.5 = ordinary).

REGISTERED BEFORE THE DATA ARRIVED (2026-11-13)
  N1  No feature has a mean rank above 0.75 with at least 6 of 7 clicks above 0.5 (what a public-feed trigger he follows would look like).  (80%)
  N2  The pre-market sitting (3 clicks) looks no different from the 4 cash-session clicks on any feature (all |difference in rank| < 0.4).  (60%)
  With n = 7, only a feature that sits near the top for nearly every click can show; a mild lean cannot. Twelve features: by chance one in
  ~12 reaches p 0.08 on its own.

RESULT (2026-11-13, logs/his_cme_new.txt; 5.07M mbp-10 events, USD 0.99) - NOTHING on the CME feed calls his 7 new clicks. N1 right; N2 wrong
  (mv10, 3 vs 4 clicks - noise).
  Mean ranks 0.34-0.62 on all 12 features; none above 0.75, no feature with 6 of 7 above 0.5 except flow5 (6 of 7, mean 0.58, p 0.30). The
  smallest p is imb1 at 0.078 AGAINST his side (the best level heavier on the side he trades into - one of 12, chance). His 10-08 BUY ranks
  0.03-0.21 on flow and moves: he bought straight after a 28-point drop with sellers in control, and won. The pre-market sitting is no
  different from the cash-session clicks except the 10-s move (3 vs 4 clicks). Same verdict as the first 46 (his_cme_scan.py) on fresh data.

    python -m backtest.his_cme_new
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data" / "nq_new_mbp10.parquet"
LOG = ROOT / "logs" / "his_cme_new.txt"
CLICKS = [("2026-10-08 22:10:48", "SELL"), ("2026-10-08 22:17:55", "BUY"), ("2026-10-13 20:24:30", "SELL"), ("2026-10-13 20:27:06", "SELL"),
          ("2026-11-12 14:38:38", "SELL"), ("2026-11-12 14:44:57", "SELL"), ("2026-11-12 15:00:57", "SELL")]
CLOCK = 5                                          # statement clock, UTC+5 (his_strategy s74)
FEAT = ["flow5", "flow10", "flow30", "flow60", "imb1", "imb5", "imb10", "dimb5_10", "mv10", "mv30", "mv60", "big30"]


def clicks() -> pd.DataFrame:
    c = pd.DataFrame(CLICKS, columns=["local", "side"])
    c["t"] = pd.to_datetime(c.local) - pd.Timedelta(hours=CLOCK)
    c["s"] = np.where(c.side == "BUY", 1, -1)
    return c


def windows(c: pd.DataFrame) -> list:
    W = []
    for x in sorted(c.t):
        a, b = x - pd.Timedelta(minutes=22), x + pd.Timedelta(minutes=20)
        if W and a <= W[-1][1]:
            W[-1][1] = max(W[-1][1], b)
        else:
            W.append([a, b])
    return W


def fetch(c: pd.DataFrame) -> pd.DataFrame:
    if DATA.exists():
        return pd.read_parquet(DATA)
    import databento as db
    cl = db.Historical()
    parts = []
    for a, b in windows(c):
        st = cl.timeseries.get_range(dataset="GLBX.MDP3", symbols=["NQ.v.0"], schema="mbp-10", stype_in="continuous",
                                     start=a.isoformat(), end=b.isoformat())
        df = st.to_df(price_type="float", pretty_ts=False, map_symbols=False)
        keep = ["ts_event", "action", "side", "size", "price"] + [f"{s}_{k:02d}" for k in range(10) for s in ("bid_px", "ask_px", "bid_sz", "ask_sz")]
        parts.append(df.reset_index()[[k for k in keep if k in df.reset_index().columns]])
    out = pd.concat(parts, ignore_index=True)
    out["ns"] = pd.to_datetime(out.ts_event, utc=True).dt.tz_localize(None).astype("datetime64[ns]").astype("int64")
    out = out.drop(columns="ts_event").sort_values("ns", kind="stable").reset_index(drop=True)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(DATA)
    return out


def seconds(df: pd.DataFrame) -> pd.DataFrame:
    """One row per second (label = the second's END, so a row at second k uses data strictly before k+1... read at t uses rows <= t-1)."""
    sec = (df.ns // 1_000_000_000).to_numpy()
    tr = df.action.to_numpy() == "T"
    sgn = np.where(df.side.to_numpy() == "B", 1, np.where(df.side.to_numpy() == "A", -1, 0))
    v = np.where(tr, df["size"].to_numpy() * sgn, 0)
    big = np.where(tr & (df["size"].to_numpy() >= 5), v, 0)
    bs = np.stack([df[f"bid_sz_{k:02d}"].to_numpy() for k in range(10)], 1).astype(float)
    a_ = np.stack([df[f"ask_sz_{k:02d}"].to_numpy() for k in range(10)], 1).astype(float)
    mid = (df.bid_px_00.to_numpy() + df.ask_px_00.to_numpy()) / 2
    f = pd.DataFrame({"sec": sec, "v": v, "big": big, "mid": mid,
                      "b1": bs[:, 0], "a1": a_[:, 0], "b5": bs[:, :5].sum(1), "a5": a_[:, :5].sum(1), "b10": bs.sum(1), "a10": a_.sum(1)})
    g = f.groupby("sec")
    S = pd.DataFrame({"v": g.v.sum(), "big": g.big.sum(), "mid": g.mid.last(), "b1": g.b1.last(), "a1": g.a1.last(), "b5": g.b5.last(),
                      "a5": g.a5.last(), "b10": g.b10.last(), "a10": g.a10.last()})
    full = np.arange(S.index.min(), S.index.max() + 1)
    S = S.reindex(full)
    S[["v", "big"]] = S[["v", "big"]].fillna(0)
    S = S.ffill()
    return S


def feats(S: pd.DataFrame, t_sec: int, s: int):
    """Features at click second t_sec using seconds <= t_sec - 1."""
    e = t_sec - 1
    if e - 61 < S.index[0] or e not in S.index:
        return None
    w = S.loc[:e]
    cv = w.v.to_numpy()
    out = {f"flow{n}": cv[-n:].sum() for n in (5, 10, 30, 60)}
    r = S.loc[e]
    for k in (1, 5, 10):
        b, a = r[f"b{k}"], r[f"a{k}"]
        out[f"imb{k}"] = (b - a) / (b + a) if b + a > 0 else 0.0
    r10 = S.loc[e - 10]
    out["dimb5_10"] = out["imb5"] - ((r10.b5 - r10.a5) / (r10.b5 + r10.a5) if r10.b5 + r10.a5 > 0 else 0.0)
    for n in (10, 30, 60):
        out[f"mv{n}"] = r.mid - S.loc[e - n].mid
    out["big30"] = w.big.to_numpy()[-30:].sum()
    return {k: s * v for k, v in out.items()}


def main():
    c = clicks()
    df = fetch(c)
    S = seconds(df)
    click_secs = (c.t.astype("datetime64[ns]").astype("int64") // 1_000_000_000).to_numpy()
    rows = []
    for r, ts in zip(c.itertuples(), click_secs):
        me = feats(S, int(ts), r.s)
        ctl = []
        for m in range(1, 21):
            for sg in (-1, 1):
                u = int(ts) + sg * 60 * m
                if np.min(np.abs(click_secs - u)) < 60:
                    continue
                f = feats(S, u, r.s)
                if f is not None and S.index[0] <= u <= S.index[-1]:
                    ctl.append(f)
        C = pd.DataFrame(ctl)
        rk = {k: (np.sum(C[k] < me[k]) + 0.5 * np.sum(C[k] == me[k])) / len(C) for k in FEAT}
        rows.append(dict(local=r.local, side=r.side, pre=r.local.startswith("2026-11-12"), n_ctl=len(C), **{f"v_{k}": me[k] for k in FEAT}, **rk))
    R = pd.DataFrame(rows)
    L = [f"backtest/his_cme_new.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(df):,} mbp-10 events, {len(R)} clicks, controls {R.n_ctl.min()}-{R.n_ctl.max()} each", "",
         "RANK OF HIS SIDE-ALIGNED VALUE AMONG SAME-SECOND MOMENTS (0.5 ordinary; > 0.5 = more his way)",
         "  feature    " + "  ".join(f"{x[5:10]} {x[11:16]}" for x in R.local) + "   mean   above .5   p (Wilcoxon)  pre-mkt  cash"]
    best = []
    for k in FEAT:
        v = R[k].to_numpy()
        p = stats.wilcoxon(v - 0.5).pvalue if np.any(v != 0.5) else 1.0
        d = R[R.pre][k].mean() - R[~R.pre][k].mean()
        best.append((k, v.mean(), int((v > 0.5).sum()), p, d))
        L.append(f"  {k:<10} " + "  ".join(f"{z:11.2f}" for z in v) + f"   {v.mean():.2f}   {int((v > 0.5).sum())} of 7     {p:.3f}       "
                 f"{R[R.pre][k].mean():.2f}    {R[~R.pre][k].mean():.2f}")
    L += ["", "RAW (his side + ): " + "; ".join(f"{r.local[5:16]} flow30 {r.v_flow30:+.0f} imb5 {r.v_imb5:+.2f} mv60 {r.v_mv60:+.2f}" for r in R.itertuples())]
    n1 = [b for b in best if b[1] > 0.75 and b[2] >= 6]
    n2 = [b for b in best if abs(b[4]) >= 0.4]
    L += ["", "PREDICTIONS",
          f"  N1 no feature with mean rank > 0.75 and >= 6 of 7 above 0.5 (found: {[(b[0], round(b[1], 2), b[2]) for b in n1] or 'none'}) -> {'RIGHT' if not n1 else 'WRONG'}",
          f"  N2 pre-market vs cash differ by < 0.4 on every feature (over: {[(b[0], round(b[4], 2)) for b in n2] or 'none'}) -> {'RIGHT' if not n2 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
