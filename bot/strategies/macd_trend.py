"""MACD crossover with an EMA trend filter (jimtin-style, plus a trend gate)."""
from __future__ import annotations

import pandas as pd

from bot.core.indicators import ema, macd
from bot.strategies.base import Action, Strategy


class MacdTrend(Strategy):
    name = "macd_trend"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9, trend: int = 200):
        super().__init__(fast=fast, slow=slow, signal=signal, trend=trend)
        self.fast, self.slow, self.signal, self.trend = fast, slow, signal, trend

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        close = candles["close"]
        line, sigl, _hist = macd(close, self.fast, self.slow, self.signal)
        et = ema(close, self.trend)

        cross_up = (line > sigl) & (line.shift(1) <= sigl.shift(1))
        cross_dn = (line < sigl) & (line.shift(1) >= sigl.shift(1))

        sig = pd.Series(Action.HOLD, index=candles.index, dtype=int)
        sig[cross_up & (close > et)] = Action.BUY
        sig[cross_dn & (close < et)] = Action.SELL
        return sig.shift(1).fillna(Action.HOLD).astype(int)
