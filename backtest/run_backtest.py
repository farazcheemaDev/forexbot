"""Run strategies over real MT5 history with an out-of-sample split.

    python -m backtest.run_backtest            # default EURUSDm H1, 25000 bars
    python -m backtest.run_backtest --bars 40000

Prints IN-SAMPLE (train) and OUT-OF-SAMPLE (test) metrics side by side. The
out-of-sample numbers are the ones that matter -- in-sample is easy to fake.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.strategies.bollinger_rsi import BollingerRsi  # noqa: E402
from bot.strategies.ema_cross import EmaCross  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}


def load_cfg() -> dict:
    with open(Path(__file__).resolve().parents[1] / "config" / "config.yaml",
              encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_history(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()} "
                         "(open MT5 + log into demo first)")
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, _TF[timeframe], 0, bars)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        raise SystemExit(f"No history for {symbol} {timeframe}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.reset_index(drop=True)


def fmt(metrics: dict) -> str:
    if metrics.get("n_trades", 0) == 0:
        return "  no trades"
    keys = ["n_trades", "return_pct", "win_rate", "profit_factor",
            "expectancy", "max_drawdown_pct", "final_equity"]
    return "  " + "  ".join(f"{k}={metrics[k]}" for k in keys)


def evaluate(name: str, df: pd.DataFrame, strat, cfg: BacktestConfig,
             split: float = 0.7) -> None:
    n = int(len(df) * split)
    train, test = df.iloc[:n].reset_index(drop=True), df.iloc[n:].reset_index(drop=True)
    print(f"\n=== {name} ({strat.params}) ===")
    for label, part in [("IN-SAMPLE ", train), ("OUT-SAMPLE", test)]:
        sig = strat.signals(part)
        res = run_backtest(part, sig, cfg)
        print(f"{label}:{fmt(res.metrics())}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=25000)
    args = ap.parse_args()

    conf = load_cfg()
    symbol = conf["trading"]["symbol"]
    tf = conf["trading"]["timeframe"]
    risk = conf["risk"]

    df = get_history(symbol, tf, args.bars)
    print(f"Loaded {len(df)} {symbol} {tf} bars: "
          f"{df['time'].iloc[0]} -> {df['time'].iloc[-1]}")

    cfg = BacktestConfig(
        sl_pips=risk["default_sl_pips"],
        tp_pips=risk["default_tp_pips"],
        risk_per_trade_pct=risk["risk_per_trade_pct"],
    )

    evaluate("EMA cross (trend)", df, EmaCross(fast=20, slow=50, trend=200), cfg)
    evaluate("Bollinger+RSI (mean reversion)", df,
             BollingerRsi(bb_period=20, bb_std=2.0, rsi_period=14), cfg)


if __name__ == "__main__":
    main()
