"""ADD DAYS TO THE USTECm TICK CACHE (strategy_analysis/data/ustec_tick_days.pkl) - for his January-March trades.

The cache was filled from 2026-04-01 (his_microstructure.py), because January-March was set aside as "prices
not the market's" (his_strategy.md s25). s35 suspects that was a one-hour winter clock error; drawing and testing
those trades needs their days in the cache. This fetches ONLY the missing days, with his_microstructure.day_ticks
(the same format every reader expects: seconds from 09:30 ET, mid, spread; 09:30-19:30 ET), and never touches a
day already there. Run on the PC with the MT5 terminal open.

    python -m backtest.his_tick_cache --from 2026-01-02 --to 2026-03-31
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest.his_microstructure import CACHE, day_ticks  # noqa: E402


def fill(cache: dict, days, fetch, save=None, every: int = 25) -> list:
    """Fetch the days not in the cache; return them. `save(cache)` checkpoints every `every` days."""
    need = [d for d in days if d not in cache]
    for k, d in enumerate(need, 1):
        cache[d] = fetch(d)
        if save and k % every == 0:
            save(cache)
            print(f"  fetched {k}/{len(need)}", flush=True)
    if save and need:
        save(cache)
    return need


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="a", default="2026-01-02")
    ap.add_argument("--to", dest="b", default="2026-03-31")
    a = ap.parse_args(argv)
    cache = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    days = list(pd.bdate_range(a.a, a.b))
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    try:
        got = fill(cache, days, lambda d: day_ticks(mt5, d), save=lambda c: CACHE.write_bytes(pickle.dumps(c)))
    finally:
        mt5.shutdown()
    empty = [d for d in got if cache.get(d) is None]
    print(f"{len(got)} days fetched, {len(empty)} with no ticks (holidays, or before MT5's history starts)"
          + (f": {', '.join(f'{d:%m-%d}' for d in empty[:12])}" if empty else ""))
    print(f"cache now {sum(v is not None for v in cache.values())} days with ticks: {CACHE}")


if __name__ == "__main__":
    main()
