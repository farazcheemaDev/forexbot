"""DAILY SPOT HISTORY 2017-07 .. 2020-03 FOR EVERY BTC-QUOTED PAIR, DEAD ONES INCLUDED.

For the out-of-sample test of the bear-market breadth signal (doc 13) on the 2018 bear market,
which predates the perp archive (backtest/perp_fetch.py starts 2020-01). In 2018 most altcoins
traded against BTC, not USDT, so the fair universe is the BTC-quoted book: every *BTC pair
priced in dollars as ALTBTC x BTCUSDT. Source: data.binance.vision's monthly archive, which
keeps delisted symbols (dead_fetch.py's discovery). Public, no keys.

    python -m backtest.spot2018_fetch
"""
from __future__ import annotations

import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.dead_fetch import NS, S3, fetch_month, months_for  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "spot1d_2017"
OUT.mkdir(parents=True, exist_ok=True)
FIRST, LAST = "2017-07", "2020-03"


def all_symbols():
    prefix = "data/spot/monthly/klines/"
    out, token = [], None
    while True:
        q = {"list-type": "2", "prefix": prefix, "delimiter": "/"}
        if token:
            q["continuation-token"] = token
        x = ET.fromstring(urllib.request.urlopen(S3 + "?" + urllib.parse.urlencode(q), timeout=60).read())
        for p in x.findall(f"{NS}CommonPrefixes/{NS}Prefix"):
            out.append(p.text[len(prefix):].strip("/"))
        t = x.find(f"{NS}IsTruncated"); tok = x.find(f"{NS}NextContinuationToken")
        if t is None or t.text != "true" or tok is None:
            break
        token = tok.text
    return out


def one(sym):
    f = OUT / f"{sym}.csv.gz"
    if f.exists():
        return sym, "cached"
    mons = [m for m in months_for(sym, "1d") if FIRST <= m <= LAST]
    if not mons:
        return sym, "none in window"
    parts = [p for p in (fetch_month(sym, m, "1d") for m in mons) if p is not None]
    if not parts:
        return sym, "fetch failed"
    d = pd.concat(parts, ignore_index=True)
    ot = pd.to_numeric(d["open_time"], errors="coerce")
    d["time"] = pd.to_datetime(ot, unit="ms")
    d = d[["time", "open", "high", "low", "close", "volume"]].dropna()
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna().drop_duplicates("time").sort_values("time")
    d.to_csv(f, index=False, compression="gzip")
    return sym, f"{len(d)} days"


def main():
    syms = all_symbols()
    want = sorted(s for s in syms if (s.endswith("BTC") and len(s) > 3) or s == "BTCUSDT")
    print(f"{len(syms)} spot symbols in the archive, {len(want)} BTC-quoted (+ BTCUSDT)")
    got = 0
    with ThreadPoolExecutor(8) as ex:
        for sym, msg in ex.map(one, want):
            if msg.endswith("days") or msg == "cached":
                got += 1
    print(f"{got} symbols with data in {FIRST}..{LAST} -> {OUT}")


if __name__ == "__main__":
    main()
