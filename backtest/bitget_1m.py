"""Bitget USDT-perp 1-minute candles, cached and topped up (2026-10-09).

Bitget's history endpoint serves 200 bars a request (the recent endpoint 1000), so 90 days is ~650 requests. The cache
is strategy_analysis/data/bitget_1m/<COIN>.parquet (gitignored), with columns t (bar open, ms UTC) o h l c v, and only
CLOSED bars are kept: the last bar is dropped while it is still forming.

    python -m backtest.bitget_1m DOGE BTC --days 90
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "bitget_1m"
MIN = 60_000


def exchange():
    import ccxt
    ex = ccxt.bitget({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    ex.load_markets()
    return ex


def fetch(coin: str, days: float = 90, ex=None, quiet: bool = False) -> pd.DataFrame:
    """Closed 1m bars for `coin` covering at least the last `days`, from the cache plus whatever is missing."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{coin}.parquet"
    old = pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["t", "o", "h", "l", "c", "v"])
    ex = ex or exchange()
    sym = f"{coin}/USDT:USDT"
    now = ex.milliseconds()
    want = now - int(days * 86_400_000)
    rows = []
    starts = []
    if len(old):
        if int(old.t.min()) > want:
            starts.append((want, int(old.t.min())))                   # older history missing
        starts.append((int(old.t.max()) + MIN, now))                  # top up to now
    else:
        starts.append((want, now))
    for a, b in starts:
        since = a
        while since < b - MIN:
            r = None
            for k in range(5):
                try:
                    r = ex.fetch_ohlcv(sym, "1m", since=since, limit=200)
                    break
                except Exception as e:
                    if not quiet:
                        print(f"  retry {k + 1}: {str(e)[:80]}", flush=True)
                    time.sleep(2 + 2 * k)
            if not r:
                break
            rows += [x for x in r if x[0] < b]
            # restart AT the last bar returned, not one minute after it: Bitget's history endpoint skipped the bar at
            # `since` on every page that way - 206 single-minute holes in 90 days (2026-10-09). Duplicates are dropped.
            nxt = r[-1][0]
            if nxt <= since:
                break
            since = nxt
    new = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "v"]) if rows else old.iloc[:0]
    d = pd.concat([old, new]).astype({"t": "int64"}).drop_duplicates("t").sort_values("t", kind="stable")
    d = d[d.t + MIN <= now].reset_index(drop=True)                   # closed bars only
    for c in "ohlcv":
        d[c] = d[c].astype(float)
    d.to_parquet(f, index=False)
    if not quiet:
        gaps = (d.t.diff() > MIN).sum()
        print(f"{coin}: {len(d):,} bars {pd.Timestamp(d.t.iloc[0], unit='ms')} .. {pd.Timestamp(d.t.iloc[-1], unit='ms')} "
              f"UTC, {gaps} gaps", flush=True)
    return d


if __name__ == "__main__":
    days = float(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 90
    ex = exchange()
    for c in [a for a in sys.argv[1:] if not a.startswith("--") and not a.replace(".", "").isdigit()]:
        fetch(c, days, ex)
