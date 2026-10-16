"""THE PLAIN-SIGHT DETAILS - his own trade list read line by line (2026-10-16)

The user: "see every peculiar detail; the missing pieces are hidden in front of us, not fancy stuff". No new data: the
statement's 46 NASDAQ trades, scored with the same +-7 race on the Exness mid as every other test (his_race_curve.race2).
READS    1. his entry hours on HIS clock (Pakistan, UTC+5 all year) against New York's
         2. race won by lot size relative to his previous 5 trades (does size carry confidence?)
         3. race won for the first trade of a sitting / a later trade on the same side / a later trade that FLIPS side
         4. the scratches (closed at +3 points or less) and the 2026-09-14 sitting, trade by trade (overlaps = hedging)
REGISTERED (informal, written before the run): 2 and 3 within 10 points of each other - size and order carry nothing.

RESULT (2026-10-16, logs/his_plain.txt)
    1. ON HIS CLOCK his entries sit at the same local hours all year: ~20:00-20:45 and ~23:15-00:15 Pakistan time. In New
       York terms that is 10:00-10:45 in winter and 11:00-11:45 in summer - the "11:00 New York" cluster (s49-s50) is his
       evening routine, not a market event; the US clock change moves the market under him, not him. 21 of 46 trades
       in PKT 19:45-21:00, 13 in 23:00-00:30, 12 elsewhere - 74% in 2.75 hours of his day.
    2-3. Size and order carry nothing (registered right): bigger than usual 87%, smaller 83%, usual 90%; first trade 88%,
       later same side 90%, later FLIPPED side 80%. He picks the side equally well every time.
    4. 2026-09-14: long 0.15 at 14:14 NY goes against him; he ADDS a long 0.20 lower (+5.25 on the add), then SELLS four
       times (0.20 -> 0.25) while still long - hedged - opens the last sell 2 s BEFORE closing the long at -31.75. The
       sells pay for it. That losing long WON the +-7 race on the mid: even his worst trade started right; the +7 was not
       banked. Scratches (+1.0..+3.5 points) on 02-20, 02-25, 02-27, 05-07: trades that did not go, closed flat.
       Floating P/L on the statement is 0.00 - no losers hidden as open positions.

    python -m backtest.his_plain
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

LOG = ROOT / "logs" / "his_plain.txt"


def main():
    x = TP.entries()
    ticks = pickle.loads(TP.TICKS.read_bytes())
    x["race"] = [race2(*ticks[r.d][:2], r.t, r.s, 600, 7, 7) if r.d in ticks else np.nan for r in x.itertuples()]
    x["pkt"] = x.utc + pd.Timedelta(hours=5)
    x["rel"] = x.lots / x.lots.shift(1).rolling(5, min_periods=2).median()
    gap = x.utc.diff().dt.total_seconds() / 60
    x["first"] = gap.isna() | (gap > 60)
    x["flip"] = (~x["first"]) & (x.s != x.s.shift(1))
    x["pts"] = (x.close_price - x.open_price) * x.s
    x["close"] = x.open_time + pd.to_timedelta((pd.to_datetime(x.close_time) - x.open_time).dt.total_seconds(), unit="s")
    out = [f"backtest/his_plain.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(x)} NASDAQ trades, "
           f"{x.race.notna().sum()} with Exness ticks", "", "1. ENTRY HOURS, his clock (UTC+5) vs New York"]
    for r in x.itertuples():
        out.append(f"   {r.et:%Y-%m-%d}  PKT {r.pkt:%H:%M}  NY {r.et:%H:%M}  {r.side:<4} {r.lots:.2f}  {r.pts:+7.2f} pts  "
                   f"race {'-' if np.isnan(r.race) else int(r.race)}  {'first' if r.first else ('FLIP' if r.flip else 'same')}")
    h = x.pkt.dt.hour + x.pkt.dt.minute / 60
    ev = ((h >= 19.75) & (h < 21)).sum()
    late = ((h >= 23) | (h < 0.5)).sum()
    out += [f"   PKT 19:45-21:00: {ev} trades; PKT 23:00-00:30: {late}; elsewhere {len(x) - ev - late}", "",
            "2-3. RACE WON BY SIZE AND ORDER"]
    v = x.dropna(subset=["race", "rel"])
    for lab, m in (("bigger than his usual", v.rel > 1), ("his usual size", v.rel == 1), ("smaller than usual", v.rel < 1)):
        out.append(f"   {lab:<24} n {m.sum():2d}  race won {v.race[m].mean() * 100:.0f}%")
    w = x.dropna(subset=["race"])
    for lab, m in (("first of a sitting", w["first"]), ("later, same side", ~w["first"] & ~w.flip), ("later, FLIPPED", w.flip)):
        out.append(f"   {lab:<24} n {m.sum():2d}  race won {w.race[m].mean() * 100:.0f}%  mean lots {w.lots[m].mean():.3f}")
    out += ["", "4. SCRATCHES (|pts| <= 3.5) and OVERLAPPING positions"]
    for r in x[x.pts.abs() <= 3.5].itertuples():
        out.append(f"   scratch {r.et:%Y-%m-%d %H:%M} NY  {r.side} {r.pts:+.2f}")
    ct = pd.to_datetime(x.close_time)
    for i in range(len(x)):
        ov = x[(x.open_time > x.open_time.iat[i]) & (x.open_time < ct.iat[i])]
        for r in ov.itertuples():
            out.append(f"   while {x.side.iat[i]} {x.lots.iat[i]:.2f} from {x.et.iat[i]:%m-%d %H:%M:%S} NY was open "
                       f"({x.pts.iat[i]:+.2f}): {r.side} {r.lots:.2f} at {r.et:%H:%M:%S} -> {r.pts:+.2f}")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
