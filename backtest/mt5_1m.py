"""1-MINUTE BARS WITH THE REAL SPREAD, BUILT FROM EXNESS TICKS (MT5) - for the CFD scalping test (2026-10-12).

MT5 serves at most 100,000 one-minute bars (the terminal's "max bars", ~3 months) and its bar `spread` field is one
number per bar. Its TICK history is not capped that way: on this account it starts in December 2025 / January 2026.
So the bars here are built from every tick: MID price (bid + ask) / 2 open/high/low/close, the tick count as volume,
and the spread (ask - bid) at the minute's FIRST tick (what a market order at the open pays) and on average.

    out: strategy_analysis/data/mt5_1m/<SYMBOL>.parquet   t (ms, minute open, UTC), o h l c (mid), v (ticks),
         sp_o (spread at the first tick), sp (mean spread) - in price units
    days already fetched are listed in <SYMBOL>.days.json and never fetched twice (an empty weekday is retried);
         today (UTC) is never cached.

Run on the PC with the MT5 terminal open:
    python -m backtest.mt5_1m USTECm XAUUSDm --from 2025-12-01
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "strategy_analysis" / "data" / "mt5_1m"
UTC = dt.timezone.utc
MIN = 60_000


def day_bars(mt5, sym: str, day: pd.Timestamp) -> pd.DataFrame:
    a = dt.datetime(day.year, day.month, day.day, tzinfo=UTC)
    tk = mt5.copy_ticks_range(sym, a, a + dt.timedelta(days=1), mt5.COPY_TICKS_ALL)
    if tk is None or not len(tk):
        return pd.DataFrame()
    t = pd.DataFrame(tk)[["time_msc", "bid", "ask"]]
    t = t[(t.bid > 0) & (t.ask >= t.bid)]
    if t.empty:
        return pd.DataFrame()
    t["mid"] = (t.bid + t.ask) / 2
    t["sp"] = t.ask - t.bid
    t["m"] = t.time_msc // MIN * MIN
    g = t.groupby("m", sort=True)
    b = pd.DataFrame({"o": g.mid.first(), "h": g.mid.max(), "l": g.mid.min(), "c": g.mid.last(),
                      "v": g.size().astype(float), "sp_o": g.sp.first(), "sp": g.sp.mean()})
    b.index.name = "t"
    return b.reset_index()


def load(sym: str) -> pd.DataFrame:
    return pd.read_parquet(OUT / f"{sym}.parquet")


def fetch(syms, start: str, end: str | None = None):
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    OUT.mkdir(parents=True, exist_ok=True)
    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    end_d = min(pd.Timestamp(end), today - pd.Timedelta(days=1)) if end else today - pd.Timedelta(days=1)
    try:
        for sym in syms:
            mt5.symbol_select(sym, True)
            pf, df_ = OUT / f"{sym}.parquet", OUT / f"{sym}.days.json"
            done = set(json.loads(df_.read_text())) if df_.exists() else set()
            old = pd.read_parquet(pf) if pf.exists() else pd.DataFrame()
            new = []
            days = [d for d in pd.date_range(start, end_d, freq="D") if d.strftime("%Y-%m-%d") not in done]
            for k, d in enumerate(days, 1):
                b = day_bars(mt5, sym, d)
                if len(b):
                    new.append(b)
                if len(b) or d.weekday() >= 5:                   # an empty weekday is retried next run
                    done.add(d.strftime("%Y-%m-%d"))
                if k % 20 == 0:
                    print(f"  {sym} {k}/{len(days)} days", flush=True)
            if new:
                allb = pd.concat([old] + new, ignore_index=True) if len(old) else pd.concat(new, ignore_index=True)
                allb = allb.drop_duplicates("t").sort_values("t", kind="stable").reset_index(drop=True)
                allb.to_parquet(pf)
            df_.write_text(json.dumps(sorted(done)))
            b = pd.read_parquet(pf) if pf.exists() else pd.DataFrame()
            if len(b):
                print(f"{sym}: {len(b):,} bars, {pd.Timestamp(b.t.min(), unit='ms'):%Y-%m-%d} .. "
                      f"{pd.Timestamp(b.t.max(), unit='ms'):%Y-%m-%d %H:%M} UTC, median spread "
                      f"{(b.sp_o / b.c).median() * 1e4:.2f}bp", flush=True)
            else:
                print(f"{sym}: no ticks", flush=True)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("syms", nargs="+")
    ap.add_argument("--from", dest="a", default="2025-12-01")
    ap.add_argument("--to", dest="b", default=None)
    a = ap.parse_args()
    fetch(a.syms, a.a, a.b)
