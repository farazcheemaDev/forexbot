"""SENTIMENT ENGINE: 1-minute bars around every tradable news event (2026-10-17)

For the entry / exit / score work (news/entry.py): Binance USDT-M perp 1-minute klines, from data.binance.vision's DAILY
archive (it keeps delisted coins), for each event of ENTRY_TYPES and each of its first 3 coins, from the event's day to
8 days after, plus BTCUSDT on the same days (the hedge leg). One cached file per symbol-day:
strategy_analysis/data/news/m1/<SYM>/<YYYY-MM-DD>.csv.gz (time, open, high, low, close, qvol). Days with no archive (the
current day, a coin not yet listed) are recorded as missing and skipped.

    python -m news.min1_fetch
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.perp_fetch import read_zip  # noqa: E402

EV = ROOT / "strategy_analysis" / "data" / "news" / "events.parquet"
OUT = ROOT / "strategy_analysis" / "data" / "news" / "m1"
ENTRY_TYPES = ("adds_products", "monitoring_tag", "list_spot")
DAYS = 8


def jobs():
    E = pd.read_parquet(EV)
    E = E[E.etype.isin(ENTRY_TYPES) & (E.coins != "")]
    # the strong types first (news_book.py: adds_products, monitoring_tag), the weak list_spot last
    E = E.assign(_o=E.etype.map({"adds_products": 0, "monitoring_tag": 0}).fillna(1)).sort_values(["_o", "t"], kind="stable")
    need, order = set(), []
    for r in E.itertuples():
        d0 = pd.Timestamp(r.t).normalize()
        days = [d0 + pd.Timedelta(days=k) for k in range(DAYS + 1)]
        for c in [c for c in r.coins.split(",") if c and c != "BTCUSDT"][:3] + ["BTCUSDT"]:
            for d in days:
                k = (c, d.strftime("%Y-%m-%d"))
                if k not in need:
                    need.add(k)
                    order.append(k)
    return order


def one(job):
    sym, day = job
    f = OUT / sym / f"{day}.csv.gz"
    miss = OUT / sym / f"{day}.missing"
    if f.exists() or miss.exists():
        return "cached"
    f.parent.mkdir(parents=True, exist_ok=True)
    r = read_zip(f"data/futures/um/daily/klines/{sym}/1m/{sym}-1m-{day}.zip")
    if not r:
        miss.write_text("")
        return "missing"
    d = pd.DataFrame([(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])) for x in r],
                     columns=["t", "open", "high", "low", "close", "qvol"])
    d.insert(0, "time", pd.to_datetime(d.pop("t"), unit="ms"))
    d.to_csv(f, index=False, compression="gzip")
    return "ok"


def main():
    J = jobs()
    print(f"{len(J):,} symbol-days to fetch", flush=True)
    n = {"ok": 0, "missing": 0, "cached": 0}
    with ThreadPoolExecutor(32) as ex:
        for i, s in enumerate(ex.map(one, J), 1):
            n[s] += 1
            if i % 1000 == 0:
                print(f"  {i:,} / {len(J):,}  {n}", flush=True)
    print(f"done: {n}", flush=True)


if __name__ == "__main__":
    main()
