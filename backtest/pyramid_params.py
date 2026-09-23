"""THE PYRAMID'S OWN PARAMETERS - where the profit comes from, never swept on the fixed engine.

WHY THESE THREE AND WHY NOW
    This book makes its money from adds: a position that works gets four more units funded by
    profit that already exists, and pyramid.py found that gave more return AND less drawdown at
    matched risk - unusual, and the largest single improvement in the project's history. So the
    two numbers that govern it matter more than most:

        ADD_EVERY = 2.0   add one unit every 2R of gain
        MAX_UNITS = 5     stop at five

    Neither has been swept on the corrected engine. BE_AT = 3.0 (stop to entry at +3R) was last
    swept in ddcontrol.py, which predates funding, causal entry times and entry-sized
    compounding - and all three of those changed every number in this repo.

    The immediate reason to look: ATR(14) turned out to be a genuine parameter sitting at its
    optimum on both halves (doc 11 part 7). If ADD_EVERY or MAX_UNITS is sitting OFF its optimum,
    that is return available for nothing.

THE BAR, and it is deliberately hard
    Baseline is the TIGHT book, not main - tight is the validated config and the leading paper
    book, so an improvement has to be an improvement on top of it.

    Stage 1: beat tight on BOTH halves, paired within ordering, |t| > 2 on both.
    Stage 2: anything that clears stage 1 then faces the phase test, because doc 11 part 5
    measured 1.3-2.4 %/mo of bar-phase noise and a 1%/mo "edge" on one grid is nothing.

    Nothing is adopted from stage 1 alone. The holdout is mined out; only a result that survives
    both halves AND four independent bar grids means anything.

REGISTERED PREDICTIONS (before running, 2026-09-24)
    1. ADD_EVERY: 2.0 is near-optimal. Tighter (1.0-1.5R) stacks size onto trades that have
       barely moved, so worse drawdown and roughly flat return; wider (3-4R) gets fewer units
       onto the runners that pay for everything.
    2. MAX_UNITS: 7 beats 5 on RETURN with worse drawdown, because the biggest winners are where
       the units land. 10 is indistinguishable from 7 - few positions ever get that far.
    3. BE_AT: 3.0 is near-optimal. Removing it entirely raises return and drawdown together
       (ddcontrol.py had 12 of 12 cells reducing drawdown); 2R is too tight and clips runners.
    4. OVERALL: none of the fourteen cells clears stage 1. That is what almost every sweep in
       this project has found, and the prior should be stated rather than discovered.

    python -m backtest.pyramid_params
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bar_phase import daily, rows_for_phase, stats, worst_month  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402

SEEDS = tuple(range(10))
GRID = {
    "ADD_EVERY": ("add_every", (1.0, 1.5, 2.0, 3.0, 4.0), 2.0),
    "MAX_UNITS": ("max_units", (3, 4, 5, 7, 10), 5),
    "BE_AT": ("be_at", (2.0, 3.0, 5.0, 1e9), 3.0),
}


def series(kw, bear, cut):
    """Per-ordering holdout and tune stats for one config on the deployed grid."""
    rows = rows_for_phase(0, tight=True, **kw)
    out = {}
    for win, sl in (("tune", dict(t_to=cut)), ("hold", dict(t_from=cut))):
        vals = []
        for sd in SEEDS:
            r = daily(rows, bear, sd, **sl)
            if r is None:
                continue
            st = stats(r)
            st["wm"] = worst_month(r)
            vals.append(st)
        out[win] = vals
    return out


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print(f"baseline = TIGHT book on the deployed grid | {len(SEEDS)} orderings | "
          f"3x haircut | tune < {cut:%Y-%m-%d} <= holdout")
    print("bar: beats tight on BOTH halves with |t| > 2, then the phase test\n")

    base = series({}, bear, cut)
    b_t = np.array([x["hpm"] for x in base["tune"]])
    b_h = np.array([x["hpm"] for x in base["hold"]])
    print(f"  TIGHT baseline: tune {b_t.mean():+.2f}%/mo   holdout {b_h.mean():+.2f}%/mo   "
          f"worst month {np.mean([x['wm'] for x in base['hold']]):+.1f}%")

    survivors = []
    for name, (kwname, values, deployed) in GRID.items():
        print()
        print(f"{name}  (deployed {deployed:g})")
        print(f"  {'value':>9}{'TUNE/mo':>10}{'diff':>8}{'t':>7}{'w':>6}"
              f"{'HOLD/mo':>10}{'diff':>8}{'t':>7}{'w':>6}{'HOLD wm':>9}")
        for v in values:
            if v == deployed:
                print(f"  {v:>9.6g}{b_t.mean():>+9.2f}%{'-':>8}{'-':>7}{'-':>6}"
                      f"{b_h.mean():>+9.2f}%{'-':>8}{'-':>7}{'-':>6}"
                      f"{np.mean([x['wm'] for x in base['hold']]):>+8.1f}  <- DEPLOYED")
                continue
            s = series({kwname: v}, bear, cut)
            cells, clears = "", True
            for win, b in (("tune", b_t), ("hold", b_h)):
                a = np.array([x["hpm"] for x in s[win]])
                d = a - b
                se = d.std(ddof=1) / len(d) ** 0.5
                t = d.mean() / se if se else np.nan
                cells += f"{a.mean():>+9.2f}%{d.mean():>+7.2f}%{t:>+7.2f}{(d > 0).sum():>4}/{len(d)}"
                clears &= (d.mean() > 0 and abs(t) > 2)
            wm = np.mean([x["wm"] for x in s["hold"]])
            print(f"  {v:>9.6g}{cells}{wm:>+8.1f}" + ("   CLEARS STAGE 1" if clears else ""))
            if clears:
                survivors.append((name, kwname, v))

    print()
    if not survivors:
        print("  Nothing clears stage 1, so there is no stage 2. Prediction 4 held: the deployed")
        print("  pyramid settings are not leaving return on the table, and the reason to believe")
        print("  that is a sweep that was registered to expect exactly this and then found it.")
        return
    print(f"  {len(survivors)} cell(s) clear stage 1 -> the phase test, because 1%/mo on one")
    print("  grid is inside the 1.3-2.4 %/mo of bar-phase noise measured in doc 11 part 5.")
    from backtest.bar_phase import variant_across_phases
    for name, kwname, v in survivors:
        variant_across_phases(bear, cut, f"TIGHT + {name}={v:g} vs TIGHT",
                              dict(tight=True), dict(tight=True, **{kwname: v}))


if __name__ == "__main__":
    main()
