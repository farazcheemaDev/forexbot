"""Diagnose how CCXT routes Bitget demo (paper) trading requests."""
import inspect
import os

import ccxt

key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                os.getenv("BITGET_PASSWORD"))
ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                  "options": {"defaultType": "swap"}})
ex.set_sandbox_mode(True)
print("options.sandboxMode :", ex.options.get("sandboxMode"))
print("headers             :", ex.headers)

src = inspect.getsource(ex.sign)
hits = [l.strip() for l in src.splitlines()
        if "paptrading" in l.lower() or "sandbox" in l.lower()]
print("sign() sandbox lines:", hits or "none found")

ex.load_markets()
print()
for pt in ("SUSDT-FUTURES", "susdt-futures", "SUSDT-FUTURES ".strip()):
    try:
        b = ex.fetch_balance({"productType": pt})
        print(f"balance productType={pt} -> USDT {b.get('USDT')}")
    except Exception as e:
        print(f"balance productType={pt} -> ERR {str(e)[:160]}")

# try the raw implicit endpoint with explicit demo product type
try:
    r = ex.privateMixGetV2MixAccountAccounts({"productType": "SUSDT-FUTURES"})
    print("raw v2 accounts SUSDT-FUTURES ->", str(r)[:300])
except Exception as e:
    print("raw v2 accounts ERR:", str(e)[:200])
