"""LIQUIDATIONS AND OPEN INTEREST, recorded live beside book_rec.py (2026-10-09).

The user (2026-10-09): "what we have to do to see something majority doesn't see". Forced liquidations are the one
public feed a retail trader can act on at minute speed that almost nobody records: a cascade is selling (or buying) that
must happen whatever the price, so it can overshoot and snap back over minutes - a horizon the millisecond bots do not
hold for. The repo killed the liquidation bounce on HOURLY bars (backtest/cascade_redux.py); it was never tested live at
minute resolution. PUBLIC DATA ONLY (no keys, no orders):
    OKX liquidations      every filled liquidation OKX publishes for the DOGE, BTC, ETH, SOL and XRP USDT swaps,
                          polled every ~10 s (REST: the newest 100 per coin, deduplicated). DOGE is the signal; the
                          five together are the market-wide gauge.
    Binance DOGE open interest every ~10 s (REST)
WHY OKX, NOT BINANCE: the first version listened to Binance's !forceOrder@arr websocket. On this PC's network every
Binance WEBSOCKET connects and then delivers nothing - DOGE's own trade stream gave 0 messages in 12 s (2026-10-09 17:07
UTC) - while Binance REST works. Nothing was ever recorded from it, so the predictions below are unchanged.
Files (gitignored): strategy_analysis/data/doge_book/liqs.csv, oi.csv. Scored by backtest/doge_book.py.

REGISTERED BEFORE ANY DATA (2026-10-09 ~16:58 UTC), scored like R1-R5 in book_rec.py:
    L1  A burst of DOGE LONG liquidations (forced sells; the 60 s total in the top decile of non-zero 60 s windows) is
        followed by a Bitget mid move UP over the next 5 min (the overshoot snaps back); a SHORT-liquidation burst by a
        move down. Direction right, but on a quiet day there will be too few bursts to separate from zero (< 20).
    L2  Market-wide liquidation pressure (net long-minus-short liquidated $ over 60 s, all symbols) predicts DOGE's
        next 5 min with |IC| < 0.05.
    L3  The 5-min change in DOGE open interest predicts the next 5-min move with |IC| < 0.05.

RESULT (2026-10-09 21:09 UTC): NOT TESTED - a quiet day (one $103 DOGE liquidation in ~2 hours) and a ~2 h network outage
left too few events for L1-L3. The recorder works; it needs a volatile day.

    python liq_rec.py           record until stopped; appends
"""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "strategy_analysis" / "data" / "doge_book"
LIQS, OI = OUT / "liqs.csv", OUT / "oi.csv"
OKX = "https://www.okx.com/api/v5/public"
FAPI = "https://fapi.binance.com"
COINS = ("DOGE", "BTC", "ETH", "SOL", "XRP")


def get(url: str):
    rq = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(rq, timeout=10) as r:
        return json.loads(r.read().decode())


def appender(path: Path, cols: list):
    new = not path.exists()
    f = open(path, "a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if new:
        w.writerow(cols)
        f.flush()

    def put(rows):
        w.writerows(rows)
        f.flush()
    return put


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ct = {}
    for c in COINS:                                                   # coins per contract
        d = get(f"{OKX}/instruments?instType=SWAP&instId={c}-USDT-SWAP")["data"][0]
        ct[c] = float(d["ctVal"])
    put_l = appender(LIQS, ["t", "symbol", "side", "price", "qty", "usd"])
    put_o = appender(OI, ["t", "oi_coins"])
    seen: set = set()
    start_ms = int(time.time() * 1000)
    n, last_oi = 0, 0.0
    print(f"recording OKX liquidations ({', '.join(COINS)}) + Binance DOGE open interest from "
          f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC; contract sizes {ct}", flush=True)
    while True:
        t0 = time.time()
        rows = []
        for c in COINS:
            try:
                r = get(f"{OKX}/liquidation-orders?instType=SWAP&instFamily={c}-USDT&state=filled&limit=100")
                for g in r.get("data") or []:
                    for x in g.get("details") or []:
                        key = (c, x["ts"], x["side"], x["bkPx"], x["sz"])
                        if key in seen:
                            continue
                        seen.add(key)
                        if int(x["ts"]) < start_ms - 600_000:             # history from before the start: skip
                            continue
                        qty = float(x["sz"]) * ct[c]
                        px = float(x["bkPx"])
                        # OKX side is the liquidation ORDER's side: sell = a long was liquidated (forced sell)
                        rows.append([int(x["ts"]), f"{c}USDT", x["side"].upper(), px, qty, round(px * qty, 2)])
                        if c == "DOGE":
                            print(f"{datetime.now(timezone.utc):%H:%M:%S} DOGE liquidation: {x['posSide']} "
                                  f"${px * qty:,.0f} at {px}", flush=True)
            except Exception as e:
                print(f"{datetime.now(timezone.utc):%H:%M:%S} okx {c} error: {str(e)[:80]}", flush=True)
        if rows:
            put_l(sorted(rows))
            n += len(rows)
        if time.time() - last_oi >= 10:
            try:
                o = get(f"{FAPI}/fapi/v1/openInterest?symbol=DOGEUSDT")
                put_o([[o["time"], o["openInterest"]]])
                last_oi = time.time()
            except Exception as e:
                print(f"oi error: {str(e)[:80]}", flush=True)
        if len(seen) > 20000:
            seen = set(list(seen)[-10000:])
        time.sleep(max(1.0, 10 - (time.time() - t0)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
