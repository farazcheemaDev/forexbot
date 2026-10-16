"""HIS CLOCK, TO THE SECOND, PER BROKER - and his gold trades scored (2026-10-12)

THE COUNCIL (2026-10-12): the one gap never closed is his exact second, trade by trade, against the real market (only a
POOLED +-600 s search was done, s25). If his broker's clock runs a few seconds off, he may be REACTING to the first seconds
of a move that his statement stamps as BEFORE it - the only reading of him a bot could copy on its own (the user: "we
don't want to copy him - the bot should be independent - what we copy is his strategy"). And his 41 gold trades were
never scored.

CLOCK FIT  for each trade the points he made, side x (exit - entry), are compared with the reference market's move over
           the same two stamps shifted by d seconds: side x (M(exit + d) - M(entry + d)). The broker's offset from the
           exchange cancels (constant within a 1-2 minute trade); his spread is a constant cost. d* = the shift that makes
           his points and the market's move agree best (smallest median absolute deviation of the difference), per
           broker; then each trade's own best d within +-30 s. This fits the CLOCK from the price PATH between his two
           fills - it does not look at what happened before his entry, so it cannot manufacture "the market had already
           moved his way".
REFERENCE  CME NQ futures 1-second mid (Databento bbo-1s windows around his NASDAQ sittings, Jan-Sep: the VertexPro
           statement), and Exness's own ticks (MT5) for every trade incl. the two CapitalFX trades of 2026-10-08 and gold.
THEN       at the corrected entry second: how far had the market moved HIS way in the 5 s and 15 s before it; and the
           +7 / -7 race from the corrected second.
GOLD       his 41 gold trades (5 days, a burst of 37 on 2026-02-02), on Exness XAUUSDm ticks: the +X / -X race at his own
           typical move (median |exit - entry| = $3.875) from his second, against moments of the same sittings in his
           direction.

REGISTERED BEFORE THE RUN (2026-10-12)
    K1  (the council's hypothesis) a NON-ZERO, consistent offset within each broker: |d*| >= 2 s and >= 60% of trades'
        own best d within 2 s of it. My expectation: d* within +-1 s of zero for VertexPro (s42 found his fills matching
        the market at the stamped second).
    K2  (the council's) at the corrected entry the market had already moved >= 2 points his way over the prior 5 s in
        >= 60% of trades. My expectation: no - s25 found the last 30 s and 5 s moving AGAINST him.
    G1  gold: his race win rate is well below NASDAQ's 88% (I expect 55-75%) and within 15 points of same-sitting moments
        in his direction - gold is not where his edge is.

RESULT (2026-10-12 14:44 UTC, logs/his_clock_exits.txt; 46 VertexPro NASDAQ, 2 CapitalFX NASDAQ, 41 VertexPro gold)
    - K1: NO consistent clock offset - his main broker's stamps are right to the second. VertexPro NASDAQ: the best shift
      is 0 s against BOTH references (CME 1-s and Exness ticks; the difference's spread is smallest at d = 0); each trade's
      own best shift scatters from -30 to +28 s with no cluster (24% / 35% within 2 s). The council's hypothesis fails;
      my expectation (d* within +-1 s of zero) holds.
    - K2 WRONG for the council, right for my expectation: at his true entry second the market had NOT moved his way -
      median 0.00 points over the 5 s before (>= 2 points his way in only 24%), +0.01 over 15 s - and from that second
      he won the +-7 race 40 of 46 (87%). He clicks BEFORE the move, not after it.
    - CapitalFX: 2 trades - the fit wanders to +5 s with both trades' own best at 5 and 25 s; nothing can be read.
    - G1 WRONG in size: gold has NO edge - from his entries the +-$3.875 race was won 51% (21 of 41) against 47% for
      moments of the same sittings in his direction (1,640); his gold profit (+$117.69, 30 of 41 winners) is the
      small-target / no-stop shape, not direction. His edge is NASDAQ-only.
    Reading: the council's "he reacts to bursts and his clock is off" is ruled out on his main broker: the clock is exact
    and the move comes after him. By the kill line set before the test, no bot can reproduce his NASDAQ direction from
    price; the source is a person, a feed or a skill that leaves no trace in the market before he clicks.

    python -m backtest.his_clock_exits
"""
from __future__ import annotations

import datetime as dt
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.his_clock_check import to_utc  # noqa: E402

LOG = ROOT / "logs" / "his_clock_exits.txt"
CACHE = ROOT / "strategy_analysis" / "data" / "his_ticks_exness.pkl"
SHIFTS = np.arange(-30, 31)


def trades() -> pd.DataFrame:
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    x = x[x.symbol.str.startswith(("NASDAQ", "GOLD"))].copy()
    x["entry"] = to_utc(x.open_time, 4.0, 5.0)
    x["exit"] = to_utc(x.close_time, 4.0, 5.0)
    x["broker"] = "VertexPro"
    rows = x[["symbol", "side", "open_price", "close_price", "entry", "exit", "net", "broker"]]
    new = ROOT / "strategy_analysis" / "his_statement_2026-10_trades.csv"
    if new.exists():
        n = pd.read_csv(new)
        n = n[pd.to_datetime(n.open_time, format="%d-%m-%Y %H:%M:%S") > "2026-10-01"]
        add = pd.DataFrame({"symbol": n.symbol, "side": n.side, "open_price": n.open_px.astype(float),
                            "close_price": n.close_px.astype(float),
                            "entry": pd.to_datetime(n.open_time, format="%d-%m-%Y %H:%M:%S") - pd.Timedelta(hours=5),
                            "exit": pd.to_datetime(n.close_time, format="%d-%m-%Y %H:%M:%S") - pd.Timedelta(hours=5),
                            "net": n.net.astype(str).str.replace(",", "").astype(float), "broker": "CapitalFX"})
        rows = pd.concat([rows, add], ignore_index=True)
    rows = rows[rows.entry >= "2026-01-01"].reset_index(drop=True)
    rows["kind"] = np.where(rows.symbol.str.startswith("GOLD"), "GOLD", "NASDAQ")
    rows["s"] = np.where(rows.side == "BUY", 1, -1)
    return rows


def exness_ticks(T: pd.DataFrame) -> dict:
    cache = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    need = [i for i in T.index if i not in cache]
    if need:
        import MetaTrader5 as mt5
        assert mt5.initialize(), mt5.last_error()
        try:
            for i in need:
                r = T.loc[i]
                sym = "USTECm" if r.kind == "NASDAQ" else "XAUUSDm"
                a = dt.datetime.fromtimestamp(r.entry.timestamp() - 1500, dt.timezone.utc)
                b = dt.datetime.fromtimestamp(r.exit.timestamp() + 1500, dt.timezone.utc)
                tk = mt5.copy_ticks_range(sym, a, b, mt5.COPY_TICKS_ALL)
                if tk is None or not len(tk):
                    cache[i] = None
                    continue
                d = pd.DataFrame(tk)
                d = d[(d.bid > 0) & (d.ask > 0)]
                cache[i] = (d.time_msc.to_numpy() / 1000.0, ((d.bid + d.ask) / 2).to_numpy())
        finally:
            mt5.shutdown()
        CACHE.write_bytes(pickle.dumps(cache))
    return cache


def at(ts, px, t):
    i = np.searchsorted(ts, t, "right") - 1
    return px[i] if 0 <= i < len(ts) and t - ts[i] <= 5 else np.nan


def cme_series():
    d = pickle.load(open(ROOT / "strategy_analysis" / "data" / "nq_bbo1s.pkl", "rb"))
    s = pd.concat(d.values()).sort_index()
    s = s[~s.index.duplicated()]
    idx = pd.to_datetime(s.index)
    return (idx.astype("int64") / 1e9).to_numpy(), s.to_numpy(float)


def fit(T, ref):
    """ref(i) -> (ts, px) or None. Returns per-trade residual matrix over SHIFTS and his points."""
    R, keep = [], []
    for i, r in T.iterrows():
        tp = ref(i)
        if tp is None:
            continue
        ts, px = tp
        te, tx = r.entry.timestamp(), r.exit.timestamp()
        his = r.s * (r.close_price - r.open_price)
        mv = np.array([r.s * (at(ts, px, tx + d) - at(ts, px, te + d)) for d in SHIFTS])
        if np.isnan(mv).sum() > 5:
            continue
        R.append(his - mv)
        keep.append(i)
    return np.array(R), keep


def main():
    T = trades()
    ex = exness_ticks(T)
    cts, cpx = cme_series()
    lines = [f"backtest/his_clock_exits.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(T)} trades: "
             + ", ".join(f"{k} {v}" for k, v in T.groupby(['broker', 'kind']).size().items()), ""]
    out = {}
    refs = {"CME 1s": lambda i: (cts, cpx) if T.loc[i, "kind"] == "NASDAQ" and T.loc[i, "broker"] == "VertexPro" else None,
            "Exness ticks": lambda i: ex.get(i)}
    lines.append("CLOCK FIT - his points minus the reference market's move over his two stamps shifted by d seconds")
    for rname, ref in refs.items():
        for (broker, kind), g in T.groupby(["broker", "kind"]):
            R, keep = fit(g, ref)
            if len(keep) < 2:
                continue
            mad = np.nanmedian(np.abs(R - np.nanmedian(R, axis=0)), axis=0)
            k = int(np.nanargmin(mad))
            dstar = int(SHIFTS[k])
            c = np.nanmedian(R[:, k])
            own = np.array([SHIFTS[int(np.nanargmin(np.abs(row - c)))] for row in R])
            near = np.mean(np.abs(own - dstar) <= 2)
            out[(rname, broker, kind)] = (dstar, near, len(keep), mad[k], mad[list(SHIFTS).index(0)])
            lines.append(f"  {rname:12} {broker:9} {kind:6} n {len(keep):2} | best shift d* = {dstar:+3d} s (spread of the difference "
                         f"{mad[k]:.2f} vs {mad[list(SHIFTS).index(0)]:.2f} at d = 0) | trades' own best d within 2 s of d*: "
                         f"{near * 100:3.0f}% | his cost vs the market {c:+.2f}")
            lines.append(f"  {'':12} {'':9} {'':6}      own best d: {sorted(own.tolist())}")
    lines.append("")
    # the market before / after the corrected entry, Exness reference (covers every trade)
    lines.append("AT THE CORRECTED ENTRY (Exness ticks, d* of each broker x kind): the move HIS way before it, and the +-7 race")
    k2 = {}
    for (broker, kind), g in T.groupby(["broker", "kind"]):
        if ("Exness ticks", broker, kind) not in out:
            continue
        dstar = out[("Exness ticks", broker, kind)][0]
        pre5, pre15, race = [], [], []
        X = 7.0 if kind == "NASDAQ" else 3.875
        for i, r in g.iterrows():
            tp = ex.get(i)
            if tp is None:
                continue
            ts, px = tp
            t0 = r.entry.timestamp() + dstar
            p0 = at(ts, px, t0)
            pre5.append(r.s * (p0 - at(ts, px, t0 - 5)))
            pre15.append(r.s * (p0 - at(ts, px, t0 - 15)))
            j = np.searchsorted(ts, t0, "right")
            path = r.s * (px[j:np.searchsorted(ts, t0 + 1800)] - p0)
            up, dn = np.flatnonzero(path >= X), np.flatnonzero(path <= -X)
            race.append(1.0 if len(up) and (not len(dn) or up[0] < dn[0]) else (0.0 if len(dn) else np.nan))
        pre5, pre15, race = np.array(pre5), np.array(pre15), np.array(race)
        k2[(broker, kind)] = np.nanmean(pre5 >= 2)
        lines.append(f"  {broker:9} {kind:6} d* {dstar:+3d} s, n {len(pre5):2} | 5 s before: median {np.nanmedian(pre5):+.2f}, >= 2 pts his way "
                     f"{np.nanmean(pre5 >= 2) * 100:3.0f}% | 15 s before: median {np.nanmedian(pre15):+.2f} | race +-{X:g} from there: "
                     f"{np.nansum(race):.0f}/{np.sum(~np.isnan(race))} = {np.nanmean(race) * 100:.0f}%")
    lines.append("")
    # GOLD: his moments vs same-sitting moments, his side
    G = T[T.kind == "GOLD"]
    his_w, ctl_w = [], []
    for i, r in G.iterrows():
        tp = ex.get(i)
        if tp is None:
            continue
        ts, px = tp
        for off, sink in [(0, his_w)] + [(o, ctl_w) for o in range(-1200, 1201, 60) if abs(o) >= 60]:
            t0 = r.entry.timestamp() + off
            if t0 < ts[0] or t0 > ts[-1] - 60:
                continue
            p0 = at(ts, px, t0)
            j = np.searchsorted(ts, t0, "right")
            path = r.s * (px[j:np.searchsorted(ts, t0 + 1800)] - p0)
            up, dn = np.flatnonzero(path >= 3.875), np.flatnonzero(path <= -3.875)
            if len(up) or len(dn):
                sink.append(1.0 if len(up) and (not len(dn) or up[0] < dn[0]) else 0.0)
    lines.append(f"GOLD (Exness XAUUSDm, race +-$3.875 = his median move): his {len(his_w)} entries won {np.mean(his_w) * 100:.0f}% | same-sitting "
                 f"moments, his side: {np.mean(ctl_w) * 100:.0f}% ({len(ctl_w)}) | his gold P&L: {G.net.sum():+.2f}, won {(G.net > 0).sum()}/{len(G)}")
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    for (rname, broker, kind), (dstar, near, n, m1, m0) in out.items():
        if kind != "NASDAQ":
            continue
        ok = abs(dstar) >= 2 and near >= 0.6
        lines.append(f"  K1 {rname:12} {broker:9}: d* {dstar:+d} s, {near * 100:.0f}% of trades within 2 s -> "
                     f"{'non-zero consistent offset (council)' if ok else 'no consistent non-zero offset'}")
    for (broker, kind), v in k2.items():
        if kind == "NASDAQ":
            lines.append(f"  K2 {broker:9}: >= 2 pts his way in the 5 s before the corrected entry in {v * 100:.0f}% -> "
                         f"{'RIGHT (the council)' if v >= 0.6 else 'WRONG (the council) / RIGHT (my expectation)'}")
    g1 = np.mean(his_w) if his_w else np.nan
    lines.append(f"  G1 gold {g1 * 100:.0f}% vs same-sitting {np.mean(ctl_w) * 100:.0f}% -> "
                 f"{'RIGHT' if 0.55 <= g1 <= 0.75 and abs(g1 - np.mean(ctl_w)) <= 0.15 else 'WRONG'}")
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt.encode("ascii", "replace").decode())


if __name__ == "__main__":
    main()
