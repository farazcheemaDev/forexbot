"""'CME GAPS ALWAYS FILL' - the most repeated retail BTC claim, as a trade with a stop.

THE CLAIM
    CME Bitcoin futures stop trading Friday afternoon (US) and reopen Sunday evening. BTC
    trades all weekend, so the futures reopen at a different price - a "gap". The claim is
    that price returns to fill it, most of the time. That the LEVEL is often revisited is
    arithmetic (a random walk revisits nearby levels constantly); whether fading it makes
    money after a stop is the only question worth asking.

THE TRADE
    Friday CME close = BTCUSDT price at 21:00 UTC (20:00 in US daylight time); reopen = price
    at 23:00 UTC Sunday (22:00 in daylight time). If |gap| >= 1%, fade it at the reopen:
    target = the Friday close, stop = the same distance on the other side, exit after 5 days
    if neither is hit. Hourly bars; if target and stop are both inside one bar, the STOP is
    assumed first. 12bp.
    PLACEBO: the identical rule on the Wednesday 21:00 -> Thursday 23:00 UTC move - a gap
    with no market closed in it. If the weekend version is no better, "CME gap" is just
    short-term reversal, which doc 02 has killed seven times.

REGISTERED PREDICTION: fill rate 60-80% within 5 days, mean P&L per trade within +-0.2%
of zero, no better than the placebo. Dead.

    python -m backtest.cme_gap
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PERPS = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
FEE = 12 / 1e4
MIN_GAP = 0.01


def us_dst(t):
    """US daylight time: second Sunday of March to first Sunday of November."""
    y = t.year
    mar = pd.Timestamp(y, 3, 8) + pd.Timedelta(days=(6 - pd.Timestamp(y, 3, 8).dayofweek) % 7)
    nov = pd.Timestamp(y, 11, 1) + pd.Timedelta(days=(6 - pd.Timestamp(y, 11, 1).dayofweek) % 7)
    return mar <= t < nov


def trades(h, close_dow, close_hr, open_dow, open_hr):
    """close_* / open_* in STANDARD time (UTC); one hour earlier under US daylight time."""
    o = h.set_index("time")
    out = []
    days = pd.date_range(h.time.iloc[0].normalize(), h.time.iloc[-1].normalize(), freq="D")
    for d in days[days.dayofweek == close_dow]:
        shift = 1 if us_dst(d) else 0
        tc = d + pd.Timedelta(hours=close_hr - shift)
        to = d + pd.Timedelta(days=(open_dow - close_dow) % 7, hours=open_hr - shift)
        if tc not in o.index or to not in o.index:
            continue
        pc, po = float(o.at[tc, "open"]), float(o.at[to, "open"])
        gap = po / pc - 1
        if abs(gap) < MIN_GAP:
            continue
        side = -np.sign(gap)                      # fade toward the Friday close
        tgt, stp = pc, po * (1 + np.sign(gap) * abs(gap))
        seg = o.loc[to: to + pd.Timedelta(days=5)]
        res, filled = None, False
        for _, b in seg.iterrows():
            hit_stop = (b.high >= stp) if side < 0 else (b.low <= stp)
            hit_tgt = (b.low <= tgt) if side < 0 else (b.high >= tgt)
            if hit_stop:
                res = side * (stp / po - 1); break
            if hit_tgt:
                res = side * (tgt / po - 1); filled = True; break
        if res is None:
            res = side * (float(seg.close.iloc[-1]) / po - 1)
        out.append(dict(t=to, gap=gap, ret=res - FEE, filled=filled))
    return pd.DataFrame(out)


def main():
    h = pd.read_csv(PERPS / "BTCUSDT_1h.csv.gz", usecols=["time", "open", "high", "low", "close"])
    h["time"] = pd.to_datetime(h["time"]).astype("datetime64[ns]")
    W = trades(h, 4, 21, 6, 23)          # Friday 21:00 -> Sunday 23:00 UTC (standard time)
    P = trades(h, 2, 21, 3, 23)          # placebo: Wednesday 21:00 -> Thursday 23:00
    for lab, X in (("WEEKEND (CME gap)", W), ("PLACEBO (Wed->Thu)", P)):
        cut = X.t.quantile(0.6)
        print(f"{lab}: {len(X)} gaps >= {MIN_GAP*100:.0f}%  filled {X.filled.mean()*100:.0f}%  "
              f"mean {X.ret.mean()*100:+.2f}%  median {X.ret.median()*100:+.2f}%  "
              f"t {X.ret.mean() / X.ret.std() * np.sqrt(len(X)):+.2f}  "
              f"tune {X.ret[X.t < cut].mean()*100:+.2f}% hold {X.ret[X.t >= cut].mean()*100:+.2f}%")
        print("   by year: " + "  ".join(f"{y}: {v.mean()*100:+.2f}% (n{len(v)})"
                                        for y, v in X.ret.groupby(X.t.dt.year)))


if __name__ == "__main__":
    main()
