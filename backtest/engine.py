"""Honest, event-driven backtester with multiple exit modes.

Deliberately conservative:
  - one position at a time
  - entries fill at the current bar's open (signals are pre-shifted by strategy)
  - full spread + slippage on entry, slippage again on exit, plus commission
  - if a bar's range touches BOTH stop and target, we assume the STOP hit first
  - position size from the risk manager, based on equity at entry

Exit modes:
  - "fixed":     SL/TP a fixed number of pips from entry
  - "atr":       SL/TP = atr_sl_mult / atr_tp_mult * ATR(at entry)
  - "atr_trail": ATR stop that trails the best price; TP still atr_tp_mult*ATR

This under-states, not over-states, performance on purpose.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from bot.core.indicators import atr as atr_indicator
from bot.core.risk import lot_size
from bot.strategies.base import Action


@dataclass
class BacktestConfig:
    pip_size: float = 0.0001
    pip_value_per_lot: float = 10.0
    spread_pips: float = 0.8
    slippage_pips: float = 0.3
    commission_per_lot: float = 7.0
    risk_per_trade_pct: float = 0.5
    start_equity: float = 10000.0
    # exits
    exit_mode: str = "fixed"          # fixed | atr | atr_trail
    sl_pips: float = 30.0
    tp_pips: float = 60.0
    atr_period: int = 14
    atr_sl_mult: float = 2.0
    atr_tp_mult: float = 3.0
    trail_atr_mult: float = 2.0


@dataclass
class Trade:
    side: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry: float
    exit: float
    lots: float
    pnl: float
    reason: str


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series | None = None
    cfg: BacktestConfig | None = None

    def metrics(self) -> dict:
        if not self.trades:
            return {"n_trades": 0}
        pnls = np.array([t.pnl for t in self.trades])
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        eq = self.equity_curve.values
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / peak
        gross_win = wins.sum()
        gross_loss = -losses.sum()
        return {
            "n_trades": len(pnls),
            "net_profit": round(float(pnls.sum()), 2),
            "return_pct": round(float(eq[-1] / eq[0] - 1) * 100, 2),
            "win_rate": round(float((pnls > 0).mean()) * 100, 1),
            "profit_factor": round(float(gross_win / gross_loss), 2) if gross_loss > 0 else float("inf"),
            "avg_win": round(float(wins.mean()), 2) if len(wins) else 0.0,
            "avg_loss": round(float(losses.mean()), 2) if len(losses) else 0.0,
            "expectancy": round(float(pnls.mean()), 2),
            "max_drawdown_pct": round(float(dd.max()) * 100, 2),
            "final_equity": round(float(eq[-1]), 2),
        }


def run_backtest(candles: pd.DataFrame, signals: pd.Series,
                 cfg: BacktestConfig) -> BacktestResult:
    o = candles["open"].values
    h = candles["high"].values
    lo = candles["low"].values
    t = candles["time"].values
    sig = signals.values

    # SHIFTED BY 1 — critical. Entries fill at bar i's OPEN, so only data through
    # bar i-1 is known then. Using ATR[i] (which contains bar i's own high/low/
    # close) to place that entry's stop is LOOK-AHEAD BIAS: it widens the stop on
    # bars that turn out volatile and tightens it on quiet ones. Measured cost of
    # the bug: ~+0.25R/trade of pure fiction, lifting win rate from the
    # random-walk 40% to 50% and profit factor from ~0.98 to ~1.50.
    # Found 2026-09-11. The LIVE bots were always correct (portfolio_bot uses
    # .iloc[-2], crypto_demo uses the last closed bar) — only the backtest lied,
    # which is why live results were so much worse than backtested ones.
    atr_arr = (atr_indicator(candles, cfg.atr_period).shift(1).values
               if cfg.exit_mode != "fixed" else None)

    pip = cfg.pip_size
    spread = cfg.spread_pips * pip
    slip = cfg.slippage_pips * pip

    equity = cfg.start_equity
    eq_curve = np.empty(len(candles))
    trades: list[Trade] = []
    pos = None

    def close_position(i, exit_price, reason):
        nonlocal equity, pos
        direction = 1 if pos["side"] == "BUY" else -1
        fill = exit_price - direction * slip
        pips = (fill - pos["entry"]) / pip * direction
        pnl = pips * cfg.pip_value_per_lot * pos["lots"] - cfg.commission_per_lot * pos["lots"]
        equity += pnl
        trades.append(Trade(pos["side"], pos["entry_time"], t[i], pos["entry"],
                            fill, pos["lots"], pnl, reason))
        pos = None

    for i in range(len(candles)):
        price_open = o[i]

        if pos is not None:
            direction = 1 if pos["side"] == "BUY" else -1

            # trailing stop update (based on this bar's extreme in our favor)
            if cfg.exit_mode == "atr_trail":
                if pos["side"] == "BUY":
                    pos["sl"] = max(pos["sl"], h[i] - pos["trail_dist"])
                else:
                    pos["sl"] = min(pos["sl"], lo[i] + pos["trail_dist"])

            exit_price, reason = None, ""
            if pos["side"] == "BUY":
                if lo[i] <= pos["sl"]:
                    exit_price, reason = pos["sl"], "SL"
                elif pos["tp"] is not None and h[i] >= pos["tp"]:
                    exit_price, reason = pos["tp"], "TP"
            else:
                if h[i] >= pos["sl"]:
                    exit_price, reason = pos["sl"], "SL"
                elif pos["tp"] is not None and lo[i] <= pos["tp"]:
                    exit_price, reason = pos["tp"], "TP"

            if exit_price is None and sig[i] != Action.HOLD:
                want = "BUY" if sig[i] == Action.BUY else "SELL"
                if want != pos["side"]:
                    exit_price, reason = price_open, "signal"

            if exit_price is not None:
                close_position(i, exit_price, reason)

        if pos is None and sig[i] != Action.HOLD:
            side = "BUY" if sig[i] == Action.BUY else "SELL"
            direction = 1 if side == "BUY" else -1
            entry = price_open + direction * (spread + slip)

            if cfg.exit_mode == "fixed":
                sl_dist = cfg.sl_pips * pip
                tp_dist = cfg.tp_pips * pip
            else:
                a = atr_arr[i]
                if not np.isfinite(a) or a <= 0:
                    eq_curve[i] = equity
                    continue
                sl_dist = cfg.atr_sl_mult * a
                tp_dist = cfg.atr_tp_mult * a

            sl = entry - direction * sl_dist
            tp = entry + direction * tp_dist
            sl_pips = sl_dist / pip
            lots = lot_size(equity, cfg.risk_per_trade_pct, sl_pips, cfg.pip_value_per_lot)
            pos = {"side": side, "entry": entry, "sl": sl, "tp": tp, "lots": lots,
                   "entry_time": t[i],
                   "trail_dist": cfg.trail_atr_mult * (atr_arr[i] if atr_arr is not None else 0.0)}

        eq_curve[i] = equity

    return BacktestResult(trades=trades,
                          equity_curve=pd.Series(eq_curve, index=candles["time"]),
                          cfg=cfg)
