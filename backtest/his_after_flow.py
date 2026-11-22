"""WHO MOVES NASDAQ AFTER HIS CLICK? - the CME tape in the 5 minutes AFTER his entries (2026-11-13)

THE USER: "figure out what are we missing for nasdaq" (from outside data only). Every CME test so far (his_tape, his_book, his_fullbook, his_cme_scan,
his_cme_new) asked what the feed showed BEFORE his click: nothing. His side is right ~90% within minutes and a copy 30 s late still wins
(his_strategy s74), so whatever he knows plays out over MINUTES. One thing that moves a market steadily for minutes is a big order being worked
(a fund's parent order cut into child orders, often equal clips). If that is what he sees (or is told about), the AFTER-click tape should show it:
  - his-side aggressive volume over the next 1-5 minutes far above ordinary moments, MORE than the price move alone would bring (an ordinary move
    of the same size is made with less one-sided flow), and
  - a 'child order' signature: a big share of his-side aggressive volume in ONE repeated clip size.
Never tested: the earlier files read only the seconds before t.

DATA (on disk, nothing bought): nq_trades_windows.pkl (every NQ trade with aggressor side) + nq_bbo1s.pkl (NQ mid each second) for the 31 windows
of the first 46 clicks (his_tape.entries / windows: statement clock UTC+4 before 2026-03-29, UTC+5 after), and nq_new_mbp10.parquet for the 7 new
clicks (UTC+5). Windows run 22 min before to 20 min after each click.
MEASURES at click t (his side s; + = his way): mv60 / mv300 (mid move after t), flow60 / flow300 (signed aggressor contracts after t),
  clip300 = the share of his-side aggressor volume in (t, t+300] carried by its single most common clip size (size 1 excluded).
CONTROL: same second of the minute, 1-15 minutes before / after, whole 300 s inside the window, none within 60 s of a click of his. Ranks among them.
  MATCHED-MOVE flow: his flow300 against the controls whose mv300 is his way and within a factor of 2 of his (rank; 0.5 = his move was made the way
  an ordinary move of that size is made).

REGISTERED BEFORE THE RUN (2026-11-13)
  A1  mv300 rank > 0.6 (sanity: his trades win - if not, the clock or the data is wrong).                                   (85%)
  A2  flow300 rank > 0.6 (the move after him comes with his-side aggressive flow).                                          (60%)
  A3  Matched-move flow300 rank between 0.4 and 0.6: his move is made like any move of its size - no unusual buyer / seller.  (60%)
  A4  clip300 rank between 0.4 and 0.6: no child-order signature.                                                           (70%)

RESULT (2026-11-13, logs/his_after_flow.txt; 53 clicks, 22-29 same-second controls each) - NO worked order behind his moves; his information is a
  ~1-MINUTE call. A3, A4 right; A1, A2 wrong (both because his edge fades by 5 minutes).
  After his click: mv60 rank 0.718 (42 of 53 above 0.5, p < 0.0001), mv300 0.585 (p 0.015) - the move his way is concentrated in the first minute
  and mostly spent by 5. flow60 0.649 (p 0.002), flow300 0.572 (p 0.09): the first minute's move comes with his-side aggressive flow, as any
  move does. Against controls with a move of the SAME size, his flow300 ranks 0.498 (p 0.97, 32 clicks): the move is made the way an ordinary move
  of that size is made - no unusual buyer / seller. Child-order signature (one clip size carrying his-side volume): 0.570 (p 0.16) - none.
  So the 'he sees a big order being worked' explanation is not supported; what he calls is the next minute's direction.

    python -m backtest.his_after_flow
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "his_after_flow.txt"
NS = 1_000_000_000


def old_windows():
    """[(clicks (utc, side), trades ns/size/aggr, mid Series indexed by UTC second)] for the 31 cached windows."""
    from backtest.his_tape import entries
    x = entries()
    tr = pickle.load(open(DATA / "nq_trades_windows.pkl", "rb"))
    bb = pickle.load(open(DATA / "nq_bbo1s.pkl", "rb"))
    out = []
    for key, T in tr.items():
        a, b = pd.Timestamp(key[0]), pd.Timestamp(key[1])
        cl = x[(x.utc >= a) & (x.utc <= b)]
        if not len(cl) or key not in bb:
            continue
        mid = bb[key]
        mid.index = pd.to_datetime(mid.index).tz_localize(None) if getattr(mid.index, "tz", None) else pd.to_datetime(mid.index)
        out.append(([(r.utc, r.s) for r in cl.itertuples()], T[["ns", "size", "aggr"]].copy(), mid))
    return out


def new_windows():
    from backtest.his_cme_new import clicks, windows
    c = clicks()
    df = pd.read_parquet(DATA / "nq_new_mbp10.parquet")
    tr = df[df.action == "T"]
    T = pd.DataFrame({"ns": tr.ns.to_numpy(), "size": tr["size"].to_numpy(),
                      "aggr": np.where(tr.side.to_numpy() == "B", 1, np.where(tr.side.to_numpy() == "A", -1, 0))})
    m = pd.Series((df.bid_px_00.to_numpy() + df.ask_px_00.to_numpy()) / 2, index=pd.to_datetime(df.ns.to_numpy()))
    mid = m.resample("1s").last().ffill()
    out = []
    for a, b in windows(c):
        cl = c[(c.t >= a) & (c.t <= b)]
        sel = (T.ns >= a.value) & (T.ns <= b.value)
        out.append(([(r.t, r.s) for r in cl.itertuples()], T[sel].copy(), mid[a:b]))
    return out


def measure(t: pd.Timestamp, s: int, T: pd.DataFrame, mid: pd.Series):
    def at(x):
        i = mid.index.searchsorted(x, "right") - 1
        return mid.iloc[i] if i >= 0 else np.nan
    m0 = at(t)
    if not np.isfinite(m0) or t + pd.Timedelta(seconds=300) > mid.index[-1] or t < mid.index[0]:
        return None
    t0 = t.value
    w60 = T[(T.ns > t0) & (T.ns <= t0 + 60 * NS)]
    w300 = T[(T.ns > t0) & (T.ns <= t0 + 300 * NS)]
    mine = w300[(w300.aggr == s) & (w300["size"] > 1)]
    tot = w300[w300.aggr == s]["size"].sum()
    clip = (mine.groupby("size")["size"].sum().max() / tot) if len(mine) and tot > 0 else 0.0
    return dict(mv60=s * (at(t + pd.Timedelta(seconds=60)) - m0), mv300=s * (at(t + pd.Timedelta(seconds=300)) - m0),
                flow60=s * float((w60["size"] * w60.aggr).sum()), flow300=s * float((w300["size"] * w300.aggr).sum()), clip300=clip)


def rank(v, arr):
    arr = np.asarray(arr, float)
    return (np.sum(arr < v) + 0.5 * np.sum(arr == v)) / len(arr) if len(arr) else np.nan


def main():
    W = [("old", w) for w in old_windows()] + [("new", w) for w in new_windows()]
    rows = []
    for tag, (cl, T, mid) in W:
        times = np.array([c[0].value for c in cl])
        for t, s in cl:
            me = measure(t, s, T, mid)
            if me is None:
                continue
            C = []
            for k in range(1, 16):
                for sg in (-1, 1):
                    u = t + pd.Timedelta(minutes=sg * k)
                    if np.min(np.abs(times - u.value)) < 60 * NS:
                        continue
                    f = measure(u, s, T, mid)
                    if f is not None:
                        C.append(f)
            if len(C) < 8:
                continue
            C = pd.DataFrame(C)
            r = {k: rank(me[k], C[k]) for k in ("mv60", "mv300", "flow60", "flow300", "clip300")}
            mm = C[(C.mv300 > 0) & (C.mv300 >= me["mv300"] / 2) & (C.mv300 <= me["mv300"] * 2)] if me["mv300"] > 0 else C.iloc[0:0]
            r["matched_flow300"] = rank(me["flow300"], mm.flow300) if len(mm) >= 3 else np.nan
            rows.append(dict(tag=tag, t=t, s=s, n_ctl=len(C), n_match=len(mm), **{f"v_{k}": v for k, v in me.items()}, **r))
    R = pd.DataFrame(rows)
    L = [f"backtest/his_after_flow.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(R)} clicks measured (old {int((R.tag == 'old').sum())}, new "
         f"{int((R.tag == 'new').sum())}), controls {R.n_ctl.min()}-{R.n_ctl.max()} each", "",
         "RANKS OF HIS CLICK AMONG SAME-SECOND MOMENTS (0.5 = ordinary; > 0.5 = more his way)"]
    P = {}
    for k in ("mv60", "mv300", "flow60", "flow300", "matched_flow300", "clip300"):
        v = R[k].dropna().to_numpy()
        p = stats.wilcoxon(v - 0.5).pvalue if len(v) > 5 else np.nan
        P[k] = (v.mean(), p, len(v))
        nv = R[R.tag == "new"][k].dropna()
        L.append(f"  {k:<16} n {len(v):>2}  mean rank {v.mean():.3f}  median {np.median(v):.3f}  above 0.5: {int((v > 0.5).sum())}  Wilcoxon p {p:.4f}   new clicks: "
                 + ", ".join(f"{z:.2f}" for z in nv))
    L += ["", "RAW medians (his side +): " + "  ".join(f"{k} {R[f'v_{k}'].median():+.2f}" for k in ("mv60", "mv300", "flow60", "flow300", "clip300")),
          f"  matched-move controls per click: median {int(R.n_match.median())} (clicks with >= 3: {int(R.matched_flow300.notna().sum())})"]
    L += ["", "PREDICTIONS",
          f"  A1 mv300 rank > 0.6 ({P['mv300'][0]:.3f}) -> {'RIGHT' if P['mv300'][0] > 0.6 else 'WRONG'}",
          f"  A2 flow300 rank > 0.6 ({P['flow300'][0]:.3f}) -> {'RIGHT' if P['flow300'][0] > 0.6 else 'WRONG'}",
          f"  A3 matched-move flow rank in 0.4-0.6 ({P['matched_flow300'][0]:.3f}, p {P['matched_flow300'][1]:.3f}) -> "
          f"{'RIGHT' if 0.4 <= P['matched_flow300'][0] <= 0.6 else 'WRONG'}",
          f"  A4 clip300 rank in 0.4-0.6 ({P['clip300'][0]:.3f}, p {P['clip300'][1]:.3f}) -> {'RIGHT' if 0.4 <= P['clip300'][0] <= 0.6 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    R.to_csv(ROOT / "logs" / "his_after_flow_rows.csv", index=False)
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
