"""THE LAST LEAD FROM HIS TICKS: NASDAQ LEADING THE S&P, THEN A MARKET-WIDE 30-SECOND DIP.

his_crossmarket.py, on his 26 clean entries (April on), ranked against the same clock second on 20 other
days: over the 5 minutes before entry NASDAQ out-moved the S&P 500 in his direction (S&P-minus-NASDAQ
rank 0.37, p < 0.05 uncorrected); over the last 30 seconds NASDAQ, the S&P and the Dow ALL moved
against him (ranks 0.35-0.39). his_pullback_ticks.py used NASDAQ's own path only and did no better than
random (-3.0 vs -2.9 points a trade). This adds the leadership condition.

RULE, every second 10:30-15:30 ET, 2026-04-01..2026-09-14, real USTECm bid/ask:
  lead    NASDAQ's 300 s return in the trade's direction exceeds the S&P's (US500m) by >= L
          (L = 0.01% / 0.02% / 0.04%), and NASDAQ's own 300 s move >= 3 points that way
  dip     both NASDAQ and the S&P moved AGAINST that direction over the last 30 s (NASDAQ >= 1 point)
  entry   ask (long) / bid (short); exit +7 on the exit side, -20 stop, 300 s max; one at a time
3 cells, Holm across them, both halves; random entries as the baseline (his_pullback_ticks.py).

REGISTERED PREDICTION (2026-09-25, before running): no better than random (~-2.9 points a trade after the
real spread); 0 of 3 pass. If a cell passes, look for the bug before believing it.

    python -m backtest.his_leadership_ticks
"""
from __future__ import annotations

import pickle
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_pullback_ticks import CACHE, STOP, TGT, TMAX, WAIT  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SPX_CACHE = ROOT / "strategy_analysis" / "data" / "us500_sec_cache.pkl"


def day_mid(mt5, sym, day):
    a = pd.Timestamp(day).tz_localize("America/New_York") + pd.Timedelta(hours=10, minutes=25)
    b = a + pd.Timedelta(hours=5, minutes=10)
    t = mt5.copy_ticks_range(sym, a.tz_convert("UTC").to_pydatetime(), b.tz_convert("UTC").to_pydatetime(),
                             mt5.COPY_TICKS_ALL)
    if t is None or len(t) < 500:
        return None
    d = pd.DataFrame(t)
    d = d[(d.bid > 0) & (d.ask > 0)]
    sec = ((pd.to_datetime(d.time_msc, unit="ms") - a.tz_convert("UTC").tz_localize(None)).dt.total_seconds()).astype(int)
    n = int((b - a).total_seconds())
    return pd.Series(((d.bid + d.ask) / 2).to_numpy(), index=sec).groupby(level=0).last().reindex(range(n)).ffill().to_numpy()


def simulate(bid, ask, spx, L):
    mid = (bid + ask) / 2
    n = len(mid)
    out, i = [], 600
    while i < n - TMAX - 1:
        if np.isnan(mid[i]) or np.isnan(mid[i - 300]) or np.isnan(spx[i]) or np.isnan(spx[i - 300]):
            i += 1; continue
        r_n, r_s = mid[i] / mid[i - 300] - 1, spx[i] / spx[i - 300] - 1
        side = 0
        for sgn in (1, -1):
            if (sgn * (r_n - r_s) >= L and sgn * (mid[i] - mid[i - 300]) >= 3
                    and sgn * (mid[i] - mid[i - 30]) <= -1 and sgn * (spx[i] - spx[i - 30]) < 0):
                side = sgn
        if side == 0:
            i += 1; continue
        e = ask[i] if side == 1 else bid[i]
        res = None
        for j in range(i + 1, i + TMAX + 1):
            pnl = side * ((bid[j] if side == 1 else ask[j]) - e)
            if pnl >= TGT:
                res = (TGT, j - i); break
            if pnl <= -STOP:
                res = (pnl, j - i); break
        if res is None:
            res = (side * ((bid[i + TMAX] if side == 1 else ask[i + TMAX]) - e), TMAX)
        out.append((i, side, res[0]))
        i += res[1] + WAIT
    return out


def main():
    import MetaTrader5 as mt5
    nq = pickle.loads(CACHE.read_bytes())
    spx = pickle.loads(SPX_CACHE.read_bytes()) if SPX_CACHE.exists() else {}
    days = [d for d in sorted(nq) if nq[d] is not None]
    need = [d for d in days if d not in spx]
    if need:
        assert mt5.initialize(), mt5.last_error()
        for d in need:
            spx[d] = day_mid(mt5, "US500m", d)
        mt5.shutdown()
        SPX_CACHE.write_bytes(pickle.dumps(spx))
    days = [d for d in days if spx.get(d) is not None]
    mid_day = days[len(days) // 2]
    print(f"{len(days)} days with both NASDAQ and S&P ticks; real bid/ask; +{TGT:.0f} / -{STOP:.0f} / {TMAX}s.\n")
    print(f"{'lead >= ':<10}{'n':>6}{'/day':>6}{'pts/trade':>11}{'t':>7}{'1st half':>10}{'2nd half':>10}{'win%':>6}{'+7 hit':>8}")
    res = []
    for L in (0.0001, 0.0002, 0.0004):
        T = []
        for d in days:
            bid, ask = nq[d]
            T += [(d,) + t for t in simulate(bid, ask, spx[d], L)]
        f = pd.DataFrame(T, columns=["day", "i", "side", "pts"])
        if len(f) < 20:
            print(f"{L*100:.2f}%: only {len(f)} trades"); continue
        se = f.pts.std(ddof=1) / np.sqrt(len(f))
        p = 1 - 0.5 * (1 + erf((f.pts.mean() / se) / sqrt(2)))
        res.append(p)
        print(f"{L*100:>7.2f}%  {len(f):>6}{len(f)/len(days):>6.1f}{f.pts.mean():>+11.2f}{f.pts.mean()/se:>+7.2f}"
              f"{f[f.day < mid_day].pts.mean():>+10.2f}{f[f.day >= mid_day].pts.mean():>+10.2f}{(f.pts > 0).mean()*100:>6.0f}"
              f"{(f.pts >= TGT).mean()*100:>7.0f}%")
    print("\nRandom entries, same hours and exit (his_pullback_ticks.py): -2.88 points a trade, +7 hit 54%.")


if __name__ == "__main__":
    main()
