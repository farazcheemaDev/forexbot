"""Fetch CME E-mini NASDAQ-100 (NQ) continuous front-month 1-minute bars WITH VOLUME from Databento (2026-11-03).

Why: HistData's NASDAQ minute bars have no volume, so fx_intraday_pub.py could only run the 'noise area' rule with its bound alone (and a TWAP stand-in for the published VWAP trail). These bars let
nq_noise.py run the published rule in full (VWAP) and test volume-based regimes, on the real futures. The user gave permission to spend the Databento credit on 2026-11-03; the price (free metadata call)
was USD 19.93 for 2010-06-07..2026-10-30. A hard guard refuses to download anything priced above MAX_COST.

The key is read from the environment by the databento client (DATABENTO_API_KEY) and is never printed or stored.
    python -m backtest.nq_fetch         writes strategy_analysis/data/nq_1m/NQ_<year>.parquet (ts_event UTC, open, high, low, close, volume, instrument_id); skips years already on disk
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "strategy_analysis" / "data" / "nq_1m"
MAX_COST = 25.0
START, END = "2010-06-07", "2026-10-30"
KW = dict(dataset="GLBX.MDP3", symbols=["NQ.c.0"], stype_in="continuous", schema="ohlcv-1m")


def year_bounds(year: int):
    return max(f"{year}-01-01", START), (f"{year + 1}-01-01" if year < int(END[:4]) else END)


def main():
    import databento as db
    OUT.mkdir(parents=True, exist_ok=True)
    c = db.Historical()
    total = c.metadata.get_cost(start=START, end=END, **KW)
    print(f"price for {START}..{END}: USD {total:.2f} (guard {MAX_COST})")
    if total > MAX_COST:
        raise SystemExit("REFUSED: over the spending guard")
    for year in range(int(START[:4]), int(END[:4]) + 1):
        f = OUT / f"NQ_{year}.parquet"
        if f.exists():
            print(year, "already on disk")
            continue
        s, e = year_bounds(year)
        df = c.timeseries.get_range(start=s, end=e, **KW).to_df().reset_index()
        df = df[["ts_event", "open", "high", "low", "close", "volume", "instrument_id"]]
        df.to_parquet(f)
        print(year, len(df), "bars,", f"{f.stat().st_size / 1e6:.1f} MB")
    print("done")


if __name__ == "__main__":
    main()
