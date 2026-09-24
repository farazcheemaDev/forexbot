"""Download the two external series backtest/regime_signals.py reads (doc 13 section 1).

    strategy_analysis/data/signals/fear_greed.csv   alternative.me Fear & Greed, daily, 2018-02 on
    strategy_analysis/data/signals/dvol_btc.csv     Deribit BTC implied volatility (DVOL), daily
                                                    candles, 2021-03 on

Both are public, no keys. strategy_analysis/data/ is gitignored (regenerable), so this file is
how a fresh clone rebuilds them. The other thirteen doc-12 signals come from btc_signals.py.

    python -m backtest.signals_fetch
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

SIG = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "signals"


def fear_greed():
    r = json.load(urllib.request.urlopen("https://api.alternative.me/fng/?limit=0&format=json", timeout=30))
    fg = pd.DataFrame(r["data"])
    fg["time"] = pd.to_datetime(fg.timestamp.astype(int), unit="s")
    fg = fg[["time", "value"]].astype({"value": float}).sort_values("time")
    fg.to_csv(SIG / "fear_greed.csv", index=False)
    return len(fg)


def dvol():
    rows, end = [], int(time.time() * 1000)
    start = int(pd.Timestamp("2021-01-01").value // 1_000_000)
    while True:
        u = ("https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC"
             f"&start_timestamp={start}&end_timestamp={end}&resolution=1D")
        d = json.load(urllib.request.urlopen(u, timeout=30))["result"]
        rows += d["data"]
        if not d.get("continuation") or not d["data"]:
            break
        end = d["continuation"]
        time.sleep(0.3)
    dv = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"]).drop_duplicates("ts")
    dv["time"] = pd.to_datetime(dv.ts, unit="ms")
    dv.sort_values("time")[["time", "open", "high", "low", "close"]].to_csv(SIG / "dvol_btc.csv", index=False)
    return len(dv)


if __name__ == "__main__":
    SIG.mkdir(parents=True, exist_ok=True)
    print(f"fear & greed: {fear_greed()} days; DVOL: {dvol()} days -> {SIG}")
