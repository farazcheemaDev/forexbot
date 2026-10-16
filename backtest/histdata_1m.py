"""HISTDATA.COM FREE 1-MINUTE FOREX BARS, 2007-2026 - one file per pair per year (2026-10-12)

Dukascopy's per-day files (backtest/dukascopy_1m.py) were throttled after the first few hundred requests (301 redirects to
HTTPS, which times out from this PC). HistData.com serves the same kind of data as ONE zip per pair per year (monthly for
the current year), ~3.5 MB, through its download form: GET the pair-year page for its token `tk`, then POST /get.php.

FORMAT  "YYYYMMDD HHMMSS;open;high;low;close;0" - BID prices. HistData documents its times as EST WITHOUT daylight
        saving; they are NOT: the payroll jump (08:30 New York) sits in the stamped 08:30 minute in winter AND in summer,
        so the stamps are New York local time with DST (measured 2007-2026, fx_surprises_1m.py's clock check).
CACHE   strategy_analysis/data/histdata/<PAIR>.parquet (t = minute start, ms UTC; o h l c); one zip kept per pair-year.

    python -m backtest.histdata_1m
"""
from __future__ import annotations

import http.cookiejar
import io
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "strategy_analysis" / "data" / "histdata"
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def fetch_zip(pair: str, year: int, month: int | None = None) -> bytes:
    page = f"https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{pair.lower()}/{year}"
    if month:
        page += f"/{month}"
    h = _op.open(urllib.request.Request(page, headers={"User-Agent": UA}), timeout=60).read().decode("utf-8", "replace")
    tk = re.search(r'name="tk" id="tk" value="([0-9a-f]+)"', h).group(1)
    dm = f"{year}{month:02d}" if month else str(year)
    form = urllib.parse.urlencode({"tk": tk, "date": str(year), "datemonth": dm, "platform": "ASCII", "timeframe": "M1",
                                   "fxpair": pair}).encode()
    return _op.open(urllib.request.Request("https://www.histdata.com/get.php", data=form,
                                           headers={"User-Agent": UA, "Referer": page,
                                                    "Content-Type": "application/x-www-form-urlencoded"}), timeout=180).read()


def parse(b: bytes) -> pd.DataFrame:
    z = zipfile.ZipFile(io.BytesIO(b))
    name = next(n for n in z.namelist() if n.endswith(".csv"))
    d = pd.read_csv(z.open(name), sep=";", header=None, names=["ts", "o", "h", "l", "c", "v"])
    # The stamps are NEW YORK LOCAL TIME WITH DAYLIGHT SAVING - not the fixed EST HistData documents. Measured on 20
    # years of payroll days (08:30 ET): with a fixed +5 h the jump sat at minute 0 in winter and at +60 in summer, every
    # year 2007-2026, and it produced a fake +10bp "post-release drift" at t +21 (fx_surprises_1m.py, first run).
    t = pd.to_datetime(d.ts, format="%Y%m%d %H%M%S")
    t = t.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC").dt.tz_localize(None)
    ok = t.notna().to_numpy()
    # .dt.as_unit("ms") first: to_datetime with a format returns datetime64[us] here, and int64 // 10**6 on
    # MICROseconds stamped every bar in January 1970 (first run, caught on the first pair's printout)
    return pd.DataFrame({"t": t[ok].dt.as_unit("ms").astype("int64").values, "o": d.o[ok].values, "h": d.h[ok].values,
                         "l": d.l[ok].values, "c": d.c[ok].values})


def load(pair: str) -> pd.DataFrame:
    return pd.read_parquet(OUT / f"{pair}.parquet")


def main(years=range(2007, 2026), months_2026=range(1, 10)):
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "zips"
    raw.mkdir(exist_ok=True)
    for pair in PAIRS:
        pf = OUT / f"{pair}.parquet"
        if pf.exists():
            continue
        frames = []
        jobs = [(y, None) for y in years] + [(2026, m) for m in months_2026]
        for y, m in jobs:
            zf = raw / f"{pair}_{y}{'' if m is None else f'_{m:02d}'}.zip"
            if not zf.exists():
                for k in range(3):
                    try:
                        b = fetch_zip(pair, y, m)
                        if b[:2] != b"PK":
                            raise ValueError("not a zip")
                        zf.write_bytes(b)
                        break
                    except Exception as e:                    # noqa: BLE001
                        print(f"  {pair} {y} {m}: {str(e)[:60]} - retry", flush=True)
                        time.sleep(5 + 5 * k)
                time.sleep(1.5)
            if zf.exists():
                frames.append(parse(zf.read_bytes()))
        d = pd.concat(frames, ignore_index=True).drop_duplicates("t").sort_values("t", kind="stable").reset_index(drop=True)
        d.to_parquet(pf)
        print(f"{pair}: {len(d):,} bars {pd.Timestamp(d.t.min(), unit='ms'):%Y-%m-%d} .. {pd.Timestamp(d.t.max(), unit='ms'):%Y-%m-%d}",
              flush=True)


if __name__ == "__main__":
    main()
