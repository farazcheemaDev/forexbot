"""Determine Bitget demo position mode and the order format it accepts."""
import os

import ccxt

key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                os.getenv("BITGET_PASSWORD"))
ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                  "enableRateLimit": True, "options": {"defaultType": "swap"}})
ex.load_markets()
RAW, PT, MC = "SXRPSUSDT", "SUSDT-FUTURES", "SUSDT"

print("=== account info (look for posMode) ===")
try:
    r = ex.privateMixGetV2MixAccountAccount(
        {"symbol": RAW, "productType": PT, "marginCoin": MC})
    d = r.get("data", {})
    print("  posMode:", d.get("posMode"), "| marginMode:", d.get("marginMode"),
          "| available:", d.get("available"))
except Exception as e:
    print("  ERR", str(e)[:200])

print("\n=== try forcing one-way position mode ===")
try:
    r = ex.privateMixPostV2MixAccountSetPositionMode(
        {"productType": PT, "posMode": "one_way_mode"})
    print("  set one_way_mode:", str(r.get("data"))[:120])
except Exception as e:
    print("  ERR", str(e)[:200])

print("\n=== raw order attempts ===")
base = {"symbol": RAW, "productType": PT, "marginMode": "isolated",
        "marginCoin": MC, "size": "10", "orderType": "market"}
variants = [
    ("one-way: side=sell, no tradeSide", {**base, "side": "sell"}),
    ("hedge: side=sell + tradeSide=open", {**base, "side": "sell", "tradeSide": "open"}),
    ("one-way: side=sell + reduceOnly=NO", {**base, "side": "sell", "reduceOnly": "NO"}),
]
placed = False
for label, params in variants:
    try:
        r = ex.privateMixPostV2MixOrderPlaceOrder(params)
        print(f"  {label}: OK -> {str(r.get('data'))[:140]}")
        placed = True
        break
    except Exception as e:
        print(f"  {label}: ERR {str(e)[:170]}")

if placed:
    print("\n=== positions now ===")
    r = ex.privateMixGetV2MixPositionAllPosition({"productType": PT, "marginCoin": MC})
    for p in (r.get("data") or []):
        if float(p.get("total") or 0):
            print(f"   {p.get('symbol')} {p.get('holdSide')} size={p.get('total')} "
                  f"entry={p.get('openPriceAvg')} uPnL={p.get('unrealizedPL')}")
            # flatten
            try:
                ex.privateMixPostV2MixOrderPlaceOrder({
                    "symbol": RAW, "productType": PT, "marginMode": "isolated",
                    "marginCoin": MC, "size": p["total"], "orderType": "market",
                    "side": "buy" if p.get("holdSide") == "short" else "sell",
                    "reduceOnly": "YES"})
                print("   flattened")
            except Exception as e:
                print("   flatten ERR", str(e)[:150])
