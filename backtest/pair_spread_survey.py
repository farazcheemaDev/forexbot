"""PAIR SPREAD SURVEY - how much room does a microstructure signal have on each pair? (2026-10-30)

For doc 27 (the order-flow study guide). A signal that moves the mid by about one tick can only matter where one tick is a meaningful number of
basis points; the cost to beat is the fee plus the spread. This samples Bitget's PUBLIC USDT-futures tickers (no keys, no orders) every 5 seconds for
about two minutes and prints, per pair: the median / 10th / 90th percentile spread in bp of the mid, the dollars resting at the best bid and ask,
24-hour traded dollars, and the funding rate per 8 hours in bp.

WHAT IT IS NOT: a distribution. Two minutes at one hour of one day shows the tick structure (most pairs sit on exactly one tick), not how the spread
behaves in a news minute or at 03:00 UTC. Treat it as the first picture, repeat it at other hours before relying on it.

    python -m backtest.pair_spread_survey
"""
from __future__ import annotations

import json
import statistics as st
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "pair_spread_survey.txt"
URL = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "SUIUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT", "ENAUSDT", "SHIBUSDT", "WLDUSDT",
        "NEARUSDT", "ADAUSDT", "ARBUSDT", "DOTUSDT"]
SAMPLES, EVERY_S = 24, 5


def pull() -> list:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=15))["data"]


def main():
    rows = {s: [] for s in SYMS}
    meta = {}
    start = datetime.now(timezone.utc)
    for k in range(SAMPLES):
        for r in pull():
            s = r["symbol"]
            if s in rows:
                b, a = float(r["bidPr"]), float(r["askPr"])
                if b > 0 and a > 0:
                    rows[s].append(((a - b) / ((a + b) / 2) * 1e4, float(r["bidSz"]) * b, float(r["askSz"]) * a))
                meta[s] = (float(r["usdtVolume"]), float(r["fundingRate"]), float(r["lastPr"]))
        if k < SAMPLES - 1:
            time.sleep(EVERY_S)
    L = [f"backtest/pair_spread_survey.py, started {start:%Y-%m-%d %H:%M} UTC, {SAMPLES} samples {EVERY_S} s apart, Bitget public USDT-futures tickers",
         f"{'pair':10s} {'price':>10s} {'spr bp med':>10s} {'p10':>6s} {'p90':>6s} {'best bid $':>11s} {'best ask $':>11s} {'24h vol $M':>11s} {'fund/8h bp':>10s}"]
    for s in SYMS:
        r = rows[s]
        if not r:
            continue
        sp = sorted(x[0] for x in r)
        L.append(f"{s:10s} {meta[s][2]:10.5g} {st.median(sp):10.2f} {sp[len(sp) // 10]:6.2f} {sp[-len(sp) // 10 - 1]:6.2f} "
                 f"{st.median(x[1] for x in r):11,.0f} {st.median(x[2] for x in r):11,.0f} {meta[s][0] / 1e6:11,.0f} {meta[s][1] * 1e4:10.2f}")
    txt = "\n".join(L)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
