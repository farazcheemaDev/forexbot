"""THE PAUSE HE JOINS, AS A RULE, ON EVERY SECOND OF APR-SEP 2026 - real bid/ask from MT5 ticks.

Found (2026-09-25, backtest/his_ticks.py + the his-vs-market check): his 26 NASDAQ trades from April on
are the clean ones - every fill inside the real market's range, basis steady to 0.5 points - while
January-March fills often sat where the real market never traded (he banked more than the market
ever offered in ~10 of 20). On the 26 clean ones, second by second, sign-aligned:
  - over the 5 minutes before entry the price moved ~+5 points HIS way (62% of entries);
  - in the last 30 seconds it moved ~2 points AGAINST him (62%), inside the current 1-minute candle;
  - after entry: +6 points in 60 s median, +7 reached within 3 minutes in 81%, -7 first in only 12%.
So the pause he joins is a small counter-move INSIDE a young 5-minute move, entered on the dip itself -
not after the resumption, which is where every earlier encoding (his_micro.py included) entered.

RULE, evaluated every second from 10:30 to 15:30 ET on every trading day 2026-04-01..2026-09-14:
  trend    mid now - mid 300 s ago >= +X points (long) or <= -X (short); X = 3 / 5 / 8
  dip      mid now - mid 30 s ago <= -Y (long) / >= +Y (short); Y = 1 / 2 / 3
  entry    at the ASK (long) / BID (short) of that second
  exit     +7 points on the exit side of the book (BID for a long) -> take it; -20 points -> stop;
           else out after 300 s. Every price is a real quote, so the spread is paid twice, exactly.
  one position at a time; 60 s wait after an exit.
3 x 3 = 9 cells, both halves of the period (split at the median date), Holm across the 9. A random-entry
control in the same hours with the same exit sets the baseline.

REGISTERED PREDICTION (2026-09-25, before running): the rule beats random entries by +1 to +2 points a
trade gross, and still loses after the real spread (~2 points); 0 of 9 cells pass. His own clean trades
reach +7 first in ~81% - the rule will reach it first in ~55-60%.

    python -m backtest.his_pullback_ticks
"""
from __future__ import annotations

import pickle
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "ustec_sec_cache.pkl"
TGT, STOP, TMAX, WAIT = 7.0, 20.0, 300, 60


def day_seconds(mt5, day):
    """1-second grid of last bid/ask for 10:25-15:35 ET on `day` (New York date)."""
    a = pd.Timestamp(day).tz_localize("America/New_York") + pd.Timedelta(hours=10, minutes=25)
    b = a + pd.Timedelta(hours=5, minutes=10)
    t = mt5.copy_ticks_range("USTECm", a.tz_convert("UTC").to_pydatetime(), b.tz_convert("UTC").to_pydatetime(),
                             mt5.COPY_TICKS_ALL)
    if t is None or len(t) < 2000:
        return None
    d = pd.DataFrame(t)
    d = d[(d.bid > 0) & (d.ask > 0)]
    sec = ((pd.to_datetime(d.time_msc, unit="ms") - a.tz_convert("UTC").tz_localize(None)).dt.total_seconds()).astype(int)
    n = int((b - a).total_seconds())
    bid = pd.Series(d.bid.to_numpy(), index=sec).groupby(level=0).last().reindex(range(n)).ffill().to_numpy()
    ask = pd.Series(d.ask.to_numpy(), index=sec).groupby(level=0).last().reindex(range(n)).ffill().to_numpy()
    return bid, ask


def simulate(bid, ask, X, Y, rng=None):
    """Trades on one day's grid. rng given -> random entries at the same rate instead of the rule."""
    mid = (bid + ask) / 2
    n = len(mid)
    out, i = [], 300 + 300                       # start at 10:35 (need 300 s of history), trade from 10:30+
    while i < n - TMAX - 1:
        if np.isnan(mid[i]) or np.isnan(mid[i - 300]) or np.isnan(mid[i - 30]):
            i += 1; continue
        if rng is None:
            up, dn = mid[i] - mid[i - 300] >= X and mid[i] - mid[i - 30] <= -Y, \
                mid[i] - mid[i - 300] <= -X and mid[i] - mid[i - 30] >= Y
            side = 1 if up else (-1 if dn else 0)
        else:
            side = rng.choice((-1, 1)) if rng.random() < 1 / 400 else 0
        if side == 0:
            i += 1; continue
        e = ask[i] if side == 1 else bid[i]
        res = None
        for j in range(i + 1, i + TMAX + 1):
            px = bid[j] if side == 1 else ask[j]              # the side he would close on
            pnl = side * (px - e)
            if pnl >= TGT:
                res = (TGT if pnl < TGT + 5 else pnl, j - i); break   # a gap through the target fills there
            if pnl <= -STOP:
                res = (pnl, j - i); break
        if res is None:
            px = bid[i + TMAX] if side == 1 else ask[i + TMAX]
            res = (side * (px - e), TMAX)
        out.append((i, side, res[0], res[1], ask[i] - bid[i]))
        i += res[1] + WAIT
    return out


def main():
    import MetaTrader5 as mt5
    cache = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    days = [d for d in pd.bdate_range("2026-04-01", "2026-09-14")]
    need = [d for d in days if d not in cache]
    if need:
        assert mt5.initialize(), mt5.last_error()
        for k, d in enumerate(need):
            cache[d] = day_seconds(mt5, d)
            if k % 20 == 19:
                CACHE.write_bytes(pickle.dumps(cache)); print(f"  fetched {k + 1}/{len(need)} days", flush=True)
        mt5.shutdown()
        CACHE.write_bytes(pickle.dumps(cache))
    days = [d for d in days if cache.get(d) is not None]
    mid_day = days[len(days) // 2]
    print(f"{len(days)} trading days with ticks, 2026-04-01..2026-09-14; 10:30-15:30 ET; real bid/ask; "
          f"target +{TGT:.0f}, stop -{STOP:.0f}, {TMAX}s max.\n")
    res = []
    for X in (3.0, 5.0, 8.0):
        for Y in (1.0, 2.0, 3.0):
            T = []
            for d in days:
                T += [(d,) + t for t in simulate(*cache[d], X, Y)]
            if len(T) < 30:
                continue
            f = pd.DataFrame(T, columns=["day", "i", "side", "pts", "secs", "spread"])
            se = f.pts.std(ddof=1) / np.sqrt(len(f))
            p = 1 - 0.5 * (1 + erf((f.pts.mean() / se) / sqrt(2)))
            res.append(dict(cell=f"trend {X:.0f} / dip {Y:.0f}", n=len(f), pts=f.pts.mean(), t=f.pts.mean() / se, p=p,
                            a=f[f.day < mid_day].pts.mean(), b=f[f.day >= mid_day].pts.mean(),
                            win=(f.pts > 0).mean() * 100, tgt=(f.pts >= TGT).mean() * 100, stop=(f.pts <= -STOP).mean() * 100,
                            spread=f.spread.median(), per_day=len(f) / len(days)))
    rng = np.random.default_rng(0)
    C = []
    for d in days:
        C += [(d,) + t for t in simulate(*cache[d], 0, 0, rng=rng)]
    c = pd.DataFrame(C, columns=["day", "i", "side", "pts", "secs", "spread"])
    order = sorted(range(len(res)), key=lambda i: res[i]["p"])
    for rank, i in enumerate(order):
        res[i]["holm"] = min(1.0, max(res[j]["p"] * (len(res) - q) for q, j in enumerate(order[:rank + 1])))
    print(f"{'cell':<18}{'n':>6}{'/day':>6}{'pts/trade':>11}{'t':>7}{'Holm p':>8}{'1st half':>10}{'2nd half':>10}"
          f"{'win%':>6}{'+7 hit':>8}{'stop':>6}  PASS?")
    for x in res:
        ok = x["holm"] < 0.05 and x["a"] > 0 and x["b"] > 0
        print(f"{x['cell']:<18}{x['n']:>6}{x['per_day']:>6.1f}{x['pts']:>+11.2f}{x['t']:>+7.2f}{x['holm']:>8.3f}"
              f"{x['a']:>+10.2f}{x['b']:>+10.2f}{x['win']:>6.0f}{x['tgt']:>7.0f}%{x['stop']:>5.0f}%  {'PASS' if ok else 'fail'}")
    print(f"{'RANDOM entries':<18}{len(c):>6}{len(c)/len(days):>6.1f}{c.pts.mean():>+11.2f}{'':>7}{'':>8}"
          f"{c[c.day < mid_day].pts.mean():>+10.2f}{c[c.day >= mid_day].pts.mean():>+10.2f}{(c.pts > 0).mean()*100:>6.0f}"
          f"{(c.pts >= TGT).mean()*100:>7.0f}%{(c.pts <= -STOP).mean()*100:>5.0f}%")
    print(f"\nAll points are AFTER the real spread (bought at the ask, sold at the bid); median spread "
          f"{c.spread.median():.2f} pts. His 26 clean trades: +7 reached first in ~81%.")


if __name__ == "__main__":
    main()
