"""s106 - WHO MOVES FIRST AFTER HIS CLICK? Cross-asset lead-lag in the first 15 seconds AFTER his entries (2026-11-22)

THE USER (2026-11-22): s77 showed his move is concentrated in the first minute with ordinary NQ flow and no worked order; every cross-asset
test (s44, s68, s78, s79, s89) read the seconds BEFORE his click. If he trades on news or flow that hits another market first, that market
should start moving his way first in the seconds AFTER his click (the market's reaction to whatever he saw). This reads t = +1 .. +15 s.

DATA (all on disk, nothing bought; 1-second marks, the last value at or before each second)
  NQ        CME NQ mid (nq_bbo1s.pkl), the 31 windows of his 46 statement clicks; the 7 new clicks from nq_new_mbp10.parquet's best bid / ask
  ES RTY    CME S&P 500 and Russell 2000 futures mids; ZN ZB bonds (10-year, 30-year); 6E 6J (euro and yen futures - the dollar's two
            biggest legs; no dollar index is on disk); GC CL (gold, crude) - cross_bbo1s.pkl, the same 31 windows
  QQQ MEGA8 Nasdaq's ON-exchange prints (nasdaq_basic_trades.pkl, publishers 82 / 83 = the FINN / FINC trade-reporting facilities left out:
            they report late); QQQ, and MEGA8 = the equal-weight log index of NVDA MSFT AAPL AMZN GOOGL META AVGO TSLA
  EXNESS    the Exness USTECm mid from the tick caches (09:30-19:30 New York; his broker's price is Exness + a constant, s54)
  VIX       the front VIX future mid (vx_bbo1s_windows.parquet), all 53 clicks
SIGN AND SCALE  each market is signed by the sign of its 5-second return correlation with NQ over every window second (so 'his way' means
  the way that market moves when NASDAQ moves his way) and scaled by its own sigma of 15-second moves in that window.
MEASURES at his click second t (side s): m(h) = sign x s x (price(t + h) - price(t)) / sigma15, h = 1 2 3 5 10 15 s;
  first passage = the first h in 1..15 with m(h) >= 0.5 (and >= 1.0); head-to-head vs NQ = who crosses first (strictly earlier, the same
  second, or later) among the clicks where either crosses; cross-correlation of 1-second returns over (t, t + 15], X(tau) with NQ(tau + k),
  k > 0 = X LEADS NQ by k seconds.
CONTROL  the same second of the minute, 1-15 minutes before / after inside the window, his side, none within 60 s of any click.

REGISTERED BEFORE THE FIRST RUN (2026-11-22)
  L1  Sanity: NQ moves his way after his click more than at the controls (mean m(15) higher, p < 0.05).                       (80%)
  L2  ES and RTY move with NQ: in the head-to-head ES crosses 0.5 sigma STRICTLY before NQ in 20-45% of the decided clicks, within
      10 points of the controls.                                                                                                  (70%)
  L3  Bonds, the euro / yen, gold and oil: after his click their signed moves are not his way (|t| < 2 at every h) and they cross
      0.5 sigma before NQ no more often than at the controls (within 10 points).                                                  (75%)
  L4  QQQ and MEGA8 (lit prints) do not lead NQ: strictly-first share within 10 points of the controls and the cross-correlation
      peak at k <= 0.                                                                                                              (70%)
  L5  Exness and VIX follow NQ: cross-correlation peak at k <= 0, at his clicks as at the controls.                              (75%)
  If L2-L5 hold: no outside market leads NQ after his click - the move starts in NASDAQ itself (with ES), and whatever he sees is not
  another market's reaction arriving first.

RESULT (2026-11-22, logs/his_post_click_lead.txt) - NO OUTSIDE MARKET LEADS NQ AFTER HIS CLICK: the US equity complex moves his way in
  the same second, everything else does not move. L1, L2, L4, L5 right; L3 WRONG by its symmetric rule, in the direction opposite to a lead.
  53 clicks (the cross-markets for the 46 statement clicks), 1,513 same-second controls. At +15 s, in own 15-s sigmas his way: NQ +0.49 (controls
  +0.04, p 0.0002), ES +0.54, RTY +0.33, QQQ +0.48, MEGA8 +0.33, Exness +0.48. One-second return cross-correlation peaks at lag 0 for every
  equity market (ES 0.92, Exness 0.92, QQQ 0.85, MEGA8 0.80, RTY 0.74); QQQ / MEGA8 / Exness also trail NQ by a second at the controls.
  Bonds (ZN, ZB), the euro and yen futures, gold and oil do not move his way at any horizon (|t| <= 1.9) and lead nothing; at his clicks they
  cross 0.5 sigma before NQ LESS often than at the controls (ZN -12, GC -14, CL -17 points - NQ moves sooner when he clicks), which is what
  failed L3. VIX moves against NQ in the same second (-0.30).
  POST HOC: ES crossed 0.5 sigma first 13 times to NQ's 4 at his clicks - one threshold only (0.3 / 0.75 / 1.0 sigma: 9/8, 6/9, 6/5; ES minus NQ
  at +15 s +0.03 sigma, se 0.06).
  A BUG OF MINE, caught before reading: series built from prints and ticks were first floored to the second (each labelled with the NEXT
  second's state) while Databento's bbo-1s files are as of the label - a fake 1-s lead for QQQ / MEGA8 / Exness at every moment, his and the
  controls'. Fixed with exact-time as-of marks (the last value at or before each second).

    python -m backtest.his_post_click_lead
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
LOG = ROOT / "logs" / "his_post_click_lead.txt"
FUT = {"ES": "ES.v.0", "RTY": "RTY.v.0", "ZN": "ZN.v.0", "ZB": "ZB.v.0", "6E": "6E.v.0", "6J": "6J.v.0", "GC": "GC.v.0", "CL": "CL.v.0"}
MEGA = ("NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "AVGO", "TSLA")
DARK = {82, 83}
H = (1, 2, 3, 5, 10, 15)
ORDER = ["NQ", "ES", "RTY", "QQQ", "MEGA8", "EXNESS", "ZN", "ZB", "6E", "6J", "GC", "CL", "VIX"]
LAGS = range(-3, 4)


def on_grid(s: pd.Series, grid: pd.DatetimeIndex) -> np.ndarray:
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.reindex(s.index.union(grid)).ffill().reindex(grid).to_numpy(float)


def exness_series(day_ny: pd.Timestamp, ticks: dict) -> pd.Series | None:
    v = ticks.get(day_ny)
    if v is None:
        return None
    ts, mid, _ = v
    base = (day_ny + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
    idx = base + pd.to_timedelta(np.round(ts * 1000).astype(np.int64), unit="ms")   # exact tick times: as of each second, like bbo-1s
    return pd.Series(mid, index=idx)


def vix_series(vx: pd.DataFrame, a, b) -> pd.Series:
    g = vx[(vx.t >= a - pd.Timedelta(minutes=1)) & (vx.t <= b)]
    return pd.Series((g.bid.to_numpy() + g.ask.to_numpy()) / 2, index=g.t)


def old_windows():
    import backtest.his_tape as TP
    x = TP.entries()
    nq = pickle.loads((DATA / "nq_bbo1s.pkl").read_bytes())
    cr = pickle.loads((DATA / "cross_bbo1s.pkl").read_bytes())
    tr = pickle.loads((DATA / "nasdaq_basic_trades.pkl").read_bytes())
    ticks = pickle.loads((DATA / "ustec_tick_days.pkl").read_bytes())
    vx = pd.read_parquet(DATA / "vx_bbo1s_windows.parquet")
    out = []
    for key, s in nq.items():
        a, b = pd.Timestamp(key[0]), pd.Timestamp(key[1])
        grid = pd.date_range(a, b, freq="1s")
        X = {"NQ": on_grid(s, grid)}
        for k, sym in FUT.items():
            v = cr.get((sym, key[0]))
            if v is not None:
                X[k] = on_grid(v, grid)
        T = tr.get(key)
        if T is not None:
            lit = T[~T.pub.isin(DARK)]
            sec = pd.to_datetime(lit.ns.to_numpy())          # exact print times; on_grid marks the last print at or before each second
            px = {}
            for sym in ("QQQ",) + MEGA:
                m = (lit.sym == sym).to_numpy()
                if m.any():
                    px[sym] = on_grid(pd.Series(lit.px.to_numpy()[m], index=sec[m]), grid)
            if "QQQ" in px:
                X["QQQ"] = px["QQQ"]
            if all(k in px for k in MEGA):
                lg = np.stack([np.log(px[k]) for k in MEGA])
                first = np.array([np.nanmin(np.where(np.isfinite(r))[0]) if np.isfinite(r).any() else len(r) for r in lg])
                st = int(first.max())
                if st < len(grid):
                    idx = np.full(len(grid), np.nan)
                    idx[st:] = (lg[:, st:] - lg[:, [st]]).mean(0)
                    X["MEGA8"] = np.exp(idx)
        cl = x[(x.utc >= a) & (x.utc <= b)]
        if not len(cl):
            continue
        dny = cl.d.iloc[0]
        e = exness_series(dny, ticks)
        if e is not None:
            X["EXNESS"] = on_grid(e, grid)
        X["VIX"] = on_grid(vix_series(vx, a, b), grid)
        out.append(dict(a=a, grid=grid, X=X, clicks=[(r.utc, int(r.s)) for r in cl.itertuples()], tag="old"))
    return out


def new_windows():
    from backtest.his_cme_new import clicks, windows
    c = clicks()
    df = pd.read_parquet(DATA / "nq_new_mbp10.parquet", columns=["ns", "bid_px_00", "ask_px_00"])
    mid = pd.Series((df.bid_px_00.to_numpy() + df.ask_px_00.to_numpy()) / 2, index=pd.to_datetime(df.ns.to_numpy()))
    mid = mid[np.isfinite(mid.to_numpy())].sort_index()
    fresh = pickle.loads((DATA / "fresh" / "ustec_tick_days_fresh.pkl").read_bytes())
    vx = pd.read_parquet(DATA / "vx_bbo1s_windows.parquet")
    out = []
    for a, b in windows(c):
        grid = pd.date_range(a.floor("s"), b.floor("s"), freq="1s")
        X = {"NQ": on_grid(mid[a - pd.Timedelta(minutes=1):b], grid)}       # exact event times, as of each second
        cl = c[(c.t >= a) & (c.t <= b)]
        dny = cl.t.iloc[0].tz_localize("UTC").tz_convert("America/New_York").normalize().tz_localize(None)
        e = exness_series(dny, fresh)
        if e is not None:
            ee = on_grid(e, grid)
            if np.isfinite(ee).sum() > len(grid) // 2:
                X["EXNESS"] = ee
        X["VIX"] = on_grid(vix_series(vx, a, b), grid)
        out.append(dict(a=grid[0], grid=grid, X=X, clicks=[(r.t, int(r.s)) for r in cl.itertuples()], tag="new"))
    return out


def signs(W):
    """Sign of each market's 5-second return correlation with NQ, over every window second (label-free)."""
    out, corr = {}, {}
    for k in ORDER[1:]:
        xs, ys = [], []
        for w in W:
            if k not in w["X"]:
                continue
            a, b = w["X"][k], w["X"]["NQ"]
            ra, rb = a[5:] - a[:-5], b[5:] - b[:-5]
            ok = np.isfinite(ra) & np.isfinite(rb)
            xs.append(ra[ok][::5])
            ys.append(rb[ok][::5])
        if xs:
            xa, ya = np.concatenate(xs), np.concatenate(ys)
            corr[k] = float(np.corrcoef(xa, ya)[0, 1])
            out[k] = 1.0 if corr[k] >= 0 else -1.0
    out["NQ"], corr["NQ"] = 1.0, 1.0
    return out, corr


def sigma15(v: np.ndarray) -> float:
    d = v[15:] - v[:-15]
    d = d[np.isfinite(d)]
    return float(d.std(ddof=1)) if len(d) > 100 else np.nan


def moments(w):
    """(offset, side, is_his) for his clicks and the same-second controls of a window."""
    a, n = w["a"], len(w["grid"])
    offs = [int((t - a).total_seconds()) for t, _ in w["clicks"]]
    rows = []
    for (t, s), i0 in zip(w["clicks"], offs):
        if 20 <= i0 < n - 20:
            rows.append((i0, s, True))
        for k in list(range(-15, 0)) + list(range(1, 16)):
            j = i0 + 60 * k
            if 20 <= j < n - 20 and min(abs(j - o) for o in offs) >= 60:
                rows.append((j, s, False))
    return rows


def measure(W, sg):
    rec = []
    for wi, w in enumerate(W):
        sig = {k: sigma15(v) for k, v in w["X"].items()}
        for i0, s, his in moments(w):
            r = dict(w=wi, tag=w["tag"], i0=i0, s=s, his=his)
            for k, v in w["X"].items():
                if not np.isfinite(sig.get(k, np.nan)) or sig[k] <= 0 or not np.isfinite(v[i0]):
                    continue
                path = sg[k] * s * (v[i0 + 1:i0 + 16] - v[i0]) / sig[k]
                if not np.isfinite(path).all():
                    continue
                for h in H:
                    r[f"{k}_m{h}"] = path[h - 1]
                for th in (0.3, 0.5, 0.75, 1.0):
                    hit = np.flatnonzero(path >= th)
                    r[f"{k}_fp{th}"] = float(hit[0] + 1) if len(hit) else np.inf
            rec.append(r)
    return pd.DataFrame(rec)


def xcorr(W, kname, his: bool):
    """Pooled correlation of X's 1-second returns at tau with NQ's at tau + k, tau in (t, t + 15], at his clicks or the controls."""
    res = {}
    for k in LAGS:
        xa, ya = [], []
        for w in W:
            if kname not in w["X"]:
                continue
            X, N = w["X"][kname], w["X"]["NQ"]
            rx, rn = np.diff(X), np.diff(N)               # r[i] = move from second i to i + 1
            for i0, s, h in moments(w):
                if h != his:
                    continue
                tau = np.arange(i0, i0 + 15)
                j = tau + k
                ok = (j >= 0) & (j < len(rn))
                xa.append(rx[tau[ok]])
                ya.append(rn[j[ok]])
        if xa:
            a, b = np.concatenate(xa), np.concatenate(ya)
            ok = np.isfinite(a) & np.isfinite(b)
            res[k] = float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 30 and a[ok].std() > 0 and b[ok].std() > 0 else np.nan
    return res


def h2h(D, k, th=0.5):
    """Head-to-head vs NQ: (X strictly first, same second, NQ strictly first) shares among moments where either crosses; n."""
    a, b = D.get(f"{k}_fp{th}"), D.get(f"NQ_fp{th}")
    if a is None or b is None:
        return (np.nan,) * 3 + (0,)
    ok = a.notna() & b.notna() & (np.isfinite(a) | np.isfinite(b))
    a, b = a[ok], b[ok]
    if not len(a):
        return (np.nan,) * 3 + (0,)
    return float((a < b).mean()), float((a == b).mean()), float((a > b).mean()), int(len(a))


def main():
    W = old_windows() + new_windows()
    sg, corr = signs(W)
    D = measure(W, sg)
    Hh, C = D[D.his], D[~D.his]
    L = [f"backtest/his_post_click_lead.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC (s106); {len(W)} windows; his clicks measured "
         f"{len(Hh)} (statement {int((Hh.tag == 'old').sum())}, new {int((Hh.tag == 'new').sum())}); same-second controls {len(C)}",
         "markets present (his clicks with a full 15 s after): " + ", ".join(f"{k} {int(Hh[f'{k}_m15'].notna().sum())}" for k in ORDER if f"{k}_m15" in Hh),
         "sign vs NQ (5-s return correlation, all window seconds): " + ", ".join(f"{k} {corr[k]:+.2f}" for k in ORDER if k in corr), ""]
    L.append("1. SIGNED MOVE HIS WAY AFTER HIS CLICK, in sigma of 15-s moves (mean at his clicks | mean at controls; t of his vs 0; "
             "Mann-Whitney p his vs controls at +15 s)")
    L.append(f"  {'market':<8}" + "".join(f"{'+' + str(h) + 's':>14}" for h in H) + f"{'t(+15)':>9}{'p vs ctl':>10}")
    stat = {}
    for k in ORDER:
        if f"{k}_m15" not in D:
            continue
        cells = ""
        for h in H:
            a, b = Hh[f"{k}_m{h}"].dropna(), C[f"{k}_m{h}"].dropna()
            cells += f"{a.mean():>+7.2f}|{b.mean():>+6.2f}"
        a, b = Hh[f"{k}_m15"].dropna(), C[f"{k}_m15"].dropna()
        t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a))) if len(a) > 2 else np.nan
        p = stats.mannwhitneyu(a, b).pvalue if len(a) > 2 and len(b) > 2 else np.nan
        tmax = max(abs(Hh[f"{k}_m{h}"].dropna().mean() / (Hh[f"{k}_m{h}"].dropna().std(ddof=1) / np.sqrt(Hh[f"{k}_m{h}"].notna().sum())))
                   for h in H) if len(a) > 2 else np.nan
        stat[k] = dict(t15=t, p=p, tmax=tmax, mean15=a.mean(), ctl15=b.mean())
        L.append(f"  {k:<8}{cells}{t:>9.2f}{p:>10.3f}")
    L += ["", "2. FIRST PASSAGE his way within 15 s (share of moments that cross | median seconds among those that do), his clicks vs controls"]
    L.append(f"  {'market':<8}{'0.5 sigma his':>16}{'controls':>14}{'1 sigma his':>15}{'controls':>14}")
    for k in ORDER:
        if f"{k}_fp0.5" not in D:
            continue
        cells = ""
        for th in (0.5, 1.0):
            for G in (Hh, C):
                v = G[f"{k}_fp{th}"].dropna()
                fin = v[np.isfinite(v)]
                cells += f"{len(fin) / max(len(v), 1):>7.0%} | {np.median(fin) if len(fin) else np.nan:>4.0f}s"
        L.append(f"  {k:<8}{cells}")
    L += ["", "3. HEAD TO HEAD WITH NQ at 0.5 sigma (among moments where either crosses within 15 s): X strictly first / same second / NQ "
          "strictly first"]
    L.append(f"  {'market':<8}{'his clicks':>26}{'n':>5}{'controls':>28}{'n':>6}{'X-first his - ctl':>19}")
    H2 = {}
    for k in ORDER[1:]:
        h1, h2_ = h2h(Hh, k), h2h(C, k)
        if not h1[3]:
            continue
        H2[k] = (h1, h2_)
        L.append(f"  {k:<8}{h1[0]:>10.0%}{h1[1]:>8.0%}{h1[2]:>8.0%}{h1[3]:>5}{h2_[0]:>12.0%}{h2_[1]:>8.0%}{h2_[2]:>8.0%}{h2_[3]:>6}"
                 f"{(h1[0] - h2_[0]) * 100:>+17.0f} pt")
    L += ["", "4. WHO CROSSES 0.5 sigma FIRST, all markets of the 31 statement windows together (ties split; his clicks vs controls)"]
    full = [k for k in ORDER if k not in ("VIX", "EXNESS")]
    for lab, G in (("his clicks", Hh[Hh.tag == "old"]), ("controls", C[C.tag == "old"])):
        cols = [f"{k}_fp0.5" for k in full if f"{k}_fp0.5" in G]
        M = G[cols].dropna()
        M = M[np.isfinite(M).any(axis=1)]
        share = {}
        for _, row in M.iterrows():
            v = row.to_numpy(float)
            first = np.flatnonzero(v == v.min())
            for f in first:
                share[cols[f][:-6]] = share.get(cols[f][:-6], 0) + 1 / len(first)
        tot = sum(share.values())
        L.append(f"  {lab:<11} n {len(M):>4}: " + "  ".join(f"{k} {share.get(k, 0) / tot:.0%}" for k in full if k in share))
    L += ["", "5. CROSS-CORRELATION of 1-second returns over (t, t + 15]: corr(X at tau, NQ at tau + k); k > 0 = X LEADS NQ"]
    L.append(f"  {'market':<8}{'':>4}" + "".join(f"{('k=' + str(k)):>8}" for k in LAGS) + f"{'peak k':>8}")
    PEAK = {}
    for k in ORDER[1:]:
        for lab, his in (("his", True), ("ctl", False)):
            r = xcorr(W, k, his)
            if not r or all(not np.isfinite(v) for v in r.values()):
                continue
            fin = [(v, kk) for kk, v in r.items() if np.isfinite(v)]
            pk = (min(fin) if sg.get(k, 1) < 0 else max(fin))[1]
            PEAK[(k, lab)] = pk
            L.append(f"  {k:<8}{lab:>4}" + "".join(f"{r.get(kk, np.nan):>+8.3f}" for kk in LAGS) + f"{pk:>8d}")
    L += ["", "  (for a market that moves AGAINST NQ - sign < 0 - the peak is the most negative correlation)"]
    # POST HOC (added after reading section 3, where ES was strictly first 13 times and NQ 4): is ES ahead of NQ after his clicks at every
    # threshold, and does ES simply move more (in its own sigma) than NQ at his clicks?
    L += ["", "6. POST HOC - ES vs NQ in detail (added after section 3: at his clicks ES crossed first 13 times, NQ 4). Strict firsts among the "
          "decided races; p = binomial, ES-first share at his clicks against the controls' share"]
    for th in (0.3, 0.5, 0.75, 1.0):
        es_h = Hh.dropna(subset=[f"ES_fp{th}", f"NQ_fp{th}"])
        es_c = C.dropna(subset=[f"ES_fp{th}", f"NQ_fp{th}"])
        eh, qh = es_h[f"ES_fp{th}"].to_numpy(), es_h[f"NQ_fp{th}"].to_numpy()
        ec, qc = es_c[f"ES_fp{th}"].to_numpy(), es_c[f"NQ_fp{th}"].to_numpy()
        nh_e, nh_q = int((eh < qh).sum()), int((qh < eh).sum())
        nc_e, nc_q = int((ec < qc).sum()), int((qc < ec).sum())
        pc = nc_e / max(nc_e + nc_q, 1)
        pv = stats.binomtest(nh_e, nh_e + nh_q, pc).pvalue if nh_e + nh_q else np.nan
        L.append(f"  {th:.2f} sigma: his ES first {nh_e:>2} / NQ first {nh_q:>2} (ties {int(((eh == qh) & np.isfinite(eh)).sum())}) | controls "
                 f"{nc_e} / {nc_q} (ES share {pc:.0%}) -> p {pv:.3f}")
    rat_h = (Hh.ES_m15 - Hh.NQ_m15).dropna()
    rat_c = (C.ES_m15 - C.NQ_m15).dropna()
    L.append(f"  ES minus NQ signed move at +15 s (own sigmas): his {rat_h.mean():+.3f} (se {rat_h.std(ddof=1) / np.sqrt(len(rat_h)):.3f}, n {len(rat_h)}), "
             f"controls {rat_c.mean():+.3f}; Mann-Whitney p {stats.mannwhitneyu(rat_h, rat_c).pvalue:.3f}")
    # predictions
    l1 = stat["NQ"]["mean15"] > stat["NQ"]["ctl15"] and stat["NQ"]["p"] < 0.05
    es = H2.get("ES")
    l2 = es is not None and 0.20 <= es[0][0] <= 0.45 and abs(es[0][0] - es[1][0]) <= 0.10
    outside = ["ZN", "ZB", "6E", "6J", "GC", "CL"]
    l3a = all(stat[k]["tmax"] < 2 for k in outside if k in stat)
    l3b = all(abs(H2[k][0][0] - H2[k][1][0]) <= 0.10 for k in outside if k in H2)
    l4 = all(abs(H2[k][0][0] - H2[k][1][0]) <= 0.10 and PEAK.get((k, "his"), 0) <= 0 for k in ("QQQ", "MEGA8") if k in H2)
    l5 = all(PEAK.get((k, lab), 0) <= 0 for k in ("EXNESS", "VIX") for lab in ("his", "ctl") if (k, lab) in PEAK)
    s3a = ", ".join(k + " " + format(stat[k]["tmax"], ".1f") for k in outside if k in stat)
    s3b = ", ".join(k + " " + format((H2[k][0][0] - H2[k][1][0]) * 100, "+.0f") for k in outside if k in H2)
    s4a = ", ".join(k + " " + format((H2[k][0][0] - H2[k][1][0]) * 100, "+.0f") for k in ("QQQ", "MEGA8") if k in H2)
    s4b = ", ".join(k + " " + str(PEAK.get((k, "his"))) for k in ("QQQ", "MEGA8"))
    s5 = ", ".join(k + " " + str(PEAK.get((k, "his"))) + " / " + str(PEAK.get((k, "ctl"))) for k in ("EXNESS", "VIX"))
    nq = stat["NQ"]
    L += ["", "PREDICTIONS",
          f"  L1 NQ moves his way more than at controls (m15 {nq['mean15']:+.2f} vs {nq['ctl15']:+.2f}, p {nq['p']:.4f}) -> "
          f"{'RIGHT' if l1 else 'WRONG'}",
          f"  L2 ES strictly first 20-45% and within 10 pt of controls ({es[0][0]:.0%} vs {es[1][0]:.0%}) -> {'RIGHT' if l2 else 'WRONG'}",
          f"  L3 bonds / euro / yen / gold / oil: |t| < 2 at every h ({s3a}) and first-share within 10 pt of controls ({s3b}) -> "
          f"{'RIGHT' if l3a and l3b else 'WRONG'}",
          f"  L4 QQQ / MEGA8 do not lead (first-share diff {s4a}; peak k {s4b}) -> {'RIGHT' if l4 else 'WRONG'}",
          f"  L5 EXNESS and VIX follow NQ (peak k his / ctl: {s5}) -> {'RIGHT' if l5 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    D.to_csv(ROOT / "logs" / "his_post_click_lead_rows.csv", index=False)
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
