"""Test the team-followable systematic hypotheses on real NQ 5m data:
VWAP reversion, liquidity-sweep reversal, and sweep-at-a-25-level combo.
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
from bot.strategies.base import Action  # noqa: E402
from bot.strategies.liquidity_sweep import LiquiditySweep  # noqa: E402
from bot.strategies.vwap_reversion import VwapReversion  # noqa: E402


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
        "volume": d["Volume"].astype(float),
    }).dropna().reset_index(drop=True)


def near_25(prices, prox=8.0):
    nearest = (prices / 25).round() * 25
    return (prices - nearest).abs() <= prox


def evaluate(name, sig_fn, tr, te, cfg):
    mi = run_backtest(tr, sig_fn(tr), cfg).metrics()
    mo = run_backtest(te, sig_fn(te), cfg).metrics()
    if mo.get("n_trades", 0) < 10:
        print(f"  {name:26} too few trades ({mo.get('n_trades',0)})"); return
    rob = mi.get("return_pct", 0) > 0 and mo.get("return_pct", 0) > 0
    print(f"  {name:26} IN_pf={mi.get('profit_factor',0):>5} | OUT tr={mo['n_trades']:>3} "
          f"pf={mo['profit_factor']:>5} win={mo['win_rate']:>5}% ret={mo['return_pct']:>6}% "
          f"{'<< ROBUST' if rob else ''}")


def main():
    m5 = get_nq("5m")
    print(f"NQ 5m: {len(m5)} bars, volume sum={m5.volume.sum():.0f}")
    cfg = BacktestConfig(pip_size=1.0, pip_value_per_lot=20.0, spread_pips=0.75,
                         slippage_pips=0.25, commission_per_lot=4.0, exit_mode="atr",
                         atr_sl_mult=2.0, atr_tp_mult=1.2, risk_per_trade_pct=1.0)
    n = int(len(m5) * 0.6)
    tr, te = m5.iloc[:n].reset_index(drop=True), m5.iloc[n:].reset_index(drop=True)

    def us(s, d):
        return apply_session_filter(s, d, 9, 16)

    print("\n=== VWAP REVERSION ===")
    for k in (1.5, 2.0, 2.5):
        evaluate(f"vwap k={k}", lambda d, k=k: us(VwapReversion(k, 14, 65, 35).signals(d), d), tr, te, cfg)

    print("\n=== LIQUIDITY SWEEP (stop-hunt reversal) ===")
    for sw in (10, 20, 40):
        evaluate(f"sweep swing={sw}", lambda d, sw=sw: us(LiquiditySweep(sw, True).signals(d), d), tr, te, cfg)

    print("\n=== LIQUIDITY SWEEP *AT A 25-LEVEL* (his signature) ===")
    for sw in (10, 20):
        def combo(d, sw=sw):
            s = LiquiditySweep(sw, True).signals(d)
            # keep only sweeps that happen near a 25-level (his tell)
            lvl = near_25(d["close"])
            s = s.where(lvl, Action.HOLD)
            return us(s, d)
        evaluate(f"sweep@25 swing={sw}", combo, tr, te, cfg)

    print("\n=== his entry TIMES -> ET session check ===")
    # his server (~GMT+3) entry hours; ET = server-7
    server_hours = [20, 20, 14, 21, 23, 21, 22, 3, 20]
    et = [(h - 7) % 24 for h in server_hours]
    print(f"  his entries in ET hours: {sorted(et)}  (cluster {min([x for x in et if 8<=x<=17], default='-')}-15 = US afternoon)")


if __name__ == "__main__":
    main()
