"""How much does $221 become in ONE YEAR? - every 12-month window, main vs the triple book.

Entry-sized equity paths from book_stats.path (corrected engine: funding, real entry times),
10 orderings, every overlapping 12-month window (month-end to month-end). Shown RAW and with the
3x hindsight haircut (the 12 coins were picked knowing how they turned out; the haircut divides
the annual growth rate by 3). Losses are never haircut: the "ended below $221" and worst-year
columns are raw.

    python -m backtest.one_year
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
from backtest.expectations import haircut, month_ends, windows  # noqa: E402
from backtest.graveyard_rescore import rows  # noqa: E402


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    books = {"main (deployed today)": rows(),
             "triple (tight + time stop + 7 units)": rows(tight=True, time_stop=(100, 2.0), max_units=7)}
    print(f"${CAP:.0f} after 12 months - every overlapping window, {len(SEEDS)} orderings\n")
    for lab, rs in books.items():
        for wlab, t_from in (("recent (holdout starts, 2024-08 ->)", cut), ("all history (2020 ->)", None)):
            w = np.concatenate([windows(month_ends(path(rs, bear, sd, t_from)[0]), 12) for sd in SEEDS])
            h = np.array([haircut(x, 12) for x in w])
            p = lambda a, q: CAP * np.percentile(a, q)
            print(f"  {lab} | {wlab} | {len(w)} windows")
            print(f"    after the 3x haircut: bad (25th) ${p(h, 25):,.0f}   typical ${p(h, 50):,.0f}   "
                  f"good (75th) ${p(h, 75):,.0f}")
            print(f"    raw:                  bad (25th) ${p(w, 25):,.0f}   typical ${p(w, 50):,.0f}   "
                  f"good (75th) ${p(w, 75):,.0f}   best ${CAP * w.max():,.0f}")
            print(f"    ended below ${CAP:.0f}: {(w < 1).mean()*100:.0f}%   worst year ${CAP * w.min():,.0f} (raw)\n")


if __name__ == "__main__":
    main()
