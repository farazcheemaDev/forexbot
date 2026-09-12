"""MT5 broker interface.

Design choice for safety: we attach to an ALREADY-RUNNING, already-logged-in
MetaTrader 5 terminal via mt5.initialize(). That means the trading password
lives only in your MT5 terminal, never in this project.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

try:
    import MetaTrader5 as mt5
except ImportError:  # so the file is importable off-Windows for editing/review
    mt5 = None

import pandas as pd

_TF_MAP = {}
if mt5 is not None:
    _TF_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }


@dataclass
class BrokerInfo:
    login: int
    server: str
    balance: float
    equity: float
    currency: str
    leverage: int


class Broker:
    def __init__(self, path: str | None = None):
        if mt5 is None:
            raise RuntimeError(
                "MetaTrader5 package not installed. Run: pip install MetaTrader5 "
                "(Windows only, needs the MT5 terminal installed)."
            )
        self.path = path

    def connect(self) -> BrokerInfo:
        """Attach to the running MT5 terminal. The terminal must be open and
        logged into your demo account, with Algo Trading enabled."""
        ok = mt5.initialize(self.path) if self.path else mt5.initialize()
        if not ok:
            raise ConnectionError(f"mt5.initialize() failed: {mt5.last_error()}")
        acct = mt5.account_info()
        if acct is None:
            raise ConnectionError(
                "Connected to terminal but no account. Log into your DEMO "
                "account inside MT5 first."
            )
        return BrokerInfo(
            login=acct.login,
            server=acct.server,
            balance=acct.balance,
            equity=acct.equity,
            currency=acct.currency,
            leverage=acct.leverage,
        )

    def shutdown(self) -> None:
        if mt5 is not None:
            mt5.shutdown()

    def get_candles(self, symbol: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        tf = _TF_MAP[timeframe]
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            raise ValueError(f"No data for {symbol} {timeframe}: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def symbol_ready(self, symbol: str) -> bool:
        info = mt5.symbol_info(symbol)
        if info is None:
            return False
        if not info.visible:
            mt5.symbol_select(symbol, True)
            time.sleep(0.2)
        return mt5.symbol_info(symbol) is not None
