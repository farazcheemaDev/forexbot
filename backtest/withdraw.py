"""WHAT CAN I WITHDRAW EACH MONTH? - the months, not the year.

Asked 2026-09-24: "monthly profit, how much can I expect that I can withdraw". The year figures
(typical $584 for the triple alone, $736 for the final mix; logs/final_anchor.txt) assume every
dollar stays in and compounds. Withdrawing stops the compounding, and this book makes its money in
a few large months, so the monthly picture has to be measured, not divided out of the year.

BOOKS (deployed grid, 10 orderings, entry-sized, 10x guard)
    bot alone   the triple (tight + time stop + 7 units)
    final mix   trend at 70% + 21-day equity anchor + breadth sleeve (real $221) + 0.5 x
                market-neutral (doc 14)
MONTHS: every calendar month's return, from month-end equity. "Safer" applies the repo's hindsight
haircut to up-months only (expectations.haircut(x, 1)); down-months stay RAW.
WITHDRAWAL PLANS, simulated on every 12-month stretch of history with the safer monthly returns,
starting from $221:
    A  at each month end, take out everything above $221 (the $221 keeps working, nothing compounds)
    B  at each month end, take out half of that month's profit, if there was one
Reported: dollars taken out over 12 months, the monthly average of that, and the balance left.

REGISTERED PREDICTION (2026-09-24, before running): the typical month for the final mix is a small
gain (+2% to +5%). Plan A takes out ~$15-30 a month on average over a year, and in about a third of
the 12-month stretches it takes out almost nothing for the first several months.

    python -m backtest.withdraw
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.dd_fixes import CAP, CUT, SEEDS, anchor, decompose, sim  # noqa: E402
from backtest.expectations import haircut, month_ends  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def plans(months):
    """months: sequence of monthly multiples (safer). Returns (A withdrawn, A end, B withdrawn, B end)."""
    bal, out_a = CAP, 0.0
    for m in months:
        bal *= m
        if bal > CAP:
            out_a += bal - CAP; bal = CAP
    end_a = bal
    bal, out_b = CAP, 0.0
    for m in months:
        prev = bal
        bal *= m
        if bal > prev:
            take = 0.5 * (bal - prev); out_b += take; bal -= take
    return out_a, end_a, out_b, bal


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    rows = decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))

    def book(sd, which):
        if which == "bot alone":
            return sim(rows, bn, bv, sd)
        c = sim(rows, bn, bv, sd, g=0.7, size_fn=anchor(21))
        r = c.pct_change().fillna(0.0)
        r = r + 0.5 * mn_d.reindex(r.index).fillna(0.0) + sleeve.reindex(r.index).fillna(0.0)
        return (1 + r).cumprod()

    for which in ("bot alone", "final mix"):
        for span, t0 in (("last 2 years (from 2024-09)", pd.Timestamp(CUT)), ("all 6 years", None)):
            raw, safe, A, AE, B, BE = [], [], [], [], [], []
            for sd in SEEDS:
                c = book(sd, which)
                me = month_ends(c)
                m = (me / me.shift(1)).dropna()
                if t0 is not None:
                    m = m[m.index >= t0]
                s = np.array([haircut(x, 1) if x > 1 else x for x in m.to_numpy()])
                raw.append(m.to_numpy()); safe.append(s)
                for i in range(len(s) - 11):
                    a, ae, b, be = plans(s[i:i + 12])
                    A.append(a); AE.append(ae); B.append(b); BE.append(be)
            raw, safe = np.concatenate(raw), np.concatenate(safe)
            A, AE, B, BE = map(np.array, (A, AE, B, BE))
            print(f"\n=== {which.upper()} - {span}")
            print(f"  a month, % (safer: up-months haircut, down-months raw):")
            print(f"    typical (median) {np.median(safe)*100-100:+.1f}%   average {safe.mean()*100-100:+.1f}%   "
                  f"bad month (1 in 4) {np.percentile(safe, 25)*100-100:+.1f}%   good month (1 in 4) "
                  f"{np.percentile(safe, 75)*100-100:+.1f}%   months up {(safe > 1).mean()*100:.0f}%   worst {safe.min()*100-100:+.0f}%")
            print(f"    on $221: typical month ${CAP*(np.median(safe)-1):+.0f}, bad month ${CAP*(np.percentile(safe, 25)-1):+.0f}, "
                  f"good month ${CAP*(np.percentile(safe, 75)-1):+.0f}")
            print(f"  PLAN A (take out everything above $221 each month), over 12 months:")
            print(f"    taken out: typical ${np.median(A):,.0f} (= ${np.median(A)/12:,.0f}/month), bad year (1 in 4) "
                  f"${np.percentile(A, 25):,.0f}, good year ${np.percentile(A, 75):,.0f}; nothing at all in "
                  f"{(A < 1).mean()*100:.0f}% of years; account ends below $221 in {(AE < CAP - 0.5).mean()*100:.0f}%")
            print(f"  PLAN B (take out half of each month's profit), over 12 months:")
            print(f"    taken out: typical ${np.median(B):,.0f} (= ${np.median(B)/12:,.0f}/month), bad year "
                  f"${np.percentile(B, 25):,.0f}; balance left: typical ${np.median(BE):,.0f}, "
                  f"below $221 in {(BE < CAP).mean()*100:.0f}%")


if __name__ == "__main__":
    main()
