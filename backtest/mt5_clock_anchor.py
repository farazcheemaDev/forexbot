"""WHICH CLOCK MOVED? - MT5's own bar labels, checked against the US cash open.

WHY THIS EXISTS (a review of his_strategy.md s35, 2026-10-01)
    s35 proposes that the trader's January-March statement times are one hour off, and
    backtest/his_clock_check.py tests it by finding, per period, the offset at which his points
    match the USTECm move from MT5. That test is good - but it measures the RELATIVE offset between
    two clocks: his statement's and MT5's. It cannot say which of the two moved. These read the same:

        (a) his statement is UTC+4 before the EU clock change and UTC+5 after, MT5's labels are UTC;
        (b) his statement is UTC+5 throughout, and MT5's labels carry a one-hour change in winter.

    For the copy-delay test that does not matter - only the relative alignment does. For anything
    compared against an OUTSIDE clock it decides the answer: s28 (the ForexFactory news calendar),
    s29 (Trump's posts), s27 (Binance order flow), and s35's own "10 of 19 winter trades fall before
    the New York open". Under (a) those must be re-run at the corrected hour; under (b) they stand,
    and every winter MT5 read in s17-s34 is what has to be shifted instead.

THE ANCHOR
    The US cash open, 09:30 New York time, puts a volatility jump into NASDAQ prices that no feed
    can hide. It sits at 14:30 UTC under EST (before 2026-03-08) and 13:30 UTC under EDT (from
    2026-03-08). The EU change on 2026-03-29 does not touch it. So the time-of-day at which MT5's
    5-minute bars jump, in each of s35's three periods, reads MT5's clock directly - independent of
    the trader, his statement and his broker.

    The 5-minute bars (strategy_analysis/data/USTECm_5m_400d.json, fetched 2026-09-16) are the only
    cache reaching back to January. Their bar label is the bar's OPEN, so the open bar is labelled
    14:30 / 13:30 if the labels are UTC.

REGISTERED PREDICTION (2026-10-01, before running)
    Exness runs its MT5 servers on UTC, so:
      * before 08 Mar:  the open bar is labelled 14:30
      * 08-29 Mar:      13:30   <- the window that separates the US change from the EU change
      * after 29 Mar:   13:30
    That is reading (a): MT5's labels are UTC, the seasonal hour is in his statement, and s35's
    correction applies to the statement - so s27-s29 need re-running if s35 is confirmed.
    If instead the open bar's label moves on 29 Mar (14:30, 14:30, 13:30), MT5's labels carry the
    EU change and reading (b) holds. Any other pattern means the labels are something else again,
    and both his_clock_check.py and every winter MT5 read have to be re-examined.

    python -m backtest.mt5_clock_anchor
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_clock_check import EU_DST, PERIODS, US_DST  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BARS = ROOT / "strategy_analysis" / "data" / "USTECm_5m_400d.json"
START, END = pd.Timestamp("2026-01-02"), pd.Timestamp("2026-06-30")


def load() -> pd.DataFrame:
    d = pd.DataFrame(json.load(open(BARS)))
    d["t"] = pd.to_datetime(d["t"], unit="ms")
    d = d[(d.t >= START) & (d.t < END) & (d.t.dt.weekday < 5)].copy()
    d["rng"] = (d.h - d.l) / d.c * 1e4                     # bar range, basis points
    d["tod"] = d.t.dt.strftime("%H:%M")
    d["period"] = np.where(d.t < US_DST, PERIODS[0], np.where(d.t < EU_DST, PERIODS[1], PERIODS[2]))
    return d


def jump_profile(g: pd.DataFrame) -> pd.Series:
    """Median range per time of day, divided by the median of the hour before it: the open is the
    bar where activity steps UP against what came just before, not merely the busiest bar."""
    med = g.groupby("tod").rng.median()
    idx = pd.to_datetime(med.index, format="%H:%M")
    s = pd.Series(med.to_numpy(), index=idx).sort_index()
    prev = s.shift(1).rolling(12, min_periods=6).median()
    return (s / prev).dropna()


def main():
    d = load()
    print(f"MT5 USTECm 5-minute bars, weekdays {START:%Y-%m-%d} .. {END:%Y-%m-%d}, label = bar OPEN")
    print("a 09:30 New York open is labelled 14:30 (EST, before 08 Mar) or 13:30 (EDT) if MT5 is UTC\n")
    print(f"  {'period':<16}{'days':>6}{'open bar (biggest step-up)':>28}{'x vs prior hour':>17}"
          f"{'  14:30 x':>10}{'  13:30 x':>10}")
    found = {}
    for p in PERIODS:
        g = d[d.period == p]
        if g.t.dt.date.nunique() < 3:
            continue
        j = jump_profile(g)
        # only look where a US open can be: 11:00-17:00 on any plausible label
        w = j[(j.index.hour >= 11) & (j.index.hour < 17)]
        top = w.idxmax()
        found[p] = f"{top:%H:%M}"
        a = w.get(pd.Timestamp("1900-01-01 14:30"), np.nan)
        b = w.get(pd.Timestamp("1900-01-01 13:30"), np.nan)
        print(f"  {p:<16}{g.t.dt.date.nunique():>6}{'':>8}{top:%H:%M}{'':>15}{w.max():>16.2f}x"
              f"{a:>9.2f}x{b:>9.2f}x")
    print()
    print("  the three runner-up step-ups per period (a second spike would show a mixed clock):")
    for p in PERIODS:
        g = d[d.period == p]
        if g.t.dt.date.nunique() < 3:
            continue
        w = jump_profile(g)
        w = w[(w.index.hour >= 11) & (w.index.hour < 17)].sort_values(ascending=False).head(4)
        print(f"    {p:<16}" + "   ".join(f"{t:%H:%M} {v:.2f}x" for t, v in w.items()))

    print()
    pat = tuple(found.get(p) for p in PERIODS)
    if pat == ("14:30", "13:30", "13:30"):
        print("  READING (a): MT5's labels are UTC in all three periods - the open follows the US change on")
        print("  08 Mar and ignores the EU one. If his_clock_check.py finds UTC+4 in winter, the seasonal")
        print("  hour is in HIS STATEMENT, and s27-s29 (order flow, news, posts) must be re-run at it.")
    elif pat == ("14:30", "14:30", "13:30"):
        print("  READING (b): MT5's labels move on 29 Mar - the MARKET DATA carries the EU change. A winter")
        print("  UTC+4 from his_clock_check.py would then be MT5's hour, not his: shift the winter MT5")
        print("  reads, and s27-s29 stand as they are.")
    else:
        print(f"  NEITHER PATTERN: {pat}. MT5's winter labels are not what either reading assumes -")
        print("  re-examine every winter MT5 read before trusting his_clock_check.py's offsets.")


if __name__ == "__main__":
    main()
