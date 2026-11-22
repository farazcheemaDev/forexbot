"""RESTING ORDERS JUST PAST THE LIQUIDATION CLUSTERS (2026-11-15)

THE QUESTION. backtest/liq_map_1m.py found that within 5 minutes of reaching a predicted liquidation cluster the price runs a median
0.58% (long) / 0.55% (short) past it, against 0.48% for a random level the same distance away: the cluster is where forced trading
pushes THROUGH. The one use that follows is execution: rest the order a little PAST the cluster, so the forced trading fills it at a
better price, then see whether that trade pays. The user: "Yes, test it" (2026-11-15).

ORDERS   For every liq_map.py event whose cluster order filled (liq_map_1m.py's fills table: 9,366 cluster fills and their 19,755 filled
         controls, with the same minute windows) a second order rests k PAST the level - a buy k under a long cluster, a sell k over a
         short cluster - for k = 0.25%, 0.5%, 1.0%. It rests from when the cluster order was placed; a deeper level is further from the
         price, so it can only trade once the cluster level has, and it is CANCELLED 60 minutes after the minute that first trades
         0.05% through the cluster level (that minute included). It fills in the first minute that trades 0.05% through ITS level, at
         its level, or at the minute's open if the minute opens past it.
EXITS    the close 15 and 60 minutes after its fill minute, and liq_map_1m.py's scalp bracket (stop 0.5% past the entry, target 1.0%,
         out after 60 minutes; the fill minute counts as stopped if it reaches the stop; a minute touching both = stopped; a gap
         through the stop exits at the open). 12bp a round trip + funding 1bp / 8h pro rata - the repo's rule. A resting entry at
         Bitget's maker fee would cost about 8bp; that is printed beside it and not used to judge.
CONTROL  the same order k past each filled control level (same distance, random time, same coin, same half), scored the same way;
         EXCESS = the cluster trade minus the mean of its FILLED controls.
PASS     per cell (side x k x exit = 18), on BOTH halves (liq_map.py's CUT): net > 0 with t >= 2 AND excess > 0 with t >= 2 (day-
         clustered); Holm < 0.05 over the 18. The same rule as liq_map_1m.py.
SECONDARY long, k = 0.5%, clusters 8% or more under the close (crash-bid territory), 15m and 60m; Holm over its own 2.
DIAGNOSTICS fill rates by k (cluster vs control); the net PER ORDER PLACED at 60 minutes (an unfilled order counts 0) beside the
         order AT the cluster (k = 0, which must reproduce liq_map_1m.py's trades exactly - the parity check).

REGISTERED BEFORE THE FIRST NUMBER (2026-11-15; my prior that any of the 18 cells passes: about 4%)
  P1  No primary cell passes.
  P2  At every k, on both sides, the order past a cluster fills more often than the same order past a random level.
  P3  No primary cell has excess t >= 2 on both halves.
  P4  Every scalp cell loses after costs on both halves.
  P5  Per order placed, every k loses at 60 minutes on both halves, both sides.
  P6  The deep-long secondary cells do not pass.

RESULT (2026-11-15, logs/liq_map_past.txt): NO PASS, 0 of 18. Parity exact (k = 0 reproduces liq_map_1m.py on all 29,121 rows).
The order past a cluster fills only 1-3 points more often than the same order past a random level (k 0.5%: 73.4% vs 71.8% long,
74.6% vs 72.7% short): over an hour most of the 5-minute overshoot difference washes out. Long 15m / 60m nets +1.5..+22bp on the tune
half and -12.7..+0.2bp on the holdout; no excess over random levels reaches t 2 on either half (the largest, long 1% 60m, +17.2bp tune
/ -16.4bp holdout). Shorts lose everywhere (-12..-35bp) and do worse than random levels on the holdout (-16..-48bp). Every scalp cell
loses (-16..-26bp). Per order placed the long side improves with depth (tune -0.4 -> +12.2bp, holdout -13.8 -> -2.9bp; P5 wrong on the
tune half) - but POST HOC the random levels show the same slope (holdout at k 1%: -2.9bp for both): a deeper order trades less and pays
fewer fees; the map adds nothing. At a maker entry (about 8bp) the three long 15m cells read +0.4..+4.2bp on the holdout - noise.
Secondary (longs 8%+ under the close, k 0.5%): +56 / +43bp at 15m (t 2.2 / 2.1, Holm 0.03) but only +20 / +22bp over random 8%+ dips
(t 0.5 / 0.8, MDE80 53bp): the dip again, as at the cluster itself. P1-P4 and P6 right, P5 wrong. Tests 10; planted bugs 17 of 17
(two first survivors - a short row never scored, the scalp's holding cost unchecked - were gaps in my tests), control survived.

    python -m backtest.liq_map_past     (needs liq_map_1m.py's fills and windows; logs/liq_map_past.txt)
"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import liq_map as lm  # noqa: E402
from backtest import liq_map_1m as m1  # noqa: E402
from backtest import sweep_confluence as sc  # noqa: E402

LOG = ROOT / "logs" / "liq_map_past.txt"
OFFSETS = (0.0025, 0.005, 0.010)
CANCEL = 60
XS = ("15m", "60m", "scalp")
CELLS = [(s, k, x) for s in ("long", "short") for k in OFFSETS for x in XS]
SEC_K = 0.005
MAKER_SAVE = 0.0004                                # 12bp -> about 8bp with a maker entry


def first_through(o, h, l, sg, level, a, b):  # noqa: E741
    """The first minute in [a, b) that trades 0.05% through `level` (down for sg +1, up for sg -1), or None."""
    seg = (l[a:b] <= level * (1 - lm.THROUGH)) if sg > 0 else (h[a:b] >= level * (1 + lm.THROUGH))
    hit = np.flatnonzero(np.nan_to_num(seg, nan=0).astype(bool))
    return a + int(hit[0]) if hit.size else None


def past_trade(w, side, level, k, cancel=CANCEL):
    """The order k past `level` on one window (liq_map_1m.WIN_MIN x [o, h, l, c]). None if no minute of the first hour trades through
    the cluster level (the minute bars disagree with the hourly bar: dropped, as in liq_map_1m.py). Else dict(filled, m, ...) with,
    when filled, the fill minute m2, the fill price and liq_map_1m.exits_from's returns."""
    sg = 1 if side == "long" else -1
    o, h, l, c = (w[:, j].astype(float) for j in range(4))  # noqa: E741
    m = first_through(o, h, l, sg, level, 0, 60)
    if m is None:
        return None
    deep = level * (1 - sg * k)
    m2 = first_through(o, h, l, sg, deep, m, min(m + cancel, len(c)))
    if m2 is None:
        return dict(filled=False, m=m)
    fill = min(deep, o[m2]) if sg > 0 else max(deep, o[m2])
    if not np.isfinite(fill):
        fill = deep
    out = dict(filled=True, m=m, m2=m2, fill=fill)
    out.update(m1.exits_from(w, sg, m2, fill))
    return out


def score(D: pd.DataFrame, W: dict, ks=(0.0,) + OFFSETS) -> pd.DataFrame:
    rows = []
    for r in D.itertuples():
        w = W.get((r.coin, r.hour))
        base = dict(eid=r.eid, coin=r.coin, side=r.side, half=r.half, dist=r.dist, kind=r.kind,
                    day=pd.Timestamp(r.hour, unit="ms").strftime("%Y-%m-%d"))
        for k in ks:
            tr = None if w is None else past_trade(w, r.side, r.level, k)
            x = dict(base, k=k, ok=tr is not None, filled=bool(tr is not None and tr["filled"]))
            if x["filled"]:
                for e in ("15m", "60m"):
                    x[e] = m1.net(tr["r" + e], m1.EXITS[e] + 1)
                x["scalp"] = m1.net(tr["rscalp"], tr["mscalp"])
            rows.append(x)
    return pd.DataFrame(rows)


def at_k(S: pd.DataFrame, k) -> pd.DataFrame:
    """The rows of one offset, with `ok` meaning FILLED (liq_map_1m.cell keeps the ok rows)."""
    return S[np.isclose(S.k, k)].assign(ok=lambda d: d.filled)


def fill_rate(S: pd.DataFrame, side, k, kind):
    d = S[np.isclose(S.k, k) & (S.side == side) & (S.kind == kind) & S.ok]
    return float(d.filled.mean()) if len(d) else np.nan


def per_order(S: pd.DataFrame, side, k, half, x="60m", kind="cluster"):
    """Mean net per order placed (an unfilled order counts 0; a filled one with no exit price is dropped) and its t."""
    d = S[np.isclose(S.k, k) & (S.side == side) & (S.half == half) & (S.kind == kind) & S.ok]
    v = np.where(d.filled, d[x].astype(float), 0.0)
    keep = np.isfinite(v)
    v, days = v[keep], d.day.to_numpy()[keep]
    return float(v.mean()) if len(v) else np.nan, sc.t_by_day(pd.Series(v), pd.Series(days)) if len(v) > 2 else np.nan


def name(c):
    return f"{c[0]} {c[1] * 100:.2f}% {c[2]}"


def main():
    t0 = time.time()
    D = pd.read_pickle(m1.FILLS)
    W = pickle.loads(m1.WINDOWS.read_bytes())
    S = score(D, W)
    st = {c: {h: m1.cell(at_k(S, c[1]), c[0], c[2], h) for h in ("tu", "ho")} for c in CELLS}
    hp = m1.holm_of(st, CELLS)
    sec = [("long", SEC_K, "15m"), ("long", SEC_K, "60m")]
    st2 = {c: {h: m1.cell(at_k(S, c[1]), c[0], c[2], h, sub=lambda d: d.dist >= m1.DEEP) for h in ("tu", "ho")} for c in sec}
    hp2 = m1.holm_of(st2, sec)

    L = [f"backtest/liq_map_past.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; orders resting k past liq_map.py's clusters, "
         f"cancelled {CANCEL} minutes after the cluster level trades through; Binance 1-minute bars; 12bp + 1bp / 8h", ""]
    ref = m1.LOG.with_suffix(".pkl")
    if ref.exists():
        R = pd.read_pickle(ref)
        S0 = S[S.k == 0.0].reset_index(drop=True)
        same = all(np.allclose(S0[x].to_numpy(float), R[x].to_numpy(float), equal_nan=True, atol=1e-12) for x in XS)
        same = same and len(S0) == len(R) and (S0.ok.to_numpy() == R.ok.to_numpy()).all()
        L.append(f"PARITY: the order AT the cluster (k = 0) reproduces liq_map_1m.py's 15m / 60m / scalp on all {len(R)} rows: "
                 f"{'YES' if same else 'NO - STOP'}")
    L.append("")
    for side in ("long", "short"):
        L.append(f"FILL RATE {side} (of fills whose minute reaches the cluster level): " + "; ".join(
            f"k {k * 100:.2f}% cluster {fill_rate(S, side, k, 'cluster') * 100:.1f}% vs control {fill_rate(S, side, k, 'control') * 100:.1f}%"
            for k in OFFSETS))
    L += ["", "PRIMARY (tune / holdout)", *[m1.fmt(name(c), st[c], hp[c]) for c in CELLS]]
    L += ["", "PER ORDER PLACED, 60 minutes (unfilled = 0), tune / holdout"]
    po = {}
    for side in ("long", "short"):
        for k in (0.0,) + OFFSETS:
            a, b = per_order(S, side, k, "tu"), per_order(S, side, k, "ho")
            po[(side, k)] = (a, b)
            L.append(f"  {side:<6} k {k * 100:.2f}%{' (at the cluster)' if k == 0 else '':<17} {a[0] * 1e4:+7.1f}bp ({a[1]:+.1f}) / "
                     f"{b[0] * 1e4:+7.1f}bp ({b[1]:+.1f})")
    L += ["", "POST HOC (added after the first run, which showed deeper long orders doing better per order): the same orders past the",
          "RANDOM levels (controls), 60 minutes, unfilled = 0, tune / holdout - is 'deeper is better' the cluster or any level?"]
    for side in ("long", "short"):
        for k in (0.0,) + OFFSETS:
            a, b = (per_order(S, side, k, h, kind="control") for h in ("tu", "ho"))
            L.append(f"  {side:<6} k {k * 100:.2f}%{'':<17} {a[0] * 1e4:+7.1f}bp ({a[1]:+.1f}) / {b[0] * 1e4:+7.1f}bp ({b[1]:+.1f})")
    both8 = [name(c) for c in CELLS if all(st[c][h]["net"] + MAKER_SAVE > 0 for h in ("tu", "ho"))]
    L += ["", f"AT A MAKER ENTRY (about 8bp instead of 12bp) every net rises by {MAKER_SAVE * 1e4:.0f}bp; cells then positive on both "
              f"halves: {len(both8)}{' (' + ', '.join(both8) + ')' if both8 else ''} (not the judging cost)"]
    L += ["", "SECONDARY: long, k 0.50%, clusters 8%+ under the close", *[m1.fmt("deep " + name(c), st2[c], hp2[c]) for c in sec]]

    npass = sum(m1.passes(st[c], hp[c]) for c in CELLS)
    p2 = all(fill_rate(S, s, k, "cluster") > fill_rate(S, s, k, "control") for s in ("long", "short") for k in OFFSETS)
    p3 = not any(all(st[c][h]["ex_t"] >= 2 for h in ("tu", "ho")) for c in CELLS)
    p4 = all(st[c][h]["net"] < 0 for c in CELLS if c[2] == "scalp" for h in ("tu", "ho"))
    p5 = all(po[(s, k)][i][0] < 0 for s in ("long", "short") for k in OFFSETS for i in (0, 1))
    p6 = not any(m1.passes(st2[c], hp2[c]) for c in sec)
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    L += ["", f"PASSING: {npass} of {len(CELLS)} primary", "REGISTERED PREDICTIONS",
          f"  P1 no primary cell passes -> {ok(npass == 0)}",
          f"  P2 the order past a cluster fills more often than past a random level, every k, both sides -> {ok(p2)}",
          f"  P3 no cell has excess t >= 2 on both halves -> {ok(p3)}",
          f"  P4 every scalp cell loses on both halves -> {ok(p4)}",
          f"  P5 per order placed, every k loses at 60 minutes on both halves, both sides -> {ok(p5)}",
          f"  P6 the deep-long secondary cells do not pass -> {ok(p6)}",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    S.to_pickle(LOG.with_suffix(".pkl"))
    print(txt)


if __name__ == "__main__":
    main()
