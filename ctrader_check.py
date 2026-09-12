"""cTrader Open API connection test (IC Markets demo, Path via cTrader).

Read-only: authenticates the app + account, finds the gold symbol, pulls a few
H1 candles. Proves the pipe before we build order execution.

Set these env vars first (from the Open API app + Playground; see chat steps):
    setx CTRADER_CLIENT_ID "..."
    setx CTRADER_CLIENT_SECRET "..."
    setx CTRADER_ACCESS_TOKEN "..."
    setx CTRADER_ACCOUNT_ID "123456"        # ctidTraderAccountId (numeric)
(reopen shell), then:  python ctrader_check.py

NOTE: draft against ctrader-open-api 0.9.2 (Twisted). Signatures/decoding will
be confirmed & fixed on first real run with live credentials.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from twisted.internet import reactor

from ctrader_open_api import Client, EndPoints, Protobuf, TcpProtocol
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import (
    ProtoOAApplicationAuthReq,
)
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAGetTrendbarsReq,
    ProtoOASymbolsListReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod

CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
ACCOUNT_ID = int(os.getenv("CTRADER_ACCOUNT_ID", "0"))
SYMBOL_NAME = "XAUUSD"
PRICE_SCALE = 1e5

client = Client(EndPoints.PROTOBUF_DEMO_HOST, EndPoints.PROTOBUF_PORT, TcpProtocol)
_symbol_id = {"id": None}


def stop(msg=""):
    if msg:
        print(msg)
    if reactor.running:
        reactor.stop()


def on_error(failure):
    stop(f"[FAIL] {failure}")


def connected(_c):
    print("connected; authenticating application...")
    req = ProtoOAApplicationAuthReq()
    req.clientId = CLIENT_ID
    req.clientSecret = CLIENT_SECRET
    client.send(req).addCallbacks(app_authed, on_error)


def app_authed(_res):
    print("app authed; authenticating account...")
    req = ProtoOAAccountAuthReq()
    req.ctidTraderAccountId = ACCOUNT_ID
    req.accessToken = ACCESS_TOKEN
    client.send(req).addCallbacks(account_authed, on_error)


def account_authed(_res):
    print(f"account {ACCOUNT_ID} authed; fetching symbol list...")
    req = ProtoOASymbolsListReq()
    req.ctidTraderAccountId = ACCOUNT_ID
    client.send(req).addCallbacks(got_symbols, on_error)


def got_symbols(res):
    msg = Protobuf.extract(res)
    for s in msg.symbol:
        if s.symbolName.upper() == SYMBOL_NAME:
            _symbol_id["id"] = s.symbolId
            break
    if _symbol_id["id"] is None:
        stop(f"[FAIL] {SYMBOL_NAME} not found among {len(msg.symbol)} symbols")
        return
    print(f"{SYMBOL_NAME} symbolId={_symbol_id['id']}; fetching H1 candles...")
    req = ProtoOAGetTrendbarsReq()
    req.ctidTraderAccountId = ACCOUNT_ID
    req.symbolId = _symbol_id["id"]
    req.period = ProtoOATrendbarPeriod.H1
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    req.fromTimestamp = now - 20 * 3600 * 1000
    req.toTimestamp = now
    client.send(req).addCallbacks(got_bars, on_error)


def got_bars(res):
    msg = Protobuf.extract(res)
    print(f"[OK] {len(msg.trendbar)} H1 {SYMBOL_NAME} candles:")
    for tb in msg.trendbar[-5:]:
        low = tb.low
        o = (low + tb.deltaOpen) / PRICE_SCALE
        h = (low + tb.deltaHigh) / PRICE_SCALE
        c = (low + tb.deltaClose) / PRICE_SCALE
        t = datetime.fromtimestamp(tb.utcTimestampInMinutes * 60, timezone.utc)
        print(f"  {t:%Y-%m-%d %H:%M}  O={o:.2f} H={h:.2f} L={low/PRICE_SCALE:.2f} C={c:.2f}")
    stop("done — cTrader read path works.")


def disconnected(_c, reason):
    print(f"disconnected: {reason}")


def main():
    if not all([CLIENT_ID, CLIENT_SECRET, ACCESS_TOKEN, ACCOUNT_ID]):
        raise SystemExit("Set CTRADER_CLIENT_ID/_SECRET/_ACCESS_TOKEN/_ACCOUNT_ID env vars.")
    client.setConnectedCallback(connected)
    client.setDisconnectedCallback(disconnected)
    client.startService()
    reactor.run()


if __name__ == "__main__":
    main()
