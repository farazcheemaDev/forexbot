"""Walk-forward validation (the real robustness test).

For each fold: optimize the Donchian period on the in-sample window, then trade
that choice on the FOLLOWING out-of-sample window. Concatenate all OOS windows.
A strategy that only worked in one lucky trend will fall apart here; a real edge
stays positive across most folds.

    python -m backtest.walkforward --symbol XAUUSDm --tf H1 --bars 25000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}
PERIOD_GRID = [10, 15, 20, 30, 40, 55]


def load_history(symbol, tf, bars):
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    spec = get_spec(symbol)
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, _TF[tf], 0, bars)
    mt5.shutdown()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.reset_index(drop=True), spec


def make_cfg(spec, risk):
    return BacktestConfig(
        pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
        spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
        risk_per_trade_pct=risk["risk_per_trade_pct"],
    )


def best_period(train, cfg):
    best, best_ret = PERIOD_GRID[0], -1e9
    for p in PERIOD_GRID:
        sig = DonchianBreakout(period=p, use_trend=True).signals(train)
        m = run_backtest(train, sig, cfg).metrics()
        r = m.get("return_pct", -1e9) if m.get("n_trades", 0) >= 10 else -1e9
        if r > best_ret:
            best, best_ret = p, r
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSDm")
    ap.add_argument("--tf", default="H1")
    ap.add_argument("--bars", type=int, default=25000)
    ap.add_argument("--train", type=int, default=5000)
    ap.add_argument("--test", type=int, default=2500)
    args = ap.parse_args()

    conf = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config" / "config.yaml", encoding="utf-8"))
    df, spec = load_history(args.symbol, args.tf, args.bars)
    cfg = make_cfg(spec, conf["risk"])
    print(f"{args.symbol} {args.tf}: {len(df)} bars  "
          f"{df['time'].iloc[0]} -> {df['time'].iloc[-1]}")
    print(f"walk-forward: train={args.train} test={args.test} bars per fold\n")

    all_oos_pnl = []
    start = 0
    fold = 0
    print(f"{'fold':>4} {'period':>6} {'trades':>7} {'ret%':>8} {'pf':>6} {'win%':>6} {'window'}")
    while start + args.train + args.test <= len(df):
        train = df.iloc[start:start + args.train].reset_index(drop=True)
        test = df.iloc[start + args.train:start + args.train + args.test].reset_index(drop=True)
        p = best_period(train, cfg)
        sig = DonchianBreakout(period=p, use_trend=True).signals(test)
        res = run_backtest(test, sig, cfg)
        m = res.metrics()
        for t in res.trades:
            all_oos_pnl.append(t.pnl)
        wspan = f"{test['time'].iloc[0].date()}..{test['time'].iloc[-1].date()}"
        print(f"{fold:>4} {p:>6} {m.get('n_trades',0):>7} {m.get('return_pct',0):>8} "
              f"{m.get('profit_factor',0):>6} {m.get('win_rate',0):>6} {wspan}")
        start += args.test
        fold += 1

    pnl = np.array(all_oos_pnl)
    print("\n=== AGGREGATE OUT-OF-SAMPLE (all folds stitched) ===")
    if len(pnl) == 0:
        print("no trades"); return
    eq = conf["risk"] and 10000.0
    equity = 10000.0 + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[10000.0], equity]))
    dd = (peak[1:] - equity) / peak[1:]
    gross_win = pnl[pnl > 0].sum(); gross_loss = -pnl[pnl < 0].sum()
    print(f"  trades:          {len(pnl)}")
    print(f"  net profit:      ${pnl.sum():.2f}  (start $10,000)")
    print(f"  total return:    {(equity[-1]/10000-1)*100:.1f}%")
    print(f"  win rate:        {(pnl>0).mean()*100:.1f}%")
    print(f"  profit factor:   {gross_win/gross_loss:.2f}" if gross_loss>0 else "  profit factor: inf")
    print(f"  expectancy/trade:${pnl.mean():.2f}")
    print(f"  max drawdown:    {dd.max()*100:.1f}%")


if __name__ == "__main__":
    main()
