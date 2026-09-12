"""Level-fade mean-reversion — an attempt to encode the discretionary scalper's
judgment: fade price only when it stretches INTO a real level (a round number
or the prior day's high/low) AND momentum is exhausted (RSI extreme).

SELL when price pushes up to resistance (round level or prior-day high) with
RSI overbought. BUY when it drops to support (round level or prior-day low)
with RSI oversold. This is 'fade a stretched move at a level', not 'fade every
Bollinger touch'.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot.core.indicators import rsi
from bot.strategies.base import Action, Strategy


class LevelFade(Strategy):
    name = "level_fade"

    def __init__(self, round_step: float = 100.0, prox: float = 8.0,
                 rsi_period: int = 14, rsi_hi: float = 68.0, rsi_lo: float = 32.0,
                 use_prior_day: bool = True):
        super().__init__(round_step=round_step, prox=prox, rsi_period=rsi_period,
                         rsi_hi=rsi_hi, rsi_lo=rsi_lo, use_prior_day=use_prior_day)
        self.round_step, self.prox = round_step, prox
        self.rsi_period, self.rsi_hi, self.rsi_lo = rsi_period, rsi_hi, rsi_lo
        self.use_prior_day = use_prior_day

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        c = candles["close"]
        high, low = candles["high"], candles["low"]
        r = rsi(c, self.rsi_period)

        # nearest round levels
        res_round = np.ceil(c / self.round_step) * self.round_step
        sup_round = np.floor(c / self.round_step) * self.round_step
        near_res = high >= (res_round - self.prox)
        near_sup = low <= (sup_round + self.prox)

        # prior-day high/low
        if self.use_prior_day:
            date = candles["time"].dt.date
            daily = candles.assign(date=date).groupby("date").agg(
                dh=("high", "max"), dl=("low", "min"))
            pdh = date.map(daily["dh"].shift(1))
            pdl = date.map(daily["dl"].shift(1))
            near_res = near_res | (pdh.notna() & (high >= pdh - self.prox))
            near_sup = near_sup | (pdl.notna() & (low <= pdl + self.prox))

        sell = near_res & (r > self.rsi_hi)
        buy = near_sup & (r < self.rsi_lo)

        sig = pd.Series(Action.HOLD, index=candles.index, dtype=int)
        sig[buy] = Action.BUY
        sig[sell] = Action.SELL
        return sig.shift(1).fillna(Action.HOLD).astype(int)
