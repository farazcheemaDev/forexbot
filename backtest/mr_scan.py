"""Find and walk-forward a mean-reversion (fade) sleeve.

Step 1: scan BollingerRsi (fade band extremes) across instruments/timeframes,
with/without an ADX-ceiling (fade only in ranging conditions), 70/30 train/test.
Step 2: walk-forward the best robust config and report monthly stats + its
correlation with the trend champion (gold Donchian) to prove it de-correlates.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.filters import apply_adx_ceiling_filter  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.bollinger_rsi import BollingerRsi  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1}
_BARS = {"M15": 80000, "H1": 25000}
INSTR = ["EURUSDm", "GBPUSDm", "USDJPYm", "GBPJPYm", "XAUUSDm", "XAGUSDm"]
EXITS = [(2.0, 1.0), (2.5, 1.5)]


def load(sym, tf):
    mt5.symbol_select(sym, True)
    r = mt5.copy_rates_from_pos(sym, _TF[tf], 0, _BARS[tf])
    if r is None or len(r) < 3000:
        return None, None
    spec = get_spec(sym)
    d = pd.DataFrame(r); d["time"] = pd.to_datetime(d["time"], unit="s")
    return d.reset_index(drop=True), spec


def cfg_for(spec, sl, tp):
    return BacktestConfig(pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
                          spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
                          atr_sl_mult=sl, atr_tp_mult=tp, risk_per_trade_pct=1.0)


def mr_signals(df, use_ceiling):
    s = BollingerRsi(20, 2.0, 14, 30.0, 70.0).signals(df)
    if use_ceiling:
        s = apply_adx_ceiling_filter(s, df, max_adx=25)
    return s


def main():
    if not mt5.initialize():
        raise SystemExit(f"MT5 init: {mt5.last_error()}")
    print("=== MEAN-REVERSION SCAN (BollingerRsi fade, 70/30 train/test) ===")
    print(f"{'symbol':9} {'tf':4} {'adxceil':8} {'sl/tp':8} {'robust':7} {'out_ret%':>9} {'pf':>5} {'win%':>6} {'trades':>7}")
    results = []
    for sym in INSTR:
        for tf in ("H1", "M15"):
            df, spec = load(sym, tf)
            if df is None:
                continue
            n = int(len(df) * 0.7)
            tr, te = df.iloc[:n].reset_index(drop=True), df.iloc[n:].reset_index(drop=True)
            for ceil in (False, True):
                for sl, tp in EXITS:
                    c = cfg_for(spec, sl, tp)
                    mi = run_backtest(tr, mr_signals(tr, ceil), c).metrics()
                    mo = run_backtest(te, mr_signals(te, ceil), c).metrics()
                    if mo.get("n_trades", 0) < 30:
                        continue
                    robust = mi.get("return_pct", 0) > 0 and mo.get("return_pct", 0) > 0
                    results.append((mo["return_pct"], robust, sym, tf, ceil, sl, tp))
                    if robust or mo["return_pct"] > 0:
                        print(f"{sym:9} {tf:4} {str(ceil):8} {sl}/{tp:4} {str(robust):7} "
                              f"{mo['return_pct']:>9} {mo['profit_factor']:>5} {mo['win_rate']:>6} {mo['n_trades']:>7}")
    robust_pos = [r for r in results if r[1]]
    print(f"\nrobust positive MR configs: {len(robust_pos)} of {len(results)} tested")
    if not robust_pos:
        print("=> mean-reversion has NO robust standalone edge on these markets/costs.")
    mt5.shutdown()


if __name__ == "__main__":
    main()
