"""MetaApi cloud connection test (Path A).

Connects to your Exness demo account *hosted in MetaApi's cloud* — no local MT5
terminal needed. Prints account info and a few XAUUSDm candles.

Set these environment variables first (never hard-code the token):
    setx METAAPI_TOKEN "your-token"
    setx METAAPI_ACCOUNT_ID "your-account-id"
(reopen the shell after setx), then:
    python metaapi_check.py

NOTE: draft against metaapi-cloud-sdk 29.x — exact call signatures will be
confirmed/fixed on first real run with a live token.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from metaapi_cloud_sdk import MetaApi

TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID")
SYMBOL = "XAUUSDm"


async def main():
    if not TOKEN or not ACCOUNT_ID:
        raise SystemExit("Set METAAPI_TOKEN and METAAPI_ACCOUNT_ID env vars first.")

    api = MetaApi(TOKEN)
    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)

    print(f"account state={account.state} connection={account.connection_status}")
    if account.state != "DEPLOYED":
        print("deploying account to MetaApi cloud...")
        await account.deploy()
    print("waiting for broker connection...")
    await account.wait_connected()

    connection = account.get_rpc_connection()
    await connection.connect()
    await connection.wait_synchronized()

    info = await connection.get_account_information()
    print(f"[OK] {info['login']} {info.get('server')} "
          f"balance={info['balance']} {info['currency']} "
          f"equity={info['equity']} leverage=1:{info.get('leverage')}")

    # historical candles (MT5 only)
    now = datetime.now(timezone.utc)
    candles = await account.get_historical_candles(SYMBOL, "1h", now, 5)
    print(f"[OK] last {len(candles)} {SYMBOL} 1h candles:")
    for c in candles:
        print(f"  {c['time']}  O={c['open']} H={c['high']} L={c['low']} C={c['close']}")

    await connection.close()
    print("done — MetaApi cloud path works.")


if __name__ == "__main__":
    asyncio.run(main())
