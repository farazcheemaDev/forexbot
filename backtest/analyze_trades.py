"""Statistical autopsy of a strategy's trades.

Runs the Donchian gold strategy over full history, then slices realized P/L by
hour-of-day, weekday, month, entry-ATR bucket, and entry-ADX bucket. Reveals
systematically losing conditions we can filter out.

    python -m backtest.analyze_trades --symbol XAUUSDm --tf H1 --period 20
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
from bot.core.indicators import adx, atr  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}


def load(symbol, tf, bars):
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    spec = get_spec(symbol)
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, _TF[tf], 0, bars)
    mt5.shutdown()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.reset_index(drop=True), spec


def bucket_report(tdf, col, label):
    g = tdf.groupby(col).agg(
        trades=("pnl", "size"),
        net=("pnl", "sum"),
        win_rate=("pnl", lambda s: round((s > 0).mean() * 100, 1)),
        avg=("pnl", "mean"),
    )
    g["net"] = g["net"].round(0)
    g["avg"] = g["avg"].round(2)
    print(f"\n--- P/L by {label} ---")
    print(g.to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSDm")
    ap.add_argument("--tf", default="H1")
    ap.add_argument("--bars", type=int, default=25000)
    ap.add_argument("--period", type=int, default=20)
    args = ap.parse_args()

    conf = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config" / "config.yaml", encoding="utf-8"))
    df, spec = load(args.symbol, args.tf, args.bars)

    cfg = BacktestConfig(pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
                         spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
                         risk_per_trade_pct=conf["risk"]["risk_per_trade_pct"])
    sig = DonchianBreakout(period=args.period, use_trend=True).signals(df)
    res = run_backtest(df, sig, cfg)

    # entry-time -> ADX / ATR lookup
    a_adx = adx(df, 14); a_atr = atr(df, 14)
    lut = pd.DataFrame({"time": df["time"], "adx": a_adx.values, "atr": a_atr.values})

    trades = pd.DataFrame([{
        "entry_time": pd.Timestamp(t.entry_time),
        "side": t.side, "pnl": t.pnl,
    } for t in res.trades])
    trades = trades.merge(lut, left_on="entry_time", right_on="time", how="left")
    trades["hour"] = trades["entry_time"].dt.hour
    trades["weekday"] = trades["entry_time"].dt.day_name().str[:3]
    trades["month"] = trades["entry_time"].dt.month
    trades["atr_q"] = pd.qcut(trades["atr"], 4, labels=["ATR_low", "Q2", "Q3", "ATR_high"])
    trades["adx_bucket"] = pd.cut(trades["adx"], [0, 20, 25, 30, 100],
                                  labels=["adx<20", "20-25", "25-30", "adx>30"])

    print(f"{args.symbol} {args.tf} Donchian({args.period})  total trades={len(trades)}  "
          f"net=${trades['pnl'].sum():.0f}  win={((trades['pnl']>0).mean()*100):.1f}%")

    bucket_report(trades, "side", "SIDE (long vs short)")
    bucket_report(trades, "adx_bucket", "ADX-at-entry (trend strength)")
    bucket_report(trades, "atr_q", "ATR-at-entry (volatility quartile)")
    bucket_report(trades, "weekday", "WEEKDAY")
    # hours: only show the worst/best
    hg = trades.groupby("hour")["pnl"].agg(["size", "sum"]).round(0)
    print("\n--- P/L by HOUR (server time) ---")
    print(hg.to_string())


if __name__ == "__main__":
    main()
