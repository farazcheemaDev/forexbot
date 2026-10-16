"""RETAIL POSITIONING RECORDER - Myfxbook, OANDA and 7 more brokers' long/short ratios, every 30 minutes (2026-10-12)

THE USER (2026-10-12): "start recording myfxbook sentiment". Myfxbook's own page sits behind a Cloudflare bot check (not
bypassed) and its API needs the user's login; OANDA's site is not reachable by the user. FXSSI's public endpoint
(https://c.fxssi.com/api/current-ratios, no login) republishes the share of retail traders LONG per instrument at
Myfxbook, OANDA, Dukascopy, IG ("IGG"), FXBlue, XM, Insta, FiboGroup, Amarkets and its own panel, plus an average, for
25 instruments (FX majors and crosses, gold, silver, oil, NAS100, US30, SP500, GER40, BTC, ETH, the dollar index).

No history is free, so the record starts now; this is the one behavioural forex source left untested (doc 02, the forex
drivers entry). Read-only, public data, no keys. The response's client_ip / user_id fields are NOT stored.

STORE   strategy_analysis/data/sentiment/fxssi_ratios.csv  (gitignored): fetched_utc, formed_utc (FXSSI's own stamp),
        broker, symbol, long_pct. A fetch whose `formed` stamp equals the last stored one is skipped.

REGISTERED NOW, BEFORE ANY DATA (2026-10-12) - to be scored by a backtest/ file once >= 3 months are recorded, prices from
backtest/mt5_1m.py (Exness), costs as fx_drivers.COST:
    R1  The crowd is CONTRARIAN at hours-to-days: when Myfxbook's long share on a pair is in its top 20% of the record,
        the pair falls over the next 24 h more often than it rises (and the bottom 20% rises), on EURUSD GBPUSD USDJPY
        AUDUSD XAUUSD pooled - but the edge a trade is under the Exness spread + one night's swap.
    R2  CHANGES lead more than levels: a 10-point jump in the long share within 4 h is followed by a move AGAINST it
        over the next 4-24 h (retail buys falling prices), |IC| >= 0.05 - still not tradable after costs.
    R3  The brokers agree: Myfxbook's and OANDA's long shares correlate >= 0.6 across time on the majors.

    python sentiment_rec.py --once          # one fetch
    python sentiment_rec.py --loop          # every 30 minutes until stopped
    python sentiment_rec.py --status        # rows, span, last fetch
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "strategy_analysis" / "data" / "sentiment"
CSV = OUT / "fxssi_ratios.csv"
URL = "https://c.fxssi.com/api/current-ratios?ver=13"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
EVERY = 30 * 60


def utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def last_formed() -> str | None:
    if not CSV.exists():
        return None
    with open(CSV, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 4096))
        tail = f.read().decode("utf-8", "replace").strip().splitlines()
    return tail[-1].split(",")[1] if tail and not tail[-1].startswith("fetched_utc") else None


def fetch_once() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Referer": "https://fxssi.com/tools/current-ratio"})
    with urllib.request.urlopen(req, timeout=40) as r:
        d = json.loads(r.read().decode("utf-8"))
    formed = utc(float(d["formed"]))
    if formed == last_formed():
        return 0
    now = utc(time.time())
    rows = []
    for broker, vals in d.get("brokers", {}).items():
        for sym, v in vals.items():
            rows.append((now, formed, broker, sym, v))
    for sym, vals in d.get("pairs", {}).items():               # FXSSI's weighted average across brokers
        if "average" in vals:
            rows.append((now, formed, "average", sym, vals["average"]))
    OUT.mkdir(parents=True, exist_ok=True)
    new = not CSV.exists()
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["fetched_utc", "formed_utc", "broker", "symbol", "long_pct"])
        w.writerows(rows)
    return len(rows)


def status():
    if not CSV.exists():
        print("no record yet")
        return
    import pandas as pd
    d = pd.read_csv(CSV)
    print(f"{len(d):,} rows, {d.formed_utc.nunique()} snapshots, {d.formed_utc.min()} .. {d.formed_utc.max()} UTC, "
          f"brokers {sorted(d.broker.unique())}, {d.symbol.nunique()} symbols")
    last = d[d.formed_utc == d.formed_utc.max()]
    for b in ("myfxbook", "ftroanda", "average"):
        x = last[last.broker == b].set_index("symbol").long_pct
        print(f"  {b:9} long %: " + ", ".join(f"{s} {x[s]:.0f}" for s in ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "NAS100") if s in x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        status()
        return
    if a.once or not a.loop:
        print(f"{utc(time.time())} stored {fetch_once()} rows", flush=True)
        return
    while True:
        try:
            n = fetch_once()
            print(f"{utc(time.time())} stored {n} rows", flush=True)
        except Exception as e:                                # noqa: BLE001
            print(f"{utc(time.time())} fetch failed: {str(e)[:120]}", flush=True)
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
