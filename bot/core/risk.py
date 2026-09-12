"""Risk management: position sizing and account-level guards.

Kept deliberately simple and conservative. The live loop must call these BEFORE
sending any order.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskConfig:
    risk_per_trade_pct: float = 0.5
    max_daily_loss_pct: float = 3.0
    max_open_trades: int = 2
    default_sl_pips: float = 30.0
    default_tp_pips: float = 60.0


def lot_size(balance: float, risk_pct: float, sl_pips: float,
             pip_value_per_lot: float, min_lot: float = 0.01,
             max_lot: float = 50.0, lot_step: float = 0.01) -> float:
    """Volume (lots) so that a stop-out loses ~risk_pct of balance.

    risk_amount = balance * risk_pct/100
    loss_per_lot = sl_pips * pip_value_per_lot
    lots = risk_amount / loss_per_lot, rounded to lot_step, clamped.
    """
    if sl_pips <= 0 or pip_value_per_lot <= 0:
        return min_lot
    risk_amount = balance * (risk_pct / 100.0)
    loss_per_lot = sl_pips * pip_value_per_lot
    raw = risk_amount / loss_per_lot
    stepped = max(min_lot, round(raw / lot_step) * lot_step)
    return float(min(stepped, max_lot))


def daily_loss_exceeded(start_equity: float, current_equity: float,
                        max_daily_loss_pct: float) -> bool:
    dd = (start_equity - current_equity) / start_equity * 100.0
    return dd >= max_daily_loss_pct
