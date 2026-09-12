"""CASCADE CAPTURE ON REAL TICK DATA — from Binance's official archive.

THE MISS THIS CORRECTS
----------------------
I concluded sub-minute liquidation data "doesn't exist anywhere to download" after
checking only real-time STREAMS (Binance futures WS blocked here, Bybit's
liquidation topic removed, OKX unreachable). I never checked historical ARCHIVES.

data.binance.vision has them, free and unauthenticated:

    aggTrades   full tick history WITH aggressor side, back to 2020
    bookDepth   order book snapshots
    metrics     open interest at 5m
    (liquidationSnapshot was removed - 404 - so cascades are detected from flow)

That turns a multi-day collection problem into a backtest we can run now, on
thousands of events instead of the handful the live listener would gather.

WHAT IS MEASURED
----------------
liq_cascade.py showed, on 5m bars: drops with FALLING open interest (forced) bounce
60.6bp low-to-close vs 14.2bp for drops with RISING OI (voluntary); t=+3.79. But
the bounce happens INSIDE the bar, so 5m data could not tell us how much is
reachable. cascade_1m.py put a realistic limit order on it and got ~0bp - the
entry filled partway down a falling knife.

At tick resolution we can finally ask the right question:

    detect the burst from trade flow ONLY (causal, nothing from the future),
    wait a realistic LATENCY, enter, and measure what is actually left.

Costs are charged at taker rates on both sides, and latency is swept, because the
whole thesis is that the edge is in speed.

    python -m backtest.cascade_hist --days 10 --coins ARBUSDT,OPUSDT,APTUSDT
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "aggzip"
CACHE.mkdir(parents=True, exist_ok=True)
BASE = "https://data.binance.vision/data/futures/um/daily"

BUCKET_MS = 1000          # 1-second flow buckets
WINDOW_S = 10             # burst window
BASELINE_S = 1800         # the symbol's own normal flow
MULT = 6.0                # burst must exceed this multiple of normal
IMBALANCE = 0.75          # fraction of burst on one side
MIN_NOTIONAL = 15_000.0
COOLDOWN_S = 120
TAKER_BP = 6.0
LATENCIES = (0, 1, 2, 5, 10, 30)
HORIZONS = (5, 15, 30, 60, 300)


def fetch_day(sym: str, d: date) -> pd.DataFrame | None:
    """One day of aggTrades. Cached as a compact parquet-ish CSV of 1s buckets
    plus the raw tick price series (needed for entries/exits)."""
    f = CACHE / f"{sym}_{d:%Y-%m-%d}.csv.gz"
    if f.exists():
        try:
            return pd.read_csv(f)
        except Exception:
            f.unlink(missing_ok=True)
    url = f"{BASE}/aggTrades/{sym}/{sym}-aggTrades-{d:%Y-%m-%d}.zip"
    try:
        raw = urllib.request.urlopen(url, timeout=120).read()
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            head = fh.read(200).decode("utf-8", "ignore")
        has_header = "agg_trade_id" in head or "price" in head.split(",")[1:2]
        with z.open(name) as fh:
            df = pd.read_csv(
                fh,
                header=0 if has_header else None,
                names=None if has_header else
                ["agg_trade_id", "price", "quantity", "first_trade_id",
                 "last_trade_id", "transact_time", "is_buyer_maker"],
                usecols=None)
    cols = {c.lower(): c for c in df.columns}
    p = df[cols.get("price", "price")].astype(float).to_numpy()
    q = df[cols.get("quantity", "quantity")].astype(float).to_numpy()
    t = df[cols.get("transact_time", "transact_time")].astype("int64").to_numpy()
    # is_buyer_maker True => the AGGRESSOR was a seller
    m = df[cols.get("is_buyer_maker", "is_buyer_maker")]
    m = (m.astype(str).str.lower().isin(["true", "1"])).to_numpy()
    out = pd.DataFrame({"t": t, "p": p, "notional": p * q, "sell_agg": m})
    out.to_csv(f, index=False, compression="gzip")
    return out


def detect_and_measure(tk: pd.DataFrame) -> list[dict]:
    """Cascade detection from flow, then forward returns at several latencies."""
    t = tk["t"].to_numpy()
    p = tk["p"].to_numpy()
    n = tk["notional"].to_numpy()
    sa = tk["sell_agg"].to_numpy()
    if len(t) < 5000:
        return []
    t0 = t[0]
    sec = ((t - t0) // BUCKET_MS).astype(np.int64)
    nsec = int(sec[-1]) + 1
    sell = np.zeros(nsec); buy = np.zeros(nsec)
    np.add.at(sell, sec[sa], n[sa])
    np.add.at(buy, sec[~sa], n[~sa])
    tot = sell + buy
    csum = np.concatenate(([0.0], np.cumsum(tot)))
    csell = np.concatenate(([0.0], np.cumsum(sell)))

    def win_sum(c, a, b):
        a = max(a, 0); b = min(b, nsec)
        return c[b] - c[a] if b > a else 0.0

    events = []
    last_fire = -10 ** 9
    for s in range(BASELINE_S, nsec - max(HORIZONS) - 1):
        if s - last_fire < COOLDOWN_S:
            continue
        cluster = win_sum(csum, s - WINDOW_S, s)
        if cluster < MIN_NOTIONAL:
            continue
        normal = win_sum(csum, s - BASELINE_S, s) / (BASELINE_S / WINDOW_S)
        if normal <= 0 or cluster < MULT * normal:
            continue
        cs = win_sum(csell, s - WINDOW_S, s)
        frac = cs / cluster
        if frac >= IMBALANCE:
            direction, sgn = "FORCED_SELL", 1.0
        elif (1 - frac) >= IMBALANCE:
            direction, sgn = "FORCED_BUY", -1.0
        else:
            continue
        last_fire = s
        det_ms = t0 + s * BUCKET_MS
        rec = dict(direction=direction, cluster=cluster, ratio=cluster / normal)
        for lat in LATENCIES:
            i = np.searchsorted(t, det_ms + lat * 1000)
            if i >= len(t) - 2:
                continue
            entry = p[i]
            for h in HORIZONS:
                j = np.searchsorted(t, det_ms + (lat + h) * 1000)
                if j >= len(t):
                    j = len(t) - 1
                if j <= i:
                    continue
                rec[f"L{lat}_H{h}"] = ((p[j] / entry - 1) * 1e4 * sgn
                                       - 2 * TAKER_BP)
        events.append(rec)
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--coins", default="ARBUSDT,OPUSDT,APTUSDT,SUIUSDT,SEIUSDT")
    args = ap.parse_args()
    coins = [c.strip().upper() for c in args.coins.split(",")]

    end = date.today() - timedelta(days=2)     # archive lags ~1 day
    days = [end - timedelta(days=i) for i in range(args.days)]
    print(f"Binance tick archive: {len(coins)} coins x {len(days)} days "
          f"({days[-1]} .. {days[0]})\n")

    allev = []
    for c in coins:
        got = 0
        for d in days:
            tk = fetch_day(c, d)
            if tk is None or len(tk) < 5000:
                continue
            ev = detect_and_measure(tk)
            for e in ev:
                e["sym"] = c; e["day"] = str(d)
            allev += ev
            got += len(ev)
            print(f"  {c:9} {d}  {len(tk):>9,} ticks  {len(ev):>3} cascades",
                  flush=True)
        print(f"  {c:9} TOTAL {got} cascades\n")
    if not allev:
        print("no cascades detected"); return
    E = pd.DataFrame(allev)
    print(f"{len(E)} cascades total "
          f"({(E.direction=='FORCED_SELL').sum()} forced-sell, "
          f"{(E.direction=='FORCED_BUY').sum()} forced-buy)\n")

    print("=" * 88)
    print("NET bp AFTER COSTS (12bp round trip taker), by latency x holding time")
    print("positive = the forced move reverted and we captured it")
    print("=" * 88)
    print(f"{'latency':>8} " + " ".join(f"{'+'+str(h)+'s':>12}" for h in HORIZONS))
    for lat in LATENCIES:
        cells = []
        for h in HORIZONS:
            col = f"L{lat}_H{h}"
            if col not in E:
                cells.append("     -"); continue
            a = E[col].dropna()
            if len(a) < 20:
                cells.append(f"  n={len(a)}"); continue
            se = a.std(ddof=1) / np.sqrt(len(a))
            cells.append(f"{a.mean():>+7.1f}±{se:>4.1f}")
        print(f"{lat:>7}s " + " ".join(f"{c:>12}" for c in cells))

    print(f"\n{'latency':>8} {'horizon':>8} {'n':>5} {'mean bp':>9} {'t':>7} {'win%':>6}")
    best = []
    for lat in LATENCIES:
        for h in HORIZONS:
            col = f"L{lat}_H{h}"
            if col not in E:
                continue
            a = E[col].dropna()
            if len(a) < 20:
                continue
            se = a.std(ddof=1) / np.sqrt(len(a))
            best.append((a.mean() / se if se else 0, lat, h, a.mean(), len(a),
                         (a > 0).mean() * 100, se))
    best.sort(reverse=True)
    for t_, lat, h, m, n, w, se in best[:6]:
        print(f"{lat:>7}s {h:>7}s {n:>5} {m:>+9.1f} {t_:>+7.2f} {w:>5.0f}%")

    # forced vs the two directions separately - a real mechanism should show in both
    print(f"\nby direction at the strongest setting:")
    if best:
        _, lat, h, *_ = best[0]
        col = f"L{lat}_H{h}"
        for d, g in E.groupby("direction"):
            a = g[col].dropna()
            if len(a) >= 10:
                se = a.std(ddof=1) / np.sqrt(len(a))
                print(f"  {d:12} n={len(a):>4} {a.mean():>+8.1f}bp "
                      f"(t={a.mean()/se if se else 0:+.2f})")


if __name__ == "__main__":
    main()
