"""Find the correct one-way-mode order parameters for Bitget demo."""
import os

import ccxt

key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                os.getenv("BITGET_PASSWORD"))
ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                  "enableRateLimit": True, "options": {"defaultType": "swap"}})
ex.load_markets()

print("options with 'way'/'hedge'/'pos':",
      {k: v for k, v in ex.options.items()
       if any(x in k.lower() for x in ("way", "hedge", "pos"))})

SYM = "SXRP/SUSDT:SUSDT"          # cheapest demo contract (min 1 XRP)
px = float(ex.publicMixGetV2MixMarketTicker(
    {"symbol": "SXRPSUSDT", "productType": "SUSDT-FUTURES"})["data"][0]["lastPr"])
print(f"\n{SYM} last = {px}")

attempts = [
    ("options.oneWayMode=True", {"oneWayMode": True}, True),
    ("params oneWayMode", {"oneWayMode": True}, False),
    ("params tradeSide=open", {"tradeSide": "open"}, False),
    ("params reduceOnly=False+hedged=False", {"hedged": False}, False),
]

for label, extra, set_option in attempts:
    print(f"\n--- {label} ---")
    if set_option:
        ex.options["oneWayMode"] = True
        params = {"marginMode": "isolated"}
    else:
        ex.options.pop("oneWayMode", None)
        params = {"marginMode": "isolated", **extra}
    try:
        r = ex.create_order(SYM, "market", "sell", 1, None, params)
        print("  ORDER OK:", r.get("id"), r.get("status"))
        # immediately flatten so we leave nothing open
        try:
            c = ex.create_order(SYM, "market", "buy", 1, None,
                                {"marginMode": "isolated", "reduceOnly": True, **extra})
            print("  closed with:", c.get("id"))
        except Exception as e2:
            print("  close failed:", str(e2)[:160])
        break
    except Exception as e:
        print("  ERR", str(e)[:190])
