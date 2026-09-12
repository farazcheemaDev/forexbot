"""Test his mean-reversion FADE logic on real Nasdaq futures (NQ=F) data with
realistic FUTURES costs (~0.75pt round trip, not the 1.1pt CFD spread that
killed the earlier test). Also aligns a few of his real trades to the chart.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.filters import apply_adx_ceiling_filter, apply_session_filter  # noqa: E402
from bot.strategies.bollinger_rsi import BollingerRsi  # noqa: E402


def get_nq(interval, period="60d"):
    d = yf.download("NQ=F", interval=interval, period=period, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.reset_index()
    tcol = "Datetime" if "Datetime" in d.columns else "Date"
    df = pd.DataFrame({
        "time": pd.to_datetime(d[tcol]).dt.tz_localize(None),
        "open": d["Open"].astype(float), "high": d["High"].astype(float),
        "low": d["Low"].astype(float), "close": d["Close"].astype(float),
    }).dropna().reset_index(drop=True)
    return df


def forensic(df, date, entry_px, side, label):
    day = df[(df.time >= f"{date} 00:00") & (df.time <= f"{date} 23:59")]
    if len(day) == 0:
        print(f"  {label}: no NQ data {date}"); return
    hit = day[(day.high >= entry_px) & (day.low <= entry_px)]
    if len(hit) == 0:
        print(f"  {label}: {entry_px} not in {date} range ({day.low.min():.0f}-{day.high.max():.0f})")
        return
    i = hit.index[0]
    pre = df.iloc[max(0, i - 6):i]
    mv = pre.close.iloc[-1] - pre.close.iloc[0] if len(pre) > 1 else 0
    # was entry near the local extreme of the last ~12 bars?
    win = df.iloc[max(0, i - 12):i + 1]
    at_high = entry_px >= win.high.max() - 0.15 * (win.high.max() - win.low.min())
    at_low = entry_px <= win.low.min() + 0.15 * (win.high.max() - win.low.min())
    loc = "TOP of range" if at_high else ("BOTTOM of range" if at_low else "mid-range")
    print(f"  {label} {side}@{entry_px} ~{df.time[i]:%m-%d %H:%M} ET | prior move {mv:+.0f}pt | "
          f"entry at {loc} -> {'FADE confirmed' if (side=='SELL' and at_high) or (side=='BUY' and at_low) else 'not a clean fade'}")


def main():
    print("Downloading NQ=F 5m/15m ...")
    m5 = get_nq("5m"); m15 = get_nq("15m")
    print(f"NQ 5m: {len(m5)} bars {m5.time.iloc[0]} -> {m5.time.iloc[-1]}")
    print(f"NQ price range (60d): {m5.low.min():.0f} - {m5.high.max():.0f}")

    print("\n=== FORENSIC: his trades vs real NQ chart (ET) ===")
    forensic(m5, "2026-07-01", 30305.5, "SELL", "07-01")
    forensic(m5, "2026-07-10", 29786.25, "BUY", "07-10")
    forensic(m5, "2026-08-07", 29752.25, "SELL", "08-07")
    forensic(m5, "2026-08-07", 29742.50, "BUY", "08-07b")

    # realistic futures cost: ~0.5pt spread + 0.25 slippage; pip=1pt, value scaled to $ per pt
    def test(df, tf_name):
        print(f"\n=== FADE backtest on NQ {tf_name} (real futures cost) ===")
        for spr in (0.75,):
            for ceil in (False, True):
                for sl, tp in [(2.0, 1.0), (2.5, 1.5), (1.5, 1.0)]:
                    cfg = BacktestConfig(pip_size=1.0, pip_value_per_lot=20.0,
                                         spread_pips=spr, slippage_pips=0.25,
                                         commission_per_lot=4.0, exit_mode="atr",
                                         atr_sl_mult=sl, atr_tp_mult=tp, risk_per_trade_pct=1.0)
                    n = int(len(df) * 0.6)
                    tr, te = df.iloc[:n].reset_index(drop=True), df.iloc[n:].reset_index(drop=True)

                    def sig(d):
                        s = BollingerRsi(20, 2.0, 14, 30.0, 70.0).signals(d)
                        s = apply_session_filter(s, d, 9, 16)  # RTH ET
                        if ceil:
                            s = apply_adx_ceiling_filter(s, d, max_adx=25)
                        return s
                    mi = run_backtest(tr, sig(tr), cfg).metrics()
                    mo = run_backtest(te, sig(te), cfg).metrics()
                    if mo.get("n_trades", 0) < 15:
                        continue
                    rob = mi.get("return_pct", 0) > 0 and mo.get("return_pct", 0) > 0
                    print(f"  ceil={str(ceil):5} sl/tp={sl}/{tp} | IN pf={mi.get('profit_factor',0)} "
                          f"| OUT trades={mo['n_trades']} pf={mo['profit_factor']} win={mo['win_rate']}% "
                          f"ret={mo['return_pct']}% {'<< ROBUST' if rob else ''}")

    test(m5, "5m"); test(m15, "15m")


if __name__ == "__main__":
    main()
