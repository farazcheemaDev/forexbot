"""expectations.py's planning numbers, re-run on the corrected engine AND the bot's real
compounding.

Doc 00 / CLAUDE.md quote, for $200 on the holdout: median month -0.83%, 57% of months lose,
median 12 months +58% ($316). Those came from expectations.py, which (a) stamps 4h/12h
entries at their bar label (causal_t0.py), (b) charges no funding (funding_cost.py), and
(c) compounds SEQUENTIALLY at each close through small_capital.simulate, which scales every
closing trade by equity it was never sized on (compounding.py). The bot fixes a position's
dollars at entry from closed-trade equity. So this uses mtm_sizing.simulate in 'realised'
mode, the entry-sized path that reproduces compounding.py exactly.

The venue minimum is not simulated: at $200 it rejects 0% of signals (small_capital.py).
Overlapping windows; upside haircut 3x, downside RAW (expectations.haircut's rule).

Printed twice: the sequential curves expectations.py used, for continuity, then the
entry-sized ones that are the planning numbers.

REGISTERED PREDICTION (made after compounding.py, before this ran): entry-sized 12-month
median on the holdout is well under the documented +58%; P(losing month) rises above 57%.

    python -m backtest.expectations_honest
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.expectations import haircut, month_ends, windows  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.mtm_sizing import attach_prices, simulate as entry_sized  # noqa: E402
from backtest.small_capital import price_maps, simulate as sequential  # noqa: E402

SEEDS = tuple(range(10))
CAP = 200


def table(lab, curves, cut):
    for wlab, sel in (("holdout", lambda c: c[c.index >= cut]), ("full", lambda c: c)):
        me = [month_ends(sel(c)) for c in curves]
        w1 = np.concatenate([windows(m, 1) for m in me])
        w12 = np.concatenate([windows(m, 12) for m in me])
        g1 = np.array([haircut(x, 1) for x in w1])
        g12 = np.array([haircut(x, 12) for x in w12])
        dd = float(np.mean([(1 - sel(c) / sel(c).cummax()).max() * 100 for c in curves]))
        print(f"  {lab:<40}{wlab:<9}{(np.median(g1)-1)*100:>+8.2f}%{(w1 < 1).mean()*100:>6.0f}%"
              f"{(w1.min()-1)*100:>+9.1f}%{(np.median(w12)-1)*100:>+9.0f}%"
              f"{(np.median(g12)-1)*100:>+9.0f}%{CAP*np.median(g12):>9,.0f}{dd:>7.0f}%")


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    raw = rows_for(BASE_RULES)
    main_c = charged(real_t0(short_funding(long_funding(attach_prices(raw)))))
    tight_c = charged(real_t0(short_funding(long_funding(attach_prices(
        rows_for(BASE_RULES, tight=True))))))
    print(f"${CAP} start, {len(SEEDS)} orderings, holdout from {cut:%Y-%m-%d}")
    print("med 1mo haircut; loses / worst mo / 12mo RAW / DD raw; 12mo hc = haircut; $ = haircut\n")
    print(f"  {'book':<40}{'window':<9}{'med 1mo':>9}{'loses':>7}{'worst mo':>10}"
          f"{'12mo RAW':>9}{'12mo hc':>9}{'$ 12mo':>9}{'DD raw':>8}")
    px, step = price_maps()
    table("SEQUENTIAL, as documented (label t0)",
          [sequential(raw, bear, px, step, CAP, 0.30, 12, sd)["curve"] for sd in SEEDS], cut)
    table("ENTRY-SIZED, main, corrected",
          [entry_sized(main_c, bear, sd, "realised", want_curve=True) for sd in SEEDS], cut)
    table("ENTRY-SIZED, tight, corrected",
          [entry_sized(tight_c, bear, sd, "realised", want_curve=True) for sd in SEEDS], cut)


if __name__ == "__main__":
    main()
