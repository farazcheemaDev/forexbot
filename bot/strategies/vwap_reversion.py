"""VWAP reversion — fade price when it stretches N sigma from the session VWAP,
with an RSI-exhaustion confirmation. A common systematic desk approach.
"""
from __future__ import annotations

import pandas as pd

from bot.core.indicators import rsi, session_vwap
from bot.strategies.base import Action, Strategy


class VwapReversion(Strategy):
    name = "vwap_reversion"

    def __init__(self, k: float = 2.0, rsi_period: int = 14,
                 rsi_hi: float = 65.0, rsi_lo: float = 35.0):
        super().__init__(k=k, rsi_period=rsi_period, rsi_hi=rsi_hi, rsi_lo=rsi_lo)
        self.k, self.rsi_period, self.rsi_hi, self.rsi_lo = k, rsi_period, rsi_hi, rsi_lo

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        vwap, sigma = session_vwap(candles)
        c = candles["close"]
        r = rsi(c, self.rsi_period)

        sell = (c > vwap + self.k * sigma) & (r > self.rsi_hi)
        buy = (c < vwap - self.k * sigma) & (r < self.rsi_lo)

        sig = pd.Series(Action.HOLD, index=candles.index, dtype=int)
        sig[buy] = Action.BUY
        sig[sell] = Action.SELL
        return sig.shift(1).fillna(Action.HOLD).astype(int)
