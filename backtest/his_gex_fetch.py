"""Data for his_gex.py (2026-10-20): QQQ options open interest before each session + QQQ 1-minute bars, Databento.

Spend approved by the user ("yes" to a $15 limit, 2026-10-20). The full Jan-Oct pull was quoted at ~$310 (statistics
$106.61, daily option prices $199.86, definitions $3.44) and refused. This pulls only:
    OPRA.PILLAR statistics, QQQ.OPT parent, 00:00-13:00 UTC of each chosen day - in that window the feed carries ONLY the
        open-interest records (stat_type 9), every listed contract by ~10:30 UTC, identical across publishers (checked on
        2026-07-24: 11,556 contracts, 279,754 records, $0.183)
    XNAS.ITCH ohlcv-1m QQQ for the same days (~$0.001 a day)
Days: logs/his_gex_days.json - his 31 NASDAQ trade days and 31 random other trading days (seed 20261020).
A running cost guard stops before the total passes $14. Files: strategy_analysis/data/his_gex/ (gitignored).

    python -m backtest.his_gex_fetch
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "strategy_analysis" / "data" / "his_gex"
LIMIT = 14.0


def fetch(cl, path: Path, kw: dict, tries: int = 4):
    """get_range with retries on dropped connections (run 2 died on one); a partial file is removed before a retry."""
    import time
    for k in range(tries):
        try:
            cl.timeseries.get_range(path=str(path), **kw)
            return
        except db.BentoClientError:
            raise
        except Exception as e:
            if path.exists():
                path.unlink()
            if k == tries - 1:
                raise
            print(f"  retry {k + 1} after {type(e).__name__}", flush=True)
            time.sleep(10 * (k + 1))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cl = db.Historical()
    days = json.loads((ROOT / "logs" / "his_gex_days.json").read_text())
    todo = sorted(set(days["his"]) | set(days["ctrl"]))
    spent = 3.38                                             # probe + runs 1-2 (to 2026-04-24), as their logs printed
    for d in todo:
        p = OUT / f"stats_{d}.dbn.zst"
        q = OUT / f"qqq1m_{d}.dbn.zst"
        try:
            if not p.exists():
                kw = dict(dataset="OPRA.PILLAR", symbols=["QQQ.OPT"], schema="statistics", stype_in="parent",
                          start=f"{d}T00:00", end=f"{d}T13:00")
                c = float(cl.metadata.get_cost(**kw))
                if spent + c > LIMIT:
                    print(f"STOP before {d}: ${spent:.2f} spent, this day ${c:.3f} would pass ${LIMIT}", flush=True)
                    break
                fetch(cl, p, kw)
                spent += c
            if not q.exists():
                kw = dict(dataset="XNAS.ITCH", symbols=["QQQ"], schema="ohlcv-1m", start=f"{d}T00:00", end=f"{d}T23:59")
                spent += float(cl.metadata.get_cost(**kw))
                fetch(cl, q, kw)
        except db.BentoClientError as e:                      # a US market holiday (2026-01-19 MLK day): no options data
            print(f"{d} SKIPPED - {str(e).splitlines()[0][:80]}", flush=True)
            continue
        print(f"{d} ok  (running total ${spent:.2f})", flush=True)
    print(f"DONE, about ${spent:.2f} spent", flush=True)


if __name__ == "__main__":
    sys.exit(main())
