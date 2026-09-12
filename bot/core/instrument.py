"""Pull real contract specs from MT5 so the backtester uses correct pip size,
pip value, and spread per instrument (EURUSD vs XAUUSD differ a lot).
"""
from __future__ import annotations

from dataclasses import dataclass

import MetaTrader5 as mt5


@dataclass
class InstrumentSpec:
    symbol: str
    pip_size: float
    pip_value_per_lot: float   # account-currency value of a 1-pip move on 1.0 lot
    spread_pips: float
    digits: int


def get_spec(symbol: str) -> InstrumentSpec:
    if not mt5.symbol_select(symbol, True):
        raise ValueError(f"cannot select symbol {symbol}")
    info = mt5.symbol_info(symbol)
    if info is None:
        raise ValueError(f"no symbol_info for {symbol}")

    point = info.point
    digits = info.digits
    # fx 5/3-digit quotes: 1 pip = 10 points; otherwise 1 pip = 1 point
    pip_size = point * 10 if digits in (3, 5) else point

    tick_size = info.trade_tick_size or point
    tick_value = info.trade_tick_value or 0.0
    pip_value_per_lot = tick_value * (pip_size / tick_size) if tick_size else 0.0

    spread_pips = (info.spread * point) / pip_size if pip_size else 0.0

    return InstrumentSpec(symbol, pip_size, round(pip_value_per_lot, 4),
                          round(spread_pips, 2), digits)
