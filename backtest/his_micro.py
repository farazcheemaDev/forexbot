"""HIS METHOD AS READ OFF THE 1-MINUTE CHARTS, ENCODED AND TESTED.

Reading his trades on 1-minute bars (backtest/his_charts.py, logs/his_charts_05-08.png) showed one
pattern clearly, most of all on 2026-09-14: once the day's short-term structure turns (lower highs
after a top), he sells every small bounce - four shorts in 16 minutes, 7-17 points each, size rising
0.20 -> 0.25 - and on 2026-08-07 he bought the first pullback of a V-bounce. In words: READ THE
1-MINUTE TREND, JOIN IT RIGHT AFTER A SMALL PAUSE, TAKE 5-10 POINTS. Earlier encodings of him
(his_strategy.md s17-22) measured 5-minute and 60-minute features; the 1-minute structure never was.

RULE (USTECm 1-minute bars, 2026-06-04 to 2026-09-15, 10:30-15:30 ET - his busiest hours):
  trend    UP when the 20-bar EMA is above where it was 10 bars ago and the close is above the EMA;
           DOWN mirrored.
  pause    the last k bars (k = 1 / 2 / 3) closed AGAINST the trend,
  resume   and the current bar closes WITH it -> enter at the NEXT bar's open (nothing read after
           the signal bar).
  day      (variant D) longs only above the 09:30 open, shorts only below it.
  exit     target T points (T = 5 / 7 / 10; a limit, filled only in a bar AFTER the entry bar),
           stop 20 points (his average loss is 19.6; filled at the worse of the stop and the bar's
           open), else the close of the 5th bar. One position at a time.
  costs    2.2 points round trip (USTECm spread, 0.77bp at ~29,000; his own broker is ~2 points).
3 pauses x 2 day filters x 3 targets = 18 cells; a cell must be positive AFTER costs on both
halves of the period; Holm across the 18.

REGISTERED PREDICTION (2026-09-25, before running): gross within +-0.5 points a trade in every cell
(his own is +9.17 gross), net about -2 points; 0 of 18 pass. Which would say again that his edge is in
WHICH pauses he takes, not in the pattern.

    python -m backtest.his_micro
"""
from __future__ import annotations

import json
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COST = 2.2
STOP = 20.0


def load():
    d = pd.DataFrame(json.load(open(ROOT / "strategy_analysis" / "data" / "USTECm_1m_400d.json")))
    d["t"] = pd.to_datetime(d.t, unit="ms")
    d = d.set_index("t").sort_index()
    et = d.index.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
    d["et"] = et
    d["mod"] = et.hour * 60 + et.minute
    d["day"] = et.normalize()
    return d


def run(d, k, day_filter, target):
    o, h, l, c = (d[x].to_numpy(float) for x in ("o", "h", "l", "c"))
    ema = pd.Series(c).ewm(span=20, adjust=False).mean().to_numpy()
    mod, day = d["mod"].to_numpy(), d["day"].to_numpy()
    t = d.index
    # the 09:30 open per day
    op = {}
    for i in np.flatnonzero(mod == 570):
        op[day[i]] = o[i]
    up_bar, dn_bar = c > o, c < o
    out, i, n = [], 30, len(c)
    while i < n - 7:
        if not (630 <= mod[i] < 930) or (t[i + 1] - t[i]) != pd.Timedelta(minutes=1):
            i += 1; continue
        trend = 1 if (ema[i] > ema[i - 10] and c[i] > ema[i]) else (-1 if (ema[i] < ema[i - 10] and c[i] < ema[i]) else 0)
        if trend == 0:
            i += 1; continue
        against = dn_bar if trend == 1 else up_bar
        withb = up_bar if trend == 1 else dn_bar
        if not (withb[i] and all(against[i - j] for j in range(1, k + 1))):
            i += 1; continue
        if day_filter:
            ref = op.get(day[i])
            if ref is None or (trend == 1 and c[i] <= ref) or (trend == -1 and c[i] >= ref):
                i += 1; continue
        e = o[i + 1]
        px = None
        for j in range(i + 1, min(i + 6, n)):
            if (t[j] - t[i]) > pd.Timedelta(minutes=10):
                px = c[j - 1]; break
            stop_hit = (l[j] <= e - STOP) if trend == 1 else (h[j] >= e + STOP)
            if stop_hit:
                px = min(e - STOP, o[j]) if trend == 1 else max(e + STOP, o[j]); break
            if j > i + 1 and ((h[j] >= e + target) if trend == 1 else (l[j] <= e - target)):
                px = e + trend * target; break
        if px is None:
            px = c[min(i + 5, n - 1)]
        out.append((t[i], trend * (px - e)))
        i += 6                                                    # one position at a time
    return out


def main():
    d = load()
    res = []
    for k in (1, 2, 3):
        for df in (False, True):
            for T in (5.0, 7.0, 10.0):
                r = run(d, k, df, T)
                if len(r) < 30:
                    continue
                tt = pd.DatetimeIndex([x[0] for x in r]); g = np.array([x[1] for x in r])
                net = g - COST
                cut = tt.sort_values()[len(tt) // 2]
                se = net.std(ddof=1) / np.sqrt(len(net))
                p = 1 - 0.5 * (1 + erf((net.mean() / se) / sqrt(2)))
                res.append(dict(cell=f"pause {k}, {'day filter' if df else 'no filter'}, target {T:.0f}", n=len(g),
                                gross=g.mean(), net=net.mean(), t=net.mean() / se, p=p, a=net[tt < cut].mean(),
                                b=net[tt >= cut].mean(), win=(net > 0).mean() * 100))
    order = sorted(range(len(res)), key=lambda i: res[i]["p"])
    for rank, i in enumerate(order):
        res[i]["holm"] = min(1.0, max(res[j]["p"] * (len(res) - q) for q, j in enumerate(order[:rank + 1])))
    print(f"1-MINUTE TREND + PAUSE + RESUME on USTECm, 10:30-15:30 ET, {d.index[0]:%Y-%m-%d} .. {d.index[-1]:%Y-%m-%d}; "
          f"points per trade, cost {COST} pts. His own record: +9.17 gross, +7.17 net of 2 pts, 95.7% wins.")
    print(f"{'cell':<36}{'n':>6}{'gross':>8}{'net':>8}{'t':>7}{'Holm p':>8}{'1st half':>10}{'2nd half':>10}{'win%':>7}  PASS?")
    for x in res:
        ok = x["holm"] < 0.05 and x["a"] > 0 and x["b"] > 0
        print(f"{x['cell']:<36}{x['n']:>6}{x['gross']:>+8.2f}{x['net']:>+8.2f}{x['t']:>+7.2f}{x['holm']:>8.3f}"
              f"{x['a']:>+10.2f}{x['b']:>+10.2f}{x['win']:>7.0f}  {'PASS' if ok else 'fail'}")


if __name__ == "__main__":
    main()
