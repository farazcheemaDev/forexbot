"""CASCADE CAPTURE AT TICK RESOLUTION — is the 60bp bounce actually reachable?

WHAT WE ESTABLISHED FIRST (backtest/liq_cascade.py)
--------------------------------------------------
Bars where open interest FELL sharply while price dropped sharply - i.e. forced
liquidation, the seller had no choice - bounce 60.6bp from low to close, versus
14.2bp for bars with the same price drop but RISING open interest (voluntary
selling). Difference +46.4bp, t=+3.79, 7.4 events/day across 16 coins.

That is 15x the 4bp maker cost, and it is the only effect measured today that is
not swamped by its own frictions. The mechanism is non-informational: a
force-closed position is sold regardless of value, so whoever absorbs it is paid
for providing liquidity to distress.

THE PROBLEM THIS FILE SOLVES
----------------------------
The bounce happens INSIDE the 5-minute bar, and open interest is only published
every 5 minutes - so by the time OI confirms a cascade, it is over. Measuring the
effect is not the same as capturing it.

But aggTrades gives every individual trade WITH THE AGGRESSOR SIDE, both live and
historically by time window. A cascade is a burst of one-sided aggressive selling,
which is visible in real time. So we can ask the only question that matters:

    detect the cascade from trade flow alone, enter AFTER a realistic delay,
    and measure what is actually left.

HONEST DESIGN
  * detection uses ONLY trade flow up to the detection instant - no OI, no
    future bars, nothing unknowable at that moment.
  * an explicit LATENCY delay is imposed between detection and entry, and swept,
    because that is what decides whether a real bot can get there.
  * entry is at the actual traded price after the delay (a taker fill - the
    pessimistic assumption for a bot that must act fast).
  * costs charged at taker rates on entry AND exit.

    python -m backtest.cascade_ticks
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.liq_cascade import build  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "ticks"
CACHE.mkdir(parents=True, exist_ok=True)

BIG = 2.0
N_EVENTS = 70            # largest cascades to examine
BUCKET_MS = 5000         # 5-second flow buckets
LATENCIES = (0, 2, 5, 10, 30)     # seconds between detection and entry
HORIZONS = (60, 180, 300)         # seconds to hold
TAKER_BP = 6.0                    # per side


def agg_trades(sym: str, start_ms: int, end_ms: int) -> pd.DataFrame | None:
    f = CACHE / f"{sym}_{start_ms}.csv"
    if f.exists():
        try:
            return pd.read_csv(f)
        except Exception:
            pass
    rows, cur = [], start_ms
    for _ in range(8):
        u = (f"https://fapi.binance.com/fapi/v1/aggTrades?symbol={sym}"
             f"&startTime={cur}&endTime={end_ms}&limit=1000")
        try:
            r = json.load(urllib.request.urlopen(u, timeout=25))
        except Exception:
            return None
        if not r:
            break
        rows += r
        if len(r) < 1000:
            break
        cur = int(r[-1]["T"]) + 1
        if cur >= end_ms:
            break
        time.sleep(0.15)
    if not rows:
        return None
    d = pd.DataFrame([{"T": int(x["T"]), "p": float(x["p"]), "q": float(x["q"]),
                       "sell_agg": bool(x["m"])} for x in rows])
    d = d.drop_duplicates("T", keep="first").sort_values("T").reset_index(drop=True)
    d.to_csv(f, index=False)
    return d


def main():
    print("Loading 5m cascade events...")
    D = build()
    D["mag"] = D.ret_z.abs() * D.doi_z.abs()
    fs = D[(D.doi_z < -BIG) & (D.ret_z < -BIG)].nlargest(N_EVENTS, "mag")
    print(f"  {len(fs)} largest forced-sell cascades selected "
          f"({fs.sym.nunique()} coins)\n")

    print("Pulling tick data for each event (cached)...")
    events = []
    for _, row in fs.iterrows():
        t0 = int(pd.Timestamp(row.t).timestamp() * 1000)
        td = agg_trades(row.sym, t0, t0 + 10 * 60 * 1000)   # the bar + 5 min after
        if td is None or len(td) < 200:
            continue
        events.append((row.sym, t0, td))
    print(f"  {len(events)} events with usable tick data\n")
    if len(events) < 20:
        print("too few events to conclude"); return

    print("=" * 86)
    print("DETECTION FROM TRADE FLOW ONLY, then enter after a REALISTIC DELAY")
    print("=" * 86)
    print(f"{'latency':>8} {'n':>5} " +
          " ".join(f"{'+'+str(h)+'s':>10}" for h in HORIZONS) + "   (net bp, taker both sides)")

    for lat in LATENCIES:
        results = {h: [] for h in HORIZONS}
        for sym, t0, td in events:
            T = td["T"].to_numpy()
            p = td["p"].to_numpy()
            q = td["q"].to_numpy()
            sa = td["sell_agg"].to_numpy()
            # 5s buckets of sell-aggressor volume, causal
            b = (T - T[0]) // BUCKET_MS
            nb = int(b.max()) + 1
            sv = np.zeros(nb)
            for i in range(len(T)):
                if sa[i]:
                    sv[b[i]] += q[i] * p[i]
            if nb < 12:
                continue
            # detection: first bucket whose sell flow exceeds 4x the median of the
            # PRECEDING buckets (uses only past information)
            det = None
            for k in range(4, nb):
                base = np.median(sv[max(0, k - 12):k])
                if base > 0 and sv[k] > 4 * base and sv[k] > 0:
                    det = T[0] + (k + 1) * BUCKET_MS     # end of the spike bucket
                    break
            if det is None:
                continue
            entry_t = det + lat * 1000
            ix = np.searchsorted(T, entry_t)
            if ix >= len(T) - 5:
                continue
            entry = p[ix]
            for h in HORIZONS:
                jx = np.searchsorted(T, entry_t + h * 1000)
                if jx >= len(T):
                    jx = len(T) - 1
                if jx <= ix:
                    continue
                ret_bp = (p[jx] / entry - 1) * 1e4 - 2 * TAKER_BP
                results[h].append(ret_bp)
        n = len(results[HORIZONS[0]])
        if n < 15:
            print(f"{lat:>7}s {n:>5}  too few detections")
            continue
        cells = []
        for h in HORIZONS:
            a = np.array(results[h])
            se = a.std(ddof=1) / np.sqrt(len(a)) if len(a) > 1 else np.nan
            cells.append(f"{a.mean():>+7.1f}±{se:>4.1f}")
        print(f"{lat:>7}s {n:>5} " + " ".join(f"{c:>10}" for c in cells))

    print("\n  entry is a TAKER fill at the traded price after the delay;")
    print("  12bp of round-trip cost already subtracted from every number.")
    print("  detection uses only trade flow available at that instant.")


if __name__ == "__main__":
    main()
