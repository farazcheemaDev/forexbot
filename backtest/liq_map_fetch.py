"""Hourly open interest for the liquidation-map study (backtest/liq_map.py), from Binance's free metrics archive.

data.binance.vision/data/futures/um/daily/metrics/<SYM>/<SYM>-metrics-<day>.zip holds a 5-minute row per perp per day from about
2021-12: sum_open_interest (coins) and sum_open_interest_value (USD). Kept: the LAST 5-minute row of each UTC hour (the open interest
standing at the hour's close) for every day a symbol is in the point-in-time top-40 (wide_book.eligibility, dead coins in), plus the
month before its first eligible month of each stretch (so the map has history when the symbol enters). One parquet per symbol in
strategy_analysis/data/liqmap/ (gitignored); a symbol already written is skipped (resumable by symbol).

    python -m backtest.liq_map_fetch            (~100k small files over 32 threads; about an hour)
"""
from __future__ import annotations

import io
import sys
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "strategy_analysis" / "data" / "liqmap"
URL = "https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip"
FIRST, LAST = "2022-01-01", "2026-09-20"


def months_needed(months: set) -> list:
    """Eligible months plus the month before each run of eligible months (warm-up)."""
    ps = sorted(pd.Period(m, "M") for m in months)
    keep = set(ps)
    for p in ps:
        if p - 1 not in keep:
            keep.add(p - 1)
    lo, hi = pd.Period(FIRST, "M"), pd.Period(LAST, "M")
    return sorted(p for p in keep if lo <= p <= hi)


def hourly_last(d: pd.DataFrame) -> pd.DataFrame:
    """The last 5-minute row of each UTC hour: t = the hour's start (ms), oi in coins, oiv in USD."""
    t = pd.to_datetime(d["create_time"])
    h = t.dt.floor("h")
    x = pd.DataFrame({"h": h, "t": t, "oi": pd.to_numeric(d["sum_open_interest"], errors="coerce"),
                      "oiv": pd.to_numeric(d["sum_open_interest_value"], errors="coerce")}).dropna()
    x = x.sort_values("t", kind="stable").groupby("h", sort=True).last().reset_index()
    return pd.DataFrame({"t": x.h.dt.as_unit("ns").astype("int64") // 10**6, "oi": x.oi.to_numpy(float),
                         "oiv": x.oiv.to_numpy(float)})


def one_day(sym: str, day: str):
    for attempt in range(3):
        try:
            b = urllib.request.urlopen(urllib.request.Request(URL.format(s=sym, d=day), headers={"User-Agent": "forexbot"}),
                                       timeout=30).read()
            d = pd.read_csv(zipfile.ZipFile(io.BytesIO(b)).open(f"{sym}-metrics-{day}.csv"))
            return hourly_last(d) if len(d) else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(1 + attempt)
        except Exception:  # noqa: BLE001 - a network blip: retry, then give up on that day
            time.sleep(1 + attempt)
    return None


def plan():
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    el = drop_non_crypto(eligibility(40))
    jobs = {}
    for s, months in el.items():
        ms = months_needed({m for m in months if FIRST[:7] <= m <= LAST[:7]})
        if not ms:
            continue
        days = [d.strftime("%Y-%m-%d") for p in ms for d in pd.date_range(p.start_time, p.end_time.normalize(), freq="D")
                if FIRST <= d.strftime("%Y-%m-%d") <= LAST]
        if days:
            jobs[s] = days
    return jobs


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = plan()
    todo = {s: d for s, d in jobs.items() if not (OUT / f"{s}.parquet").exists()}
    print(f"{len(jobs)} symbols, {sum(len(d) for d in jobs.values()):,} symbol-days; to fetch {len(todo)} symbols", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(32) as ex:
        for i, (s, days) in enumerate(sorted(todo.items())):
            parts = [p for p in ex.map(lambda d: one_day(s, d), days) if p is not None]
            df = pd.concat(parts).drop_duplicates("t").sort_values("t", kind="stable") if parts else pd.DataFrame(columns=["t", "oi", "oiv"])
            df.to_parquet(OUT / f"{s}.parquet", index=False)
            print(f"{i + 1}/{len(todo)} {s}: {len(days)} days, {len(df)} hours, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
