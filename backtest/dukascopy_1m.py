"""DUKASCOPY 1-MINUTE FOREX BARS, FREE, 2007-2026 - only the days a high-impact release came out (2026-10-12)

Dukascopy (a Swiss bank) serves its own interbank-fed minute candles free, one LZMA-compressed .bi5 file per pair per
day: http://datafeed.dukascopy.com/datafeed/<PAIR>/<YYYY>/<MM-1>/<DD>/BID_candles_min_1.bi5 (HTTPS times out from this
PC; plain HTTP works). Each record is 24 bytes, big-endian: seconds from 00:00 UTC, open, close, low, high (integers in
1e-5 of the price, 1e-3 for JPY pairs), volume (float). BID side only - the spread is charged separately.

Only the days that backtest/fx_surprises.py needs are fetched: every day (and the day after) with a high-impact release
of |score| >= 1 - the dollar's releases on EURUSD, GBPUSD and USDJPY, each other currency's on its own pair.
Cache: strategy_analysis/data/dukascopy/<PAIR>.parquet (t = minute start, ms UTC; o h l c) + <PAIR>.days.json.

    python -m backtest.dukascopy_1m
"""
from __future__ import annotations

import json
import lzma
import struct
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "strategy_analysis" / "data" / "dukascopy"
PAIR_OF = {"EUR": "EURUSD", "GBP": "GBPUSD", "JPY": "USDJPY", "AUD": "AUDUSD", "NZD": "NZDUSD", "CAD": "USDCAD",
           "CHF": "USDCHF"}
DOLLAR_PAIRS = ["EURUSD", "GBPUSD", "USDJPY"]


def day_bars(pair: str, day: pd.Timestamp):
    """minute bars of one day, or None if the server refused (it answers a burst of requests with a 301 to its HTTPS
    address, which times out from this PC - so redirects are NOT followed; the caller backs off and retries)."""
    import http.client
    path = f"/datafeed/{pair}/{day.year}/{day.month - 1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    try:
        c = http.client.HTTPConnection("datafeed.dukascopy.com", timeout=25)
        c.request("GET", path, headers={"User-Agent": "Mozilla/5.0"})
        r = c.getresponse()
        b = r.read()
        c.close()
    except Exception:                                        # noqa: BLE001
        return None
    if r.status == 404:
        return np.zeros((0, 5))
    if r.status != 200:
        return None
    if not b:
        return np.zeros((0, 5))
    try:
        raw = lzma.decompress(b)
    except lzma.LZMAError:
        return None
    n = len(raw) // 24
    a = np.frombuffer(raw[: n * 24], dtype=">i4").reshape(n, 6)[:, :5].astype(np.float64)
    div = 1e3 if "JPY" in pair else 1e5
    t0 = int(day.timestamp() * 1000)
    out = np.empty((n, 5))
    out[:, 0] = t0 + a[:, 0] * 1000
    out[:, 1], out[:, 4], out[:, 3], out[:, 2] = a[:, 1] / div, a[:, 2] / div, a[:, 3] / div, a[:, 4] / div  # o c l h -> o h l c
    return out


def needed_days():
    from backtest.fx_surprises import events
    E = events()
    E = E[E.score.abs() >= 1]
    need = {}
    for r in E.itertuples():
        d = pd.Timestamp(r.utc).normalize()
        pairs = DOLLAR_PAIRS if r.currency == "USD" else [PAIR_OF[r.currency]]
        for p in pairs:
            need.setdefault(p, set()).update({d, d + pd.Timedelta(days=1)})
    return {p: sorted(x for x in v if x.dayofweek < 5 or x.dayofweek == 6) for p, v in need.items()}


def load(pair: str) -> pd.DataFrame:
    return pd.read_parquet(OUT / f"{pair}.parquet")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    need = needed_days()
    for pair, days in need.items():
        pf, jf = OUT / f"{pair}.parquet", OUT / f"{pair}.days.json"
        done = set(json.loads(jf.read_text())) if jf.exists() else set()
        todo = [d for d in days if d.strftime("%Y-%m-%d") not in done]
        print(f"{pair}: {len(days)} days needed, {len(todo)} to fetch", flush=True)
        frames = []
        for i in range(0, len(todo), 100):
            chunk = todo[i:i + 100]
            for attempt in range(6):
                with ThreadPoolExecutor(4) as ex:
                    res = list(ex.map(lambda d: (d, day_bars(pair, d)), chunk))
                failed = [d for d, a in res if a is None]
                for d, a in res:
                    if a is None:
                        continue
                    if len(a):
                        frames.append(pd.DataFrame(a, columns=["t", "o", "h", "l", "c"]))
                    done.add(d.strftime("%Y-%m-%d"))
                if not failed:
                    break
                print(f"  {pair}: {len(failed)} refused, backing off {30 * (attempt + 1)} s", flush=True)
                time.sleep(30 * (attempt + 1))
                chunk = failed
            old = pd.read_parquet(pf) if pf.exists() else None
            if frames:
                allb = pd.concat(([old] if old is not None else []) + frames, ignore_index=True)
                allb = allb.drop_duplicates("t").sort_values("t", kind="stable").reset_index(drop=True)
                allb["t"] = allb.t.astype(np.int64)
                allb.to_parquet(pf)
                frames = []
            jf.write_text(json.dumps(sorted(done)))
            print(f"  {pair} {min(i + 100, len(todo))}/{len(todo)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
