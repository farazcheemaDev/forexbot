"""DOWNLOAD DELISTED COIN HISTORY — fixing the survivorship hole.

WHY THIS EXISTS
    Every crypto universe used in this project was built from coins trading TODAY.
    The archive says 735 USDT pairs have existed and 203 of them are DEAD - a 30%
    death rate. Those 203 are precisely the losers, so leaving them out biases
    every long-side result upward and every short-side result downward.

    That bias was not hypothetical. backtest/xs_wide.py found an apparent +0.70R
    edge on "virgin recent listings" (WIF, BONK, PENGU, TRUMP, MUBARAK...) which
    are in today's top-120 by volume BECAUSE they pumped. The thousands that
    launched and died were never in the data. I reported at the time that the bias
    "cannot be corrected without delisted-symbol history, which Binance's public
    API does not serve." That was wrong: the API does not serve it, but
    data.binance.vision's monthly archive does. Verified 2026-09-12 -
    LUNAUSDT/FTTUSDT/SRMUSDT/WAVESUSDT all fetch fine.

    Second time in one day I declared data unavailable after checking one source.

WHAT IT GIVES US
    A survivorship-free universe, which makes two things testable for the first
    time:
      1. new-listing momentum - the category where crypto's largest returns
         actually live, and which is untestable on survivors alone
      2. an honest re-run of the wide cross-sectional result

    Output format matches backtest.mass_search.fetch's cache so the existing
    engines can consume it unchanged.

    python -m backtest.dead_fetch              # all dead symbols
    python -m backtest.dead_fetch --limit 40   # first N, for a quick look
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
DEAD = DATA / "dead"
DEAD.mkdir(parents=True, exist_ok=True)
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
CDN = "https://data.binance.vision"

COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]


def months_for(sym: str, tf: str = "1h") -> list[str]:
    """Which monthly files exist for this symbol. One request, no guessing."""
    prefix = f"data/spot/monthly/klines/{sym}/{tf}/"
    out, token = [], None
    while True:
        q = {"list-type": "2", "prefix": prefix}
        if token:
            q["continuation-token"] = token
        try:
            x = ET.fromstring(urllib.request.urlopen(
                S3 + "?" + urllib.parse.urlencode(q), timeout=40).read())
        except Exception:
            return out
        for k in x.findall(f"{NS}Contents/{NS}Key"):
            name = k.text.rsplit("/", 1)[-1]
            if name.endswith(".zip"):
                out.append(name[:-4].split("-", 2)[-1])   # YYYY-MM
        t = x.find(f"{NS}IsTruncated")
        tok = x.find(f"{NS}NextContinuationToken")
        if t is None or t.text != "true" or tok is None:
            break
        token = tok.text
    return sorted(out)


def fetch_month(sym: str, mon: str, tf: str = "1h") -> pd.DataFrame | None:
    u = f"{CDN}/data/spot/monthly/klines/{sym}/{tf}/{sym}-{tf}-{mon}.zip"
    try:
        raw = urllib.request.urlopen(u, timeout=60).read()
    except Exception:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            with z.open(z.namelist()[0]) as fh:
                head = fh.read(120).decode("utf-8", "ignore")
            hdr = 0 if "open_time" in head else None
            with z.open(z.namelist()[0]) as fh:
                df = pd.read_csv(fh, header=hdr,
                                 names=None if hdr == 0 else COLS)
    except Exception:
        return None
    df.columns = [str(c) for c in df.columns]
    ren = {c: c for c in df.columns}
    if hdr is None:
        pass
    need = ["open_time", "open", "high", "low", "close", "volume"]
    if not all(n in df.columns for n in need):
        return None
    return df[need]


def build(sym: str, tf: str = "1h") -> pd.DataFrame | None:
    """All months concatenated, cached as gzipped CSV."""
    f = DEAD / f"{sym}_{tf}.csv.gz"
    if f.exists():
        try:
            return pd.read_csv(f, parse_dates=["time"])
        except Exception:
            f.unlink(missing_ok=True)
    mons = months_for(sym, tf)
    if not mons:
        return None
    parts = [p for p in (fetch_month(sym, m, tf) for m in mons) if p is not None]
    if not parts:
        return None
    d = pd.concat(parts, ignore_index=True)
    # Binance switched kline open_time from MILLISECONDS to MICROSECONDS partway
    # through 2025, so a symbol spanning that switch has BOTH units in one
    # concatenation. Deciding the unit per symbol (max > 1e15 -> us) silently
    # reinterpreted every millisecond row as microseconds and dated it to
    # 1970-01-20. Classify PER ROW instead: ms epoch is ~1.8e12 now, us is
    # ~1.8e15, so 1e14 separates them cleanly for any plausible date.
    ot = pd.to_numeric(d["open_time"], errors="coerce")
    ms = ot.where(ot < 1e14)
    us = ot.where(ot >= 1e14)
    d["time"] = pd.to_datetime(ms, unit="ms").fillna(
        pd.to_datetime(us, unit="us"))
    d = d[["time", "open", "high", "low", "close", "volume"]].dropna()
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna().drop_duplicates("time").sort_values("time").reset_index(drop=True)
    if len(d) < 200:
        return None
    d.to_csv(f, index=False, compression="gzip")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--tf", default="1h")
    args = ap.parse_args()

    dead = json.load(open(DATA / "dead_symbols.json"))
    if args.limit:
        dead = dead[:args.limit]
    print(f"delisted symbols to fetch: {len(dead)}  tf={args.tf}")
    print("these are the coins that DIED - the half every prior universe omitted\n")
    ok, skip = [], []
    for i, s in enumerate(dead, 1):
        d = build(s, args.tf)
        if d is None:
            skip.append(s)
            print(f"  {i:>3}/{len(dead)} {s:14} no usable data", flush=True)
            continue
        ok.append(s)
        span = (d["time"].iloc[-1] - d["time"].iloc[0]).days
        print(f"  {i:>3}/{len(dead)} {s:14} {len(d):>7,} bars  "
              f"{d['time'].iloc[0]:%Y-%m-%d}..{d['time'].iloc[-1]:%Y-%m-%d} "
              f"({span}d)  last px {d['close'].iloc[-1]:.6g}", flush=True)
    json.dump(ok, open(DATA / "dead_fetched.json", "w"), indent=1)
    print(f"\nFETCHED {len(ok)}   unusable {len(skip)}")
    print(f"cached in {DEAD}")


if __name__ == "__main__":
    main()
