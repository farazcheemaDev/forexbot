"""Donchian channel breakout ('turtle'-style). Classic trend/momentum entry.

BUY when close breaks above the highest high of the prior N bars.
SELL when close breaks below the lowest low of the prior N bars.
An optional trend EMA filters counter-trend breakouts.
"""
from __future__ import annotations

import pandas as pd

from bot.core.indicators import donchian, ema
from bot.strategies.base import Action, Strategy


class DonchianBreakout(Strategy):
    name = "donchian_breakout"

    def __init__(self, period: int = 20, trend: int = 200, use_trend: bool = True,
                 long_only: bool = False):
        super().__init__(period=period, trend=trend, use_trend=use_trend,
                         long_only=long_only)
        self.period, self.trend, self.use_trend = period, trend, use_trend
        self.long_only = long_only

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        close = candles["close"]
        lower, upper = donchian(candles, self.period)

        buy = close > upper
        sell = (close < lower) & (not self.long_only)
        if self.use_trend:
            et = ema(close, self.trend)
            buy &= close > et
            sell &= close < et

        sig = pd.Series(Action.HOLD, index=candles.index, dtype=int)
        sig[buy] = Action.BUY
        sig[sell] = Action.SELL
        return sig.shift(1).fillna(Action.HOLD).astype(int)
