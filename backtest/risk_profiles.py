"""Risk profiles + the honest '$5/day on $50' reality check.

Takes the best gold configs, measures the DAILY return distribution, then shows
what different risk-per-trade levels do — including where drawdown crosses into
account-ruin. Also models the $50 standard-account minimum-lot problem.

    python -m backtest.risk_profiles
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1}

PROFILES = {  # name -> risk % per trade
    "Conservative": 0.5,
    "Balanced": 1.0,
    "Aggressive": 3.0,
    "Extreme": 6.0,
    "Degen": 12.0,
}


def load(symbol, tf, bars):
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, _TF[tf], 0, bars)
    spec = get_spec(symbol)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.reset_index(drop=True), spec


def daily_returns(df, spec, risk_pct, start=10000.0):
    """Backtest and return (metrics, daily_return_pct_series, blown_bool)."""
    cfg = BacktestConfig(pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
                         spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
                         risk_per_trade_pct=risk_pct, start_equity=start)
    sig = DonchianBreakout(20, 200, True, long_only=True).signals(df)
    res = run_backtest(df, sig, cfg)
    eq = res.equity_curve
    blown = bool((eq.values <= start * 0.1).any())      # lost 90% = effectively ruined
    # daily % change of the equity curve
    daily = eq.resample("1D").last().dropna()
    dret = daily.pct_change().dropna() * 100
    return res.metrics(), dret, blown


def main():
    if not mt5.initialize():
        raise SystemExit(f"MT5 init: {mt5.last_error()}")

    # --- daily distribution on the champion (gold H1) at conservative risk ---
    df_h1, spec = load("XAUUSDm", "H1", 25000)
    m, dret, _ = daily_returns(df_h1, spec, 0.5)
    print("=== GOLD H1 daily return distribution (Conservative 0.5%/trade) ===")
    print(f"  mean/day: {dret.mean():.3f}%   median: {dret.median():.3f}%")
    print(f"  best day: {dret.max():.2f}%   worst day: {dret.min():.2f}%")
    print(f"  % days green: {(dret>0).mean()*100:.1f}%   trading days: {len(dret)}")
    print(f"  --> to average +10%/day you'd need ~{10/max(dret.mean(),1e-9):.0f}x this risk")

    # --- risk profiles: scale risk, watch return vs drawdown vs ruin ---
    print("\n=== RISK PROFILES on GOLD H1 (starting $10,000) ===")
    print(f"{'profile':13} {'risk/trade':>10} {'return%':>9} {'maxDD%':>8} {'final$':>12} {'verdict'}")
    for name, r in PROFILES.items():
        mm, _, blown = daily_returns(df_h1, spec, r)
        verdict = "BLOWN UP" if blown or mm.get("max_drawdown_pct", 0) >= 90 else "survived"
        print(f"{name:13} {r:>9}% {mm.get('return_pct',0):>9} {mm.get('max_drawdown_pct',0):>8} "
              f"{mm.get('final_equity',0):>12,.0f} {verdict}")

    # --- the $50 standard-account minimum-lot problem ---
    print("\n=== $50 STANDARD ACCOUNT on GOLD (min lot 0.01 forces oversized risk) ===")
    for tf in ("H1", "M15"):
        d, sp = load("XAUUSDm", tf, 25000)
        mm, _, blown = daily_returns(d, sp, 0.5, start=50.0)
        print(f"  gold {tf}: start $50 -> final ${mm.get('final_equity',0):,.2f}  "
              f"maxDD {mm.get('max_drawdown_pct',0)}%  {'BLOWN UP' if blown else 'survived'}")

    mt5.shutdown()


if __name__ == "__main__":
    main()
