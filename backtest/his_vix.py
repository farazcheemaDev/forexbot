"""VIX FUTURES at the NASDAQ trader's clicks - does the fear gauge move first? (2026-11-14)

THE USER: "Yes, buy $4.89" (Databento XCBF.PITCH, bbo-1s, VX.c.0 = the front VIX future, best bid / offer each second, the 34 windows around his
53 NASDAQ clicks: 31 of the first 46 + 3 of the 7 new). Never tested against him. Option dealers and vol traders often re-price the VIX future
a moment before index futures move; if he watches VIX (or something that moves it), the VIX should lean his way BEFORE his click.

SIGN: VIX rising = NASDAQ falling. 'His way' for VIX = -side x VIX change (a buy is 'his way' when VIX FALLS).
FEATURES at his click t from data BEFORE t: vx10 / vx30 / vx60 / vx120 / vx300 = his-way VIX mid move over the last 10..300 s.
AFTER (sanity, should lean his way if VIX tracks NQ): vxa60 = his-way VIX move over the 60 s after t.
CONTROL: same second of the minute, 1-20 minutes away, inside the window, none within 60 s of a click; rank 0.5 = ordinary.
RULE (does VIX lead NQ at all?): at every control and click moment, side = the sign of -(VIX 30 s move); the +-7 NQ race on the mid. Win rate.
LEAD-LAG: correlation of 1-s VIX changes with NQ changes k seconds later, k = -10..+10, pooled over the windows.

REGISTERED BEFORE THE DATA (2026-11-14)
  V1  No pre-click VIX feature has a mean rank above 0.65 with p < 0.01.                                                (80%)
  V2  The after-click VIX move leans his way (vxa60 rank > 0.6) - VIX moves with NQ.                                     (75%)
  V3  Following VIX's last 30 s wins the NQ +-7 race 45-55% (no usable lead).                                            (80%)
  V4  Lead-lag: the strongest correlation is at lag 0 (same second); VIX-leads-NQ correlations (k > 0) are under 0.05.    (70%)

RESULT (2026-11-14, logs/his_vix.txt; USD 4.89, 59,848 VIX seconds, 53 clicks, 30-37 controls each) - VIX does NOT move first. V1, V3, V4 right;
  V2 wrong by a hair (0.584).
  Before his clicks the his-way VIX move ranks 0.48-0.54 at every horizon (10 s - 5 min, all p > 0.3). Following VIX's last 30 s wins the NQ
  +-7 race 48.0% (448 moments). Lead-lag: VIX and NQ move together in the SAME second (corr -0.227) and NQ leads by a second (-0.047 at k = -1);
  every VIX-first lag is |corr| <= 0.008. After his click VIX does lean his way (0.584, p 0.048) - it follows NQ. Limit: the VIX quote is
  unchanged in 40-79% of 10-60 s windows (coarse tick), so it can only show a lean at a minute and longer - none there either.
  Two days (2026-01-16 / 21) flagged 'degraded' by Databento.

    python -m backtest.his_vix
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
CACHE = DATA / "vx_bbo1s_windows.parquet"
LOG = ROOT / "logs" / "his_vix.txt"


def all_windows():
    from backtest.his_tape import entries, windows
    from backtest.his_cme_new import clicks, windows as nw
    x, c = entries(), clicks()
    clk = [(r.utc, r.s) for r in x.itertuples()] + [(r.t, r.s) for r in c.itertuples()]
    W = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in windows(x)] + [(a, b) for a, b in nw(c)]
    return W, clk


def fetch(W):
    if CACHE.exists():
        return pd.read_parquet(CACHE)
    import databento as db
    cl = db.Historical()
    parts = []
    for a, b in W:
        df = cl.timeseries.get_range(dataset="XCBF.PITCH", symbols=["VX.c.0"], stype_in="continuous", schema="bbo-1s",
                                     start=a.isoformat(), end=b.isoformat()).to_df(price_type="float", pretty_ts=False, map_symbols=False).reset_index()
        tcol = "ts_recv" if "ts_recv" in df.columns else "ts_event"
        parts.append(pd.DataFrame({"t": pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None), "bid": df.bid_px_00, "ask": df.ask_px_00}))
    out = pd.concat(parts, ignore_index=True).sort_values("t", kind="stable").reset_index(drop=True)
    out.to_parquet(CACHE)
    return out


def nq_mid():
    """NQ mid per second over all windows: the old cache + the new mbp-10."""
    bb = pickle.load(open(DATA / "nq_bbo1s.pkl", "rb"))
    s = [pd.Series(v.to_numpy(), index=pd.to_datetime(v.index).tz_localize(None) if getattr(v.index, "tz", None) else pd.to_datetime(v.index)) for v in bb.values()]
    df = pd.read_parquet(DATA / "nq_new_mbp10.parquet", columns=["ns", "bid_px_00", "ask_px_00"])
    s.append(pd.Series(((df.bid_px_00 + df.ask_px_00) / 2).to_numpy(), index=pd.to_datetime(df.ns.to_numpy())).resample("1s").last().dropna())
    m = pd.concat(s).sort_index()
    return m[~m.index.duplicated()]


def at(ser: pd.Series, x):
    i = ser.index.searchsorted(x, "right") - 1
    return ser.iloc[i] if i >= 0 else np.nan


def feats(vx: pd.Series, t, s):
    v0 = at(vx, t - pd.Timedelta(seconds=1))
    out = {f"vx{n}": -s * (v0 - at(vx, t - pd.Timedelta(seconds=n + 1))) for n in (10, 30, 60, 120, 300)}
    out["vxa60"] = -s * (at(vx, t + pd.Timedelta(seconds=60)) - at(vx, t))
    return out


def race(nq: pd.Series, t, s, k=7.0, horizon=240):
    w = nq[t:t + pd.Timedelta(seconds=horizon)]
    if len(w) < 30:
        return np.nan
    p = s * (w.to_numpy() - w.iloc[0])
    up, dn = np.flatnonzero(p >= k), np.flatnonzero(p <= -k)
    if not len(up) and not len(dn):
        return np.nan
    return 1.0 if len(up) and (not len(dn) or up[0] < dn[0]) else 0.0


def main():
    W, clk = all_windows()
    v = fetch(W)
    vx = pd.Series(((v.bid + v.ask) / 2).to_numpy(), index=v.t).dropna()
    vx = vx[~vx.index.duplicated()]
    nq = nq_mid()
    ct = np.array([c[0].value for c in clk])
    rows, rule = [], []
    for t, s in clk:
        win = [w for w in W if w[0] <= t <= w[1]]
        if not win:
            continue
        a, b = win[0]
        me = feats(vx, t, s)
        if not np.all(np.isfinite(list(me.values()))):
            continue
        C = []
        for k in range(1, 21):
            for sg in (-1, 1):
                u = t + pd.Timedelta(minutes=sg * k)
                if u - pd.Timedelta(seconds=301) < a or u + pd.Timedelta(seconds=240) > b or np.min(np.abs(ct - u.value)) < 60e9:
                    continue
                f = feats(vx, u, s)
                if np.all(np.isfinite(list(f.values()))):
                    C.append(f)
                    side = -np.sign(at(vx, u - pd.Timedelta(seconds=1)) - at(vx, u - pd.Timedelta(seconds=31)))
                    if side != 0:
                        rule.append(race(nq, u, int(side)))
        if len(C) < 8:
            continue
        C = pd.DataFrame(C)
        rk = {k: (np.sum(C[k] < me[k]) + 0.5 * np.sum(C[k] == me[k])) / len(C) for k in me}
        rows.append(dict(t=t, s=s, new=t > pd.Timestamp("2026-10-01"), n_ctl=len(C), **{f"v_{k}": x for k, x in me.items()}, **rk))
    R = pd.DataFrame(rows)
    L = [f"backtest/his_vix.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; VX.c.0 bbo-1s {len(vx):,} seconds over {len(W)} windows; clicks measured {len(R)} "
         f"(new {int(R.new.sum())}); controls {R.n_ctl.min()}-{R.n_ctl.max()}", "",
         "RANK OF HIS-WAY VIX MOVE AMONG SAME-SECOND MOMENTS (0.5 ordinary; > 0.5 = VIX moved his way: down before a buy, up before a sell)"]
    P = {}
    for k in ("vx10", "vx30", "vx60", "vx120", "vx300", "vxa60"):
        x = R[k].to_numpy()
        p = stats.wilcoxon(x - 0.5).pvalue
        P[k] = (x.mean(), p)
        L.append(f"  {k:<6} mean {x.mean():.3f}  median {np.median(x):.3f}  above 0.5: {int((x > 0.5).sum())} of {len(x)}  p {p:.4f}   moved at all: "
                 f"{(R[f'v_{k}'] != 0).mean() * 100:.0f}%")
    rr = np.array([z for z in rule if np.isfinite(z)])
    L += ["", f"RULE: follow VIX's last 30 s (VIX down -> buy NQ) at the sittings' moments: NQ +-7 race won {rr.mean() * 100:.1f}% of {len(rr)}"]
    # lead-lag on 1-s changes, pooled over windows
    j = pd.concat([vx.rename("vx"), nq.rename("nq")], axis=1).dropna()
    j = j[j.index.isin(pd.DatetimeIndex(vx.index))]
    lines, cors = [], {}
    for a, b in W:
        seg = j[a:b].resample("1s").last().ffill().diff().dropna()
        for k in range(-10, 11):
            cors.setdefault(k, []).append(seg.vx.corr(seg.nq.shift(-k)) if len(seg) > 100 else np.nan)
    cc = {k: np.nanmean(v_) for k, v_ in cors.items()}
    L += ["", "LEAD-LAG corr(VIX change at s, NQ change at s + k), mean over windows (k > 0 = VIX first):",
          "  " + "  ".join(f"{k:+d}:{c:+.3f}" for k, c in cc.items())]
    best_k = max(cc, key=lambda k: abs(cc[k]))
    lead = max(abs(cc[k]) for k in cc if k > 0)
    pre = [k for k in ("vx10", "vx30", "vx60", "vx120", "vx300") if P[k][0] > 0.65 and P[k][1] < 0.01]
    L += ["", "PREDICTIONS",
          f"  V1 no pre-click VIX feature > 0.65 with p < 0.01 (found: {pre or 'none'}) -> {'RIGHT' if not pre else 'WRONG'}",
          f"  V2 after-click VIX leans his way, vxa60 > 0.6 ({P['vxa60'][0]:.3f}) -> {'RIGHT' if P['vxa60'][0] > 0.6 else 'WRONG'}",
          f"  V3 following VIX wins 45-55% ({rr.mean() * 100:.1f}%) -> {'RIGHT' if 0.45 <= rr.mean() <= 0.55 else 'WRONG'}",
          f"  V4 strongest at lag 0 and VIX-first |corr| < 0.05 (best k {best_k:+d}, VIX-first max {lead:.3f}) -> {'RIGHT' if best_k == 0 and lead < 0.05 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
