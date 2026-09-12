"""Generate a visual results report (PNG) for the locked strategy on Exness gold.

Runs the long-only Donchian walk-forward, stitches the out-of-sample equity
curve, and plots equity + drawdown with a stats box. Saves logs/results.png.

    python -m backtest.equity_report
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402

PERIOD_GRID = [10, 15, 20, 30, 40, 55]
START = 10000.0


def load(symbol, bars):
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    spec = get_spec(symbol)
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, bars)
    mt5.shutdown()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.reset_index(drop=True), spec


def best_period(train, cfg):
    best, best_ret = PERIOD_GRID[0], -1e9
    for p in PERIOD_GRID:
        sig = DonchianBreakout(period=p, use_trend=True, long_only=True).signals(train)
        m = run_backtest(train, sig, cfg).metrics()
        r = m.get("return_pct", -1e9) if m.get("n_trades", 0) >= 10 else -1e9
        if r > best_ret:
            best, best_ret = p, r
    return best


def main():
    conf = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config" / "config.yaml", encoding="utf-8"))
    symbol = "XAUUSDm"
    df, spec = load(symbol, 25000)
    cfg = BacktestConfig(pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
                         spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
                         risk_per_trade_pct=conf["risk"]["risk_per_trade_pct"], start_equity=START)

    train_n, test_n = 5000, 2500
    rows = []
    start = 0
    while start + train_n + test_n <= len(df):
        train = df.iloc[start:start + train_n].reset_index(drop=True)
        test = df.iloc[start + train_n:start + train_n + test_n].reset_index(drop=True)
        p = best_period(train, cfg)
        res = run_backtest(test, DonchianBreakout(period=p, use_trend=True, long_only=True).signals(test), cfg)
        for t in res.trades:
            rows.append({"exit": pd.Timestamp(t.exit_time), "pnl": t.pnl})
        start += test_n

    trades = pd.DataFrame(rows).sort_values("exit").reset_index(drop=True)
    trades["equity"] = START + trades["pnl"].cumsum()
    eq = trades["equity"].values
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak * 100

    pnl = trades["pnl"].values
    gross_win = pnl[pnl > 0].sum(); gross_loss = -pnl[pnl < 0].sum()
    metrics = {
        "Net profit": f"${pnl.sum():,.0f}",
        "Total return": f"{(eq[-1]/START-1)*100:.1f}%",
        "Trades": f"{len(pnl)}",
        "Win rate": f"{(pnl>0).mean()*100:.1f}%",
        "Profit factor": f"{gross_win/gross_loss:.2f}",
        "Max drawdown": f"{dd.max():.1f}%",
        "Avg $/trade": f"${pnl.mean():.2f}",
    }
    period = f"{trades['exit'].iloc[0]:%b %Y} – {trades['exit'].iloc[-1]:%b %Y}"

    # ---- plot ----
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), height_ratios=[3, 1], sharex=True)
    fig.suptitle(f"Gold (XAUUSD) H1 — Donchian long-only — out-of-sample walk-forward\n{period}",
                 fontsize=13, fontweight="bold")

    ax1.plot(trades["exit"], eq, color="#1a7f4b", linewidth=1.6)
    ax1.axhline(START, color="#888", linestyle="--", linewidth=0.8)
    ax1.fill_between(trades["exit"], START, eq, where=(eq >= START), color="#1a7f4b", alpha=0.08)
    ax1.set_ylabel("Equity (USD)")
    ax1.grid(alpha=0.25)
    txt = "\n".join(f"{k}: {v}" for k, v in metrics.items())
    ax1.text(0.015, 0.97, txt, transform=ax1.transAxes, va="top", ha="left", fontsize=10,
             family="monospace", bbox=dict(boxstyle="round", fc="white", ec="#1a7f4b", alpha=0.9))

    ax2.fill_between(trades["exit"], 0, -dd, color="#c0392b", alpha=0.5)
    ax2.set_ylabel("Drawdown %")
    ax2.grid(alpha=0.25)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    out = Path(__file__).resolve().parents[1] / "logs" / "results.png"
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print("saved", out)
    for k, v in metrics.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
