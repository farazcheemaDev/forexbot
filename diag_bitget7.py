"""Is the attached SL/TP what triggers 40774? Test with sufficient size."""
import os

import ccxt

key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                os.getenv("BITGET_PASSWORD"))
ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                  "enableRateLimit": True, "options": {"defaultType": "swap"}})
ex.load_markets()

SYM, RAW = "SXRP/SUSDT:SUSDT", "SXRPSUSDT"
px = float(ex.publicMixGetV2MixMarketTicker(
    {"symbol": RAW, "productType": "SUSDT-FUTURES"})["data"][0]["lastPr"])
amt = 10          # ~$13.5 notional, above the $5 minimum
sl = round(px * 1.02, 4)      # short -> stop above
tp = round(px * 0.97, 4)
print(f"{SYM} last={px} amount={amt} (~${px*amt:.2f})  sl={sl} tp={tp}\n")


def positions():
    r = ex.privateMixGetV2MixPositionAllPosition(
        {"productType": "SUSDT-FUTURES", "marginCoin": "SUSDT"})
    return [p for p in (r.get("data") or []) if float(p.get("total") or 0) != 0]


def flatten():
    for p in positions():
        side = "buy" if p.get("holdSide") == "short" else "sell"
        try:
            ex.create_order(SYM, "market", side, float(p["total"]), None,
                            {"marginMode": "isolated", "reduceOnly": True})
            print(f"  flattened {p.get('holdSide')} {p.get('total')}")
        except Exception as e:
            print("  flatten ERR", str(e)[:150])


print("--- A: WITH attached stopLoss/takeProfit ---")
try:
    r = ex.create_order(SYM, "market", "sell", amt, None, {
        "marginMode": "isolated",
        "stopLoss": {"triggerPrice": sl},
        "takeProfit": {"triggerPrice": tp}})
    print("  OK:", r.get("id"))
    flatten()
except Exception as e:
    print("  ERR", str(e)[:200])

print("\n--- B: plain order, then separate TP/SL via position endpoint ---")
try:
    r = ex.create_order(SYM, "market", "sell", amt, None, {"marginMode": "isolated"})
    print("  entry OK:", r.get("id"))
    print("  positions:", [(p.get("holdSide"), p.get("total")) for p in positions()])
    try:
        t = ex.privateMixPostV2MixOrderPlaceTpslOrder({
            "symbol": RAW, "productType": "SUSDT-FUTURES", "marginCoin": "SUSDT",
            "planType": "pos_loss", "triggerPrice": str(sl),
            "holdSide": "short", "size": str(amt)})
        print("  SL attached:", str(t.get("data"))[:120])
    except Exception as e:
        print("  SL ERR", str(e)[:180])
    try:
        t = ex.privateMixPostV2MixOrderPlaceTpslOrder({
            "symbol": RAW, "productType": "SUSDT-FUTURES", "marginCoin": "SUSDT",
            "planType": "pos_profit", "triggerPrice": str(tp),
            "holdSide": "short", "size": str(amt)})
        print("  TP attached:", str(t.get("data"))[:120])
    except Exception as e:
        print("  TP ERR", str(e)[:180])
    print("  cleaning up...")
    flatten()
except Exception as e:
    print("  ERR", str(e)[:200])

print("\nfinal positions:", positions())
