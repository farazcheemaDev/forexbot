"""DEALER GAMMA AT HIS CLICKS - the last scalper tool on the list (2026-10-20, his_strategy.md s70)

The user: "do the other test too" (after his_tick.py). Dealer gamma exposure (GEX) is what options-aware NASDAQ scalpers
watch: when dealers are net LONG gamma their hedging sells rallies and buys dips (ranges, mean reversion); net SHORT
gamma it chases moves. The big-gamma strikes ("call wall", "put wall") act as magnets / walls, and the "gamma flip" is
the price where the regime changes. Only a strike-magnet check had been run on him (his_pasted_ideas2.py, 31-57%).

DATA (his_gex_fetch.py; Databento, ~$11.40 spent with the user's OK)
    QQQ option open interest published before each session (OPRA statistics, stat 9), his 31 NASDAQ trade days and 31
    random other trading days; QQQ 1-minute bars (XNAS); VXN (Yahoo, the NASDAQ-100 implied volatility index) - the
    previous close, used as ONE volatility for every option (the flat-IV shortcut most free GEX tools use)
GEX  per contract: Black-Scholes gamma x open interest x 100 x price^2 x 1% (dollars of delta per 1% move); calls +, puts -
     (the usual dealer convention: customers buy puts, sell calls); expiries within 45 days, strikes within 15%; time to
     expiry from the moment (0DTE gamma rises into the close), floor 15 minutes; r 4%
     regime = the sign of total GEX at the moment's price; flip = the nearest price within 5% where total GEX changes
     sign; walls = the strikes with the largest call and put GEX at the session's open; magnet = the strike with the
     largest |GEX| within 1.5% of the price
HIS MOMENTS: his_clock_exits.trades(), NASDAQ (UTC entries, side s); QQQ price = the last 1-minute close at his click
NULL: the same features every 5 minutes from 60 minutes before to 15 after, same session, same side (mid-ranks)

REGISTERED BEFORE THE RUN (2026-10-20)
    G1 the share of positive-gamma sessions (at the open) on his days is within 20 points of the control days'.
    G2 at his clicks, the distance to the nearest wall and to the flip rank 0.40-0.60 among the session's moments.
    G3 his side points TOWARD the magnet strike on 40-60% of his trades.

RESULT (2026-10-20, logs/his_gex.txt; 47 trades, 30 his days + 31 control; $7.03 of Databento) - style, not edge.
    G1 WRONG by a point: positive-gamma sessions 40% of his days vs 61% of control days (p ~0.13) - he leans to
       negative-gamma (trending) days, as s64 found for his days.
    G2 WRONG on the walls: his clicks sit FARTHER from the day's gamma walls than the session's other moments (mean rank
       0.611, se 0.042). Checked twice (look for the bug): random moments through the same -60..+15 window rank 0.486 on
       his days (0.541 on control days; 0.49-0.51 with a symmetric window) - not the window; the distance he had
       travelled in 30 minutes ranks 0.546 and does not correlate with it (-0.06), and the effect is strongest when he
       had NOT moved (0.672) - not "after a move". Flip distance ordinary (0.526).
    G3 RIGHT: his side points toward the magnet strike 51% of the time; AWAY from the nearer wall 49%.
    Reading: he trades in open space between the big gamma strikes, on trending days - a style that matches s55's "room
    ahead" lean - but gamma carries NO information about his direction, which is where his edge lives. One p ~0.003 in
    a programme of hundreds of tests is also what chance produces; it would need his next trades to confirm.

    python -m backtest.his_gex
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "strategy_analysis" / "data" / "his_gex"
LOG = ROOT / "logs" / "his_gex.txt"
R, MAX_DAYS, K_BAND, FLOOR_Y = 0.04, 45, 0.15, 15 / (60 * 24 * 365)
NY = "America/New_York"


def oi_table(day: str) -> pd.DataFrame | None:
    import databento as db
    p = DATA / f"stats_{day}.dbn.zst"
    if not p.exists():
        return None
    df = db.DBNStore.from_file(str(p)).to_df(map_symbols=True)
    if df.empty:
        return None
    df = df[df.stat_type == 9].groupby("symbol").quantity.last().reset_index()
    s = df.symbol.str.replace(" ", "", regex=False)                    # QQQ260724C00500000
    out = pd.DataFrame({"exp": pd.to_datetime(s.str[3:9], format="%y%m%d"), "cp": s.str[9],
                        "K": s.str[10:].astype(float) / 1000, "oi": df.quantity.astype(float)})
    out["exp_utc"] = (out.exp + pd.Timedelta(hours=16)).dt.tz_localize(NY).dt.tz_convert("UTC")
    return out[out.oi > 0]


def qqq_1m(day: str) -> pd.Series | None:
    import databento as db
    p = DATA / f"qqq1m_{day}.dbn.zst"
    if not p.exists():
        return None
    df = db.DBNStore.from_file(str(p)).to_df()
    return None if df.empty else df.close.astype(float)


def gex_at(O: pd.DataFrame, P: np.ndarray, t: pd.Timestamp, sig: float) -> np.ndarray:
    """Total dealer GEX ($ per 1%) at each price in P, at moment t."""
    T = np.maximum((O.exp_utc - t).dt.total_seconds().to_numpy() / (365 * 86400), FLOOR_Y)
    K, oi = O.K.to_numpy(), O.oi.to_numpy()
    sgn = np.where(O.cp.to_numpy() == "C", 1.0, -1.0)
    P = np.atleast_1d(P)[:, None]
    d1 = (np.log(P / K) + (R + sig ** 2 / 2) * T) / (sig * np.sqrt(T))
    g = norm.pdf(d1) / (P * sig * np.sqrt(T))
    return (sgn * g * oi * 100 * P ** 2 * 0.01).sum(axis=1)


def features(O, px, t, sig, walls):
    P = px
    near = O[(O.exp_utc > t) & ((O.exp_utc - t) <= pd.Timedelta(days=MAX_DAYS)) & ((O.K / P - 1).abs() <= K_BAND)]
    if near.empty:
        return None
    total = float(gex_at(near, P, t, sig)[0])
    grid = P * (1 + np.arange(-0.05, 0.0501, 0.001))
    prof = gex_at(near, grid, t, sig)
    ch = np.flatnonzero(np.sign(prof[:-1]) != np.sign(prof[1:]))
    flip = grid[ch[np.argmin(np.abs(grid[ch] - P))]] if len(ch) else np.nan
    loc = near[(near.K / P - 1).abs() <= 0.015]
    if loc.empty:
        magnet = np.nan
    else:
        T = np.maximum((loc.exp_utc - t).dt.total_seconds().to_numpy() / (365 * 86400), FLOOR_Y)
        d1 = (np.log(P / loc.K.to_numpy()) + (R + sig ** 2 / 2) * T) / (sig * np.sqrt(T))
        g = norm.pdf(d1) / (P * sig * np.sqrt(T)) * loc.oi.to_numpy()
        by_k = pd.Series(g, index=loc.K.to_numpy()).groupby(level=0).sum()
        magnet = float(by_k.idxmax())
    dw = min(abs(P - walls[0]), abs(P - walls[1])) / P
    return dict(total=total, pos=total > 0, dflip=abs(P - flip) / P if np.isfinite(flip) else np.nan, dwall=dw,
                magnet=magnet)


def walls_at_open(O, px_open, t_open, sig):
    near = O[(O.exp_utc > t_open) & ((O.exp_utc - t_open) <= pd.Timedelta(days=MAX_DAYS))
             & ((O.K / px_open - 1).abs() <= K_BAND)]
    T = np.maximum((near.exp_utc - t_open).dt.total_seconds().to_numpy() / (365 * 86400), FLOOR_Y)
    d1 = (np.log(px_open / near.K.to_numpy()) + (R + sig ** 2 / 2) * T) / (sig * np.sqrt(T))
    g = norm.pdf(d1) / (px_open * sig * np.sqrt(T)) * near.oi.to_numpy()
    s = pd.DataFrame({"K": near.K.to_numpy(), "cp": near.cp.to_numpy(), "g": g})
    cw = s[s.cp == "C"].groupby("K").g.sum().idxmax()
    pw = s[s.cp == "P"].groupby("K").g.sum().idxmax()
    return float(cw), float(pw)


def midrank(v, arr):
    arr = np.asarray([a for a in arr if np.isfinite(a)])
    if not np.isfinite(v) or len(arr) < 5:
        return np.nan
    return ((arr < v).sum() + 0.5 * (arr == v).sum()) / len(arr)


def main():
    from backtest.his_clock_exits import trades
    days = json.loads((ROOT / "logs" / "his_gex_days.json").read_text())
    vxn = pd.read_csv(DATA / "vxn.csv", header=[0, 1], index_col=0, parse_dates=True)
    vxn = vxn[("Close", "^VXN")].astype(float)
    T = trades()
    N = T[T.kind == "NASDAQ"].copy()
    N["entry"] = pd.to_datetime(N.entry).dt.tz_localize("UTC")
    lines = [f"backtest/his_gex.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; QQQ options open interest (Databento), "
             f"flat IV = VXN's previous close; his NASDAQ trades vs control days", ""]
    day_rows, his_rows = [], []
    for kind in ("his", "ctrl"):
        for d in days[kind]:
            O, px = oi_table(d), qqq_1m(d)
            sig_s = vxn[vxn.index < pd.Timestamp(d)]
            if O is None or px is None or sig_s.empty:
                day_rows.append(dict(day=d, kind=kind, ok=False))
                continue
            sig = float(sig_s.iloc[-1]) / 100
            t_open = pd.Timestamp(f"{d} 09:31").tz_localize(NY).tz_convert("UTC")
            pxo = px[px.index <= t_open]
            if pxo.empty:
                day_rows.append(dict(day=d, kind=kind, ok=False))
                continue
            walls = walls_at_open(O, float(pxo.iloc[-1]), t_open, sig)
            f0 = features(O, float(pxo.iloc[-1]), t_open, sig, walls)
            day_rows.append(dict(day=d, kind=kind, ok=True, pos=f0["pos"], total=f0["total"], cw=walls[0], pw=walls[1]))
            if kind != "his":
                continue
            for r in N[N.entry.dt.strftime("%Y-%m-%d") == d].itertuples():
                t = r.entry
                p_at = px[px.index <= t]
                if p_at.empty or (t - p_at.index[-1]) > pd.Timedelta(minutes=5):
                    his_rows.append(dict(t=t, s=r.s, ok=False))
                    continue
                f = features(O, float(p_at.iloc[-1]), t, sig, walls)
                nulls = []
                for m in range(-60, 16, 5):
                    if m == 0:
                        continue
                    tm = t + pd.Timedelta(minutes=m)
                    pm = px[px.index <= tm]
                    if pm.empty or (tm - pm.index[-1]) > pd.Timedelta(minutes=5):
                        continue
                    g = features(O, float(pm.iloc[-1]), tm, sig, walls)
                    if g:
                        nulls.append(g)
                toward = np.sign(f["magnet"] - float(p_at.iloc[-1])) == r.s if np.isfinite(f["magnet"]) else np.nan
                his_rows.append(dict(t=t, s=r.s, ok=True, pos=f["pos"], dwall=f["dwall"], dflip=f["dflip"],
                                     r_wall=midrank(f["dwall"], [g["dwall"] for g in nulls]),
                                     r_flip=midrank(f["dflip"], [g["dflip"] for g in nulls]),
                                     toward=toward, n=len(nulls), px=float(p_at.iloc[-1]), magnet=f["magnet"]))
    D = pd.DataFrame(day_rows)
    H = pd.DataFrame(his_rows)
    Dk = D[D.ok.astype(bool)]
    ph, pc = Dk[Dk.kind == "his"].pos.mean(), Dk[Dk.kind == "ctrl"].pos.mean()
    lines += ["1. THE SESSION'S REGIME AT THE OPEN (positive = dealers long gamma: dips bought, rallies sold)",
              f"   his days:     {int(Dk[Dk.kind == 'his'].pos.sum())} of {int((Dk.kind == 'his').sum())} positive ({ph:.0%})",
              f"   control days: {int(Dk[Dk.kind == 'ctrl'].pos.sum())} of {int((Dk.kind == 'ctrl').sum())} positive ({pc:.0%})",
              f"   days without data: {', '.join(D[~D.ok.astype(bool)].day) or 'none'}", ""]
    Hk = H[H.ok.astype(bool)] if "ok" in H else H
    tw = Hk.toward.dropna().astype(bool)
    bt = binomtest(int(tw.sum()), len(tw), 0.5) if len(tw) else None
    lines += ["2. AT HIS CLICKS (ranks among the same session's moments every 5 minutes, 0.5 = ordinary)",
              f"   trades with data {len(Hk)} of {len(H)}; in a positive-gamma moment {Hk.pos.mean():.0%}",
              f"   distance to the nearest wall: median {Hk.dwall.median() * 100:.2f}% of price, mean rank {Hk.r_wall.mean():.3f}",
              f"   distance to the gamma flip:   median {Hk.dflip.median() * 100:.2f}%, mean rank {Hk.r_flip.mean():.3f} "
              f"(flip found on {Hk.dflip.notna().mean():.0%})",
              f"   his side TOWARD the magnet strike: {int(tw.sum())} of {len(tw)} ({tw.mean():.0%}, p {bt.pvalue:.2f})" if bt else
              "   magnet: no data"]
    se = 0.289 / np.sqrt(max(Hk.r_wall.notna().sum(), 1))
    g1 = abs(ph - pc) <= 0.20
    g2 = 0.40 <= Hk.r_wall.mean() <= 0.60 and 0.40 <= Hk.r_flip.mean() <= 0.60
    g3 = 0.40 <= tw.mean() <= 0.60 if len(tw) else False
    lines += [f"   (a mean rank's standard error with {Hk.r_wall.notna().sum()} trades: ~{se:.3f})", "",
              "REGISTERED PREDICTIONS",
              f"  G1 positive-gamma share his days {ph:.0%} vs control {pc:.0%}, within 20 points -> {'RIGHT' if g1 else 'WRONG'}",
              f"  G2 wall / flip ranks within 0.40-0.60: {Hk.r_wall.mean():.3f} / {Hk.r_flip.mean():.3f} -> {'RIGHT' if g2 else 'WRONG'}",
              f"  G3 toward the magnet 40-60%: {tw.mean():.0%} -> {'RIGHT' if g3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    H.to_csv(ROOT / "logs" / "his_gex_trades.csv", index=False)
    print(txt)


if __name__ == "__main__":
    main()
