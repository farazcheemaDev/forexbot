"""PULL A COMPLETE MT5 TRADE HISTORY TO CSV — credentials never touch the file.

    set MT5_LOGIN=12345678
    set MT5_PASSWORD=...
    set MT5_SERVER=VertexPro-Live
    python pull_history.py --months 12

WHY THIS EXISTS
    The analysis in strategy_analysis/ is built from 72 trades transcribed out of 55
    phone screenshots. That was enough to establish HE IS PROFITABLE (P=100% on the win
    rate) and nothing else: the fade-vs-follow question came in at p=0.17 on 26 NASDAQ
    entries and needs roughly 85. The screenshots are a sample someone chose to send;
    the account itself is the whole record.

CREDENTIALS
    Read from ENVIRONMENT VARIABLES, never from a file and never from the command line.
      * nothing is written to disk except the trade CSV
      * the password is not printed, not logged, and not stored
      * `set` (Windows) / `export` (bash) keeps it out of your shell history file only
        if you are careful; close the terminal afterwards

    USE THE INVESTOR PASSWORD IF YOU HAVE IT. MT5 accounts have two passwords: the
    MASTER password can place and close trades, the INVESTOR password is READ-ONLY and
    exists for exactly this purpose. This script only ever reads, but an investor
    password makes that guarantee structural instead of a promise. If you were given the
    master password, ask for the investor one instead.

WHAT IT WRITES
    strategy_analysis/mt5_history.csv — one row per closed position, with entry and exit
    time, price, volume, commission, swap and profit. No account number, no balance, no
    name. That file is safe to share and is what the analysis needs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "strategy_analysis" / "mt5_history.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12,
                    help="how far back to pull (default 12)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    try:
        import MetaTrader5 as mt5
        import pandas as pd
    except ImportError as e:
        raise SystemExit(f"missing package: {e}. pip install MetaTrader5 pandas")

    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    if not (login and password and server):
        raise SystemExit(
            "Set these first, then re-run. They are read from the environment so they\n"
            "never appear in a file:\n\n"
            "  Windows CMD:   set MT5_LOGIN=12345678\n"
            "                 set MT5_PASSWORD=yourpassword\n"
            "                 set MT5_SERVER=VertexPro-Live\n\n"
            "  PowerShell:    $env:MT5_LOGIN='12345678'   (etc)\n\n"
            "The SERVER name is shown in the app under account settings. Use the\n"
            "INVESTOR (read-only) password if you have it.")

    # The terminal must be installed; MT5's python API drives it.
    ok = mt5.initialize(login=int(login), password=password, server=server,
                        timeout=60000)
    if not ok:
        raise SystemExit(f"could not connect: {mt5.last_error()}\n"
                         "Check the server name exactly as the app shows it, and that "
                         "the MT5 terminal is installed.")
    # Deliberately does NOT print account_info(): no balance, no name, no number.
    to = dt.datetime.now() + dt.timedelta(days=1)
    frm = to - dt.timedelta(days=31 * args.months)
    deals = mt5.history_deals_get(frm, to)
    mt5.shutdown()
    if deals is None or len(deals) == 0:
        raise SystemExit("no deals returned for that window. Try --months 24.")

    d = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    d["time"] = pd.to_datetime(d["time"], unit="s")
    # entry: 0 = open, 1 = close. Pair them by position_id so one row = one round trip.
    opens = d[d["entry"] == 0].set_index("position_id")
    closes = d[d["entry"] == 1].set_index("position_id")
    rows = []
    for pid, c in closes.iterrows():
        if pid not in opens.index:
            continue
        o = opens.loc[pid]
        o = o.iloc[0] if hasattr(o, "iloc") and getattr(o, "ndim", 1) > 1 else o
        rows.append(dict(
            position_id=pid, symbol=c["symbol"],
            side="BUY" if o["type"] == 0 else "SELL",
            lots=o["volume"], open_time=o["time"], close_time=c["time"],
            open_price=o["price"], close_price=c["price"],
            commission=float(o["commission"]) + float(c["commission"]),
            swap=float(c["swap"]), profit=float(c["profit"])))
    if not rows:
        raise SystemExit("deals found but none could be paired into positions.")
    out = pd.DataFrame(rows).sort_values("close_time")
    out["net"] = out["profit"] + out["commission"] + out["swap"]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)

    w = out[out.net > 0]
    print(f"wrote {len(out):,} closed positions to {args.out}")
    print(f"  {out.close_time.min():%Y-%m-%d} to {out.close_time.max():%Y-%m-%d}")
    print(f"  net {out.net.sum():,.2f}   win rate {100*len(w)/len(out):.1f}%")
    print(f"  symbols: {', '.join(sorted(out.symbol.unique())[:10])}")
    print("\nThat CSV holds no account number, balance or name — safe to share.")


if __name__ == "__main__":
    sys.exit(main())
