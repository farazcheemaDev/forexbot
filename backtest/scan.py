"""Scan the trend edge across instruments AND timeframes.

For each (symbol, timeframe), runs Donchian (long-only & both-sides) and MACD,
with none/adx30 filters and ATR exits, train/test split, and reports the best
robust (positive in BOTH halves) out-of-sample result. Lets us see where the
edge is strongest and where faster timeframes / other markets help.

    python -m backtest.scan
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.filters import apply_adx_filter  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402
from bot.strategies.macd_trend import MacdTrend  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1}
_BARS = {"M15": 80000, "M30": 50000, "H1": 25000}

COMBOS = [
    ("XAUUSDm", "M15"), ("XAUUSDm", "M30"), ("XAUUSDm", "H1"),
    ("XAGUSDm", "H1"), ("US30m", "H1"), ("USTECm", "H1"),
    ("US500m", "H1"), ("BTCUSDm", "H1"), ("BTCUSDm", "M30"),
]

STRATS = [
    ("donchian_LO", lambda: DonchianBreakout(20, 200, True, long_only=True)),
    ("donchian", lambda: DonchianBreakout(20, 200, True, long_only=False)),
    ("macd", lambda: MacdTrend(12, 26, 9, 200)),
]


def load(symbol, tf, bars):
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, _TF[tf], 0, bars)
    if rates is None or len(rates) < 2000:
        return None, None
    spec = get_spec(symbol)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.reset_index(drop=True), spec


def best_for(df, spec, risk_pct):
    cfg = BacktestConfig(pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
                         spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
                         risk_per_trade_pct=risk_pct)
    n = int(len(df) * 0.7)
    train, test = df.iloc[:n].reset_index(drop=True), df.iloc[n:].reset_index(drop=True)
    best = None
    for sname, make in STRATS:
        for fname in ("none", "adx30"):
            si = make().signals(train)
            so = make().signals(test)
            if fname == "adx30":
                si = apply_adx_filter(si, train, min_adx=30)
                so = apply_adx_filter(so, test, min_adx=30)
            mi = run_backtest(train, si, cfg).metrics()
            mo = run_backtest(test, so, cfg).metrics()
            if mo.get("n_trades", 0) < 20:
                continue
            robust = mi.get("return_pct", 0) > 0 and mo.get("return_pct", 0) > 0
            score = mo.get("return_pct", -1e9)
            row = (score, robust, sname, fname, mo)
            if best is None or score > best[0]:
                best = row
    return best


def main():
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    print(f"{'symbol':9} {'tf':4} {'strategy':12} {'filt':6} {'robust':7} "
          f"{'out_ret%':>9} {'pf':>5} {'win%':>6} {'maxDD%':>7} {'trades':>7} {'span':>18}")
    for sym, tf in COMBOS:
        df, spec = load(sym, tf, _BARS[tf])
        if df is None:
            print(f"{sym:9} {tf:4} -- insufficient data --")
            continue
        best = best_for(df, spec, 0.5)
        span = f"{df['time'].iloc[0].date()}..{df['time'].iloc[-1].date()}"
        if best is None:
            print(f"{sym:9} {tf:4} (no combo >=20 trades)  {span}")
            continue
        _score, robust, sname, fname, mo = best
        print(f"{sym:9} {tf:4} {sname:12} {fname:6} {str(robust):7} "
              f"{mo['return_pct']:>9} {mo['profit_factor']:>5} {mo['win_rate']:>6} "
              f"{mo['max_drawdown_pct']:>7} {mo['n_trades']:>7} {span:>18}")
    mt5.shutdown()


if __name__ == "__main__":
    main()
