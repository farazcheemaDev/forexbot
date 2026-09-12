"""REAL-TIME CASCADE LISTENER — collecting the sub-minute data we could not backtest.

WHY THIS EXISTS
---------------
Nine strategies tested; every one found a real effect too small or too slow to
capture. The closest was liquidation cascades:

    5m bars with FALLING open interest + a sharp price drop (forced selling)
    bounced 60.6bp low-to-close, vs 14.2bp for the same drop with RISING OI
    (voluntary selling). Difference +46.4bp, t=+3.79, ~7.4 events/day.

    Dip-buying where OI was RISING lost -30.6bp. The identical trade where OI was
    FALLING came out ~0bp. A +33bp gap from identical price action, separated only
    by whether the seller had a choice. The mechanism is real.

It was not capturable at the resolution available: the bounce happens inside the
5-minute bar, open interest only publishes every 5 minutes, and Binance serves
aggTrades for just 2-3 days - so the sub-minute version could not even be tested.
The edge is in SPEED and we had no data at that speed. This fixes that.

WHY TRADE FLOW AND NOT A LIQUIDATION FEED
-----------------------------------------
Measured, not assumed:
    Binance futures WS  - connects, delivers NOTHING here (regional block on
                          futures streaming; the futures REST API works fine)
    Bybit liquidation.* - "handler not found" (removed)
    Bybit allLiquidation- subscribes OK, emits nothing in 90s over 24 symbols
    OKX                 - DNS failure from here
    Bitget trade        - WORKS: 352 trades/40s over 4 symbols, WITH aggressor side

So no labelled liquidation feed is reachable. That is fine, because a cascade IS a
burst of one-sided AGGRESSIVE trading - which is precisely what forced selling
looks like on the tape, and is exactly how cascade_ticks.py detected them. Trade
flow is also better in one way: it captures the market impact of distress whether
or not the exchange labels it.

Bitget is used because it is the venue we actually trade, so the measured bounce is
the bounce WE could have captured - not one on an exchange we have no account on.

IT DOES NOT TRADE. Deliberately. There is no validated edge yet. Every detected
cascade is recorded with a HYPOTHETICAL entry and its realised forward returns, so
the answer arrives without risking anything.

    python liq_listener.py            # collect
    python liq_listener.py --report   # analyse what has been collected
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
CASCADE_CSV = LOGS / "cascades.csv"
FLOW_CSV = LOGS / "cascade_flow.csv"

WS = "wss://ws.bitget.com/v2/ws/public"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT",
           "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "ARBUSDT", "SUIUSDT",
           "APTUSDT", "OPUSDT", "LTCUSDT", "NEARUSDT", "PEPEUSDT", "TIAUSDT",
           "INJUSDT", "SEIUSDT"]

WINDOW_S = 10.0          # cluster window for one-sided aggressive volume
BASELINE_S = 1800.0      # the symbol's own "normal" flow, 30 min
MIN_NOTIONAL = 15_000.0  # ignore trivial bursts (USD)
MULT = 6.0               # burst must exceed MULT x normal flow for that window
IMBALANCE = 0.75         # >=75% of the burst must be ONE side (forced = one-sided)
SNAPS = (5, 15, 30, 60, 300)
COOLDOWN_S = 120.0       # per symbol, so one cascade is not logged repeatedly
MIN_BASELINE_S = 600.0   # refuse to judge until 10 min of flow history exists

last_px: dict[str, float] = {}
win: dict[str, deque] = defaultdict(deque)      # (ts, notional, side)
base: dict[str, deque] = defaultdict(deque)     # (ts, notional)
last_fire: dict[str, float] = defaultdict(float)
pending: list[dict] = []
stats = defaultdict(int)


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOGS / "cascade_listener.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _append(path: Path, header: str, row: str) -> None:
    new = not path.exists()
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(header + "\n")
        f.write(row + "\n")


def on_trade(sym: str, px: float, sz: float, side: str, ts: float) -> None:
    """side is the AGGRESSOR: 'sell' means someone hit the bid (forced sellers do)."""
    last_px[sym] = px
    notional = px * sz
    stats["trades"] += 1

    w = win[sym]
    w.append((ts, notional, side))
    while w and ts - w[0][0] > WINDOW_S:
        w.popleft()
    b = base[sym]
    b.append((ts, notional))
    while b and ts - b[0][0] > BASELINE_S:
        b.popleft()

    cluster = sum(x[1] for x in w)
    if cluster < MIN_NOTIONAL or len(b) < 50:
        return
    if ts - last_fire[sym] < COOLDOWN_S:
        return
    # WARMUP: the baseline must actually span a meaningful period. Dividing the
    # baseline sum by the NOMINAL span (1800/10 = 180) while the buffer holds only
    # a few seconds makes `normal` ~180x too small, so every burst reads as a
    # 180x cascade. That produced a flood of false detections on first run.
    span = ts - b[0][0]
    if span < MIN_BASELINE_S:
        return
    normal = sum(x[1] for x in b) / (span / WINDOW_S)
    if normal <= 0 or cluster < MULT * normal:
        return
    sells = sum(x[1] for x in w if x[2] == "sell")
    frac_sell = sells / cluster
    if frac_sell >= IMBALANCE:
        direction = "FORCED_SELL"
    elif (1 - frac_sell) >= IMBALANCE:
        direction = "FORCED_BUY"
    else:
        return                      # two-sided churn is not a cascade

    last_fire[sym] = ts
    stats["cascades"] += 1
    log(f"CASCADE {sym} {direction} ${cluster:,.0f} in {WINDOW_S:.0f}s "
        f"({cluster/normal:.1f}x normal, {frac_sell*100:.0f}% sell) px={px}")
    _append(FLOW_CSV,
            "ts_utc,symbol,direction,cluster_usd,x_normal,pct_sell,px",
            f"{datetime.fromtimestamp(ts, timezone.utc):%Y-%m-%d %H:%M:%S},"
            f"{sym},{direction},{round(cluster)},{round(cluster/normal,2)},"
            f"{round(frac_sell*100,1)},{px}")
    pending.append(dict(sym=sym, ts=ts, direction=direction, cluster=cluster,
                        ratio=cluster / normal, px0=px, snaps={}))


def flush(now: float) -> None:
    done = []
    for ev in pending:
        for s in SNAPS:
            if s not in ev["snaps"] and now >= ev["ts"] + s:
                ev["snaps"][s] = last_px.get(ev["sym"])
        if len(ev["snaps"]) == len(SNAPS):
            done.append(ev)
    for ev in done:
        pending.remove(ev)
        px0 = ev["px0"]
        # sign so POSITIVE = the move REVERTED (forced selling pushed price down,
        # so a bounce up is a positive reversion)
        sgn = 1.0 if ev["direction"] == "FORCED_SELL" else -1.0
        cols = []
        for s in SNAPS:
            p = ev["snaps"].get(s)
            cols.append("" if not p else round((p / px0 - 1) * 1e4 * sgn, 2))
        _append(CASCADE_CSV,
                "ts_utc,symbol,direction,cluster_usd,x_normal,px0," +
                ",".join(f"rev_{s}s_bp" for s in SNAPS),
                f"{datetime.fromtimestamp(ev['ts'], timezone.utc):%Y-%m-%d %H:%M:%S},"
                f"{ev['sym']},{ev['direction']},{round(ev['cluster'])},"
                f"{round(ev['ratio'],2)},{px0}," + ",".join(str(c) for c in cols))
        log(f"  -> {ev['sym']} {ev['direction']} reversion: " +
            " ".join(f"{s}s={cols[i]}" for i, s in enumerate(SNAPS)))


async def stream():
    import websockets
    while True:
        try:
            async with websockets.connect(WS, ping_interval=None,
                                          open_timeout=20) as ws:
                args = [{"instType": "USDT-FUTURES", "channel": "trade",
                         "instId": s} for s in SYMBOLS]
                for i in range(0, len(args), 10):
                    await ws.send(json.dumps({"op": "subscribe",
                                              "args": args[i:i + 10]}))
                    await asyncio.sleep(0.3)
                log(f"subscribed: {len(SYMBOLS)} symbols on Bitget USDT-FUTURES")

                async def keepalive():
                    # Bitget expects an application-level 'ping' every <30s
                    while True:
                        await asyncio.sleep(25)
                        try:
                            await ws.send("ping")
                        except Exception:
                            return
                ka = asyncio.create_task(keepalive())
                try:
                    async for raw in ws:
                        if raw == "pong":
                            continue
                        m = json.loads(raw)
                        if m.get("event"):
                            if m.get("event") == "error":
                                log(f"sub error: {m}")
                            continue
                        sym = (m.get("arg") or {}).get("instId")
                        if not sym:
                            continue
                        for d in m.get("data") or []:
                            try:
                                on_trade(sym, float(d["price"]), float(d["size"]),
                                         str(d["side"]).lower(),
                                         float(d["ts"]) / 1000.0)
                            except (KeyError, ValueError):
                                continue
                finally:
                    ka.cancel()
        except Exception as e:
            log(f"stream error: {type(e).__name__}: {str(e)[:110]} - reconnecting")
            await asyncio.sleep(5)


async def heartbeat():
    t0 = time.time()
    while True:
        await asyncio.sleep(1.0)
        flush(time.time())
        if int(time.time() - t0) % 300 < 1.05:
            log(f"{stats['trades']:,} trades | {stats['cascades']} cascades | "
                f"{len(pending)} awaiting snapshots | {len(last_px)} live prices")


def report() -> None:
    import numpy as np
    import pandas as pd
    if not CASCADE_CSV.exists():
        print("no completed cascades yet")
        if FLOW_CSV.exists():
            print(f"(detections logged: {sum(1 for _ in open(FLOW_CSV))-1}, "
                  f"awaiting their 300s snapshot)")
        return
    d = pd.read_csv(CASCADE_CSV)
    print(f"CASCADES WITH COMPLETE FORWARD PRICES: {len(d)}")
    print(f"span: {d.ts_utc.min()} .. {d.ts_utc.max()}")
    cols = [c for c in d.columns if c.startswith("rev_")]
    print(f"\nREVERSION after detection (positive = price moved back our way)")
    print(f"{'horizon':>9} {'n':>5} {'mean bp':>9} {'se':>7} {'t':>7} {'median':>8} "
          f"{'>0':>6}")
    for c in cols:
        a = pd.to_numeric(d[c], errors="coerce").dropna()
        if len(a) < 3:
            print(f"{c:>9} {len(a):>5}  too few")
            continue
        se = a.std(ddof=1) / np.sqrt(len(a))
        print(f"{c.replace('rev_','').replace('_bp',''):>9} {len(a):>5} "
              f"{a.mean():>+9.2f} {se:>7.2f} {a.mean()/se if se else 0:>+7.2f} "
              f"{a.median():>+8.2f} {(a>0).mean()*100:>5.0f}%")
    print(f"\n  cost to beat: 8bp (maker in / taker out), 12bp if both taker")
    print(f"  the 5m-bar study implied ~60bp low-to-close; how much survives here")
    print(f"  at a REALISTIC entry is the whole question.")
    if len(d) < 30:
        print(f"\n  -> {len(d)} cascades so far; need ~30+ before this means anything")
    for dd, g in d.groupby("direction"):
        a = pd.to_numeric(g[cols[2]], errors="coerce").dropna()
        if len(a):
            print(f"  {dd:12} n={len(g):>4}  30s reversion {a.mean():+.2f}bp")


async def main_async():
    log("CASCADE LISTENER (Bitget USDT-FUTURES trade flow) — collecting, NOT trading")
    log(f"  rule: one-sided aggressive burst >{MULT}x the symbol's own 30-min "
        f"normal flow in {WINDOW_S:.0f}s, min ${MIN_NOTIONAL:,.0f}, "
        f"{IMBALANCE*100:.0f}% one-sided")
    log(f"  snapshots at {SNAPS}s after detection")
    log(f"  warmup: no detections until {MIN_BASELINE_S:.0f}s of baseline flow per symbol")
    await asyncio.gather(stream(), heartbeat())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        report(); return
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        log("stopped by user")


if __name__ == "__main__":
    main()
