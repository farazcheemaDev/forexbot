"""Funding-rate history on Binance, Bybit and Bitget for the coins listed on both Binance and Bybit (2026-10-18).

For backtest/funding_spread.py (the cross-exchange funding gap). Public endpoints, no keys. Universe: today's USDT
perpetuals on BOTH Binance and Bybit, top 120 by Binance 24h volume (coins delisted before today are missing - the
test says so). Binance and Bybit: full history from 2022-01-01. Bitget: its API keeps ~90 days only (all it has).
Cache: strategy_analysis/data/funding_spread/<venue>_<SYMBOL>.csv (ts_ms, rate), gitignored with the data dir.

    python -m backtest.funding_spread_fetch
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "strategy_analysis" / "data" / "funding_spread"
START_MS = 1640995200000            # 2022-01-01
UA = {"User-Agent": "Mozilla/5.0"}


def get(url: str, tries: int = 5):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read())
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 + 3 * k)


def universe(n: int = 120) -> list:
    bn = get("https://fapi.binance.com/fapi/v1/ticker/24hr")
    bn = {x["symbol"]: float(x["quoteVolume"]) for x in bn if x["symbol"].endswith("USDT")}
    by, cur = set(), ""
    while True:
        d = get("https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000" + (f"&cursor={cur}" if cur else ""))
        for x in d["result"]["list"]:
            if x.get("quoteCoin") == "USDT" and x.get("contractType") == "LinearPerpetual":
                by.add(x["symbol"])
        cur = d["result"].get("nextPageCursor") or ""
        if not cur:
            break
    both = [s for s in bn if s in by]
    return sorted(both, key=lambda s: -bn[s])[:n]


def binance(sym: str) -> list:
    rows, t = [], START_MS
    while True:
        d = get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit=1000&startTime={t}")
        if not d:
            break
        rows += [(int(x["fundingTime"]), float(x["fundingRate"])) for x in d]
        if len(d) < 1000:
            break
        t = int(d[-1]["fundingTime"]) + 1
        time.sleep(0.15)
    return rows


def bybit(sym: str) -> list:
    rows, end = [], int(time.time() * 1000)
    while end > START_MS:
        d = get(f"https://api.bybit.com/v5/market/funding/history?category=linear&symbol={sym}&limit=200&endTime={end}")
        lst = d.get("result", {}).get("list") or []
        if not lst:
            break
        rows += [(int(x["fundingRateTimestamp"]), float(x["fundingRate"])) for x in lst]
        end = min(int(x["fundingRateTimestamp"]) for x in lst) - 1
        time.sleep(0.12)
    return sorted(r for r in rows if r[0] >= START_MS)


def bitget(sym: str) -> list:
    rows = []
    for p in range(1, 8):
        d = get(f"https://api.bitget.com/api/v2/mix/market/history-fund-rate?symbol={sym}&productType=usdt-futures"
                f"&pageSize=100&pageNo={p}")
        lst = d.get("data") or []
        if not lst:
            break
        rows += [(int(x["fundingTime"]), float(x["fundingRate"])) for x in lst]
        time.sleep(0.15)
    return sorted(rows)


def save(venue: str, sym: str, rows: list):
    with (OUT / f"{venue}_{sym}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_ms", "rate"])
        w.writerows(rows)


def one(sym: str) -> str:
    out = []
    for venue, fn in (("binance", binance), ("bybit", bybit), ("bitget", bitget)):
        p = OUT / f"{venue}_{sym}.csv"
        if p.exists():
            continue
        try:
            rows = fn(sym)
            save(venue, sym, rows)
            out.append(f"{venue} {len(rows)}")
        except Exception as e:
            out.append(f"{venue} FAILED {str(e)[:60]}")
    return f"{sym}: " + ", ".join(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    syms = universe()
    (OUT / "universe.json").write_text(json.dumps(syms))
    print(f"{len(syms)} coins on both Binance and Bybit", flush=True)
    with ThreadPoolExecutor(6) as ex:
        for k, msg in enumerate(ex.map(one, syms), 1):
            print(f"[{k}/{len(syms)}] {msg}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
