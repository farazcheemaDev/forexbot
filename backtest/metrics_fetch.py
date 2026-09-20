"""DOWNLOAD BINANCE'S POSITIONING ARCHIVE — the first non-price data in this project.

    python -m backtest.metrics_fetch                 # the deployed 12-coin book + BTC
    python -m backtest.metrics_fetch --symbols XRPUSDT ADAUSDT

WHAT THIS IS AND WHY IT MATTERS
    Every test in this repo used OHLCV bars. docs/02-what-failed.md states that returns
    come from three places and that the third - "information nobody else has" - is
    "unavailable at retail". That line is wrong, and the counter-example has been free
    since September 2020:

        data.binance.vision/data/futures/um/daily/metrics/{SYMBOL}/

    Each daily file is 288 rows (one per 5 minutes) of:

        sum_open_interest                  contracts outstanding
        sum_open_interest_value            the same in USD
        count_toptrader_long_short_ratio   top traders, by ACCOUNT COUNT
        sum_toptrader_long_short_ratio     top traders, by POSITION SIZE
        count_long_short_ratio             all accounts, by count
        sum_taker_long_short_vol_ratio     aggressor imbalance

    None of that is derivable from price. Open interest rising with price means new
    longs; open interest FALLING with price rising means shorts being squeezed - the
    same bar, the opposite meaning. And the gap between the count ratio and the size
    ratio is the closest thing to "small accounts against large ones" that exists for
    free.

WHY THE ARCHIVE AND NOT THE API
    Binance's REST endpoints for this data (/futures/data/openInterestHist and
    friends) only serve the last 30 days. The daily archive goes back to 2020-09 and
    there is no monthly roll-up, so the only route to real history is one file per
    symbol per day. That is the entire reason this data is under-used: it is tedious
    to assemble, not restricted.

OUTPUT
    strategy_analysis/data/metrics/{SYMBOL}.csv.gz, one tidy frame per symbol, so
    later tests read it without ever touching the network.
"""
from __future__ import annotations

import argparse
import io
import urllib.parse
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "strategy_analysis" / "data" / "metrics"
BASE = "https://data.binance.vision"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT",
        "BTCUSDT", "ETHUSDT"]


def get(url, timeout=45, tries=4):
    for a in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers={"User-Agent": "research"}),
                    timeout=timeout) as r:
                return r.read()
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(1.5 * (a + 1))


def list_keys(symbol):
    """Every metrics file for a symbol. S3 caps a listing at 1000 keys, so this
    follows the continuation token - without it only the first ~2.7 years appear."""
    keys, token = [], None
    prefix = f"data/futures/um/daily/metrics/{symbol}/"
    while True:
        u = f"{S3}?list-type=2&delimiter=/&prefix={prefix}"
        if token:
            u += f"&continuation-token={urllib.parse.quote(token, safe='')}"
        root = ET.fromstring(get(u))
        keys += [e.text for e in root.iter(f"{NS}Key") if e.text.endswith(".zip")]
        trunc = root.find(f"{NS}IsTruncated")
        if trunc is None or trunc.text != "true":
            break
        nxt = root.find(f"{NS}NextContinuationToken")
        if nxt is None:
            break
        token = nxt.text
    return sorted(keys)


def one_day(key):
    try:
        z = zipfile.ZipFile(io.BytesIO(get(f"{BASE}/{key}")))
        return pd.read_csv(z.open(z.namelist()[0]))
    except Exception:
        return None


def fetch(symbol, workers=12):
    keys = list_keys(symbol)
    if not keys:
        print(f"  {symbol:<10} no files")
        return None
    with ThreadPoolExecutor(workers) as ex:
        parts = [p for p in ex.map(one_day, keys) if p is not None and len(p)]
    if not parts:
        print(f"  {symbol:<10} {len(keys)} keys, nothing parsed")
        return None
    d = pd.concat(parts, ignore_index=True)
    d["create_time"] = pd.to_datetime(d["create_time"])
    d = (d.drop_duplicates("create_time").sort_values("create_time")
         .reset_index(drop=True))
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{symbol}.csv.gz"
    d.to_csv(f, index=False, compression="gzip")
    miss = len(keys) - len(parts)
    print(f"  {symbol:<10} {len(d):>8,} rows  {d.create_time.min():%Y-%m-%d} .. "
          f"{d.create_time.max():%Y-%m-%d}  ({len(keys)} files"
          f"{f', {miss} failed' if miss else ''})  -> {f.name}")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=BOOK)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    print(__doc__.split("WHY THE ARCHIVE")[0].rstrip())
    print(f"\nfetching {len(a.symbols)} symbols into {OUT}\n")
    t0 = time.time()
    n = 0
    for s in a.symbols:
        try:
            d = fetch(s, a.workers)
            n += len(d) if d is not None else 0
        except Exception as e:
            print(f"  {s:<10} FAILED {type(e).__name__}: {e}")
    print(f"\n{n:,} rows total in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (used in list_keys)
    main()
