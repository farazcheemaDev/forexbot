"""DOES MAX_UNITS=7 STACK WITH THE TIME STOP? - one check the units finding left open.

pyramid_params.py (commit 0214658) found MAX_UNITS=7 beats 5 against the TIGHT book: +1.30%/mo
tune, +1.07% holdout, 10/10 orderings, both halves on all four bar grids, and a matched-risk
control showing it is not leverage in disguise. It was forked as paper book #6.

The recommended book is TIGHT + TIME STOP (paper book #5), not tight alone. The two rules could
interact: the time stop closes longs still under +2R after 100 bars, and units 6-7 are added at
+10R / +12R. They act on different positions, so they should add - but "should" is what a test
is for.

Same corrected engine and paired method as pyramid_params.py / graveyard_rescore.py: real entry
times, funding per unit, entry-sized compounding, 1000h gate, 10 orderings, 0.30% risk.

REGISTERED PREDICTION (before running): 7 units adds +0.9 to +1.3 %/mo on BOTH halves on top of
tight + time stop, 10/10 orderings each, with the worst month within 2 points of TSTOP's.

    python -m backtest.units_on_tstop
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.btc_dial import score  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.graveyard_rescore import rows  # noqa: E402

TS = (100, 2.0)


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    books = {"main": rows(),
             "tight": rows(tight=True),
             "tight + 7 units": rows(tight=True, max_units=7),
             "tight + time stop (TSTOP)": rows(tight=True, time_stop=TS),
             "tight + time stop + 7 units": rows(tight=True, time_stop=TS, max_units=7)}
    S = {k: score(v, bear, cut) for k, v in books.items()}
    print("corrected engine, entry-sized, 0.30% risk, 1000h gate, 10 orderings | %/mo = CAGR/3; DD, worst raw\n")
    print(f"  {'book':<30}{'TUNE':>8}{'DD':>5}{'worst':>8}{'HOLD':>8}{'DD':>5}{'worst':>8}")
    for k, R_ in S.items():
        print(f"  {k:<30}{R_['tune'][:,0].mean():>+7.2f}%{R_['tune'][:,1].mean():>4.0f}%"
              f"{R_['tune'][:,2].mean():>+7.1f}%{R_['hold'][:,0].mean():>+7.2f}%"
              f"{R_['hold'][:,1].mean():>4.0f}%{R_['hold'][:,2].mean():>+7.1f}%")
    print("\n  PAIRED, same orderings:")
    for a, b in (("tight + 7 units", "tight"),
                 ("tight + time stop + 7 units", "tight + time stop (TSTOP)"),
                 ("tight + time stop + 7 units", "main")):
        parts = []
        for half in ("tune", "hold"):
            d = S[a][half][:, 0] - S[b][half][:, 0]
            se = d.std(ddof=1) / np.sqrt(len(d))
            parts.append(f"{half} {d.mean():+.2f} +- {se:.2f} (t {d.mean() / se if se else 0:+.1f}, "
                         f"{int((d > 0).sum())}/{len(d)} wins)")
        print(f"    {a}  vs  {b}:  " + "   ".join(parts))


if __name__ == "__main__":
    main()
