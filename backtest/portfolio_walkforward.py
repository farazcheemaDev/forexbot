"""HONEST portfolio validation: walk-forward every sleeve (optimize on past,
trade forward into unseen data), compound each sleeve across folds, combine into
one portfolio, and report monthly returns + drawdown. Also saves a chart.

    python -m backtest.portfolio_walkforward --risk 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402
from bot.strategies.macd_trend import MacdTrend  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1}
_BARS = {"M15": 80000, "M30": 50000, "H1": 25000}
_WIN = {"H1": (5000, 2500), "M30": (10000, 5000), "M15": (20000, 10000)}
PERIODS = [10, 15, 20, 30, 40, 55]

SLEEVES = [
    ("XAUUSDm", "H1", "donchian"),
    ("XAUUSDm", "M15", "donchian"),
    ("XAGUSDm", "H1", "donchian"),
    ("BTCUSDm", "M30", "donchian"),
    ("XAUUSDm", "H1", "macd"),
]


def make(kind, period=20):
    if kind == "donchian":
        return DonchianBreakout(period, 200, True, long_only=True)
    return MacdTrend(12, 26, 9, 200)


def load(symbol, tf):
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, _TF[tf], 0, _BARS[tf])
    if rates is None or len(rates) < 2000:
        return None, None
    spec = get_spec(symbol)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.reset_index(drop=True), spec


def walk_forward_sleeve(symbol, tf, kind, risk, slice_cap):
    df, spec = load(symbol, tf)
    if df is None:
        return None
    cfg = BacktestConfig(pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
                         spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
                         risk_per_trade_pct=risk, start_equity=slice_cap)
    train_n, test_n = _WIN[tf]
    equity_pieces = []
    running = slice_cap
    start = 0
    while start + train_n + test_n <= len(df):
        train = df.iloc[start:start + train_n].reset_index(drop=True)
        test = df.iloc[start + train_n:start + train_n + test_n].reset_index(drop=True)
        if kind == "donchian":
            best_p, best_r = PERIODS[0], -1e9
            for p in PERIODS:
                m = run_backtest(train, make(kind, p).signals(train), cfg).metrics()
                r = m.get("return_pct", -1e9) if m.get("n_trades", 0) >= 8 else -1e9
                if r > best_r:
                    best_p, best_r = p, r
        else:
            best_p = 20
        cfg.start_equity = running
        res = run_backtest(test, make(kind, best_p).signals(test), cfg)
        eq = res.equity_curve
        running = float(eq.iloc[-1])
        equity_pieces.append(eq)
        start += test_n
    if not equity_pieces:
        return None
    full = pd.concat(equity_pieces)
    return full.resample("1D").last().dropna()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risk", type=float, default=3.0)
    ap.add_argument("--capital", type=float, default=10000.0)
    args = ap.parse_args()

    if not mt5.initialize():
        raise SystemExit(f"MT5 init: {mt5.last_error()}")
    slice_cap = args.capital / len(SLEEVES)
    print(f"WALK-FORWARD portfolio: {len(SLEEVES)} sleeves, risk {args.risk}%/trade\n")
    daily = []
    for sym, tf, kind in SLEEVES:
        eq = walk_forward_sleeve(sym, tf, kind, args.risk, slice_cap)
        if eq is None:
            print(f"  skip {sym} {tf} {kind}")
            continue
        print(f"  sleeve {sym:9} {tf:4} {kind:9}: {(eq.iloc[-1]/slice_cap-1)*100:+.0f}% (OOS)")
        daily.append(eq)
    mt5.shutdown()

    idx = pd.date_range(min(s.index.min() for s in daily),
                        max(s.index.max() for s in daily), freq="1D")
    combined = None
    for s in daily:
        s2 = s.reindex(idx).ffill().fillna(slice_cap)
        combined = s2 if combined is None else combined + s2

    yrs = (idx[-1] - idx[0]).days / 365.25
    total = (combined.iloc[-1] / args.capital - 1) * 100
    cagr = ((combined.iloc[-1] / args.capital) ** (1 / yrs) - 1) * 100
    peak = combined.cummax()
    dd = (peak - combined) / peak * 100
    monthly = combined.resample("ME").last()
    mret = monthly.pct_change().dropna() * 100

    print(f"\n=== WALK-FORWARD COMBINED (risk {args.risk}%) — OUT-OF-SAMPLE ===")
    print(f"  span {idx[0].date()}..{idx[-1].date()} ({yrs:.1f}yr)")
    print(f"  total {total:+.0f}%   CAGR ~{cagr:.0f}%/yr   maxDD {dd.max():.1f}%")
    print(f"  monthly mean {mret.mean():+.2f}%  median {mret.median():+.2f}%  "
          f"best {mret.max():+.0f}%  worst {mret.min():+.0f}%")
    print(f"  %months +ve {(mret>0).mean()*100:.0f}%   >=+10% {(mret>=10).mean()*100:.0f}%   "
          f"<=-10% {(mret<=-10).mean()*100:.0f}%")

    # chart
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), height_ratios=[3, 2])
    fig.suptitle(f"Walk-forward diversified portfolio (5 sleeves) — risk {args.risk}%/trade\n"
                 f"OUT-OF-SAMPLE  CAGR ~{cagr:.0f}%/yr  maxDD {dd.max():.0f}%  "
                 f"mean {mret.mean():.1f}%/mo", fontsize=12, fontweight="bold")
    ax1.plot(combined.index, combined.values, color="#1a7f4b", lw=1.5)
    ax1.set_ylabel("Equity (USD)"); ax1.set_yscale("log"); ax1.grid(alpha=0.25)
    colors = ["#1a7f4b" if v >= 0 else "#c0392b" for v in mret.values]
    ax2.bar(mret.index, mret.values, width=20, color=colors)
    ax2.axhline(10, color="#f39c12", ls="--", lw=1, label="+10%/mo goal")
    ax2.set_ylabel("Monthly return %"); ax2.grid(alpha=0.25); ax2.legend(loc="upper left")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    out = Path(__file__).resolve().parents[1] / "logs" / f"portfolio_wf_{int(args.risk)}pct.png"
    fig.tight_layout(); fig.savefig(out, dpi=130)
    print(f"  chart saved: {out}")


if __name__ == "__main__":
    main()
