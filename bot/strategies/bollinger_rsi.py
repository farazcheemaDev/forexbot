"""Mean-reversion: Bollinger Bands + RSI.

BUY when price closes below the lower band AND RSI is oversold.
SELL when price closes above the upper band AND RSI is overbought.
Works best in ranging markets; the backtester will show where it doesn't.
"""
from __future__ import annotations

import pandas as pd

from bot.core.indicators import bollinger, rsi
from bot.strategies.base import Action, Strategy


class BollingerRsi(Strategy):
    name = "bollinger_rsi"

    def __init__(self, bb_period: int = 20, bb_std: float = 2.0,
                 rsi_period: int = 14, rsi_low: float = 30.0, rsi_high: float = 70.0):
        super().__init__(bb_period=bb_period, bb_std=bb_std,
                         rsi_period=rsi_period, rsi_low=rsi_low, rsi_high=rsi_high)
        self.bb_period, self.bb_std = bb_period, bb_std
        self.rsi_period, self.rsi_low, self.rsi_high = rsi_period, rsi_low, rsi_high

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        close = candles["close"]
        lower, _mid, upper = bollinger(close, self.bb_period, self.bb_std)
        r = rsi(close, self.rsi_period)

        buy = (close < lower) & (r < self.rsi_low)
        sell = (close > upper) & (r > self.rsi_high)

        sig = pd.Series(Action.HOLD, index=candles.index, dtype=int)
        sig[buy] = Action.BUY
        sig[sell] = Action.SELL
        return sig.shift(1).fillna(Action.HOLD).astype(int)
