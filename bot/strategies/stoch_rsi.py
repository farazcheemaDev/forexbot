"""Stochastic RSI strategy, in two framings selected by `mode`:

  mode="reversion": classic mean reversion. BUY when %K crosses up through the
      oversold level; SELL when %K crosses down through the overbought level.
      (Fights the trend — expected to work only in ranging markets.)

  mode="pullback": trend-aligned. Only BUY oversold-recoveries when price is
      above the trend EMA (buy the dip in an uptrend); only SELL overbought
      rollovers when below it. long_only suppresses shorts.
"""
from __future__ import annotations

import pandas as pd

from bot.core.indicators import ema, stoch_rsi
from bot.strategies.base import Action, Strategy


class StochRsi(Strategy):
    name = "stoch_rsi"

    def __init__(self, rsi_period: int = 14, stoch_period: int = 14,
                 k_smooth: int = 3, d_smooth: int = 3,
                 oversold: float = 0.2, overbought: float = 0.8,
                 mode: str = "pullback", trend: int = 200, long_only: bool = False):
        super().__init__(rsi_period=rsi_period, stoch_period=stoch_period,
                         k_smooth=k_smooth, d_smooth=d_smooth, oversold=oversold,
                         overbought=overbought, mode=mode, trend=trend,
                         long_only=long_only)
        self.rsi_period, self.stoch_period = rsi_period, stoch_period
        self.k_smooth, self.d_smooth = k_smooth, d_smooth
        self.oversold, self.overbought = oversold, overbought
        self.mode, self.trend, self.long_only = mode, trend, long_only

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        close = candles["close"]
        k, _d = stoch_rsi(close, self.rsi_period, self.stoch_period,
                          self.k_smooth, self.d_smooth)

        cross_up = (k > self.oversold) & (k.shift(1) <= self.oversold)
        cross_dn = (k < self.overbought) & (k.shift(1) >= self.overbought)

        buy = cross_up
        sell = cross_dn & (not self.long_only)
        if self.mode == "pullback":
            et = ema(close, self.trend)
            buy &= close > et
            sell &= close < et

        sig = pd.Series(Action.HOLD, index=candles.index, dtype=int)
        sig[buy] = Action.BUY
        sig[sell] = Action.SELL
        return sig.shift(1).fillna(Action.HOLD).astype(int)
