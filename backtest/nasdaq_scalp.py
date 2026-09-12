"""Nasdaq scalper prototype + forensic look at the real trader's Aug entries.

Data caveat: Exness only serves ~30 days of Nasdaq intraday history, so the
backtest is a SMALL-SAMPLE sanity check, not a validation.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.filters import apply_session_filter  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402

SYM = "USTECm"


def rng(tf, days):
    now = datetime.now(timezone.utc)
    r = mt5.copy_rates_range(SYM, tf, now - timedelta(days=days), now)
    if r is None or len(r) == 0:
        return None
    d = pd.DataFrame(r)
    d["time"] = pd.to_datetime(d["time"], unit="s")
    return d.reset_index(drop=True)


def forensic(day_m1, entry_px, label):
    """Find where price crossed the trader's entry price; show momentum before."""
    if day_m1 is None:
        print(f"  {label}: no data"); return
    near = day_m1[(day_m1.high >= entry_px) & (day_m1.low <= entry_px)]
    if len(near) == 0:
        print(f"  {label}: price never touched {entry_px} that day "
              f"(our range {day_m1.low.min():.0f}-{day_m1.high.max():.0f})")
        return
    i = near.index[0]
    ctx = day_m1.iloc[max(0, i - 10):i + 3]
    pre = day_m1.iloc[max(0, i - 10):i]
    slope = pre.close.iloc[-1] - pre.close.iloc[0] if len(pre) > 1 else 0
    print(f"  {label}: touched {entry_px} at {day_m1.time[i]:%H:%M}  "
          f"prior-10min move={slope:+.1f}pts  "
          f"({'price RISING into it -> he faded/shorted a push up' if slope>0 else 'price FALLING into it -> he sold a breakdown (momentum)'})")


def main():
    if not mt5.initialize():
        raise SystemExit(f"MT5 init: {mt5.last_error()}")
    mt5.symbol_select(SYM, True); time.sleep(1)
    spec = get_spec(SYM)
    print(f"{SYM} spec: pip={spec.pip_size} $/pip/lot={spec.pip_value_per_lot} spread={spec.spread_pips}")

    # --- forensic on his real Aug entries (inside the 30-day window) ---
    print("\n=== FORENSIC: his real entries vs our Nasdaq chart ===")
    aug11 = rng(mt5.TIMEFRAME_M1, 33)
    if aug11 is not None:
        d11 = aug11[(aug11.time >= "2026-08-11 00:00") & (aug11.time <= "2026-08-11 12:00")]
        forensic(d11.reset_index(drop=True), 29748.75, "Aug-11 SELL 29748.75")
        d07 = aug11[(aug11.time >= "2026-08-07 18:00") & (aug11.time <= "2026-08-08 02:00")]
        forensic(d07.reset_index(drop=True), 29752.25, "Aug-07 SELL 29752.25")

    # --- scalper backtest on ~30 days M5, US session only ---
    print("\n=== SCALPER BACKTEST (USTECm M5, ~30d, US session) ===")
    m5 = rng(mt5.TIMEFRAME_M5, 33)
    if m5 is None or len(m5) < 500:
        print("  insufficient M5 data"); mt5.shutdown(); return
    print(f"  {len(m5)} M5 bars  {m5.time.iloc[0]} -> {m5.time.iloc[-1]}")
    for period in (6, 10, 20):
        for sl_m, tp_m in [(1.0, 1.5), (1.5, 1.5), (1.0, 2.0)]:
            cfg = BacktestConfig(pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
                                 spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
                                 atr_period=14, atr_sl_mult=sl_m, atr_tp_mult=tp_m,
                                 risk_per_trade_pct=1.0)
            sig = DonchianBreakout(period, 200, use_trend=False, long_only=False).signals(m5)
            sig = apply_session_filter(sig, m5, start_hour=15, end_hour=23)  # US session (server)
            m = run_backtest(m5, sig, cfg).metrics()
            if m.get("n_trades", 0) >= 10:
                print(f"  period={period:2} sl={sl_m} tp={tp_m}: "
                      f"trades={m['n_trades']:3} ret={m['return_pct']:+6}% pf={m['profit_factor']:.2f} "
                      f"win={m['win_rate']}% dd={m['max_drawdown_pct']}%")
    mt5.shutdown()


if __name__ == "__main__":
    main()
