"""DOGE ORDER-BOOK AND TRADE-FLOW RECORDER - the scalper's information, recorded live (2026-10-09).

The user (2026-10-09), after "how do scalpers scalp then": yes - test whether the order book gives an edge. Chart rules on
DOGE's own bars lose to the fee (backtest/doge_adapt.py). Scalpers who make money read what bars do not hold: the book,
the aggressive trades, and the bigger venue moving first. This records them, about once a second, PUBLIC DATA ONLY (no
keys, no orders), for backtest/doge_book.py to score:
    Bitget DOGE perp    order book (50 levels) every ~1 s, and every trade (taker side) every ~2 s
    Binance DOGE perp   order book (20 levels) every ~1 s, and every aggregated trade every ~2 s
    Binance BTC perp    best bid / ask every ~1 s
Snapshots by REST at ~1 s are what a bot on a home PC can act on; the market makers who own the edge act in
milliseconds, and what they leave behind is the question.
Files (gitignored): strategy_analysis/data/doge_book/book.csv, trades.csv.

REGISTERED BEFORE ANY DATA (2026-10-09 ~16:55 UTC). Scored on the recording's two halves; thresholds for any trading
rule are set on the FIRST half and read on the SECOND; information coefficients (Spearman) on non-overlapping samples.
    R1  Bitget's top-5 book imbalance predicts Bitget's mid over the next 10 s: IC > +0.05 on both halves. (The effect
        is documented in every market; it is real.)
    R2  But it is not tradable at retail costs: in the top / bottom decile of imbalance (first-half thresholds) the mean
        mid move in the signalled direction over the next 30 s is < 4bp on the second half - under even the MAKER round
        trip (Bitget 0.02% x 2), let alone the 12bp taker one.
    R3  Binance leads Bitget: Binance's mid change over the last 2 s predicts Bitget's next 10 s with IC > +0.05, but the
        conditional move is < 2bp - arbitraged within the second.
    R4  Net aggressive (taker) flow over the last 30 s predicts the next 60 s with |IC| < 0.05.
    R5  No feature gives a move above 12bp at 60 s or longer in its extreme decile on the second half.

RESULT (2026-10-09 21:11 UTC, logs/doge_book.txt; 16:47-21:09 UTC, 7,795 snapshots with a ~2 h network outage, halves by
snapshot count)
    R1 RIGHT: top-5 imbalance -> next 10 s IC +0.132 / +0.141 (the top-level one +0.245 / +0.199).
    R2 RIGHT: its extreme deciles move +0.32bp in the signalled direction over 30 s (101 signals).
    R3 RIGHT: Binance-first IC +0.077 / +0.123, move +1.20bp; the Binance-Bitget gap is stronger (IC +0.21 / +0.22, +1.9bp).
    R4 WRONG: taker flow vs the next 60 s -0.011 / -0.092 (a mild reversal, not ~0).
    R5 not decidable: 14 samples at 5 min.
    Every feature at every horizon: taker net -11..-13bp, maker net -2..-3bp. The information is real out to a minute;
    the move it predicts is ~1-2bp - a fifth to a tenth of a retail round trip.

    python book_rec.py            record until stopped (Ctrl+C); appends, so a restart continues the files
"""
from __future__ import annotations

import csv
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "strategy_analysis" / "data" / "doge_book"
BOOK, TRADES = OUT / "book.csv", OUT / "trades.csv"
FAPI = "https://fapi.binance.com"
SYM_BG = "DOGE/USDT:USDT"
BAND = (0.001, 0.0025)            # depth within 0.10% / 0.25% of the mid

BOOK_COLS = (["ts", "bg_ts", "bn_ts", "btc_ts", "bg_bid", "bg_ask", "bg_bq1", "bg_aq1"]
             + [f"bg_imb{k}" for k in (1, 5, 20, 50)] + [f"bg_band{int(b * 1e4)}" for b in BAND]
             + ["bg_bid_usd20", "bg_ask_usd20", "bn_bid", "bn_ask", "bn_bq1", "bn_aq1"]
             + [f"bn_imb{k}" for k in (1, 5, 20)] + [f"bn_band{int(b * 1e4)}" for b in BAND]
             + ["btc_bid", "btc_ask"])
TRADE_COLS = ["venue", "id", "t", "side", "price", "qty"]


def get(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read().decode())


def imbalance(bids: list, asks: list, k: int) -> float:
    """(bid notional - ask notional) / (sum) over the top k levels: +1 all bids, -1 all asks."""
    b = sum(p * q for p, q in bids[:k])
    a = sum(p * q for p, q in asks[:k])
    return (b - a) / (b + a) if b + a > 0 else 0.0


def band(bids: list, asks: list, frac: float) -> float:
    """Imbalance of the notional resting within frac of the mid."""
    mid = (bids[0][0] + asks[0][0]) / 2
    b = sum(p * q for p, q in bids if p >= mid * (1 - frac))
    a = sum(p * q for p, q in asks if p <= mid * (1 + frac))
    return (b - a) / (b + a) if b + a > 0 else 0.0


def book_feats(prefix: str, bids: list, asks: list, ks: tuple) -> dict:
    out = {f"{prefix}_bid": bids[0][0], f"{prefix}_ask": asks[0][0], f"{prefix}_bq1": bids[0][1], f"{prefix}_aq1": asks[0][1]}
    out.update({f"{prefix}_imb{k}": round(imbalance(bids, asks, k), 5) for k in ks})
    out.update({f"{prefix}_band{int(f * 1e4)}": round(band(bids, asks, f), 5) for f in BAND})
    return out


class Writer:
    def __init__(self, path: Path, cols: list):
        new = not path.exists()
        self.f = open(path, "a", newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=cols, extrasaction="ignore")
        if new:
            self.w.writeheader()

    def rows(self, rows: list):
        for r in rows:
            self.w.writerow(r)
        self.f.flush()


def snap_bitget(ex) -> dict:
    ob = ex.fetch_order_book(SYM_BG, limit=50)
    row = {"bg_ts": ob.get("timestamp") or ""}
    row.update(book_feats("bg", ob["bids"], ob["asks"], (1, 5, 20, 50)))
    row["bg_bid_usd20"] = round(sum(p * q for p, q in ob["bids"][:20]), 1)
    row["bg_ask_usd20"] = round(sum(p * q for p, q in ob["asks"][:20]), 1)
    return row


def snap_binance() -> dict:
    d = get(f"{FAPI}/fapi/v1/depth?symbol=DOGEUSDT&limit=20")
    bids = [(float(p), float(q)) for p, q in d["bids"]]
    asks = [(float(p), float(q)) for p, q in d["asks"]]
    row = {"bn_ts": d.get("T") or d.get("E") or ""}
    row.update(book_feats("bn", bids, asks, (1, 5, 20)))
    return row


def snap_btc() -> dict:
    b = get(f"{FAPI}/fapi/v1/ticker/bookTicker?symbol=BTCUSDT")
    return {"btc_ts": b.get("time") or "", "btc_bid": float(b["bidPrice"]), "btc_ask": float(b["askPrice"])}


def trades_loop(ex, tw: "Writer", stop: threading.Event, errs: list):
    """Every trade on both venues, every ~2 s, in its own thread so the book snapshots keep their 1 s cadence."""
    seen_bg: list = []
    bn_from = None
    while not stop.is_set():
        t0 = time.time()
        new = []
        try:
            for t in ex.fetch_trades(SYM_BG, limit=100):
                if t["id"] in seen_bg:
                    continue
                seen_bg.append(t["id"])
                new.append(dict(venue="bg", id=t["id"], t=t["timestamp"], side=t["side"], price=t["price"], qty=t["amount"]))
            seen_bg = seen_bg[-3000:]
        except Exception as e:
            errs.append(1)
            print(f"bitget trades error: {str(e)[:100]}", flush=True)
        try:
            url = f"{FAPI}/fapi/v1/aggTrades?symbol=DOGEUSDT&limit=1000" + (f"&fromId={bn_from}" if bn_from else "")
            for t in get(url):
                new.append(dict(venue="bn", id=t["a"], t=t["T"], side="sell" if t["m"] else "buy",
                                price=float(t["p"]), qty=float(t["q"])))
                bn_from = int(t["a"]) + 1
        except Exception as e:
            errs.append(1)
            print(f"binance trades error: {str(e)[:100]}", flush=True)
        tw.rows(new)
        stop.wait(max(0.0, 2.0 - (time.time() - t0)))


def main():
    import ccxt
    OUT.mkdir(parents=True, exist_ok=True)
    ex = ccxt.bitget({"enableRateLimit": False, "options": {"defaultType": "swap"}})
    ex.load_markets()
    ex_t = ccxt.bitget({"enableRateLimit": False, "options": {"defaultType": "swap"}})   # its own session for the thread
    ex_t.markets, ex_t.markets_by_id, ex_t.symbols = ex.markets, ex.markets_by_id, ex.symbols
    bw, tw = Writer(BOOK, BOOK_COLS), Writer(TRADES, TRADE_COLS)
    errs: list = []
    stop = threading.Event()
    threading.Thread(target=trades_loop, args=(ex_t, tw, stop, errs), daemon=True).start()
    pool = ThreadPoolExecutor(3)
    n, t_start = 0, time.time()
    print(f"recording to {OUT} from {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC", flush=True)
    try:
        while True:
            t0 = time.time()
            row = {"ts": int(t0 * 1000)}
            futs = {"bitget book": pool.submit(snap_bitget, ex), "binance book": pool.submit(snap_binance),
                    "binance btc": pool.submit(snap_btc)}
            for name, f in futs.items():
                try:
                    row.update(f.result(timeout=6))
                except Exception as e:
                    errs.append(1)
                    print(f"{name} error: {str(e)[:100]}", flush=True)
            if "bg_bid" in row:
                bw.rows([row])
            n += 1
            if n % 600 == 0:
                print(f"{datetime.now(timezone.utc):%H:%M:%S} UTC: {n} snapshots in {(time.time() - t_start) / 60:.1f} min, "
                      f"{len(errs)} errors", flush=True)
            time.sleep(max(0.0, 1.0 - (time.time() - t0)))
    finally:
        stop.set()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
