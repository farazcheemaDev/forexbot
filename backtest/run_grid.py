"""Brute-force test harness: every strategy x filter combo x exit mode.

Ranks by OUT-OF-SAMPLE performance and flags combos that are profitable in BOTH
the train and test periods (the only ones worth trusting).

    python -m backtest.run_grid                # EURUSDm H1, 25000 bars
    python -m backtest.run_grid --bars 40000 --min-trades 30
"""
from __future__ import annotations

import argparse
import sys
from itertools import product
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.filters import apply_atr_filter, apply_session_filter  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.bollinger_rsi import BollingerRsi  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402
from bot.strategies.ema_cross import EmaCross  # noqa: E402
from bot.strategies.macd_trend import MacdTrend  # noqa: E402
from bot.strategies.rsi_trend import RsiTrend  # noqa: E402
from bot.strategies.stoch_rsi import StochRsi  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}

STRATEGIES = [
    EmaCross(20, 50, 200),
    MacdTrend(12, 26, 9, 200),
    RsiTrend(14, 40, 60, 200),
    DonchianBreakout(20, 200, True),
    BollingerRsi(20, 2.0, 14),
    StochRsi(mode="pullback", long_only=False),
    StochRsi(mode="reversion", long_only=False),
]


def _strat_label(s):
    if s.name == "stoch_rsi":
        return f"stoch_rsi:{s.params['mode']}"
    return s.name
FILTERS = ["none", "session", "atr", "session+atr"]
EXITS = ["fixed", "atr", "atr_trail"]


def get_history(symbol, timeframe, bars):
    """Assumes mt5 is already initialized."""
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, _TF[timeframe], 0, bars)
    if rates is None or len(rates) == 0:
        raise SystemExit(f"No history for {symbol} {timeframe}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.reset_index(drop=True)


def apply_filter(sig, candles, kind):
    if kind in ("session", "session+atr"):
        sig = apply_session_filter(sig, candles)
    if kind in ("atr", "session+atr"):
        sig = apply_atr_filter(sig, candles)
    return sig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=25000)
    ap.add_argument("--min-trades", type=int, default=20)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--symbol", type=str, default=None)
    ap.add_argument("--tf", type=str, default=None)
    args = ap.parse_args()

    conf = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config" / "config.yaml", encoding="utf-8"))
    symbol = args.symbol or conf["trading"]["symbol"]
    tf = args.tf or conf["trading"]["timeframe"]
    risk = conf["risk"]

    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()} (open MT5 + log into demo)")
    spec = get_spec(symbol)
    df = get_history(symbol, tf, args.bars)
    mt5.shutdown()
    print(f"spec: pip_size={spec.pip_size} pip_value/lot=${spec.pip_value_per_lot} "
          f"spread={spec.spread_pips}pips digits={spec.digits}")
    n = int(len(df) * 0.7)
    train, test = df.iloc[:n].reset_index(drop=True), df.iloc[n:].reset_index(drop=True)
    print(f"{symbol} {tf}: {len(df)} bars  train={len(train)}  test={len(test)}")
    print(f"span {df['time'].iloc[0]} -> {df['time'].iloc[-1]}\n")

    rows = []
    for strat, filt, exit_mode in product(STRATEGIES, FILTERS, EXITS):
        cfg = BacktestConfig(
            pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
            spread_pips=max(spec.spread_pips, 0.1),
            exit_mode=exit_mode,
            sl_pips=risk["default_sl_pips"], tp_pips=risk["default_tp_pips"],
            risk_per_trade_pct=risk["risk_per_trade_pct"],
        )
        m = {}
        for label, part in (("in", train), ("out", test)):
            sig = apply_filter(strat.signals(part), part, filt)
            m[label] = run_backtest(part, sig, cfg).metrics()
        rows.append({
            "strategy": _strat_label(strat), "filter": filt, "exit": exit_mode,
            "in_ret": m["in"].get("return_pct", 0), "in_pf": m["in"].get("profit_factor", 0),
            "out_trades": m["out"].get("n_trades", 0),
            "out_ret": m["out"].get("return_pct", 0), "out_pf": m["out"].get("profit_factor", 0),
            "out_win": m["out"].get("win_rate", 0), "out_dd": m["out"].get("max_drawdown_pct", 0),
        })

    res = pd.DataFrame(rows)
    res = res[res["out_trades"] >= args.min_trades]
    res["robust"] = (res["in_ret"] > 0) & (res["out_ret"] > 0)
    res = res.sort_values(["out_ret"], ascending=False)

    pd.set_option("display.width", 200, "display.max_columns", 20)
    print(f"=== TOP {args.top} by OUT-OF-SAMPLE return (min {args.min_trades} test trades) ===")
    print(res.head(args.top).to_string(index=False))

    robust = res[res["robust"]]
    print(f"\n=== ROBUST (profitable in BOTH train AND test): {len(robust)} combos ===")
    print(robust.to_string(index=False) if len(robust) else "  none")


if __name__ == "__main__":
    main()
