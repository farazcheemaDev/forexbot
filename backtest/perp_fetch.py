"""EVERY USDT-M PERPETUAL THAT EVER EXISTED - daily bars and funding, dead ones included.

WHY
    Every short-side test so far used today's coins. For shorts that bias runs the
    opposite way to longs: the coins that died are exactly the ones a short seller
    wanted, and a survivor book leaves them out. It also leaves out the category
    that has never been tested here at all - shorting NEW perps, where the supply
    overhang (airdrops, unlocks, low float / high FDV) is structural, not a pattern.

    A short is executed on a perp, so the universe has to be PERPS: listing date =
    first perp bar, P&L on perp prices, and the funding a short actually pays or
    receives. Spot history would put coins in the test months before anyone could
    have shorted them.

SOURCE
    data.binance.vision, futures/um/monthly/{klines/1d, fundingRate}. It keeps
    delisted symbols, which the live API does not. Completed months only - the
    current month is taken from the live API for symbols still trading.

    Also records each coin's first SPOT bar, so a perp listed on a coin that had
    already traded for years (an old coin getting a perp late) can be told apart
    from a genuinely new token.

    python -m backtest.perp_fetch            # everything, resumable
    python -m backtest.perp_fetch --hourly   # 1h bars too (after the daily run)
"""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.metrics_fetch import BASE, NS, S3, get  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
FAPI = "https://fapi.binance.com"


def list_prefix(prefix, dirs=False):
    """All keys (or sub-directories) under a prefix, following continuation tokens."""
    out, token = [], None
    while True:
        u = f"{S3}?list-type=2&prefix={urllib.parse.quote(prefix, safe='/')}"
        if dirs:
            u += "&delimiter=/"
        if token:
            u += f"&continuation-token={urllib.parse.quote(token, safe='')}"
        root = ET.fromstring(get(u))
        if dirs:
            out += [e.find(f"{NS}Prefix").text for e in root.iter(f"{NS}CommonPrefixes")]
        else:
            out += [e.text for e in root.iter(f"{NS}Key") if e.text.endswith(".zip")]
        t = root.find(f"{NS}IsTruncated")
        if t is None or t.text != "true":
            break
        token = root.find(f"{NS}NextContinuationToken").text
    return out


def read_zip(key):
    try:
        z = zipfile.ZipFile(io.BytesIO(get(f"{BASE}/{key}")))
        raw = z.open(z.namelist()[0]).read().decode()
    except Exception:
        return None
    rows = [r.split(",") for r in raw.strip().splitlines()]
    if rows and not rows[0][0].strip().isdigit():
        rows = rows[1:]                       # newer files carry a header
    return rows


def klines(sym, alive):
    keys = list_prefix(f"data/futures/um/monthly/klines/{sym}/1d/")
    rows = []
    for k in keys:
        r = read_zip(k)
        if r:
            rows += [(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]),
                      float(x[7])) for x in r]
    if alive:                                 # the current, unarchived month
        try:
            start = max((r[0] for r in rows), default=0) + 1
            u = f"{FAPI}/fapi/v1/klines?symbol={sym}&interval=1d&limit=1500"
            if start > 1:
                u += f"&startTime={start}"
            rows += [(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]),
                      float(x[7])) for x in json.loads(get(u))]
        except Exception:
            pass
    if not rows:
        return None
    d = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "qvol"])
    d = d.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    d.insert(0, "time", pd.to_datetime(d.pop("t"), unit="ms"))
    return d


def funding(sym, alive):
    keys = list_prefix(f"data/futures/um/monthly/fundingRate/{sym}/")
    rows = []
    for k in keys:
        r = read_zip(k)
        if r:
            rows += [(int(x[0]), float(x[2])) for x in r if len(x) >= 3]
    if alive:
        try:
            start = max((r[0] for r in rows), default=0) + 1
            for _ in range(20):
                u = (f"{FAPI}/fapi/v1/fundingRate?symbol={sym}&limit=1000"
                     f"&startTime={start}")
                got = json.loads(get(u))
                if not got:
                    break
                rows += [(int(x["fundingTime"]), float(x["fundingRate"])) for x in got]
                start = int(got[-1]["fundingTime"]) + 1
                if len(got) < 1000:
                    break
                time.sleep(0.7)               # fundingRate shares a 500/5min limit
        except Exception:
            pass
    if not rows:
        return None
    d = pd.DataFrame(rows, columns=["t", "rate"]).drop_duplicates("t").sort_values("t")
    d.insert(0, "time", pd.to_datetime(d.pop("t"), unit="ms"))
    return d.reset_index(drop=True)


def spot_first(sym):
    """First month the coin traded SPOT on Binance, or None (perp-only listing)."""
    for s in (sym, sym.removeprefix("1000000"), sym.removeprefix("1000"),
              sym.removeprefix("1M")):
        try:
            ks = list_prefix(f"data/spot/monthly/klines/{s}/1d/")
        except Exception:
            ks = []
        if ks:
            return sorted(ks)[0].split("-1d-")[1][:7]
    return None


def one(sym, alive):
    fk, ff = OUT / f"{sym}_1d.csv.gz", OUT / f"{sym}_funding.csv.gz"
    meta = OUT / f"{sym}.json"
    if meta.exists():
        return json.load(open(meta))
    try:
        k = klines(sym, alive)
        if k is None or len(k) < 2:
            m = dict(sym=sym, ok=False)
        else:
            k.to_csv(fk, index=False, compression="gzip")
            f = funding(sym, alive)
            if f is not None:
                f.to_csv(ff, index=False, compression="gzip")
            m = dict(sym=sym, ok=True, alive=alive,
                     first=str(k.time.iloc[0].date()), last=str(k.time.iloc[-1].date()),
                     bars=len(k), funding=0 if f is None else len(f),
                     spot_first=spot_first(sym))
    except Exception as e:
        return dict(sym=sym, ok=False, err=str(e)[:100])
    json.dump(m, open(meta, "w"))
    return m


def hourly(sym, alive):
    """1h perp bars, same archive, for the short-side family test. Cached; resumable."""
    f = OUT / f"{sym}_1h.csv.gz"
    if f.exists():
        return True
    keys = list_prefix(f"data/futures/um/monthly/klines/{sym}/1h/")
    rows = []
    for k in keys:
        r = read_zip(k)
        if r:
            rows += [(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]),
                      float(x[7])) for x in r]
    if alive:
        try:
            start = max((r[0] for r in rows), default=0) + 1
            for _ in range(3):
                u = f"{FAPI}/fapi/v1/klines?symbol={sym}&interval=1h&limit=1500"
                if start > 1:
                    u += f"&startTime={start}"
                got = json.loads(get(u))
                if not got:
                    break
                rows += [(int(x[0]), float(x[1]), float(x[2]), float(x[3]),
                          float(x[4]), float(x[7])) for x in got]
                start = int(got[-1][0]) + 1
                if len(got) < 1500:
                    break
        except Exception:
            pass
    if not rows:
        return False
    d = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "qvol"])
    d = d.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    d.insert(0, "time", pd.to_datetime(d.pop("t"), unit="ms"))
    d.to_csv(f, index=False, compression="gzip")
    return True


def main_hourly():
    uni = json.load(open(OUT / "universe.json"))
    print(f"1h bars for {len(uni)} perps", flush=True)
    done = ok = 0
    with ThreadPoolExecutor(16) as ex:
        for r in ex.map(lambda m: hourly(m["sym"], m["alive"]), uni):
            done += 1; ok += bool(r)
            if done % 50 == 0:
                print(f"  {done}/{len(uni)}", flush=True)
    print(f"done: {ok} of {len(uni)} with 1h bars")


def main():
    if "--hourly" in sys.argv:
        return main_hourly()
    OUT.mkdir(parents=True, exist_ok=True)
    dirs = list_prefix("data/futures/um/monthly/klines/", dirs=True)
    syms = sorted({d.rstrip("/").split("/")[-1] for d in dirs})
    syms = [s for s in syms if s.endswith("USDT") and "_" not in s]
    info = json.loads(get(f"{FAPI}/fapi/v1/exchangeInfo"))
    live = {s["symbol"] for s in info["symbols"]
            if s.get("status") == "TRADING" and s.get("contractType") == "PERPETUAL"}
    print(f"{len(syms)} USDT perps in the archive, {len(live & set(syms))} trading "
          f"today, {len(set(syms) - live)} dead", flush=True)
    done = 0
    with ThreadPoolExecutor(16) as ex:
        for m in ex.map(lambda s: one(s, s in live), syms):
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(syms)}", flush=True)
    metas = [json.load(open(p)) for p in OUT.glob("*.json") if p.name != "universe.json"]
    good = [m for m in metas if m.get("ok")]
    json.dump(good, open(OUT / "universe.json", "w"), indent=1)
    print(f"done: {len(good)} usable, "
          f"{sum(1 for m in good if not m['alive'])} dead, "
          f"{sum(1 for m in good if m['spot_first'] is None)} perp-only listings")


if __name__ == "__main__":
    main()
