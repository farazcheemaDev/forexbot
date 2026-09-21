"""FORWARD COLLECTOR FOR PUMP.FUN GRADUATIONS - records data only. No wallet, no keys, no orders.

WHY THIS EXISTS
    pump.fun's API pages only ~24h back, so backtest/meme_grad.py can measure one day of
    graduations over their first hours and nothing longer. The honest way to test day- and
    week-long holds is to record every graduation as it happens - before anyone knows
    which will survive - and measure each one after its first week has passed.

WHAT IT DOES
    Every 20 minutes: pages pump.fun's graduated list newest-first until it reaches coins it
    has already recorded, and appends the new ones to logs/meme_graduates.csv with the
    time first seen. Then, for up to 60 recorded coins that are at least 7.1 days old and
    have no price history yet, fetches their pool's minute candles from GeckoTerminal into
    the same cache backtest/meme_grad.py uses.

    Known gap: the list is ordered by CREATION time, so a coin created more than ~24h
    before it graduates is never seen. Most graduate within hours of creation.

    python -u meme_collector.py
"""
from __future__ import annotations

import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backtest.meme_grad import OUT, PF, PF_H, candles, get  # noqa: E402

LOGS = ROOT / "logs"
CSV = LOGS / "meme_graduates.csv"
LOGF = LOGS / "meme_collector.log"
FIELDS = ["seen_utc", "mint", "symbol", "created_ms", "pool", "program", "mayhem_state"]
POLL_S, FETCH_PER_CYCLE, AGE_D = 20 * 60, 60, 7.1


def log(m):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load():
    if not CSV.exists():
        return {}
    with open(CSV, encoding="utf-8") as f:
        return {r["mint"]: r for r in csv.DictReader(f)}


def record(seen):
    new, off = [], 0
    while off <= 1050:
        d = get(PF.format(off), PF_H)
        if not d:
            break
        fresh = [c for c in d if c.get("mint") and c["mint"] not in seen]
        now = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"
        for c in fresh:
            row = dict(seen_utc=now, mint=c["mint"], symbol=(c.get("symbol") or "")[:30],
                       created_ms=c.get("created_timestamp"),
                       pool=c.get("pump_swap_pool") or c.get("pool_address") or "",
                       program=c.get("program") or "", mayhem_state=c.get("mayhem_state") or "")
            seen[c["mint"]] = row
            new.append(row)
        if len(fresh) < len(d):               # reached coins recorded last cycle
            break
        off += 50
        time.sleep(1.5)
    if new:
        first = not CSV.exists()
        with open(CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if first:
                w.writeheader()
            w.writerows(new)
    return len(new)


def fetch_matured(seen):
    now_ms = time.time() * 1000
    due = [r for r in seen.values() if r["pool"]
           and now_ms - float(r["created_ms"] or now_ms) >= AGE_D * 86400e3
           and not (OUT / "ohlcv" / f"{r['pool']}.json").exists()]
    for r in due[:FETCH_PER_CYCLE]:
        try:
            candles(r["pool"])
        except Exception as e:
            log(f"candles failed for {r['pool'][:8]}: {type(e).__name__}")
    return len(due)


def main():
    from longtrend_bot import acquire_lock
    acquire_lock("meme_collector")
    seen = load()
    log(f"MEME COLLECTOR - data only, no wallet. {len(seen)} graduations already recorded")
    while True:
        try:
            n = record(seen)
            due = fetch_matured(seen)
            log(f"recorded {n} new graduations (total {len(seen)}); "
                f"{due} matured coins awaiting candles")
        except KeyboardInterrupt:
            return
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:160]}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
