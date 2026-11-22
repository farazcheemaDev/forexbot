"""THE LIQUIDATION MAP INSIDE THE LIQUIDITY SWEEP: DOES A SWEEP THAT CLEARED LEVERAGE HOLD BETTER? (2026-11-15)

THE USER (2026-11-15), after the map failed as an entry (liq_map.py, liq_map_1m.py) and as an execution trick (liq_map_past.py): "find
me a new strategy from it then or integrate it in liquidity sweep". The sweep study (sweep_confluence.py, 2026-10-30) tested seven
factors and listed open interest / liquidation volume AT THE SWEEP as the one it could not test (no hourly open interest then). The
liquidation-map work has since put hourly open interest for the point-in-time top-40 on disk (liq_map_fetch.py, 2022-01..2026-09).
The SMC story this tests: a sweep that ran the stops and liquidations under the level has removed the sellers, so its reclaim holds.

EVENTS   sweep_confluence.py's own events (logs/sweep_confluence_events.pkl, its definition, trades, random controls and halves - split
         2024-04-07): a 1h bar that trades under the 24-bar low and closes back above it, up (shorts mirror); in at the next open, stop at
         the sweep's extreme, T24 = out 24 bars later (primary), TP2 = with a +2% target (printed beside); 12bp + funding. Kept: events
         from 2022-02 whose coin has open interest at the sweep bar and the bar before (consecutive hours) and whose map has run for at
         least 14 days since it started or was last reset (a gap of over 48 hours in open interest resets it, as in liq_map.py).
THE TWO FACTORS (fixed here; each read at the sweep bar's close, before the entry)
  liq    the liquidation map's estimate of what the sweep bar LIQUIDATED: the long-liquidation value at or above the bar's low (shorts:
         short-liquidation value at or below its high) in the map as it stood after the bar before (liq_map.map_step's own model), as a
         share of the open-interest value an hour earlier.                                                   favourable = HIGH
  flush  the fall in REAL open interest during the sweep bar: -(OI at the bar's close / OI an hour earlier - 1).  favourable = HIGH
STAGE 1  as sweep_confluence.py: per side and factor, the cut = the 2/3 quantile on the TUNE half's events; flagged = at or above it;
         spread = flagged minus unflagged T24 net per trade (OLS on the flag, clustered by day). CONFIRMED = tune spread > 0 with t > 2
         AND holdout spread > 0 with Holm p < 0.05 over the 4 cells.
PASS (the strategy question) per side for three subsets - liq flagged, flush flagged, both flagged (6 subsets): T24 net > 0 with t >= 2
         on BOTH halves, >= 100 holdout trades, AND its spread over the same side's unflagged sweeps (for 'both': flagged by neither)
         > 0 with t >= 2 on both halves;
         Holm < 0.05 over the 6 (p from the weaker half's net t).
DIAGNOSTICS coverage (events kept vs dropped); the rank correlation of liq and flush; each subset's excess over sweep_confluence's random
         control; TP2 beside T24; that the matched sweep bars are the cached ones (the stop distance recomputed from the bars).

REGISTERED BEFORE THE FIRST NUMBER (2026-11-15; my prior that any subset passes: about 5%)
  S1  No subset passes.
  S2  The model and the real data agree: the rank correlation of liq and flush is positive for both sides (the map is not blind; liq_map's
      volume check).
  S3  0 of the 4 stage-1 cells is confirmed.
  S4  Every subset's T24 holdout net is under +0.10% a trade.
  S5  Long sweeps flagged by flush do no better than the other long sweeps on the holdout (spread <= 0), as oi_flush_pit.py found for
      daily flushes on the same universe.

RESULT (2026-11-15, logs/liq_sweep.txt): NO PASS, 0 of 6 subsets; stage 1 0 of 4. 43,846 sweeps from 2022-02 on 339 coins, 43,500
kept (20,972 long / 22,528 short); the stop distance recomputed from every matched bar equals the cached one. Both factors make LONG
sweeps WORSE, not better: spread liq -17 / -7bp, flush -8 / -4bp, both -25 / -13bp (tune / holdout, |t| <= 1.2); the flagged long
subsets net -12..-31bp a trade. Short liq is worse on the tune half (t -2.8). The one positive cell: SHORT flush (open interest fell
during the up-wick - shorts forced out) spread +11 / +15bp (t 1.2 / 1.5, Holm 0.26), net +3 / +6bp a trade (t 0.3 / 0.5): under
every bar. S2 WRONG: the map's estimate and the real open-interest fall are nearly unrelated (rank +0.07 long, -0.04 short); POST HOC
the map's figure is mostly how deep the wick went in ATR (rank +0.60 / +0.58), which sweep_confluence.py already tested (F1, not
confirmed). S1, S3, S4, S5 right. Tests 10; planted bugs 20 of 20, control survived.

    python -m backtest.liq_sweep      (needs logs/sweep_confluence_events.pkl and liq_map_fetch.py's open interest; logs/liq_sweep.txt)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402
from backtest import liq_map as lm  # noqa: E402
from backtest import sweep_confluence as sc  # noqa: E402

LOG = ROOT / "logs" / "liq_sweep.txt"
H = lm.H
WARM = 14 * 24
START = pd.Timestamp("2022-02-01")
FACT = ("liq", "flush")
SUBSETS = [(s, f) for s in (1, -1) for f in ("liq", "flush", "both")]
MIN_HOLD = 100


def liq_series(t, h, l, c, oi):  # noqa: E741
    """Per hour i of one coin: liqL[i] / liqS[i] = the map's long / short liquidation value inside bar i's range (the map after bar
    i-1, before bar i is applied) over the open-interest value at i-1; doi[i] = oi[i] / oi[i-1] - 1 for consecutive hours with both
    readings; age[i] = hours since the map started (the first reading) or was last reset (a gap of over 48 hours). NaN where undefined."""
    n = len(c)
    grid = lm.Grid(np.nanmin(l[l > 0]) * 0.5, np.nanmax(h) * 2.0)
    longm, shortm = np.zeros(grid.n), np.zeros(grid.n)
    liqL, liqS, doi, age = (np.full(n, np.nan) for _ in range(4))
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
            val = prev * c[i - 1]
            liqL[i] = longm[grid.idx(l[i]):].sum() / val
            liqS[i] = shortm[:grid.idx(h[i]) + 1].sum() / val
            if np.isfinite(oi[i]) and np.isfinite(oi[i - 1]) and oi[i - 1] > 0 and t[i] - t[i - 1] == H:
                doi[i] = oi[i] / oi[i - 1] - 1
        if start is not None:
            age[i] = i - start
        lm.map_step(longm, shortm, grid, prev, cur, h[i], l[i], c[i])
        prev = cur
    return liqL, liqS, doi, age


def attach(T: pd.DataFrame, series: dict) -> pd.DataFrame:
    """T = sweep events (coin, t_in, side, dist, ...); series[coin] = (t ms, h, l, c, liqL, liqS, doi, age). Adds bar (the sweep bar's
    index, -1 if not found), liq, flush, age and dist_chk (the stop distance recomputed from the bars)."""
    T = T.copy()
    bar = np.full(len(T), -1)
    liq, flush, age, chk = (np.full(len(T), np.nan) for _ in range(4))
    tin = T.t_in.to_numpy("datetime64[ns]").astype(np.int64) // 10**6
    for coin, idx in T.groupby("coin").indices.items():
        if coin not in series:
            continue
        t, h, l, c, liqL, liqS, doi, ag = series[coin]  # noqa: E741
        want = tin[idx] - H
        k = np.searchsorted(t, want)
        ok = (k < len(t)) & (t[np.minimum(k, len(t) - 1)] == want)
        for j, kk, good in zip(idx, k, ok):
            if not good:
                continue
            sd = T.side.iat[j]
            bar[j] = kk
            liq[j] = liqL[kk] if sd > 0 else liqS[kk]
            flush[j] = -doi[kk]
            age[j] = ag[kk]
            chk[j] = abs((l[kk] if sd > 0 else h[kk]) / c[kk] - 1)
    T["bar"], T["liq"], T["flush"], T["age"], T["dist_chk"] = bar, liq, flush, age, chk
    return T


def keep(T: pd.DataFrame) -> pd.DataFrame:
    return T[(T.t_in >= START) & (T.bar >= 0) & (T.age >= WARM) & np.isfinite(T.liq) & np.isfinite(T.flush)]


def flags(T: pd.DataFrame, tune: pd.Series):
    """Per side and factor the tune-half 2/3 cut; returns (cuts, flag columns as a DataFrame aligned to T)."""
    cuts, F = {}, pd.DataFrame(index=T.index)
    for side in (1, -1):
        g = T.side == side
        for f in FACT:
            cuts[side, f] = float(np.nanquantile(T.loc[g & tune, f], 2 / 3))
            F.loc[g, f] = (T.loc[g, f] >= cuts[side, f]).astype(bool)
        F.loc[g, "both"] = F.loc[g, "liq"].astype(bool) & F.loc[g, "flush"].astype(bool)
    return cuts, F.astype(bool)


def half_stats(x: pd.DataFrame, rest: pd.DataFrame, col="net"):
    """Subset net and t, its spread over `rest` (same side, unflagged) and t, n."""
    if len(x) < 3:
        return dict(n=len(x), net=np.nan, t=np.nan, sp=np.nan, sp_t=np.nan, ex=np.nan)
    y = np.r_[x[col].to_numpy(float), rest[col].to_numpy(float)]
    fl = np.r_[np.ones(len(x)), np.zeros(len(rest))]
    dd = np.r_[x.day.to_numpy(), rest.day.to_numpy()]
    b, bt = sc.spread_t(y, fl, dd) if len(rest) >= 3 else (np.nan, np.nan)
    return dict(n=len(x), net=float(x[col].mean()), t=sc.t_by_day(x[col], x.day), sp=b, sp_t=bt,
                ex=float(x["ex" if col == "net" else "ex_tp"].mean()))


def passes(st, holm_p):
    return (all(st[h]["net"] > 0 and st[h]["t"] >= 2 and st[h]["sp"] > 0 and st[h]["sp_t"] >= 2 for h in ("tu", "ho"))
            and st["ho"]["n"] >= MIN_HOLD and holm_p < 0.05)


def build_series(coins):
    out, n_bad = {}, 0
    for s in coins:
        x = lm.load_coin(s)
        if x is None:
            n_bad += 1
            continue
        t, o, h, l, c, oi = x  # noqa: E741
        out[s] = (t, h, l, c, *liq_series(t, h, l, c, oi))
    return out, n_bad


def posthoc_lines(K: pd.DataFrame) -> list:
    """POST HOC (added after the first run, when S2 failed): what the map's 'liquidated' figure actually tracks."""
    L = ["", "POST HOC (added after the first run, which found liq and the real open-interest fall nearly unrelated): rank correlations"]
    for side, nm in ((1, "long"), (-1, "short")):
        g = K[K.side == side]
        r = lambda a, b: float(g[a].rank().corr(g[b].rank()))  # noqa: E731
        L.append(f"  {nm:<5} liq vs the wick's depth in ATR (sweep_confluence F1) {r('liq', 'depth'):+.3f}, vs the stop distance "
                 f"{r('liq', 'dist'):+.3f}, vs the bar's volume ratio (F2) {r('liq', 'vol'):+.3f}; flush vs depth {r('flush', 'depth'):+.3f}, "
                 f"vs volume {r('flush', 'vol'):+.3f}")
    L.append("  -> the map's estimate is mostly how deep the wick went (already F1, not confirmed in sweep_confluence.py); the real "
             "open-interest change is a different, unrelated quantity")
    return L


def append_posthoc():
    K = pd.read_pickle(LOG.with_suffix(".pkl"))
    txt = LOG.read_text(encoding="utf-8").split("\nPOST HOC")[0].rstrip("\n")
    LOG.write_text(txt + "\n" + "\n".join(posthoc_lines(K)) + "\n", encoding="utf-8")
    print("\n".join(posthoc_lines(K)))


def main():
    t0 = time.time()
    T0 = pd.read_pickle(sc.CACHE)
    coins = sorted(T0[T0.t_in >= START].coin.unique())
    series, n_bad = build_series(coins)
    T = attach(T0[T0.t_in >= START].reset_index(drop=True), series)
    K = keep(T).reset_index(drop=True)
    tune = K.t_in < sc.HOLDOUT
    cuts, F = flags(K, tune)
    L = [f"backtest/liq_sweep.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; sweep_confluence.py's sweeps x the liquidation map and "
         f"real open interest; T24 primary, TP2 beside; 12bp + funding; halves split {sc.HOLDOUT.date()}", "",
         f"COVERAGE: {len(T)} sweeps from {START.date()} on {len(coins)} coins ({n_bad} coins with no open interest); matched to a bar "
         f"{(T.bar >= 0).sum()}; kept (map run >= 14 days, both readings) {len(K)}: long {(K.side > 0).sum()}, short {(K.side < 0).sum()}",
         f"CHECK: the stop distance recomputed from the matched bars equals the cached one on "
         f"{np.mean(np.isclose(K.dist, K.dist_chk, rtol=1e-6, atol=1e-9)) * 100:.2f}% of kept events", ""]
    rho = {}
    for side, nm in ((1, "long"), (-1, "short")):
        g = K[K.side == side]
        rho[side] = float(g.liq.rank().corr(g.flush.rank()))
        L.append(f"{nm:<5}: liq median {g.liq.median() * 100:.2f}% of open interest (cut {cuts[side, 'liq'] * 100:.2f}%), flush median "
                 f"{g.flush.median() * 100:+.2f}% (cut {cuts[side, 'flush'] * 100:+.2f}%); rank correlation liq vs flush {rho[side]:+.3f}")
    # stage 1
    L += ["", "STAGE 1 - one factor at a time (flagged = at or above the tune 2/3 cut); spread = flagged minus unflagged T24 net"]
    res, pv = {}, {}
    for side, nm in ((1, "LONG"), (-1, "SHORT")):
        g = K[K.side == side]
        for f in FACT:
            fl = F.loc[g.index, f].to_numpy()
            r = {}
            for h, m in (("tu", tune.loc[g.index].to_numpy()), ("ho", ~tune.loc[g.index].to_numpy())):
                b, tt = sc.spread_t(g.net.to_numpy()[m], fl[m], g.day.to_numpy()[m])
                r[h] = dict(b=b, t=tt)
            res[side, f] = r
            pv[side, f] = sc.p_one_sided(r["ho"]["t"])
    hp1 = sc.holm(pv)
    conf = 0
    for side, nm in ((1, "LONG"), (-1, "SHORT")):
        for f in FACT:
            r = res[side, f]
            ok = r["tu"]["b"] > 0 and r["tu"]["t"] > 2 and r["ho"]["b"] > 0 and hp1[side, f] < 0.05
            conf += ok
            L.append(f"  {nm + ' ' + f:<12} tune {r['tu']['b'] * 100:+6.2f}% (t {r['tu']['t']:+.1f})  holdout {r['ho']['b'] * 100:+6.2f}% "
                     f"(t {r['ho']['t']:+.1f})  Holm {hp1[side, f]:.2f}{'  CONFIRMED' if ok else ''}")
    # the subsets
    L += ["", "SUBSETS (T24 net per trade, t by day; spread over the same side's unflagged sweeps; excess over the random control) - tune / holdout"]
    st = {}
    for side, f in SUBSETS:
        g = K[K.side == side]
        fl = F.loc[g.index, f]
        rest_fl = ~F.loc[g.index, "liq"] & ~F.loc[g.index, "flush"] if f == "both" else ~fl
        st[side, f] = {h: half_stats(g[fl & m], g[rest_fl & m]) for h, m in (("tu", tune.loc[g.index]), ("ho", ~tune.loc[g.index]))}
    hp = dict(zip(SUBSETS, cs.holm([cs.p_one_sided(np.nan_to_num(min(st[k]["tu"]["t"], st[k]["ho"]["t"]), nan=-10.0)) for k in SUBSETS])))
    for side, f in SUBSETS:
        a, b = st[side, f]["tu"], st[side, f]["ho"]
        g = K[K.side == side]
        fl = F.loc[g.index, f]
        tp = [g[fl & m].net_tp.mean() * 1e4 for m in (tune.loc[g.index], ~tune.loc[g.index])]
        L.append(f"  {('LONG' if side > 0 else 'SHORT') + ' ' + f:<12} {a['n']:>5}/{b['n']:<5} NET {a['net'] * 1e4:+6.1f} ({a['t']:+.1f}) / "
                 f"{b['net'] * 1e4:+6.1f}bp ({b['t']:+.1f})  SPREAD {a['sp'] * 1e4:+6.1f} ({a['sp_t']:+.1f}) / {b['sp'] * 1e4:+6.1f}bp "
                 f"({b['sp_t']:+.1f})  EXCESS {a['ex'] * 1e4:+6.1f} / {b['ex'] * 1e4:+6.1f}bp  TP2 {tp[0]:+6.1f} / {tp[1]:+6.1f}bp  "
                 f"holm {hp[side, f]:.2f}{'  PASS' if passes(st[side, f], hp[side, f]) else ''}")
    for side, nm in ((1, "LONG"), (-1, "SHORT")):
        g = K[K.side == side]
        L.append(f"  {nm + ' all':<12} {int((g.t_in < sc.HOLDOUT).sum()):>5}/{int((g.t_in >= sc.HOLDOUT).sum()):<5} NET "
                 f"{g[g.t_in < sc.HOLDOUT].net.mean() * 1e4:+6.1f} / {g[g.t_in >= sc.HOLDOUT].net.mean() * 1e4:+6.1f}bp  (every kept sweep)")
    npass = sum(passes(st[k], hp[k]) for k in SUBSETS)
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    s4 = all(not (st[k]["ho"]["net"] >= 0.0010) for k in SUBSETS)
    L += ["", f"PASSING: {npass} of {len(SUBSETS)}", "REGISTERED PREDICTIONS",
          f"  S1 no subset passes -> {ok(npass == 0)}",
          f"  S2 rank correlation of liq and flush positive on both sides -> {ok(all(v > 0 for v in rho.values()))} "
          f"(long {rho[1]:+.3f}, short {rho[-1]:+.3f})",
          f"  S3 0 of 4 stage-1 cells confirmed -> {ok(conf == 0)} ({conf})",
          f"  S4 every subset's T24 holdout net under +0.10% -> {ok(s4)}",
          f"  S5 long flush-flagged sweeps no better than the rest on the holdout -> {ok(not (st[1, 'flush']['ho']['sp'] > 0))} "
          f"(spread {st[1, 'flush']['ho']['sp'] * 1e4:+.1f}bp)",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L + posthoc_lines(K))
    LOG.write_text(txt + "\n", encoding="utf-8")
    K.assign(**{f"f_{c}": F[c] for c in F.columns}).to_pickle(LOG.with_suffix(".pkl"))
    print(txt)


if __name__ == "__main__":
    if "--posthoc" in sys.argv:
        append_posthoc()
    else:
        main()
