"""Verify open demo positions AND that stop-loss / take-profit really attached."""
import os

import ccxt

key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                os.getenv("BITGET_PASSWORD"))
ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                  "enableRateLimit": True, "options": {"defaultType": "swap"}})
ex.load_markets()
PT, MC = "SUSDT-FUTURES", "SUSDT"

r = ex.privateMixGetV2MixAccountAccounts({"productType": PT})
for a in r.get("data", []):
    if a.get("marginCoin") == MC:
        print(f"EQUITY {a.get('accountEquity')} SUSDT  available={a.get('available')} "
              f"uPnL={a.get('unrealizedPL')}\n")

print("=== OPEN POSITIONS ===")
r = ex.privateMixGetV2MixPositionAllPosition({"productType": PT, "marginCoin": MC})
pos = [p for p in (r.get("data") or []) if float(p.get("total") or 0)]
for p in pos:
    print(f"  {p.get('symbol'):12} {p.get('holdSide'):6} size={p.get('total'):10} "
          f"entry={p.get('openPriceAvg'):12} mark={p.get('markPrice'):12} "
          f"uPnL={p.get('unrealizedPL')}")
    print(f"      liq={p.get('liquidationPrice')}  lev={p.get('leverage')}  "
          f"margin={p.get('marginMode')}")
if not pos:
    print("  (none)")

print("\n=== TRIGGER ORDERS (the actual SL/TP protection) ===")
found_any = False
for plan in ("profit_loss", "normal_plan"):
    try:
        r = ex.privateMixGetV2MixOrderOrdersPlanPending(
            {"productType": PT, "planType": plan})
        data = (r.get("data") or {}).get("entrustedList") or []
        for o in data:
            found_any = True
            print(f"  [{plan}] {o.get('symbol')} type={o.get('planType')} "
                  f"trigger={o.get('triggerPrice')} side={o.get('side')} "
                  f"size={o.get('size')} status={o.get('planStatus')}")
        if not data:
            print(f"  [{plan}] none")
    except Exception as e:
        print(f"  [{plan}] ERR {str(e)[:160]}")

print("\nVERDICT:", "positions ARE protected by exchange-side stops"
      if found_any else "*** NO TRIGGER ORDERS FOUND - positions are UNPROTECTED ***")
