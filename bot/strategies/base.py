"""Strategy plug-in interface.

Each strategy computes a vectorized signal Series over a candle DataFrame, so
the backtester and the live loop use the EXACT same logic. Signals are computed
on CLOSED bars and shifted by one bar so we never act on information from a
still-forming candle (look-ahead-bias guard).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import pandas as pd


class Action(IntEnum):
    HOLD = 0
    BUY = 1
    SELL = 2


@dataclass
class Signal:
    action: Action
    reason: str = ""


class Strategy:
    name = "base"

    def __init__(self, **params):
        self.params = params

    def signals(self, candles: pd.DataFrame) -> pd.Series:
        """Return an integer Series (Action values) aligned to candles.index.
        Must already be shifted to avoid look-ahead bias."""
        raise NotImplementedError

    def generate(self, candles: pd.DataFrame) -> Signal:
        """Live convenience: the signal for the latest closed bar."""
        s = self.signals(candles)
        if len(s) == 0:
            return Signal(Action.HOLD, "no data")
        return Signal(Action(int(s.iloc[-1])), reason=self.name)
