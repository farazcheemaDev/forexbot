"""THE TWO SURVIVORS OF dd_fixes.py, AGAINST THE STANDARD THE 7-UNIT CHANGE HAD TO MEET.

dd_fixes.py (logs/dd_fixes.txt) tried 56 fixes for the triple book's halving against the
uniform-bet-size frontier. Two beat it on both halves, each by a hair, with neighbours that fail:
    1b anchor 30d          size from min(equity, its 30-day average)   excess +0.13 / +0.71 %/mo
    2a streak 1h N20 0.8   halve 1h longs when 16 of the last 20 closed 1h long signals lost
                                                                        excess +0.51 / +0.26 %/mo
One pass in 56 is what luck produces. The check:
  * 20 orderings instead of 10;
  * the excess measured PER ORDERING against that ordering's own frontier (baseline at g
    0.4..1.0), so it has a standard error and a win count;
  * every neighbour: anchor k 14/21/30/45/60; streak N 15/20/25/30 x f 0.75/0.8/0.85;
  * all FOUR bar phases (bar_phase.rows_for_phase, 4h/12h grids shifted), the test that
    promoted the tight exit and 7 units.
PASS = mean excess > 0 on both halves on all four phases, for the named config AND most of its
neighbours.

REGISTERED PREDICTION (2026-09-24, before running): neither passes. The anchor's tune excess
(+0.13) is inside one standard error; the streak's neighbours already straddle zero.

    python -m backtest.dd_fix_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.compounding import summarize  # noqa: E402
from backtest.dd_fixes import CUT, anchor, decompose, sim, streak_gate  # noqa: E402

SEEDS = tuple(range(20))
GS = (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


def run_half(rows, bn, bv, sd, half, **kw):
    c = sim(rows, bn, bv, sd, **({"t_to": CUT} if half == "tune" else {"t_from": CUT}), **kw)
    return summarize(c)[0], float((1 - c / c.cummax()).max() * 100)


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    cands = [(f"anchor {k}d", lambda rows, k=k: dict(size_fn=anchor(k))) for k in (14, 21, 30, 45, 60)]
    cands += [(f"streak 1h N{N} {f:g} half", lambda rows, N=N, f=f: dict(gate_fn=streak_gate(rows, "1h", N, f, "half")))
              for N in (15, 20, 25, 30) for f in (0.75, 0.8, 0.85)]
    res = {name: {p: {} for p in range(4)} for name, _ in cands}
    for p in range(4):
        rows = decompose(rows_for_phase(p, tight=True, time_stop=(100, 2.0), max_units=7))
        for half in ("tune", "hold"):
            fr = {sd: [run_half(rows, bn, bv, sd, half, g=g) for g in GS] for sd in SEEDS}
            for name, mk in cands:
                kw = mk(rows)
                ex = []
                for sd in SEEDS:
                    r, d = run_half(rows, bn, bv, sd, half, **kw)
                    dds = np.array([x[1] for x in fr[sd]]); rets = np.array([x[0] for x in fr[sd]])
                    o = np.argsort(dds)
                    ex.append(r - np.interp(d, dds[o], rets[o], left=np.nan, right=np.nan))
                res[name][p][half] = np.array(ex)
        print(f"phase {p} done", flush=True)

    print("\nEXCESS over the same ordering's uniform-bet-size frontier, %/mo (haircut): "
          "mean +- se (wins/20); nan = drawdown outside the frontier's range")
    print(f"  {'config':<24}" + "".join(f"{'phase ' + str(p) + ' TUNE':>22}{'HOLD':>20}" for p in range(4)) + "   verdict")
    for name, _ in cands:
        cells, ok = "", True
        for p in range(4):
            for half in ("tune", "hold"):
                x = res[name][p][half]
                v = x[np.isfinite(x)]
                if len(v) < 10:
                    cells += f"{'n/a':>20}"; ok = False; continue
                m, se = v.mean(), v.std(ddof=1) / np.sqrt(len(v))
                cells += f"{m:>+10.2f}+-{se:.2f} ({(v > 0).sum():>2})"
                ok &= m > 0
        print(f"  {name:<24}{cells}   {'PASS all 4 phases, both halves' if ok else 'fails'}")


if __name__ == "__main__":
    main()
