"""Combined multi-market portfolio backtest, measured by MONTHLY return.

Runs several uncorrelated 'sleeves' (market+timeframe+strategy), allocates equal
capital to each, sums their equity curves, and reports the monthly return
distribution + drawdown. Directly answers: can a diversified framework average
~10%/month, and at what risk / drawdown?

NOTE: full-history (in-sample) with fixed params -> OPTIMISTIC. Live/walk-forward
will be lower and drawdowns deeper. Read the SHAPE (diversification, monthly
consistency), not the absolute return.

    python -m backtest.portfolio_backtest --risk 1
    python -m backtest.portfolio_backtest --risk 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402
from bot.strategies.macd_trend import MacdTrend  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1}
_BARS = {"M15": 80000, "M30": 50000, "H1": 25000}

# The diversified sleeves (robust markets from the scan)
SLEEVES = [
    ("XAUUSDm", "H1", "donchian"),
    ("XAUUSDm", "M15", "donchian"),
    ("XAGUSDm", "H1", "donchian"),
    ("BTCUSDm", "M30", "donchian"),
    ("XAUUSDm", "H1", "macd"),
]


def make_strat(kind):
    if kind == "donchian":
        return DonchianBreakout(20, 200, True, long_only=True)
    return MacdTrend(12, 26, 9, 200)


def sleeve_equity(symbol, tf, kind, risk_pct, slice_capital):
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, _TF[tf], 0, _BARS[tf])
    if rates is None or len(rates) < 2000:
        return None
    spec = get_spec(symbol)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    cfg = BacktestConfig(pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
                         spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
                         risk_per_trade_pct=risk_pct, start_equity=slice_capital)
    res = run_backtest(df, make_strat(kind).signals(df), cfg)
    eq = res.equity_curve
    return eq.resample("1D").last().dropna()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risk", type=float, default=1.0)
    ap.add_argument("--capital", type=float, default=10000.0)
    args = ap.parse_args()

    if not mt5.initialize():
        raise SystemExit(f"MT5 init: {mt5.last_error()}")

    slice_cap = args.capital / len(SLEEVES)
    daily = []
    print(f"Portfolio: {len(SLEEVES)} sleeves, risk {args.risk}%/trade, "
          f"${args.capital:,.0f} total (${slice_cap:,.0f}/sleeve)\n")
    for sym, tf, kind in SLEEVES:
        eq = sleeve_equity(sym, tf, kind, args.risk, slice_cap)
        if eq is None:
            print(f"  skip {sym} {tf} {kind} (no data)")
            continue
        ret = (eq.iloc[-1] / slice_cap - 1) * 100
        print(f"  sleeve {sym:9} {tf:4} {kind:9}: {ret:+.0f}%  "
              f"({eq.index[0].date()}..{eq.index[-1].date()})")
        daily.append(eq.rename(f"{sym}/{tf}/{kind}"))
    mt5.shutdown()

    # combine: union daily index, ffill each sleeve, pre-start = slice_cap
    idx = pd.date_range(min(s.index.min() for s in daily),
                        max(s.index.max() for s in daily), freq="1D")
    combined = None
    for s in daily:
        s2 = s.reindex(idx).ffill()
        s2 = s2.fillna(slice_cap)         # before this sleeve starts, capital idle
        combined = s2 if combined is None else combined + s2

    total_ret = (combined.iloc[-1] / args.capital - 1) * 100
    peak = combined.cummax()
    dd = (peak - combined) / peak * 100
    monthly = combined.resample("ME").last()
    mret = monthly.pct_change().dropna() * 100

    print(f"\n=== COMBINED PORTFOLIO (risk {args.risk}%/trade) ===")
    yrs = (idx[-1] - idx[0]).days / 365.25
    print(f"  span: {idx[0].date()} .. {idx[-1].date()}  ({yrs:.1f} yr)")
    print(f"  total return:  {total_ret:+.0f}%   (CAGR ~{((combined.iloc[-1]/args.capital)**(1/yrs)-1)*100:.0f}%/yr)")
    print(f"  max drawdown:  {dd.max():.1f}%")
    print(f"  --- MONTHLY returns ({len(mret)} months) ---")
    print(f"  mean:   {mret.mean():+.2f}%/month     median: {mret.median():+.2f}%")
    print(f"  best:   {mret.max():+.1f}%     worst: {mret.min():+.1f}%")
    print(f"  % months positive:      {(mret>0).mean()*100:.0f}%")
    print(f"  % months >= +10%:       {(mret>=10).mean()*100:.0f}%")
    print(f"  % months <= -10%:       {(mret<=-10).mean()*100:.0f}%")


if __name__ == "__main__":
    main()
