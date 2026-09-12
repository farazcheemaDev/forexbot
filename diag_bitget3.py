"""Connect to Bitget Unified Account (UTA) v3, live + demo."""
import os

import ccxt

key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                os.getenv("BITGET_PASSWORD"))


def mk(sandbox, dtype):
    ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                      "options": {"defaultType": dtype}})
    if sandbox:
        ex.set_sandbox_mode(True)
    return ex


for sandbox in (False, True):
    tag = "DEMO(paptrading)" if sandbox else "LIVE"
    print(f"===== {tag} =====")
    ex = mk(sandbox, "uta")
    # raw UTA assets
    try:
        r = ex.privateUtaGetV3AccountAssets({})
        data = r.get("data")
        print(f"  UTA assets raw: {str(data)[:300]}")
    except Exception as e:
        print(f"  UTA assets ERR: {str(e)[:200]}")
    # unified fetch_balance with uta type
    try:
        b = ex.fetch_balance()
        usdt = b.get("USDT")
        print(f"  fetch_balance USDT: {usdt}")
    except Exception as e:
        print(f"  fetch_balance ERR: {str(e)[:200]}")
    # positions
    try:
        ex.load_markets()
        p = ex.fetch_positions(["BTC/USDT:USDT"])
        print(f"  positions: {len(p)}")
    except Exception as e:
        print(f"  positions ERR: {str(e)[:200]}")
    print()
