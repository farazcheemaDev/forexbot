"""Discover Bitget DEMO (SUSDT-FUTURES) symbols and how to trade them."""
import os

import ccxt

key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                os.getenv("BITGET_PASSWORD"))
ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                  "options": {"defaultType": "swap"}})

print("=== demo contracts (SUSDT-FUTURES) ===")
try:
    r = ex.publicMixGetV2MixMarketContracts({"productType": "SUSDT-FUTURES"})
    data = r.get("data", [])
    print(f"  {len(data)} demo contracts")
    for c in data[:12]:
        print(f"   {c.get('symbol'):16} base={c.get('baseCoin'):8} quote={c.get('quoteCoin'):8} "
              f"minLev={c.get('minLever')} maxLev={c.get('maxLever')} "
              f"minTradeNum={c.get('minTradeNum')} sizeMulti={c.get('sizeMultiplier')}")
except Exception as e:
    print("  ERR", str(e)[:200])

print("\n=== does ccxt load these as markets? ===")
ex.load_markets()
s_syms = [s for s in ex.symbols if "SUSDT" in s.upper() or "SBTC" in s.upper()]
print(f"  ccxt symbols containing SUSDT/SBTC: {len(s_syms)} -> {s_syms[:10]}")

print("\n=== demo account + positions via implicit v2 ===")
for name, fn, params in (
    ("accounts", ex.privateMixGetV2MixAccountAccounts, {"productType": "SUSDT-FUTURES"}),
    ("positions", ex.privateMixGetV2MixPositionAllPosition,
     {"productType": "SUSDT-FUTURES", "marginCoin": "SUSDT"}),
):
    try:
        r = fn(params)
        print(f"  {name}: {str(r.get('data'))[:260]}")
    except Exception as e:
        print(f"  {name}: ERR {str(e)[:200]}")

print("\n=== demo ticker ===")
try:
    r = ex.publicMixGetV2MixMarketTicker({"symbol": "SBTCSUSDT", "productType": "SUSDT-FUTURES"})
    print("  SBTCSUSDT:", str(r.get("data"))[:200])
except Exception as e:
    print("  ERR", str(e)[:200])
