"""v2's TREND BOOK x TODAY'S SIGNALS - the combinations not yet run (2026-10-08).

The triple (tight + time stop + 7 units, 21-day anchor, 9x guard; dd_fixes.sim on bar_phase rows) has been swept on
its own features for weeks (CLAUDE.md: "nothing is left to tune"), but never against what today found in the
point-in-time books. Each idea as a size multiplier on LONG entries (shorts untouched), read at the entry time:
    G1 breadth    x0.5 unless daily breadth20 over the PIT top-40 is >= 50% (the market is broadly rising)
    G2 daily      x0.5 unless the coin's last completed daily close is above its 30-day mean (the daily book's own
                  "in a trend" state - the two books agreeing)
    G3 after a capitulation   x1.5 within 72h after >= 5 top-40 coins capitulated (capit_combos.py's signal)
    G4 G1 and G2 together
Method: all 4 bar phases (bar_phase.rows_for_phase) x 10 orderings, RAW (no hindsight shrink: a comparison inside one
book, rule 5 - the shrink would scale both sides alike). Per phase: CAGR tune / holdout (split 2024-04-07) and the
biggest fall, mean of 10 orderings. THE LINE: the base at risk x0.6 / 0.8 / 1.0 / 1.2 (dd_fixes.sim's g). PASS = above
the line at the same fall on both halves in all 4 phases.

REGISTERED BEFORE RUNNING: G1 and G2 cut losing chop entries but also the first entries of every new run; both fail on
the holdout in at least one phase (the 1000h gate already does this job). G3 fails (capitulation weeks are when
breakouts fail most). G4 fails. Expect 0 of 4 to pass.

RESULT (2026-10-08, logs/trend_combos.txt): 0 of 4 pass. G1 breadth (fall 51 -> 40%) beats the line in 3 phases and
    loses the holdout in phase 1; G2, G4 lose the holdout in 2-3 phases; G3 (x1.5 after a capitulation) is below the line
    everywhere. Prediction (0 of 4) - right.

    python -m backtest.trend_combos
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.dd_fixes as D  # noqa: E402
from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402

LOG = ROOT / "logs" / "trend_combos.txt"
HOLDOUT = pd.Timestamp("2024-04-07")
SEEDS = tuple(range(10))
PHASES = (0, 1, 2, 3)
GS = (0.6, 0.8, 1.0, 1.2)


def lookups():
    br = cc.daily_breadth()
    bn_, bv_ = pd.DatetimeIndex(br.index).as_unit("ns").asi8, br.to_numpy(float)
    PN = dc.panel(0)
    coin_up = {}
    for s, P in PN.items():
        m30 = pd.Series(P["c"]).rolling(30).mean().to_numpy()
        coin_up[s] = ((P["t"] + dc.DAY).astype("datetime64[ns]").astype(np.int64), P["c"] > m30)
    S = cc.signals(0)
    S = S[S.K >= 5]
    cap_known = np.sort((pd.DatetimeIndex(S.t) + pd.Timedelta(hours=4)).as_unit("ns").asi8)
    return bn_, bv_, coin_up, cap_known


def gate(kind, L):
    bn_, bv_, coin_up, cap_known = L

    def ns(t):
        return pd.Timestamp(t).value if not isinstance(t, (int, np.integer)) else int(t)

    def g1(t):
        i = np.searchsorted(bn_, ns(t), side="right") - 1
        return i >= 0 and bv_[i] >= 0.5

    def g2(coin, t):
        if coin not in coin_up:
            return True
        tk, up = coin_up[coin]
        i = np.searchsorted(tk, ns(t), side="right") - 1
        return i >= 0 and bool(up[i])

    def g3(t):
        i = np.searchsorted(cap_known, ns(t), side="right") - 1
        return i >= 0 and ns(t) - cap_known[i] <= 72 * 3600 * 10 ** 9

    def fn(r, t, ctx):
        if r["side"] != "long":
            return 1.0
        if kind == "G1":
            return 1.0 if g1(t) else 0.5
        if kind == "G2":
            return 1.0 if g2(r["coin"], t) else 0.5
        if kind == "G3":
            return 1.5 if g3(t) else 1.0
        return 1.0 if (g1(t) and g2(r["coin"], t)) else 0.5
    return fn


def stats(c):
    def cg(x):
        yrs = (x.index[-1] - x.index[0]).days / 365
        return (x.iloc[-1] / x.iloc[0]) ** (1 / yrs) - 1 if x.iloc[-1] > 0 else -1.0
    c = c.resample("D").last().ffill()
    return dict(tune=cg(c[c.index < HOLDOUT]), hold=cg(c[c.index >= HOLDOUT]), fall=float((1 - c / c.cummax()).max()))


def main():
    f = ROOT / "logs" / "daily_combos_cache" / "trend_combos.pkl"
    res = pickle.loads(f.read_bytes()) if f.exists() else {}
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    L = lookups()
    for ph in PHASES:
        if all((ph, k, sd) in res for k in ("G1", "G2", "G3", "G4") + tuple(f"g{g}" for g in GS) for sd in SEEDS):
            continue
        trows = D.decompose(rows_for_phase(ph, tight=True, time_stop=(100, 2.0), max_units=7))
        for sd in SEEDS:
            for g in GS:
                res[(ph, f"g{g}", sd)] = stats(D.sim(trows, bn, bv, sd, lev=9.0, size_fn=D.anchor(21), g=g))
            for k in ("G1", "G2", "G3", "G4"):
                res[(ph, k, sd)] = stats(D.sim(trows, bn, bv, sd, lev=9.0, size_fn=D.anchor(21), gate_fn=gate(k, L)))
            print(f"  phase {ph} ordering {sd} done", flush=True)
        f.write_bytes(pickle.dumps(res))

    def agg(ph, k, key):
        return np.mean([res[(ph, k, sd)][key] for sd in SEEDS])

    lines = [f"backtest/trend_combos.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; the triple, RAW (no hindsight shrink), 4 bar "
             f"phases x 10 orderings", ""]
    lines.append("THE LINE (base at risk x g): per phase fall / tune / holdout CAGR")
    for ph in PHASES:
        lines.append(f"  phase {ph}: " + "; ".join(f"x{g}: {agg(ph, f'g{g}', 'fall') * 100:.0f}% / {agg(ph, f'g{g}', 'tune') * 100:+.0f}% / "
                                                f"{agg(ph, f'g{g}', 'hold') * 100:+.0f}%" for g in GS))
    lines.append("")
    names = {"G1": "G1 breadth20 >= 50% (else x0.5)", "G2": "G2 coin above its 30d mean (else x0.5)",
             "G3": "G3 x1.5 within 72h of a capitulation", "G4": "G4 G1 and G2"}
    for k, nm in names.items():
        cells, ok = [], True
        for ph in PHASES:
            pts = sorted((agg(ph, f"g{g}", "fall"), agg(ph, f"g{g}", "tune"), agg(ph, f"g{g}", "hold")) for g in GS)
            fa = agg(ph, k, "fall")
            dt = agg(ph, k, "tune") - np.interp(fa, [a for a, _, _ in pts], [b for _, b, _ in pts])
            dh = agg(ph, k, "hold") - np.interp(fa, [a for a, _, _ in pts], [c for _, _, c in pts])
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
        lines.append(f"  {nm:40} tune {np.mean([agg(p, k, 'tune') for p in PHASES]) * 100:+.0f}% hold "
                     f"{np.mean([agg(p, k, 'hold') for p in PHASES]) * 100:+.0f}% fall {np.mean([agg(p, k, 'fall') for p in PHASES]) * 100:.0f}% "
                     f"| vs line by phase {'  '.join(cells)} -> {'PASS' if ok else 'fail'}")
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n")
    print("\n" + txt)


if __name__ == "__main__":
    main()
