"""LIMIT ORDERS AT ROUND NUMBERS - the hypothesis his fills point to, tested on every day Apr-Sep 2026.

Two hints from his 26 clean NASDAQ trades (his_strategy.md s25-26):
  - at his fill the price was usually STILL moving against him in the last 5 seconds (f_last5 rank 0.39,
    his_microstructure.py) - how a RESTING limit order fills, not a click after the dip turned;
  - his ENTRY prices sit near 25-point round numbers (35% within 2.5 points vs 20% by chance, p 0.039;
    his exits show nothing, p 0.47).
Together: in a small NASDAQ move he leaves a limit order at the next round number behind the price and is
filled on the dip. His round numbers are FUTURES prices; the ticks are Exness USTECm, which differs by a
basis that decays to each expiry. The basis per day = the median of NQ=F minus USTECm hourly closes (Yahoo),
which matches his own fills to ~2-3 points (2026-08-07: NQ=F 101 vs his 98-100).

RULE (every second 10:00-16:00 ET, 2026-04-01..2026-09-14, real USTECm bid/ask ticks):
  when the 5-minute move is >= +5 points (long; short mirrored), place a buy limit at the highest ROUND
  level (a multiple of L in futures terms, L = 25 / 50 / 100) that is 2-15 points below the price; it
  fills when the ASK trades at or below it (fill = the level); unfilled after 180 s -> cancelled.
  Filled: +7 on the bid side, -20 stop, 300 s max. One order or position at a time.
CONTROLS, identical except the level:
  OFFSET   the same grid shifted by half a step (L/2) - non-round prices;
  RANDOM   a level 2-15 points behind the price drawn at random - no grid at all.
Verdict: round beats OFFSET on BOTH halves by >= 1 point a trade.

REGISTERED PREDICTION (2026-09-26, before running): round ~= offset (within +-0.5 points a trade), all
negative after costs; the round-number hint in his 26 fills is chance or habit, not an edge.

    python -m backtest.his_levels
"""
from __future__ import annotations

import json
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
T0, T1 = 1800, 23400            # seconds from 09:30 ET: 10:00 .. 16:00


def daily_basis():
    import yfinance as yf
    warnings.filterwarnings("ignore")
    nq = yf.download("NQ=F", period="730d", interval="1h", progress=False, auto_adjust=False)
    nq.columns = nq.columns.get_level_values(0)
    nq.index = nq.index.tz_convert("UTC").tz_localize(None)
    cf = pd.DataFrame(json.load(open(ROOT / "strategy_analysis" / "data" / "USTECm_1h_2400d.json")))
    cf["t"] = pd.to_datetime(cf.t, unit="ms")
    j = nq[["Close"]].join(cf.set_index("t")[["c"]], how="inner").dropna()
    j["b"] = j.Close - j.c
    et = j.index.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None).normalize()
    return j.b.groupby(et).median()


def run(ts, mid, spr, basis, L, mode, rng):
    ask, bid = mid + spr / 2, mid - spr / 2
    out = []
    k = np.searchsorted(ts, T0)
    kend = np.searchsorted(ts, T1)
    while k < kend:
        t = ts[k]
        k300 = np.searchsorted(ts, t - 300, side="right") - 1
        if k300 < 0:
            k += 1; continue
        mv = mid[k] - mid[k300]
        side = 1 if mv >= 5 else (-1 if mv <= -5 else 0)
        if side == 0:
            k += 1; continue
        # the level, in Exness terms
        if mode == "random":
            lvl = mid[k] - side * rng.uniform(2, 15)
        else:
            off = 0.0 if mode == "round" else L / 2
            fut = mid[k] + basis
            if side == 1:
                g = np.floor((fut - 2 - off) / L) * L + off
                ok = fut - g <= 15
            else:
                g = np.ceil((fut + 2 - off) / L) * L + off
                ok = g - fut <= 15
            if not ok:
                k += 1; continue
            lvl = g - basis
        # wait up to 180 s for the fill
        kf = None
        kmax = np.searchsorted(ts, t + 180, side="right")
        for j in range(k + 1, kmax):
            if (side == 1 and ask[j] <= lvl) or (side == -1 and bid[j] >= lvl):
                kf = j; break
        if kf is None:
            k = kmax; continue
        e = lvl
        res = None
        kx = np.searchsorted(ts, ts[kf] + 300, side="right")
        for j in range(kf + 1, kx):
            pnl = side * ((bid[j] if side == 1 else ask[j]) - e)
            if pnl >= 7:
                res = 7.0; break
            if pnl <= -20:
                res = pnl; break
        if res is None:
            j = min(kx, len(mid) - 1)
            res = side * ((bid[j] if side == 1 else ask[j]) - e)
        out.append((ts[kf], res))
        k = kx
    return out


def main():
    cache = pickle.loads(TICKS.read_bytes())
    basis = daily_basis()
    days = [d for d in sorted(cache) if cache[d] is not None and d in basis.index]
    mid_day = days[len(days) // 2]
    print(f"{len(days)} days, 10:00-16:00 ET, real bid/ask; levels in FUTURES terms via the daily NQ=F-USTECm basis.")
    print(f"{'level':<7}{'mode':<8}{'fills':>7}{'/day':>6}{'pts/trade':>11}{'1st half':>10}{'2nd half':>10}{'+7 hit':>8}{'stops':>7}")
    rng = np.random.default_rng(7)
    summary = {}
    for L in (25, 50, 100):
        for mode in ("round", "offset", "random"):
            if mode == "random" and L != 25:
                continue
            T = []
            for d in days:
                ts, mid, spr = cache[d]
                T += [(d, p) for _, p in run(ts, mid, spr, basis[d], L, mode, rng)]
            f = pd.DataFrame(T, columns=["day", "pts"])
            a, b = f[f.day < mid_day].pts.mean(), f[f.day >= mid_day].pts.mean()
            summary[(L, mode)] = (a, b)
            print(f"{L:<7}{mode:<8}{len(f):>7}{len(f)/len(days):>6.1f}{f.pts.mean():>+11.2f}{a:>+10.2f}{b:>+10.2f}"
                  f"{(f.pts >= 7).mean()*100:>7.0f}%{(f.pts <= -20).mean()*100:>6.0f}%")
    print("\nVERDICT (round minus offset, both halves, needs >= +1 point each):")
    for L in (25, 50, 100):
        (ra, rb), (oa, ob) = summary[(L, "round")], summary[(L, "offset")]
        print(f"  {L}: {ra - oa:+.2f} / {rb - ob:+.2f} -> {'PASS' if min(ra - oa, rb - ob) >= 1 else 'fail'}")


if __name__ == "__main__":
    main()
