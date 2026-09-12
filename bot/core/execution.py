"""Order execution on MT5. Every order is tagged with our magic number so the
bot only ever touches its own positions. All prices normalized to the symbol's
digits and stop distances respected.
"""
from __future__ import annotations

import MetaTrader5 as mt5


def _filling(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    modes = getattr(info, "filling_mode", 0)
    if modes & 1:   # SYMBOL_FILLING_FOK
        fok = mt5.ORDER_FILLING_FOK
    if modes & 2:   # SYMBOL_FILLING_IOC
        return mt5.ORDER_FILLING_IOC
    if modes & 1:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def _round(symbol: str, price: float) -> float:
    return round(price, mt5.symbol_info(symbol).digits)


def min_stop_distance(symbol: str) -> float:
    """Broker's minimum SL/TP distance from price, in price units."""
    info = mt5.symbol_info(symbol)
    return info.trade_stops_level * info.point


def open_position(symbol: str, side: str, lots: float, sl: float, tp: float,
                  magic: int, comment: str = "donchian"):
    tick = mt5.symbol_info_tick(symbol)
    if side == "BUY":
        price, otype = tick.ask, mt5.ORDER_TYPE_BUY
    else:
        price, otype = tick.bid, mt5.ORDER_TYPE_SELL
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": float(lots),
        "type": otype, "price": price, "sl": _round(symbol, sl),
        "tp": _round(symbol, tp), "deviation": 30, "magic": magic,
        "comment": comment, "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _filling(symbol),
    }
    return mt5.order_send(req)


def our_positions(symbol: str, magic: int):
    ps = mt5.positions_get(symbol=symbol) or []
    return [p for p in ps if p.magic == magic]


def close_position(pos):
    tick = mt5.symbol_info_tick(pos.symbol)
    if pos.type == mt5.POSITION_TYPE_BUY:
        price, otype = tick.bid, mt5.ORDER_TYPE_SELL
    else:
        price, otype = tick.ask, mt5.ORDER_TYPE_BUY
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol,
        "volume": pos.volume, "type": otype, "position": pos.ticket,
        "price": price, "deviation": 30, "magic": pos.magic, "comment": "close",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": _filling(pos.symbol),
    }
    return mt5.order_send(req)


def normalize_lots(symbol: str, lots: float) -> float:
    info = mt5.symbol_info(symbol)
    step = info.volume_step or 0.01
    lots = max(info.volume_min, min(lots, info.volume_max))
    return round(round(lots / step) * step, 2)
