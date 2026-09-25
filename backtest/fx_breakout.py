"""THE ASIAN-RANGE BREAKOUT - the most common retail forex/gold strategy - at Exness costs.

After fx_anomalies.py (nine documented calendar/session effects, all dead after costs), the retail
playbook itself: mark the Asian session's range (00:00-07:00 UTC), and at the London open trade the
first break of it. Cause, as its users state it: London's open brings the day's first real liquidity
and the overnight range is where stops cluster, so the first break runs.

RULES (15-minute bars, 2022-06 to 2026-09 from MT5, UTC):
  range     high / low of 00:00-07:00 UTC; skipped if narrower than 0.1 ATR(14 days) or wider than 1.5
  entry     from 07:00 to 12:00 UTC, a stop order one spread beyond the range high (long) or low
            (short); the first one touched wins, the other is cancelled; one trade a day
  stop      S1 the other side of the range | S2 the middle of the range
  exit      X1 target 1R | X2 target 2R | X3 no target, out at 20:00 UTC
  fills     a bar that reaches both the stop and the target counts as the STOP (pessimistic); a bar
            that opens beyond the entry fills at its open
  costs     the measured round-trip spread (forex.py), no swap (out the same day)
Instruments: EURUSD, GBPUSD, USDJPY, XAUUSD. 6 rule variants x 4 = 24 cells, Holm across all 24,
and a cell must be positive after costs on BOTH halves (60/40 by date).

REGISTERED PREDICTION (2026-09-25, before running): no FX major passes; gold is positive gross and
holdout-only (its 2024-26 bull market); zero of 24 cells pass. Win rates near 35-50%, mean R within
+-0.05 of zero before costs on the majors.

    python -m backtest.fx_breakout
"""
from __future__ import annotations

import json
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data"
SPREAD_BP = {"EURUSD": 1.39, "GBPUSD": 1.48, "USDJPY": 1.29, "XAUUSD": 1.22}
HOLD = 0.60


def load(sym):
    d = pd.DataFrame(json.load(open(DATA / f"{sym}m_15m_2400d.json")))
    d["t"] = pd.to_datetime(d.t, unit="ms")
    return d.set_index("t")[["o", "h", "l", "c"]]


def trades(d, sym, stop_mode, exit_mode):
    sp = SPREAD_BP[sym] / 1e4
    daily = d.resample("D").agg({"h": "max", "l": "min", "c": "last"}).dropna()
    tr = (daily.h - daily.l).rolling(14).mean().shift(1)            # daily ATR, known before the day
    out = []
    for day, g in d.groupby(d.index.normalize()):
        atr = tr.get(day)
        if atr is None or not np.isfinite(atr):
            continue
        a = g[g.index.hour < 7]
        s = g[(g.index.hour >= 7) & (g.index.hour < 20)]
        if len(a) < 20 or len(s) < 40:
            continue
        hi, lo = a.h.max(), a.l.min()
        w = hi - lo
        if w < 0.1 * atr or w > 1.5 * atr:
            continue
        mid = (hi + lo) / 2
        buf = hi * sp / 2
        long_px, short_px = hi + buf, lo - buf
        pos = None
        for t, b in s.iterrows():
            if pos is None:
                if t.hour >= 12:
                    break
                up, dn = b.h >= long_px, b.l <= short_px
                if up and dn:
                    break                                          # both in one bar: order unknown, skip
                if up or dn:
                    side = 1 if up else -1
                    entry = max(long_px, b.o) if up else min(short_px, b.o)
                    stop = (lo if up else hi) if stop_mode == "S1" else mid
                    risk = abs(entry - stop)
                    if risk <= 0:
                        break
                    tgt = None if exit_mode == "X3" else entry + side * risk * (1 if exit_mode == "X1" else 2)
                    pos = dict(side=side, entry=entry, stop=stop, risk=risk, tgt=tgt, t=t)
                    # the entry bar itself: a stop hit inside it counts (pessimistic), a target does not
                    if (side == 1 and b.l <= stop) or (side == -1 and b.h >= stop):
                        out.append((day, -1.0 - sp * entry / risk)); pos = "done"; break
                continue
            p = pos
            hit_stop = (b.l <= p["stop"]) if p["side"] == 1 else (b.h >= p["stop"])
            hit_tgt = p["tgt"] is not None and ((b.h >= p["tgt"]) if p["side"] == 1 else (b.l <= p["tgt"]))
            if hit_stop:
                px = min(p["stop"], b.o) if p["side"] == 1 else max(p["stop"], b.o)
            elif hit_tgt:
                px = p["tgt"]
            elif t.hour >= 19 and t.minute >= 45:
                px = b.c
            else:
                continue
            r = p["side"] * (px - p["entry"]) / p["risk"] - sp * p["entry"] / p["risk"]
            out.append((day, r)); pos = "done"; break
        if isinstance(pos, dict):                                   # still open at the data's end of day
            last = s.c.iloc[-1]
            out.append((day, pos["side"] * (last - pos["entry"]) / pos["risk"] - sp * pos["entry"] / pos["risk"]))
    return out


def main():
    res = []
    for sym in SPREAD_BP:
        d = load(sym.replace("USD", "USD") if sym != "XAUUSD" else "XAUUSD")
        for sm in ("S1", "S2"):
            for xm in ("X1", "X2", "X3"):
                T = trades(d, sym, sm, xm)
                if len(T) < 50:
                    continue
                t = pd.DatetimeIndex([x[0] for x in T]); r = np.array([x[1] for x in T])
                cut = t.sort_values()[int(len(t) * HOLD)]
                se = r.std(ddof=1) / np.sqrt(len(r))
                p = 1 - 0.5 * (1 + erf((r.mean() / se) / sqrt(2)))
                res.append(dict(cell=f"{sym} {sm} {xm}", n=len(r), mean=r.mean(), t=r.mean() / se, p=p,
                                tune=r[t < cut].mean(), hold=r[t >= cut].mean(), win=(r > 0).mean() * 100,
                                pf=r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf, yrs=(t.max() - t.min()).days / 365.25))
    order = sorted(range(len(res)), key=lambda i: res[i]["p"])
    for rank, i in enumerate(order):
        res[i]["holm"] = min(1.0, max(res[j]["p"] * (len(res) - k) for k, j in enumerate(order[:rank + 1])))
    print("ASIAN-RANGE BREAKOUT at the London open, 15m bars 2022-2026, after spread. R per trade.")
    print("S1 stop at the other side of the range, S2 at its middle; X1 target 1R, X2 2R, X3 out at 20:00 UTC.")
    print(f"{'cell':<18}{'n':>6}{'meanR':>8}{'t':>7}{'Holm p':>8}{'TUNE':>8}{'HOLD':>8}{'win%':>6}{'PF':>6}{'trades/yr':>10}  PASS?")
    for x in res:
        ok = x["holm"] < 0.05 and x["tune"] > 0 and x["hold"] > 0
        print(f"{x['cell']:<18}{x['n']:>6}{x['mean']:>+8.3f}{x['t']:>+7.2f}{x['holm']:>8.3f}{x['tune']:>+8.3f}"
              f"{x['hold']:>+8.3f}{x['win']:>6.0f}{x['pf']:>6.2f}{x['n']/x['yrs']:>10.0f}  {'PASS' if ok else 'fail'}")


if __name__ == "__main__":
    main()
