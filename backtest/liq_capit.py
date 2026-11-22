"""THE LIQUIDATION MAP ALIGNED WITH A BOOK THAT WORKS: CAPIT2 (2026-11-15)

THE USER (2026-11-15): "you are just too eager to drop it instead of doing anything with it ... create a map of all the things that
work, connect them, align them". The liquidation map failed as an entry (liq_map.py, liq_map_1m.py), as an execution trick
(liq_map_past.py) and as a filter on the liquidity sweep (liq_sweep.py) - but the sweep is a book that does NOT work. The map's one
real property is that it locates FORCED trading (liq_map.py --validate). capit2 is the repo's surviving forced-flow book: buy a coin
that fell 10% or more in 24 hours (4h bars, breadth gate) with a limit 2% under the signal close, out at +5% or after 24 bars if not
in profit (capit_combos.py, CAPIT_BETTER; positive in all four bar phases, deployed at 2x in the final machine). The question here:
does the map, read at the signal, separate capit2's good trades from its bad ones?

TRADES   capit_combos.gen(off, BASE + CAPIT_BETTER) for the four bar phases (0 / 60 / 120 / 180 minutes), pooled; the signal is read
         at the close of the 4h bar = the hour ending at t_in (the limit lives one bar, so t_in = the signal close). Kept: trades from
         2022-02 whose coin has open interest and a map that has run at least 14 days. Net per trade as capit_combos books it.
THE THREE FACTORS (read at the signal close, from the hour ending then and earlier)
  mapflush  the map's estimated long liquidations over the 24 hours before the signal (liq_sweep.liq_series summed over 24 hours,
            each hour as a share of the open-interest value an hour before it)                     favourable = HIGH (leverage flushed)
  oiflush   the fall in REAL open interest over the same 24 hours: -(OI now / OI 24 hours ago - 1)  favourable = HIGH
  left      the long-liquidation value the map still holds from the limit price down to 5% under it, as a share of the open-
            interest value now - forced selling still AHEAD of the limit                            favourable = LOW
STAGE 1  per factor: the cut = the 2/3 quantile on the TUNE half (pair_lab.HOLDOUT, 2024-04-07, capit_combos' split; for 'left' the
         1/3 quantile, flagged = at or under it); spread = flagged minus unflagged net per trade (OLS on the flag, clustered by entry
         day). CONFIRMED = tune spread > 0 with t > 2 AND holdout spread > 0 with Holm p < 0.05 over the 3. MDE80 printed.
DIAGNOSTICS rank correlation of mapflush and oiflush; the base (every kept trade) by half; each factor's terciles by half.

REGISTERED BEFORE THE FIRST NUMBER (2026-11-15; my prior that a factor is confirmed: about 8%)
  C1  No factor is confirmed.
  C2  Over 24 hours the map's flush and the real open-interest fall agree better than in one sweep hour: rank correlation > +0.20.
  C3  The base - capit2 on the trades kept here - nets > 0 a trade on both halves (it is the working book on this subset too).
  C4  'left' (leverage still under the limit) has its favourable sign on the tune half: trades with LITTLE left under the limit do
      better (the 1-minute study: price overshoots into clusters).

RESULT (2026-11-15, logs/liq_capit.txt): NO FACTOR CONFIRMED (0 of 3, Holm 0.77). 972 capit2 trades (4 phases), 743 kept from 2022-02
(265 tune / 478 holdout). The base is the working book: +1.95% a trade (t 2.3) / +4.22% (t 10.7), 92% won - and on the holdout every
tercile of every factor nets about +4%, so there is nothing for a filter to separate there. Tune half: the REAL open-interest flush
leans the right way (lowest third -0.25%, highest +3.28%; spread +2.00%, t 1.6) and is flat on the holdout (+0.26%, t 0.7); the map's
flush leans the WRONG way on the tune half (highest third -0.78%) and is flat on the holdout; 'left' +1.33% (t 0.7) / -0.22%. C2 WRONG
and informative: over 24 hours the map's 'liquidated' figure and the real open-interest fall are NEGATIVELY related (rank -0.28) - the
model shrinks every position when open interest falls, so a real flush leaves it less to 'liquidate'; the map measures leverage that
was built and then wicked, not leverage that left. C1, C3, C4 right. Tests 6.

    python -m backtest.liq_capit       (logs/liq_capit.txt)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import liq_map as lm  # noqa: E402
from backtest import sweep_confluence as sc  # noqa: E402

LOG = ROOT / "logs" / "liq_capit.txt"
H = lm.H
WARM = 14 * 24
START = pd.Timestamp("2022-02-01")
LIMIT = 0.02
BAND = 0.05
FACT = (("mapflush", 1), ("oiflush", 1), ("left", -1))                      # (name, favourable sign)


def features(t, h, l, c, oi, queries):  # noqa: E741
    """queries: hour indices k (the hour ending at the signal). For each: mapflush (the map's long liquidations in hours k-23..k, each
    over the OI value an hour before it), oiflush (-(oi[k] / oi[k-24] - 1), 24 consecutive hours), left (the long-liquidation value
    in [limit x (1 - BAND), limit] after hour k, limit = c[k] x (1 - LIMIT), over the OI value at k) and age (hours since the map
    started or reset). NaN where undefined."""
    n = len(c)
    want = {}
    for q, k in enumerate(queries):
        want.setdefault(int(k), []).append(q)
    out = np.full((len(queries), 4), np.nan)
    grid = lm.Grid(np.nanmin(l[l > 0]) * 0.5, np.nanmax(h) * 2.0)
    longm, shortm = np.zeros(grid.n), np.zeros(grid.n)
    liqL = np.full(n, np.nan)
    prev, last_t, start = np.nan, None, None
    for i in range(n):
        if np.isfinite(oi[i]):
            if last_t is None:
                start = i
            elif t[i] - last_t > 48 * H:
                longm[:] = 0.0
                shortm[:] = 0.0
                prev, start = np.nan, i
            last_t = t[i]
        cur = oi[i] if np.isfinite(oi[i]) else prev
        if i > 0 and np.isfinite(prev) and prev > 0 and c[i - 1] > 0:
            liqL[i] = longm[grid.idx(l[i]):].sum() / (prev * c[i - 1])
        lm.map_step(longm, shortm, grid, prev, cur, h[i], l[i], c[i])
        prev = cur
        if i in want:
            age = i - start if start is not None else np.nan
            mf = float(np.sum(liqL[i - 23:i + 1])) if i >= 23 and np.isfinite(liqL[i - 23:i + 1]).all() else np.nan
            of = (-(oi[i] / oi[i - 24] - 1) if i >= 24 and np.isfinite(oi[i]) and np.isfinite(oi[i - 24]) and oi[i - 24] > 0
                  and t[i] - t[i - 24] == 24 * H else np.nan)
            lim = c[i] * (1 - LIMIT)
            val = cur * c[i] if np.isfinite(cur) and cur > 0 else np.nan
            left = longm[grid.idx(lim * (1 - BAND)):grid.idx(lim) + 1].sum() / val if np.isfinite(val) else np.nan
            for q in want[i]:
                out[q] = (mf, of, left, age)
    return out


def flags(T: pd.DataFrame, tune: pd.Series):
    cuts, F = {}, pd.DataFrame(index=T.index)
    for f, sgn in FACT:
        x = T.loc[tune, f]
        cuts[f] = float(np.nanquantile(x, 2 / 3 if sgn > 0 else 1 / 3))
        F[f] = (T[f] >= cuts[f]) if sgn > 0 else (T[f] <= cuts[f])
    return cuts, F.astype(bool)


def spread(T: pd.DataFrame, fl: pd.Series, m: pd.Series) -> dict:
    y, f, d = T.net.to_numpy(float)[m], fl.to_numpy()[m], T.day.to_numpy()[m]
    if f.sum() < 3 or (~f).sum() < 3:
        return dict(b=np.nan, t=np.nan, n=int(f.sum()), net_f=np.nan, mde=np.nan)
    b, tt = sc.spread_t(y, f, d)
    return dict(b=b, t=tt, n=int(f.sum()), net_f=float(y[f].mean()), mde=2.8 * abs(b / tt) if tt else np.nan)


def trades():
    from backtest import capit_combos as cc
    from backtest import machine_combos as mc
    rows = []
    for off in cc.PHASES:
        T = cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER))
        rows.append(T.assign(phase=off))
    return pd.concat(rows, ignore_index=True)


def attach(T: pd.DataFrame) -> pd.DataFrame:
    T = T[pd.to_datetime(T.t_in) >= START].copy().reset_index(drop=True)
    vals = np.full((len(T), 4), np.nan)
    tin = pd.to_datetime(T.t_in).to_numpy("datetime64[ns]").astype(np.int64) // 10**6
    for coin, idx in T.groupby("coin").indices.items():
        x = lm.load_coin(coin)
        if x is None:
            continue
        t, o, h, l, c, oi = x  # noqa: E741
        k = np.searchsorted(t, tin[idx] - H)
        ok = (k < len(t)) & (t[np.minimum(k, len(t) - 1)] == tin[idx] - H)
        if not ok.any():
            continue
        vals[idx[ok]] = features(t, h, l, c, oi, k[ok])
    T["mapflush"], T["oiflush"], T["left"], T["age"] = vals.T
    T["day"] = pd.to_datetime(T.t_in).dt.floor("D")
    return T


def main():
    from backtest.pair_lab import HOLDOUT
    t0 = time.time()
    T0 = trades()
    A = attach(T0)
    K = A[(A.age >= WARM) & A[["mapflush", "oiflush", "left"]].notna().all(axis=1)].reset_index(drop=True)
    tune = pd.to_datetime(K.t_in) < HOLDOUT
    cuts, F = flags(K, tune)
    L = [f"backtest/liq_capit.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; capit2 (capit_combos CAPIT_BETTER, 4 phases pooled) x the "
         f"liquidation map and real open interest; halves split {HOLDOUT.date()}", "",
         f"TRADES: {len(T0)} in all; from {START.date()} {len(A)}; kept (open interest, map >= 14 days) {len(K)}: tune {int(tune.sum())}, "
         f"holdout {int((~tune).sum())}",
         f"BASE (every kept trade): tune {K.net[tune].mean() * 100:+.2f}% a trade (t {sc.t_by_day(K.net[tune], K.day[tune]):+.1f}), holdout "
         f"{K.net[~tune].mean() * 100:+.2f}% (t {sc.t_by_day(K.net[~tune], K.day[~tune]):+.1f}); won {np.mean(K.net > 0) * 100:.0f}%",
         f"rank correlation mapflush vs oiflush {K.mapflush.rank().corr(K.oiflush.rank()):+.3f}; mapflush vs left "
         f"{K.mapflush.rank().corr(K.left.rank()):+.3f}", "",
         "STAGE 1 (flagged = the favourable third by the tune cut); spread = flagged minus unflagged net a trade, clustered by day"]
    res, pv = {}, {}
    for f, sgn in FACT:
        r = {h: spread(K, F[f], m.to_numpy()) for h, m in (("tu", tune), ("ho", ~tune))}
        res[f] = r
        pv[f] = sc.p_one_sided(r["ho"]["t"])
    hp = sc.holm(pv)
    conf = []
    for f, sgn in FACT:
        r = res[f]
        ok = r["tu"]["b"] > 0 and r["tu"]["t"] > 2 and r["ho"]["b"] > 0 and hp[f] < 0.05
        if ok:
            conf.append(f)
        L.append(f"  {f:<9} cut {cuts[f]:.4g} ({'>=' if sgn > 0 else '<='})  tune {r['tu']['b'] * 100:+.2f}% (t {r['tu']['t']:+.1f}, flagged "
                 f"{r['tu']['n']}, net {r['tu']['net_f'] * 100:+.2f}%)  holdout {r['ho']['b'] * 100:+.2f}% (t {r['ho']['t']:+.1f}, flagged "
                 f"{r['ho']['n']}, net {r['ho']['net_f'] * 100:+.2f}%)  MDE80 {r['ho']['mde'] * 100:.2f}%  Holm {hp[f]:.2f}{'  CONFIRMED' if ok else ''}")
    L += ["", "TERCILES (net a trade, tune / holdout; terciles by the tune half's cuts)"]
    for f, _ in FACT:
        q1, q2 = np.nanquantile(K.loc[tune, f], [1 / 3, 2 / 3])
        b = np.digitize(K[f], [q1, q2])
        L.append(f"  {f:<9}" + "   ".join(
            f"{['low', 'mid', 'high'][j]} {K.net[(b == j) & tune].mean() * 100:+.2f} / {K.net[(b == j) & ~tune].mean() * 100:+.2f}%"
            f" (n {int(((b == j) & tune).sum())}/{int(((b == j) & ~tune).sum())})" for j in range(3)))
    rho = float(K.mapflush.rank().corr(K.oiflush.rank()))
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    L += ["", "REGISTERED PREDICTIONS",
          f"  C1 no factor confirmed -> {ok(not conf)} ({conf})",
          f"  C2 rank correlation of mapflush and oiflush > +0.20 -> {ok(rho > 0.20)} ({rho:+.3f})",
          f"  C3 the base nets > 0 on both halves -> {ok(K.net[tune].mean() > 0 and K.net[~tune].mean() > 0)}",
          f"  C4 little leverage left under the limit does better on the tune half -> {ok(res['left']['tu']['b'] > 0)} "
          f"({res['left']['tu']['b'] * 100:+.2f}%)",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    K.to_pickle(LOG.with_suffix(".pkl"))
    print(txt)


if __name__ == "__main__":
    main()
