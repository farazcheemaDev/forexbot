"""Score a NEW trade of his from the app's History screen, in one command (2026-10-15).

No recorder is needed: Exness keeps its full tick history, so MT5 can pull the seconds around any past trade. Type the
trade as the History screen shows it (its clock is UTC+5, like his statements - his_strategy s62):

    python his_score_new.py 2026-10-13 SELL 20:24:30 30698.25 20:25:54 30686.25

It prints, and appends to logs/his_new_trades.csv (one row per trade, re-runs overwrite the same trade):
  basis      his price - the Exness cash mid at his second (~190-210 for the Dec contract; a jump means a wrong clock)
  match      the market's move over his hold vs the points he banked (they match to the cent at the right clock)
  race       +7 before -7 on the mid from his second, and how many seconds it took
  pre5       the market's move his way in the 5 s before his click (his usual: ~0 or slightly against)
  calm       quote rate / movement over the last 30 s vs the day so far (his 5 losing races came in fast, chased moments)
Needs the MT5 terminal running. Read-only: no orders, no account.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "logs" / "his_new_trades.csv"
CLOCK = 5                                  # the app's History / statement clock, UTC+5


def score(date, side, ot, op, ct, cp):
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    o = pd.Timestamp(f"{date} {ot}") - pd.Timedelta(hours=CLOCK)
    c = pd.Timestamp(f"{date} {ct}") - pd.Timedelta(hours=CLOCK)
    tk = mt5.copy_ticks_range("USTECm", (o - pd.Timedelta(minutes=10)).tz_localize("UTC").to_pydatetime(),
                              (o + pd.Timedelta(minutes=15)).tz_localize("UTC").to_pydatetime(), mt5.COPY_TICKS_ALL)
    mt5.shutdown()
    if tk is None or len(tk) < 10:
        sys.exit("no Exness ticks around that time - is MT5 running, and is the time in the History clock (UTC+5)?")
    t = pd.to_datetime(tk["time_msc"], unit="ms").values
    mid = (tk["bid"] + tk["ask"]) / 2
    s = 1 if side.upper() == "BUY" else -1

    def at(x):
        return mid[np.searchsorted(t, np.datetime64(x), "right") - 1]
    i0 = np.searchsorted(t, np.datetime64(o), "right") - 1
    path, tt = s * (mid[i0:] - mid[i0]), (t[i0:] - t[i0]) / np.timedelta64(1, "s")
    up, dn = np.flatnonzero(path >= 7), np.flatnonzero(path <= -7)
    race = "WON" if len(up) and (not len(dn) or up[0] < dn[0]) else ("LOST" if len(dn) else "open")
    secs = tt[up[0]] if race == "WON" else (tt[dn[0]] if race == "LOST" else np.nan)
    w30 = (t >= np.datetime64(o - pd.Timedelta(seconds=30))) & (t <= np.datetime64(o))
    w600 = (t >= np.datetime64(o - pd.Timedelta(minutes=10))) & (t <= np.datetime64(o))
    calm = (w30.sum() / 30) / max(w600.sum() / 600, 1e-9)
    row = dict(date=date, side=side.upper(), open=ot, open_px=op, close=ct, close_px=cp, ny_time=f"{o.tz_localize('UTC').tz_convert('America/New_York'):%H:%M:%S}",
               basis=round(op - at(o), 2), market_move=round(s * (at(c) - at(o)), 2), banked=round(s * (cp - op), 2),
               race=race, race_secs=round(float(secs), 1) if np.isfinite(secs) else "", pre5=round(s * (at(o) - at(o - pd.Timedelta(seconds=5))), 2),
               quote_pace_30s_vs_10min=round(calm, 2))
    return row


def main(argv):
    if len(argv) != 6:
        sys.exit(__doc__)
    date, side, ot, op, ct, cp = argv
    row = score(date, side, ot, float(op), ct, float(cp))
    for k, v in row.items():
        print(f"  {k:<26} {v}")
    rows = list(csv.DictReader(OUT.open())) if OUT.exists() else []
    rows = [r for r in rows if not (r["date"] == row["date"] and r["open"] == row["open"])] + [{k: str(v) for k, v in row.items()}]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader()
        w.writerows(rows)
    print(f"  saved to {OUT.relative_to(ROOT)} ({len(rows)} new trades so far)")


if __name__ == "__main__":
    main(sys.argv[1:])
