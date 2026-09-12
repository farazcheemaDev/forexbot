"""Append-only logging: a human-readable event log + a CSV of every action the
bot takes, so we can compare live-demo results to the backtest later.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)
EVENT_LOG = LOG_DIR / "bot.log"
TRADE_CSV = LOG_DIR / "trades.csv"

_CSV_HEADER = ["ts_utc", "event", "symbol", "side", "lots", "price",
               "sl", "tp", "retcode", "comment", "balance", "equity",
               "profit", "reason", "deal"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def event(msg: str) -> None:
    line = f"{_now()}  {msg}"
    print(line, flush=True)
    with open(EVENT_LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def trade(**row) -> None:
    row.setdefault("ts_utc", _now())
    new = not TRADE_CSV.exists()
    with open(TRADE_CSV, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_CSV_HEADER, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)
