"""Does CCXT's bitget support Unified Account (v3) endpoints?"""
import os

import ccxt

key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                os.getenv("BITGET_PASSWORD"))
ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw})

v3 = [m for m in dir(ex) if "V3" in m and not m.startswith("_")]
print(f"v3 implicit methods available: {len(v3)}")
for m in v3[:25]:
    print("   ", m)

print("\naccount-ish options:", {k: v for k, v in ex.options.items()
                                 if any(x in k.lower() for x in
                                        ("account", "type", "unified", "product"))})

print("\n--- trying v3 unified endpoints ---")
for name in ("privateGetV3AccountAssets", "privateGetV3AccountInfo",
             "privateGetV3AccountFundingAssets", "privateGetV3PositionCurrentPosition"):
    fn = getattr(ex, name, None)
    if not fn:
        print(f"  {name}: not in ccxt")
        continue
    try:
        print(f"  {name}: {str(fn({}))[:220]}")
    except Exception as e:
        print(f"  {name}: ERR {str(e)[:180]}")
