"""CUTTING CAPIT2'S CRASH-HOUR TAIL - which version keeps the return and shrinks the worst hour? (2026-10-16)

liq_stress.py: no hour since 2020 takes the deployed final machine under the 17% liquidation line, but capit2 at 1.0 x 2x
is now its biggest crash-hour risk - in a cascade the capitulation buys keep falling: alone it lost 68% of the account at
2021-05-19 13:00 (all 8 slots at their hour's low) and it set the machine's worst hour in 2 of 3 orderings (29% / 50%
left). Versions, each through BOTH the machine backtest (final_capit2_lev.py's method, $300, 10 orderings) and the
worst-hour stress (liq_stress.py's method, 3 orderings):
    A  deployed: 8 slots, each 2/8 of the account notional (1.0 x 2x)
    B  1.0 x 1x (each 1/8)
    C  1.0 x 1.5x
    D  2x sizing but at most 4 open at once (each 2/8 - the peak notional of 1x with 8)
    E  2x with a -15% stop on each position (cc.gen stop=0.15)
    F  2x, at most 4 open AND the -15% stop

REGISTERED BEFORE THE RUN (2026-10-16)
    1. D keeps >= 80% of A's gain over B on the typical year, and its worst hour is >= 15 points better than A's in the
       ordering where A is worst.
    2. E costs return (stops cut capitulation bounces - capit_combos.py's stop variants did not pass) but helps the hour.
    3. No version changes the machine's worst month (-30%, from the trend book).

RESULT (2026-10-16, logs/liq_fix.txt) - typical year 6y / 2y ($300), worst hour left by ordering, capit2-alone worst hour:
    A deployed 2x, 8 open   $4,098 / $5,494 | 41 / 29 / 50% | 69 / 32 / 38%
    B 1x, 8 open            $3,648 / $4,967 | 41 / 56 / 74% | 84 / 66 / 69%
    C 1.5x, 8 open          $3,922 / $5,215 | 41 / 43 / 64% | 76 / 49 / 54%
    D 2x, at most 4 open    $3,800 / $5,026 | 41 / 55 / 71% | 75 / 66 / 65%
    E 2x, -15% stop         $3,306 / $5,159 | 41 / 53 / 66%  (worst month -33.3%)
    F 2x, 4 open, -15% stop $3,308 / $4,972 | 41 / 68 / 74%
    Ordering 0's 41% is the trend book + crash bids on 2025-10-10, untouched by any capit2 version. Return per unit of
    tail: C keeps 61% of A's gain over B and lifts the worst hour 29 -> 43%; B gives up 11% / 10% of A's year for 56%.
    Predictions: 1 wrong (D keeps only 34% of the gain), 2 right, 3 wrong (E's stop deepens the worst month to -33%).

    python -m backtest.liq_fix
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.dd_fixes as Dd  # noqa: E402
from backtest import blend  # noqa: E402
from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402
from backtest import final_machine as fm  # noqa: E402
from backtest import machine_combos as mc  # noqa: E402
from backtest import mn_combos as m  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.joint_worst_hour import trend_frac  # noqa: E402
from backtest.liq_stress import book_worst  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402
from backtest.moderate_retests import scored_run  # noqa: E402
from backtest.wick_5m import CACHE, per_fill  # noqa: E402
from backtest.wick_better import fills, load_all  # noqa: E402

LOG = ROOT / "logs" / "liq_fix.txt"
V = {"A deployed 2x, 8 open": (2.0, 8, None), "B 1x, 8 open": (1.0, 8, None), "C 1.5x, 8 open": (1.5, 8, None),
     "D 2x, at most 4 open": (2.0, 4, None), "E 2x, -15% stop": (2.0, 8, 0.15), "F 2x, 4 open, -15% stop": (2.0, 4, 0.15)}


def allocate(T, seed, lev, maxopen):
    """daily_combos.allocate with each position sized at equity / 8 whatever the open limit (dc.allocate sizes at
    equity / slots), so D's positions are the same size as A's - only fewer of them at once."""
    rng = np.random.default_rng(seed)
    rnd = rng.random(len(T))
    tin = T.t_in.to_numpy("datetime64[ns]")
    order = sorted(range(len(T)), key=lambda q: (tin[q], rnd[q]))
    tout, net, worst = T.t_out.to_numpy("datetime64[ns]"), T.net.to_numpy(), T.worst.to_numpy()
    liq = 1 / lev - 0.005 - 0.0006
    eq, open_, out = 1.0, [], []
    for q in order:
        for p in sorted([p for p in open_ if p[0] <= tin[q]], key=lambda p: p[0]):
            eq += p[1]
        open_ = [p for p in open_ if p[0] > tin[q]]
        if eq <= 0:
            break
        if len(open_) >= maxopen:
            continue
        size = eq / 8
        pnl = -size if worst[q] >= liq else size * max(lev * net[q], -1.0)
        open_.append((tout[q], pnl))
        out.append((q, size, pnl))
    return out


def main():
    gens = {}
    for nm, (L, k, stop) in V.items():
        key = stop
        if key not in gens:
            gens[key] = {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER, **({"stop": stop} if stop else {})))
                         for off in cc.PHASES}
    # ---- the machine backtest
    P = mc.parts()
    T625 = fm.trend_capped(6.25)
    Dm = m.data()
    C = pd.DataFrame(Dm["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = Dm["X"] / np.r_[np.full((30, Dm["X"].shape[1]), np.nan), Dm["X"][:-30]] - 1
    T20 = {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES}
    X = {nm: [] for nm in V}
    for sd in mc.SEEDS:
        b = P[sd]
        idx = b.index
        o = sd % 7
        r = lambda s: s.reindex(idx).fillna(0.0)  # noqa: E731
        mn_blend = 0.5 * r(scored_run(mom, start=o, stop="short_only", short_stop=0.5)) \
            + 0.5 * r(scored_run(rsi, start=o, stop="short_only", short_stop=0.5))
        carry = r(m.mn_run(look=1, score="funding7", fwin=7, frac=0.2, start=o, stop="short_only", short_stop=0.5))
        off = dc.PHASES[sd % 3]
        daily20 = 0.5 * r(dc.curve(T20[off], dc.allocate(T20[off], sd), off).pct_change())
        rest = T625[sd].reindex(idx).fillna(0.0) + b.sleeve + b.bids + mn_blend + 0.5 * carry + daily20
        coff = cc.PHASES[sd % 4]
        for nm, (L, k, stop) in V.items():
            T = gens[stop][coff]
            X[nm].append(rest + r(cc.curve(T, allocate(T.assign(units=None), sd, L, k)).pct_change()))
    # ---- the worst-hour stress
    px = {}
    for c in blend.BOOK:
        dd = blend.load(c)
        if dd is not None:
            px[c] = dd.set_index(pd.DatetimeIndex(dd["time"]).as_unit("ns"))[["high", "low", "close"]]
    grid = pd.date_range(min(p.index[0] for p in px.values()), max(p.index[-1] for p in px.values()), freq="h").as_unit("ns")
    H = {c: p.reindex(grid).ffill() for c, p in px.items()}
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    rows = Dd.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    XA, _, bear_day = load_all()
    ok = per_fill(fills(XA[XA.in40], k=0.10, skip_bear=bear_day), pickle.loads(CACHE.read_bytes()))
    ok = ok[ok.ok.astype(bool)]
    x = ok.assign(tie=np.random.default_rng(0).random(len(ok))).sort_values(["t", "minute", "tie"])
    y = x[x.groupby("t").cumcount() < 10]
    w = y.groupby("t").after.sum() / 40
    w.index = pd.DatetimeIndex(w.index).as_unit("ns")
    bids = w.reindex(grid).fillna(0.0).to_numpy()
    Hc = {}
    W = {}
    for sd in (0, 1, 2):
        tr = trend_frac(rows, bn, bv, sd, grid, H).to_numpy()
        doff, coff = dc.PHASES[sd % 3], cc.PHASES[sd % 4]
        daily = book_worst(T20[doff], [q for q, _, _ in dc.allocate(T20[doff], sd)], grid, 0.5 / 8, Hc)
        for nm, (L, k, stop) in V.items():
            T = gens[stop][coff]
            tk = [q for q, _, _ in allocate(T.assign(units=None), sd, L, k)]
            cap = book_worst(T, tk, grid, L / 8, Hc)
            if stop:                                         # a stopped position cannot lose more than its stop
                cap = np.maximum(cap, -L / 8 * stop * k)
            left = 1 + tr + bids + daily + cap
            W[(nm, sd)] = (left.min(), grid[int(np.argmin(left))], (1 + cap).min())
    lines = [f"backtest/liq_fix.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the deployed final machine with capit2 "
             f"versions; $300, 10 orderings (return) / 3 orderings (worst hour, every position at its hour's worst price)", "",
             f"  {'capit2 version':<26}{'typical 6y':>11}{'2y':>8}{'worst mo':>9}{'fall':>6} | worst hour left, ord 0 / 1 / 2"
             f"{'':>4}| capit2 alone, worst hour"]
    S = {}
    for nm in V:
        s6, s2 = summary(X[nm]), summary(X[nm], CUT)
        S[nm] = (s6, s2)
        lines.append(f"  {nm:<26}${s6['typ']:>9,.0f}${s2['typ']:>7,.0f}{s6['wm']:>+8.1f}%{s6['dd']:>5.0f}% | "
                     + " / ".join(f"{W[(nm, sd)][0] * 100:>3.0f}%" for sd in (0, 1, 2))
                     + "        | " + " / ".join(f"{W[(nm, sd)][2] * 100:>3.0f}%" for sd in (0, 1, 2)))
    A, B, Dk = "A deployed 2x, 8 open", "B 1x, 8 open", "D 2x, at most 4 open"
    gain = (S[Dk][0]["typ"] - S[B][0]["typ"]) / max(S[A][0]["typ"] - S[B][0]["typ"], 1e-9)
    worst_sd = min((0, 1, 2), key=lambda sd: W[(A, sd)][0])
    p1 = gain >= 0.8 and W[(Dk, worst_sd)][0] - W[(A, worst_sd)][0] >= 0.15
    E = "E 2x, -15% stop"
    p2 = S[E][0]["typ"] < S[A][0]["typ"] and W[(E, worst_sd)][0] > W[(A, worst_sd)][0]
    p3 = all(abs(S[nm][0]["wm"] - S[A][0]["wm"]) < 1.0 for nm in V)
    lines += ["", "REGISTERED PREDICTIONS",
              f"  1 D keeps {gain * 100:.0f}% of A's gain over B (>= 80), its worst hour {(W[(Dk, worst_sd)][0] - W[(A, worst_sd)][0]) * 100:+.0f} "
              f"points in ordering {worst_sd} (>= +15) -> {'RIGHT' if p1 else 'WRONG'}",
              f"  2 the stop costs return and helps the hour -> {'RIGHT' if p2 else 'WRONG'}",
              f"  3 no version moves the worst month by >= 1 point -> {'RIGHT' if p3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
