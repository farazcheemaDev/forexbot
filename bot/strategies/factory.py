"""Build a strategy instance from a config name + params dict."""
from __future__ import annotations

from bot.strategies.bollinger_rsi import BollingerRsi
from bot.strategies.donchian_breakout import DonchianBreakout
from bot.strategies.ema_cross import EmaCross
from bot.strategies.macd_trend import MacdTrend
from bot.strategies.rsi_trend import RsiTrend
from bot.strategies.stoch_rsi import StochRsi

_REGISTRY = {
    "ema_cross": EmaCross,
    "macd_trend": MacdTrend,
    "rsi_trend": RsiTrend,
    "donchian_breakout": DonchianBreakout,
    "bollinger_rsi": BollingerRsi,
    "stoch_rsi": StochRsi,
}


def build_strategy(name: str, params: dict | None = None):
    if name not in _REGISTRY:
        raise ValueError(f"unknown strategy '{name}'. Known: {list(_REGISTRY)}")
    return _REGISTRY[name](**(params or {}))
