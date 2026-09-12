"""Liquidity-sweep / stop-hunt reversal (ICT / order-flow style).

Price pokes ABOVE a liquidity level (prior-day high or recent swing high) then
closes back BELOW it -> the breakout was a trap (stop hunt) -> fade it, SELL.
Mirror for a sweep below support -> BUY. This is a systematic, team-followable
rule (no discretion), unlike 'fade every extreme'.
"""
from __future__ import annotations

import pandas as pd

from bot.strategies.base import Action, Strategy


class LiquiditySweep(Strategy):
    name = "liquidity_sweep"

    def __init__(self, swing: int = 20, use_prior_day: bool = True, buffer: float = 0.0):
        super().__init__(swing=swing, use_prior_day=use_prior_day, buffer=buffer)
        self.swing, self.use_prior_day, self.buffer = swing, use_prior_day, buffer

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        high, low, close = candles["high"], candles["low"], candles["close"]
        swing_hi = high.rolling(self.swing).max().shift(1)
        swing_lo = low.rolling(self.swing).min().shift(1)

        res = swing_hi
        sup = swing_lo
        if self.use_prior_day:
            date = candles["time"].dt.date
            daily = candles.assign(date=date).groupby("date").agg(
                dh=("high", "max"), dl=("low", "min"))
            pdh = date.map(daily["dh"].shift(1))
            pdl = date.map(daily["dl"].shift(1))
            res = pd.concat([swing_hi, pdh], axis=1).max(axis=1)
            sup = pd.concat([swing_lo, pdl], axis=1).min(axis=1)

        # swept above resistance then rejected back below -> SELL
        sell = (high > res + self.buffer) & (close < res)
        buy = (low < sup - self.buffer) & (close > sup)

        sig = pd.Series(Action.HOLD, index=candles.index, dtype=int)
        sig[buy] = Action.BUY
        sig[sell] = Action.SELL
        return sig.shift(1).fillna(Action.HOLD).astype(int)
