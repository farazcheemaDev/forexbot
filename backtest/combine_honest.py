"""combine.py AGAIN, WITH THE TREND BOOK CHARGED WHAT THE MARKET-NEUTRAL BOOK WAS CHARGED.

combine.py (doc 10) compared a market-neutral book that pays and receives ACTUAL funding
against a trend book that was never charged any (funding_cost.py), with the trend book's
4h/12h entries stamped at their bar label rather than their real entry time
(causal_t0.py). Both errors flatter the trend side of the comparison. Same method,
same conventions (daily trend returns / 3 hindsight, weekly compounding, drawdowns
comparable only to each other), corrected inputs.

REGISTERED PREDICTION: correlation stays under +0.15; the trend book's return falls
~1-2%/mo in this table's units; every mix's Sharpe rises relative to trend-alone, and the
75/25 mix's return gap to trend-alone shrinks from 1.2 points to under 1.

    python -m backtest.combine_honest
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.combine import MIXES, SEEDS, mn_weekly, stats  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402


def trend_weekly(rows):
    bear = regimes()[1000]
    acc = []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
        acc.append(evaluate(o, bear)["daily"] / blend.HINDSIGHT)
    return pd.concat(acc, axis=1).mean(axis=1).resample("W").sum()


def main():
    raw = rows_for(BASE_RULES)
    old = trend_weekly(raw)
    new = trend_weekly(charged(real_t0(short_funding(long_funding(raw)))))
    mn, _C = mn_weekly()
    for lab, bl in (("AS IN DOC 10 (no funding, label t0)", old),
                    ("CORRECTED (funding charged, real t0)", new)):
        j = pd.DataFrame({"blend": bl, "mn": mn}).dropna()
        print(f"\n{lab}: {len(j)} weeks, correlation {j.blend.corr(j.mn):+.3f}")
        print(f"  {'book':<26}{'/mo':>9}{'/yr':>9}{'DD*':>7}{'Sharpe':>8}{'wks up':>8}")
        for lb, x in [("trend blend alone", j.blend), ("market-neutral alone", j.mn)] + \
                [(f"blend {(1-w)*100:.0f}% / MN {w*100:.0f}%", j.blend * (1 - w) + j.mn * w)
                 for w in MIXES]:
            mo, ann, dd, sh, up = stats(x)
            print(f"  {lb:<26}{mo:>+8.2f}%{ann:>+8.0f}%{dd:>6.0f}%{sh:>8.2f}{up:>7.0f}%")
        yrs = sorted(set(j.index.year))
        print("  by calendar year (sum of weekly returns, %):  " + "  ".join(
            f"{y}: T{j.blend[j.index.year == y].sum()*100:+.0f}/M{j.mn[j.index.year == y].sum()*100:+.0f}"
            for y in yrs))

    # OVERLAY: a futures account shares one margin pool, so the second book need not take
    # capital FROM the first - it can run on top of it. The trend book averages ~1.2x gross
    # and the market-neutral book is 1.0x gross at k=1 with ~zero net exposure, so the
    # constraint is margin and drawdown, not cash. Trend at full size + k x MN.
    #
    # ENTRY-SIZED rows (added after compounding.py): evaluate()'s daily-sum compounding
    # implicitly resizes open trend positions to current equity, which the bot never does,
    # and it overstates the trend book ~2x. The market-neutral book rebalances its whole
    # basket weekly, so ITS compounding is achievable as simulated. The fair pairing is
    # entry-sized trend against weekly-rebalanced MN.
    tight = trend_weekly(charged(real_t0(short_funding(long_funding(
        rows_for(BASE_RULES, tight=True))))))
    from backtest.mtm_sizing import attach_prices, simulate as entry_sized
    bear = regimes()[1000]

    def entry_weekly(rows):
        acc = [entry_sized(rows, bear, sd, "realised", want_curve=True).pct_change().fillna(0.0)
               / blend.HINDSIGHT for sd in SEEDS]
        return pd.concat(acc, axis=1).fillna(0.0).mean(axis=1).resample("W").sum()

    main_es = entry_weekly(charged(real_t0(short_funding(long_funding(attach_prices(raw))))))
    tight_es = entry_weekly(charged(real_t0(short_funding(long_funding(attach_prices(
        rows_for(BASE_RULES, tight=True)))))))
    for lab, bl in (("OVERLAY on the corrected MAIN book (daily-sum)", new),
                    ("OVERLAY on the corrected TIGHT book (daily-sum)", tight),
                    ("OVERLAY on the MAIN book, ENTRY-SIZED", main_es),
                    ("OVERLAY on the TIGHT book, ENTRY-SIZED", tight_es)):
        j = pd.DataFrame({"blend": bl, "mn": mn}).dropna()
        print(f"\n{lab} (trend at full size + k x market-neutral)")
        print(f"  {'k':<26}{'/mo':>9}{'/yr':>9}{'DD*':>7}{'Sharpe':>8}{'wks up':>8}")
        for k in (0.0, 0.25, 0.5, 1.0):
            mo, ann, dd, sh, up = stats(j.blend + k * j.mn)
            print(f"  {'k = %.2f' % k:<26}{mo:>+8.2f}%{ann:>+8.0f}%{dd:>6.0f}%{sh:>8.2f}{up:>7.0f}%")


if __name__ == "__main__":
    main()
