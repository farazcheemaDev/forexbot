"""What a MONTH looks like for the triple book (tight + time stop + 7 units) from $221.

Monthly returns from book_stats.path (entry-sized, corrected engine, funding, real entry times),
10 orderings pooled. RAW - these are the 12 hand-picked coins, so the upside carries the
hindsight premium; the 3x haircut applies to annual growth and cannot be put on one month
honestly, so the best months are shown raw with that warning.

    python -m backtest.month_dist
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.book_stats import CAP, SEEDS, path  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.graveyard_rescore import rows  # noqa: E402


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    books = {"main (deployed)": rows(),
             "triple (tight + time stop + 7 units)": rows(tight=True, time_stop=(100, 2.0), max_units=7)}
    for lab, rs in books.items():
        for wlab, t_from in (("holdout 2024-08 ->", cut), ("full 2020 ->", None)):
            M = []
            for sd in SEEDS:
                c, _T = path(rs, bear, sd, t_from)
                m = c.resample("ME").last()
                m = pd.concat([pd.Series([CAP], index=[m.index[0] - pd.offsets.MonthEnd()]), m])
                M.append((m / m.shift(1) - 1).dropna())
            allm = pd.concat(M) * 100
            per = pd.concat(M, axis=1).mean(axis=1) * 100
            q = np.percentile(allm, [5, 25, 50, 75, 95])
            print(f"\n{lab} | {wlab} | $221 start, {len(SEEDS)} orderings pooled, RAW %/month")
            print(f"  best month {allm.max():+.0f}%   worst {allm.min():+.0f}%   median {q[2]:+.1f}%")
            print(f"  5th {q[0]:+.0f}%  25th {q[1]:+.1f}%  75th {q[3]:+.1f}%  95th {q[4]:+.0f}%   "
                  f"months up {(allm > 0).mean()*100:.0f}%   months > +20%: {(allm > 20).mean()*100:.0f}%   "
                  f"months > +50%: {(allm > 50).mean()*100:.0f}%")
            print("  five best months (average across orderings): " + "  ".join(
                f"{d:%Y-%m} {v:+.0f}%" for d, v in per.sort_values(ascending=False).head(5).items()))


if __name__ == "__main__":
    main()
