"""Verify Bitget API credentials + demo (simulated futures) access.
Read-only checks: balance, positions, market info. Places NO orders.
"""
from __future__ import annotations

import os
import sys

import ccxt


def show(label, fn):
    try:
        print(f"  {label}: {fn()}")
    except Exception as e:
        print(f"  {label}: ERROR {type(e).__name__}: {str(e)[:220]}")


def main():
    key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                    os.getenv("BITGET_PASSWORD"))
    if not all([key, sec, pw]):
        raise SystemExit("env vars not visible to this process")
    print(f"credentials loaded (key len {len(key)}, secret {len(sec)}, pass {len(pw)})\n")

    for sandbox in (True, False):
        mode = "DEMO / sandbox" if sandbox else "LIVE"
        print(f"=== {mode} ===")
        ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                          "options": {"defaultType": "swap"}})
        if sandbox:
            try:
                ex.set_sandbox_mode(True)
            except Exception as e:
                print(f"  set_sandbox_mode error: {e}")
        try:
            ex.load_markets()
        except Exception as e:
            print(f"  load_markets ERROR: {str(e)[:200]}\n"); continue

        def bal():
            b = ex.fetch_balance()
            u = b.get("USDT", {})
            return f"USDT free={u.get('free')} total={u.get('total')}"
        show("balance", bal)
        show("positions", lambda: f"{len(ex.fetch_positions())} open")
        show("ticker BTC", lambda: ex.fetch_ticker("BTC/USDT:USDT")["last"])
        print()


if __name__ == "__main__":
    main()
