"""Did the Classic-mode switch take effect, and is the demo blocker separate?"""
import os

import ccxt

key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                os.getenv("BITGET_PASSWORD"))


def mk(sandbox):
    ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                      "options": {"defaultType": "swap"}})
    if sandbox:
        ex.set_sandbox_mode(True)
    return ex


for sandbox in (False, True):
    tag = "DEMO (PAPTRADING)" if sandbox else "LIVE (classic)"
    print(f"===== {tag} =====")
    ex = mk(sandbox)
    # classic mix account endpoint - fails with 40085 if still Unified
    for pt in ("USDT-FUTURES", "SUSDT-FUTURES"):
        try:
            r = ex.privateMixGetV2MixAccountAccounts({"productType": pt})
            d = r.get("data")
            print(f"  mix accounts productType={pt}: OK -> {str(d)[:180]}")
        except Exception as e:
            print(f"  mix accounts productType={pt}: ERR {str(e)[:160]}")
    try:
        b = ex.fetch_balance()
        print(f"  fetch_balance USDT: {b.get('USDT')}")
    except Exception as e:
        print(f"  fetch_balance ERR: {str(e)[:160]}")
    print()

print("interpretation:")
print("  40085 = still Unified account mode")
print("  40099 on DEMO only, with LIVE working = demo env/key issue, not mode")
