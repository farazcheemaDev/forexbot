"""FREE FOREX/METALS HISTORY FROM THE EXNESS MT5 TERMINAL — 12 years of H1, no API key.

    python fx_fetch.py --list                       what symbols and depth are available
    python fx_fetch.py                              the default book (majors + gold), 1h and 4h
    python fx_fetch.py --symbols XAUUSDm --tf 1h 15m --days 2400

WHY THIS EXISTS
    The whole backtest suite ran on crypto because forex intraday history was believed
    to be limited to 30-60 days. It is not. The MT5 terminal already installed on this
    machine holds 60,000 H1 bars per symbol going back to 2014 - 12.2 years - and the
    account is a free Exness demo. Nothing is bought and no API key exists.

THE BUG THAT MADE IT LOOK UNAVAILABLE
    mt5.copy_rates_range() returns (-2, 'Terminal: Invalid params') on this terminal for
    every intraday timeframe, at every date range, including ranges well inside the data
    it actually holds. D1 works, M1 and H1 do not. That error reads like "no such data"
    and is why the history was written off.

    copy_rates_from_pos() works fine on the SAME symbol and timeframe, and paging it
    backwards 5,000 bars at a time reaches 2014. Also: a single request above ~50,000
    bars fails with the same misleading error, so the page size matters.

        copy_rates_range(EURUSDm, H1, 2010..now)  -> Invalid params
        copy_rates_from_pos(EURUSDm, H1, 0, 5000) -> 5,000 bars
        ... start=55,000                          -> oldest 2014-07-08

    RULE: on this terminal, page from_pos. Never trust copy_rates_range's error to mean
    the data is absent.

WHY IT DROPS STRAIGHT INTO THE EXISTING SUITE
    backtest/mass_search.fetch() is a cache-first reader:

        f = DATA / f"{symbol}_{interval}_{days}d.json"
        if f.exists(): rows = json.load(open(f))

    So writing MT5 bars into that exact filename, in that exact row shape, makes every
    one of the 90 backtest files accept forex with NO code change. fetch() never learns
    where the bars came from. That is why this writes the Binance cache format rather
    than a nicer one.

TWO THINGS THAT WOULD SILENTLY CORRUPT A COMPARISON
    * SERVER TIME, NOT UTC. MT5 stamps bars in the broker's server timezone. The crypto
      cache is UTC. Mixing them shifts every session boundary by hours and would make a
      "London open" filter test the wrong hours. The offset is DETECTED and reported on
      every run, and --utc converts. Do not silently mix.
    * TICK VOLUME, NOT REAL VOLUME. Forex has no consolidated tape; real_volume is 0.
      tick_volume (number of price changes) is written as `volume`. It is a proxy for
      activity, not size - so a volume-based signal means something different here than
      it does on Binance.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "strategy_analysis" / "data"

# Exness appends 'm' to retail contract names. Gold is the reason this is worth doing:
# the trend-following edge was strongest on gold and silver, and until now it could only
# be tested on daily bars.
DEFAULT_SYMBOLS = ["XAUUSDm", "EURUSDm", "GBPUSDm", "USDJPYm", "XAGUSDm"]
DEFAULT_TFS = ["1h", "4h"]
TERMINALS = [r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe",
             r"C:\Program Files\MetaTrader 5\terminal64.exe"]

# A single from_pos request over ~50,000 bars fails with 'Invalid params', so page well
# under it. 5,000 is what the terminal's own chart limit returns per call.
PAGE = 5000
MAX_PAGES = 200


def tf_map(mt5):
    return {"1m": mt5.TIMEFRAME_M1, "5m": mt5.TIMEFRAME_M5,
            "15m": mt5.TIMEFRAME_M15, "30m": mt5.TIMEFRAME_M30,
            "1h": mt5.TIMEFRAME_H1, "4h": mt5.TIMEFRAME_H4,
            "12h": mt5.TIMEFRAME_H12, "1d": mt5.TIMEFRAME_D1}


def connect(mt5):
    for p in TERMINALS:
        if Path(p).exists() and mt5.initialize(path=p, timeout=60000):
            return p
    if mt5.initialize(timeout=60000):
        return "(default terminal)"
    raise SystemExit(f"could not attach to an MT5 terminal: {mt5.last_error()}\n"
                     "Open the Exness MT5 terminal and log in to the demo account "
                     "first - the Python API reads the terminal's own cache and cannot "
                     "fetch anything on its own.")


def server_offset_hours(mt5, sym) -> float:
    """Hours the broker's clock runs ahead of UTC, from the newest M1 bar.

    Rounded to the nearest half hour: the newest bar is up to a minute old, so the raw
    difference is never exact, and every real broker offset is a whole or half hour.
    """
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 2)
    if r is None or len(r) == 0:
        return 0.0
    newest = dt.datetime.fromtimestamp(int(r[-1]["time"]), dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    return round((newest - now).total_seconds() / 1800.0) / 2.0


def page_back(mt5, sym, tf, want_bars):
    """Newest-first paging with copy_rates_from_pos, because copy_rates_range lies.

    Deduplicated on bar time: overlapping pages are normal when a new bar forms
    mid-download, and without the dedup the file would carry duplicate timestamps that
    every downstream resample would silently average.
    """
    rows, start = {}, 0
    for _ in range(MAX_PAGES):
        if len(rows) >= want_bars:
            break
        r = mt5.copy_rates_from_pos(sym, tf, start, PAGE)
        if r is None or len(r) == 0:
            break
        for k in r:
            rows[int(k["time"])] = k
        if len(r) < PAGE:
            break
        start += PAGE
    return [rows[t] for t in sorted(rows)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--tf", nargs="+", default=DEFAULT_TFS)
    ap.add_argument("--days", type=int, default=2400,
                    help="filename suffix AND the window kept, so the name is honest")
    ap.add_argument("--utc", action="store_true",
                    help="shift server time to real UTC (do this to mix with crypto)")
    ap.add_argument("--list", action="store_true",
                    help="report available depth per symbol/timeframe and write nothing")
    args = ap.parse_args()

    try:
        import MetaTrader5 as mt5
    except ImportError:
        raise SystemExit("pip install MetaTrader5  (Windows only - it drives the "
                         "terminal, so there is no Linux/VM version)")

    where = connect(mt5)
    TF = tf_map(mt5)
    bad = [t for t in args.tf if t not in TF]
    if bad:
        raise SystemExit(f"unknown timeframe(s) {bad}. one of: {', '.join(TF)}")

    ti, ai = mt5.terminal_info(), mt5.account_info()
    print(f"terminal  {where}")
    print(f"broker    {getattr(ti, 'company', '?')}  "
          f"account {getattr(ai, 'login', '?')} on {getattr(ai, 'server', '?')}")

    known = {s.name for s in mt5.symbols_get()}
    missing = [s for s in args.symbols if s not in known]
    if missing:
        print(f"\n! not on this broker: {missing}")
        near = [n for n in sorted(known)
                if any(m[:6] in n.upper() for m in [x.upper() for x in missing])][:10]
        if near:
            print(f"  did you mean: {near}")
        args.symbols = [s for s in args.symbols if s in known]
        if not args.symbols:
            return 1

    off = server_offset_hours(mt5, args.symbols[0])
    print(f"server clock  UTC{off:+.1f}h"
          + ("  -> converting to UTC" if args.utc else
             "  -> written AS-IS in server time. Pass --utc to mix with crypto data."))

    DATA.mkdir(parents=True, exist_ok=True)
    print(f"\n{'symbol':<11}{'tf':<5}{'bars':>9}  {'from':<11}{'to':<11}{'yrs':>5}  file")
    wrote = 0
    for sym in args.symbols:
        if not mt5.symbol_select(sym, True):
            print(f"{sym:<11}     could not select: {mt5.last_error()}")
            continue
        for t in args.tf:
            per_day = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48,
                       "1h": 24, "4h": 6, "12h": 2, "1d": 1}[t]
            want = min(args.days * per_day, PAGE * MAX_PAGES)
            raw = page_back(mt5, sym, TF[t], want)
            if not raw:
                print(f"{sym:<11}{t:<5}{'none':>9}  {mt5.last_error()}")
                continue
            shift = -off * 3600 if args.utc else 0
            rows = [{"t": int((int(k["time"]) + shift) * 1000),
                     "o": float(k["open"]), "h": float(k["high"]),
                     "l": float(k["low"]), "c": float(k["close"]),
                     # forex has no consolidated tape: real_volume is 0, tick_volume is
                     # a count of price changes. An activity proxy, NOT size.
                     "v": float(k["tick_volume"])} for k in raw]
            cutoff = (time.time() - args.days * 86400) * 1000
            rows = [r for r in rows if r["t"] >= cutoff] or rows
            f = DATA / f"{sym}_{t}_{args.days}d.json"
            json.dump(rows, open(f, "w"))
            a = dt.datetime.fromtimestamp(rows[0]["t"] / 1000, dt.timezone.utc)
            b = dt.datetime.fromtimestamp(rows[-1]["t"] / 1000, dt.timezone.utc)
            print(f"{sym:<11}{t:<5}{len(rows):>9,}  {a:%Y-%m-%d} {b:%Y-%m-%d} "
                  f"{(b - a).days / 365.25:>5.1f}  {f.name}")
            wrote += 1
            if args.list:
                f.unlink()

    mt5.shutdown()
    if args.list:
        print("\n--list: nothing kept.")
        return 0
    print(f"\nwrote {wrote} file(s) into {DATA}")
    print("These are now readable by the ENTIRE existing suite with no code change,")
    print("because backtest/mass_search.fetch() is cache-first:")
    print(f"\n    from backtest.mass_search import fetch")
    print(f"    df = fetch('{args.symbols[0]}', '{args.tf[0]}', {args.days})")
    print("\nBefore comparing any result against a crypto one, read the two warnings at")
    print("the top of this file: server time vs UTC, and tick volume vs real volume.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
