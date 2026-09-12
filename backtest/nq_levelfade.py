"""Test the LevelFade strategy (round-number + prior-day-level fade) on real
NQ futures data, and compare against the naive Bollinger fade. Also checks how
often his actual entries sat at one of these levels (validating the 'judgment').
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.filters import apply_session_filter  # noqa: E402
from bot.strategies.level_fade import LevelFade  # noqa: E402


def get_nq(interval):
    d = yf.download("NQ=F", interval=interval, period="60d", progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.reset_index()
    tcol = "Datetime" if "Datetime" in d.columns else "Date"
    return pd.DataFrame({
        "time": pd.to_datetime(d[tcol]).dt.tz_localize(None),
        "open": d["Open"].astype(float), "high": d["High"].astype(float),
        "low": d["Low"].astype(float), "close": d["Close"].astype(float),
    }).dropna().reset_index(drop=True)


def his_entries_near_levels(df, step=100, prox=10):
    """How many of his real entry prices sat within `prox` of a round level?"""
    entries = [30305.75, 30305.25, 29786.25, 30005.00, 28323.75,
               29742.50, 29752.25, 29748.75, 29816.50]
    hits = 0
    for e in entries:
        nearest = round(e / step) * step
        if abs(e - nearest) <= prox:
            hits += 1
    print(f"  his entries within {prox}pt of a {step}-round level: {hits}/{len(entries)}")
    for e in entries:
        for s in (25, 50, 100):
            n = round(e / s) * s
            if abs(e - n) <= prox:
                print(f"    {e} -> near {s}-level {n} (±{abs(e-n):.2f})")
                break


def main():
    m5 = get_nq("5m")
    print(f"NQ 5m: {len(m5)} bars  {m5.time.iloc[0]} -> {m5.time.iloc[-1]}")
    print("\n=== Do his entries sit on round levels? ===")
    his_entries_near_levels(m5)

    cfg = BacktestConfig(pip_size=1.0, pip_value_per_lot=20.0, spread_pips=0.75,
                         slippage_pips=0.25, commission_per_lot=4.0, exit_mode="atr",
                         risk_per_trade_pct=1.0)
    n = int(len(m5) * 0.6)
    tr, te = m5.iloc[:n].reset_index(drop=True), m5.iloc[n:].reset_index(drop=True)

    print("\n=== LEVEL-FADE backtest on NQ 5m (round + prior-day levels, RSI stretch) ===")
    print(f"{'step':>4} {'prox':>4} {'rsi':>7} {'sl/tp':>7} {'IN_pf':>6} {'OUT_tr':>6} {'OUT_pf':>6} {'win%':>6} {'ret%':>7} {'robust'}")
    best = None
    for step in (50, 100):
        for prox in (6, 10):
            for hi, lo in [(68, 32), (72, 28)]:
                for sl, tp in [(2.0, 1.0), (1.5, 1.0), (2.5, 1.5)]:
                    cfg.atr_sl_mult, cfg.atr_tp_mult = sl, tp

                    def sig(d):
                        s = LevelFade(step, prox, 14, hi, lo, True).signals(d)
                        return apply_session_filter(s, d, 9, 16)
                    mi = run_backtest(tr, sig(tr), cfg).metrics()
                    mo = run_backtest(te, sig(te), cfg).metrics()
                    if mo.get("n_trades", 0) < 12:
                        continue
                    rob = mi.get("return_pct", 0) > 0 and mo.get("return_pct", 0) > 0
                    line = (f"{step:>4} {prox:>4} {hi}/{lo:>4} {sl}/{tp:>4} "
                            f"{mi.get('profit_factor',0):>6} {mo['n_trades']:>6} "
                            f"{mo['profit_factor']:>6} {mo['win_rate']:>6} {mo['return_pct']:>7} "
                            f"{'<< ROBUST' if rob else ''}")
                    print(line)
                    score = mo["profit_factor"] if rob else -1
                    if best is None or score > best[0]:
                        best = (score, line)
    print("\nbest robust:", best[1] if best and best[0] > 0 else "NONE robust")


if __name__ == "__main__":
    main()
