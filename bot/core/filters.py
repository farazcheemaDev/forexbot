"""Signal filters: applied AFTER a strategy produces signals, to suppress
entries in unfavorable conditions. Kept separate so we can toggle them in tests.

NOTE on time: MT5 candle timestamps are in BROKER SERVER time (Exness ~ EET,
GMT+2/+3), not UTC. The default session window is chosen broadly to cover the
active London + New York hours regardless of the exact offset.
"""
from __future__ import annotations

import pandas as pd

from bot.core.indicators import adx, atr, efficiency_ratio
from bot.strategies.base import Action


def apply_session_filter(signals: pd.Series, candles: pd.DataFrame,
                         start_hour: int = 8, end_hour: int = 21) -> pd.Series:
    """Zero out signals whose bar falls outside [start_hour, end_hour) server time."""
    hours = pd.to_datetime(candles["time"]).dt.hour.values
    mask = (hours >= start_hour) & (hours < end_hour)
    out = signals.copy()
    out[~mask] = Action.HOLD
    return out


def apply_atr_filter(signals: pd.Series, candles: pd.DataFrame,
                     period: int = 14, min_atr_pips: float = 4.0,
                     pip_size: float = 0.0001) -> pd.Series:
    """Only allow entries when volatility (ATR) is above a floor -> skip dead chop."""
    a = atr(candles, period) / pip_size
    out = signals.copy()
    out[a < min_atr_pips] = Action.HOLD
    return out


def apply_atr_quantile_filter(signals: pd.Series, candles: pd.DataFrame,
                              period: int = 14, min_quantile: float = 0.25) -> pd.Series:
    """Drop entries whose ATR is below the given quantile of ATR over this window.
    Targets the low-volatility entries that statistically lose money."""
    a = atr(candles, period)
    threshold = a.quantile(min_quantile)
    out = signals.copy()
    out[a < threshold] = Action.HOLD
    return out


def apply_adx_filter(signals: pd.Series, candles: pd.DataFrame,
                     period: int = 14, min_adx: float = 25.0) -> pd.Series:
    """Only allow entries when the market is actually trending (ADX >= min_adx).
    Directly targets the choppy-range periods where breakouts bleed."""
    a = adx(candles, period)
    out = signals.copy()
    out[a < min_adx] = Action.HOLD
    return out


def apply_adx_ceiling_filter(signals: pd.Series, candles: pd.DataFrame,
                             period: int = 14, max_adx: float = 25.0) -> pd.Series:
    """Only allow entries when the market is RANGING (ADX <= max_adx).
    For mean-reversion: fade extremes only when there's no strong trend."""
    a = adx(candles, period)
    out = signals.copy()
    out[a > max_adx] = Action.HOLD
    return out


def apply_er_filter(signals: pd.Series, candles: pd.DataFrame,
                    period: int = 20, min_er: float = 0.30) -> pd.Series:
    """Only allow entries when the Efficiency Ratio shows a clean trend."""
    er = efficiency_ratio(candles["close"], period)
    out = signals.copy()
    out[er < min_er] = Action.HOLD
    return out
