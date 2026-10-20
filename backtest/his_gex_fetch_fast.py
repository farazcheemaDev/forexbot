"""his_gex_fetch.py, in parallel (2026-10-20): the user asked for it faster. Prices EVERY remaining day first and refuses
to start if the total would pass the approved limit; then downloads 8 days at a time. Partial files are checked and
removed. Same data, same windows as his_gex_fetch.py.

    python -m backtest.his_gex_fetch_fast
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "strategy_analysis" / "data" / "his_gex"
SPENT_BEFORE, LIMIT = 3.38, 14.0


def ok(p: Path) -> bool:
    try:
        db.DBNStore.from_file(str(p)).to_df()
        return True
    except Exception:
        return False


def jobs(day: str):
    st = dict(dataset="OPRA.PILLAR", symbols=["QQQ.OPT"], schema="statistics", stype_in="parent",
              start=f"{day}T00:00", end=f"{day}T13:00")
    q = dict(dataset="XNAS.ITCH", symbols=["QQQ"], schema="ohlcv-1m", start=f"{day}T00:00", end=f"{day}T23:59")
    return [(OUT / f"stats_{day}.dbn.zst", st), (OUT / f"qqq1m_{day}.dbn.zst", q)]


def main():
    cl = db.Historical()
    days = json.loads((ROOT / "logs" / "his_gex_days.json").read_text())
    todo = []
    for d in sorted(set(days["his"]) | set(days["ctrl"])):
        for p, kw in jobs(d):
            if p.exists() and not ok(p):
                p.unlink()
                print(f"removed a partial {p.name}", flush=True)
            if not p.exists():
                todo.append((d, p, kw))

    def price(item):
        d, p, kw = item
        try:
            return float(cl.metadata.get_cost(**kw))
        except db.BentoClientError:
            return None                                       # a market holiday - nothing to buy
    with ThreadPoolExecutor(8) as ex:
        costs = list(ex.map(price, todo))
    todo = [(t, c) for t, c in zip(todo, costs) if c is not None]
    total = sum(c for _, c in todo)
    print(f"{len(todo)} files to fetch, ${total:.2f}; with ${SPENT_BEFORE:.2f} already spent: ${SPENT_BEFORE + total:.2f}", flush=True)
    if SPENT_BEFORE + total > LIMIT:
        print(f"REFUSED: would pass ${LIMIT}", flush=True)
        return 1

    def get(item):
        (d, p, kw), c = item
        for k in range(4):
            try:
                db.Historical().timeseries.get_range(path=str(p), **kw)
                if ok(p):
                    return f"{p.name} ok"
            except Exception as e:
                last = type(e).__name__
            if p.exists():
                p.unlink()
        return f"{p.name} FAILED ({last})"
    with ThreadPoolExecutor(8) as ex:
        for msg in ex.map(get, todo):
            print(msg, flush=True)
    print(f"DONE, about ${SPENT_BEFORE + total:.2f} spent in all", flush=True)


if __name__ == "__main__":
    sys.exit(main())
