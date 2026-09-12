"""Trend-following: EMA crossover.

BUY when fast EMA crosses above slow EMA, SELL when it crosses below.
A trend filter (price vs a longer EMA) optionally suppresses counter-trend entries.
"""
from __future__ import annotations

import pandas as pd

from bot.core.indicators import ema
from bot.strategies.base import Action, Strategy


class EmaCross(Strategy):
    name = "ema_cross"

    def __init__(self, fast: int = 20, slow: int = 50, trend: int = 200):
        super().__init__(fast=fast, slow=slow, trend=trend)
        self.fast, self.slow, self.trend = fast, slow, trend

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        close = candles["close"]
        ef, es, et = ema(close, self.fast), ema(close, self.slow), ema(close, self.trend)

        cross_up = (ef > es) & (ef.shift(1) <= es.shift(1))
        cross_dn = (ef < es) & (ef.shift(1) >= es.shift(1))

        sig = pd.Series(Action.HOLD, index=candles.index, dtype=int)
        sig[cross_up & (close > et)] = Action.BUY
        sig[cross_dn & (close < et)] = Action.SELL
        # act on the NEXT bar's open -> shift by 1 (no look-ahead)
        return sig.shift(1).fillna(Action.HOLD).astype(int)
