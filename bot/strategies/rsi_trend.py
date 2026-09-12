"""RSI pullback in the direction of the trend.

In an uptrend (price > trend EMA), BUY when RSI dips out of oversold (crosses
back above rsi_low). In a downtrend, SELL when RSI drops back below rsi_high.
This is 'buy the dip in a trend', not raw mean reversion.
"""
from __future__ import annotations

import pandas as pd

from bot.core.indicators import ema, rsi
from bot.strategies.base import Action, Strategy


class RsiTrend(Strategy):
    name = "rsi_trend"

    def __init__(self, rsi_period: int = 14, rsi_low: float = 40.0,
                 rsi_high: float = 60.0, trend: int = 200):
        super().__init__(rsi_period=rsi_period, rsi_low=rsi_low,
                         rsi_high=rsi_high, trend=trend)
        self.rsi_period, self.rsi_low, self.rsi_high, self.trend = (
            rsi_period, rsi_low, rsi_high, trend)

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        close = candles["close"]
        r = rsi(close, self.rsi_period)
        et = ema(close, self.trend)

        up = close > et
        dn = close < et
        buy = up & (r > self.rsi_low) & (r.shift(1) <= self.rsi_low)
        sell = dn & (r < self.rsi_high) & (r.shift(1) >= self.rsi_high)

        sig = pd.Series(Action.HOLD, index=candles.index, dtype=int)
        sig[buy] = Action.BUY
        sig[sell] = Action.SELL
        return sig.shift(1).fillna(Action.HOLD).astype(int)
