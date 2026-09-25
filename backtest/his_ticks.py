"""HIS NASDAQ ENTRIES AT THE TICK LEVEL - what the price did in the SECONDS before he entered.

Two things prompted it (2026-09-25):
  - The user: "find which pause he joins... something you are missing to check".
  - His entry timestamps (to the second, broker statement): 17 of 46 NASDAQ entries fall 10-19 seconds
    into a minute against 7.7 expected (p ~ 1e-4; his gold entries and his exits are uniform). A trader
    who acts ~10-15 s after a 1-minute candle opens is deciding INSIDE the candle, which 1-minute bars
    cannot show - every bar-based encoding of him (his_strategy.md s17-24) entered a whole bar late.
The Exness MT5 terminal serves USTECm tick history (bid/ask to the millisecond) back to early 2026, so
for every entry with ticks: the mid-price on a 1-second grid from 30 minutes before to 15 minutes after,
SIGN-ALIGNED (a sell flipped, so + is always his way) and relative to the price at his entry second
(a constant futures basis cancels). Also the tick rate (quote updates per second - the tape's speed)
and the spread.

What is looked for: the path of the last 60 seconds (does he join a burst, or enter after a stall?),
the move of the CURRENT 1-minute candle from its open to his entry second, the previous candle's
direction, and whether the tape speeds up before he enters. The tick rate is compared with the SAME
clock second on 15 other days (time-of-day matched, so the 09:30 / 11:00 rush does not pose as a signal).

REGISTERED PREDICTION (2026-09-25, before running): in the 10-20 seconds before his entry the price
moves 1-3 points HIS WAY inside a fresh 1-minute candle whose predecessor went against him (the pause);
the tick rate in the last 30 s is above the same clock time on other days (median ratio > 1.3).

    python -m backtest.his_ticks
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GMT = 5.0
PRE, POST = 1800, 900
OFFS = (-600, -300, -120, -60, -30, -20, -15, -10, -5, -2, 0, 5, 10, 30, 60, 120, 300, 600)


def ticks(mt5, sym, a, b):
    # MT5 reads a NAIVE datetime as local time; the timestamps here are naive UTC, so say so
    t = mt5.copy_ticks_range(sym, a.tz_localize("UTC").to_pydatetime(), b.tz_localize("UTC").to_pydatetime(),
                             mt5.COPY_TICKS_ALL)
    if t is None or not len(t):
        return None
    d = pd.DataFrame(t)
    d["ts"] = pd.to_datetime(d.time_msc, unit="ms")
    d = d[(d.bid > 0) & (d.ask > 0)]
    d["mid"] = (d.bid + d.ask) / 2
    d["spr"] = d.ask - d.bid
    return d


def per_second(d, a, n):
    g = d.set_index("ts")
    sec = (g.index - a).total_seconds().astype(int)
    mid = pd.Series(g.mid.to_numpy(), index=sec).groupby(level=0).last().reindex(range(n)).ffill()
    cnt = pd.Series(1, index=sec).groupby(level=0).sum().reindex(range(n)).fillna(0)
    spr = pd.Series(g.spr.to_numpy(), index=sec).groupby(level=0).mean().reindex(range(n)).ffill()
    return mid.to_numpy(), cnt.to_numpy(), spr.to_numpy()


def main():
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x["sgn"] = np.where(x.side == "BUY", 1, -1)
    rows, paths, rates = [], [], []
    rng = np.random.default_rng(0)
    for r in x.itertuples():
        a, b = r.utc - pd.Timedelta(seconds=PRE), r.utc + pd.Timedelta(seconds=POST)
        d = ticks(mt5, "USTECm", a, b)
        if d is None or len(d) < 500:
            continue
        mid, cnt, spr = per_second(d, a, PRE + POST)
        if np.isnan(mid[PRE]) or np.isnan(mid[PRE - 600]):
            continue
        p = r.sgn * (mid - mid[PRE])                               # + = his way, 0 at his entry second
        paths.append(p)
        sec_in_min = r.utc.second
        cur_open = mid[PRE - sec_in_min]                            # price at this minute's first second
        prev_open = mid[PRE - sec_in_min - 60]
        # the same clock second on 15 other trading days, for the tape's speed
        ctrl = []
        for k in rng.choice(np.r_[np.arange(-60, -1), np.arange(1, 60)], 25, replace=False):
            ca = a + pd.Timedelta(days=int(k))
            if ca.weekday() >= 5:
                continue
            dd = ticks(mt5, "USTECm", ca + pd.Timedelta(seconds=PRE - 60), ca + pd.Timedelta(seconds=PRE))
            if dd is not None and len(dd) > 20:
                ctrl.append(len(dd))
            if len(ctrl) >= 15:
                break
        rec = dict(t=r.utc, side=r.side, net=r.net, sec=sec_in_min,
                   cur_candle=r.sgn * (mid[PRE] - cur_open), prev_candle=r.sgn * (cur_open - prev_open),
                   last10=r.sgn * (mid[PRE] - mid[PRE - 10]), last30=r.sgn * (mid[PRE] - mid[PRE - 30]),
                   last60=r.sgn * (mid[PRE] - mid[PRE - 60]), last300=r.sgn * (mid[PRE] - mid[PRE - 300]),
                   fwd60=p[PRE + 60], fwd300=p[PRE + 300], rate60=cnt[PRE - 60:PRE].sum(),
                   rate_ctrl=np.median(ctrl) if ctrl else np.nan, spread=spr[PRE],
                   base_rate=cnt[PRE - 1800:PRE - 600].sum() / 20)
        rows.append(rec)
        rates.append(cnt)
    mt5.shutdown()
    R = pd.DataFrame(rows)
    P = np.array(paths)
    print(f"{len(R)} of {len(x)} NASDAQ entries have USTECm ticks (history starts ~2026-02). Points, SIGN-ALIGNED "
          f"(+ = his way), relative to his entry second.\n")
    print("PATH (median / mean across entries) at seconds from his entry:")
    print("  " + "  ".join(f"{o:+d}s" for o in OFFS))
    print("  median " + "  ".join(f"{np.nanmedian(P[:, PRE + o]):+.1f}" for o in OFFS))
    print("  mean   " + "  ".join(f"{np.nanmean(P[:, PRE + o]):+.1f}" for o in OFFS))
    print("  share moving his way before entry (price at entry above the price N s earlier):")
    for o in (-10, -30, -60, -300):
        v = -P[:, PRE + o]
        print(f"    last {-o:>3}s: {np.mean(v > 0)*100:.0f}% his way, {np.mean(v < 0)*100:.0f}% against, median {np.median(v):+.1f} pts")
    print("\nTHE 1-MINUTE CANDLE he entered in, at his entry second:")
    print(f"  seconds into the minute: median {R.sec.median():.0f}")
    print(f"  CURRENT candle open -> entry: median {R.cur_candle.median():+.2f} pts, his way in "
          f"{(R.cur_candle > 0).mean()*100:.0f}%, against in {(R.cur_candle < 0).mean()*100:.0f}%")
    print(f"  PREVIOUS candle: his way in {(R.prev_candle > 0).mean()*100:.0f}%, against in "
          f"{(R.prev_candle < 0).mean()*100:.0f}% (median {R.prev_candle.median():+.2f})")
    both = ((R.prev_candle < 0) & (R.cur_candle > 0)).mean()
    print(f"  previous AGAINST him and current WITH him (pause -> resume inside the candle): {both*100:.0f}%")
    print("\nTHE TAPE: quote updates in the 60 s before entry vs the same clock minute on ~15 other days")
    ratio = R.rate60 / R.rate_ctrl
    print(f"  median ratio {ratio.median():.2f}, mean {ratio.mean():.2f}, above 1 in {(ratio > 1).mean()*100:.0f}%, "
          f"above 1.5 in {(ratio > 1.5).mean()*100:.0f}%")
    print(f"  spread at entry: median {R.spread.median():.2f} pts")
    print("\nAFTER his entry (the part he captures): median +60s {:.1f}, +300s {:.1f} pts".format(R.fwd60.median(), R.fwd300.median()))
    R.to_csv(ROOT / "logs" / "his_ticks.csv", index=False)
    np.save(ROOT / "logs" / "his_ticks_paths.npy", P)
    print("\nper-entry detail: logs/his_ticks.csv")


if __name__ == "__main__":
    main()
