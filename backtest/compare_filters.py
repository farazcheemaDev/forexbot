"""Head-to-head: does each statistically-motivated filter actually improve the
walk-forward result on gold? Reports aggregate OOS metrics + the worst fold for
each variant, so we can see if drawdown/chop risk (fold 0) is reduced.

    python -m backtest.compare_filters --symbol XAUUSDm --tf H1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import MetaTrader5 as mt5  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.filters import (apply_adx_filter, apply_atr_quantile_filter,  # noqa: E402
                              apply_session_filter)
from bot.core.instrument import get_spec  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}
PERIOD_GRID = [10, 15, 20, 30, 40, 55]


def load(symbol, tf, bars):
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    spec = get_spec(symbol)
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, _TF[tf], 0, bars)
    mt5.shutdown()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.reset_index(drop=True), spec


VARIANTS = {
    "baseline":           dict(),
    "adx>=25":            dict(adx=25),
    "adx>=30":            dict(adx=30),
    "atr_floor(25%)":     dict(atrq=0.25),
    "long_only":          dict(long_only=True),
    "adx30+atr_floor":    dict(adx=30, atrq=0.25),
    "long+adx30":         dict(long_only=True, adx=30),
    "long+adx30+atrfloor": dict(long_only=True, adx=30, atrq=0.25),
}


def build_signals(part, period, v):
    strat = DonchianBreakout(period=period, use_trend=True,
                             long_only=v.get("long_only", False))
    sig = strat.signals(part)
    if "adx" in v:
        sig = apply_adx_filter(sig, part, min_adx=v["adx"])
    if "atrq" in v:
        sig = apply_atr_quantile_filter(sig, part, min_quantile=v["atrq"])
    if v.get("session"):
        sig = apply_session_filter(sig, part)
    return sig


def best_period(train, cfg, v):
    best, best_ret = PERIOD_GRID[0], -1e9
    for p in PERIOD_GRID:
        m = run_backtest(train, build_signals(train, p, v), cfg).metrics()
        r = m.get("return_pct", -1e9) if m.get("n_trades", 0) >= 10 else -1e9
        if r > best_ret:
            best, best_ret = p, r
    return best


def walk_forward(df, cfg, v, train=5000, test=2500):
    all_pnl, fold_rets = [], []
    start = 0
    while start + train + test <= len(df):
        tr = df.iloc[start:start + train].reset_index(drop=True)
        te = df.iloc[start + train:start + train + test].reset_index(drop=True)
        p = best_period(tr, cfg, v)
        res = run_backtest(te, build_signals(te, p, v), cfg)
        all_pnl += [t.pnl for t in res.trades]
        fold_rets.append(res.metrics().get("return_pct", 0))
        start += test
    return np.array(all_pnl), fold_rets


def summarize(pnl):
    if len(pnl) == 0:
        return dict(trades=0, ret=0, pf=0, win=0, dd=0, exp=0)
    equity = 10000.0 + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[10000.0], equity]))
    dd = ((peak[1:] - equity) / peak[1:]).max() * 100
    gw = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    return dict(trades=len(pnl), ret=round((equity[-1] / 10000 - 1) * 100, 1),
                pf=round(gw / gl, 2) if gl > 0 else 99.0,
                win=round((pnl > 0).mean() * 100, 1), dd=round(dd, 1),
                exp=round(pnl.mean(), 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSDm")
    ap.add_argument("--tf", default="H1")
    ap.add_argument("--bars", type=int, default=25000)
    args = ap.parse_args()

    conf = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config" / "config.yaml", encoding="utf-8"))
    df, spec = load(args.symbol, args.tf, args.bars)
    cfg = BacktestConfig(pip_size=spec.pip_size, pip_value_per_lot=spec.pip_value_per_lot,
                         spread_pips=max(spec.spread_pips, 0.1), exit_mode="atr",
                         risk_per_trade_pct=conf["risk"]["risk_per_trade_pct"])
    print(f"{args.symbol} {args.tf} walk-forward filter comparison "
          f"({df['time'].iloc[0].date()} -> {df['time'].iloc[-1].date()})\n")
    print(f"{'variant':22} {'trades':>7} {'ret%':>7} {'pf':>5} {'win%':>6} "
          f"{'maxDD%':>7} {'exp$':>7} {'worstFold%':>11}")
    for name, v in VARIANTS.items():
        pnl, folds = walk_forward(df, cfg, v)
        s = summarize(pnl)
        worst = round(min(folds), 1) if folds else 0
        print(f"{name:22} {s['trades']:>7} {s['ret']:>7} {s['pf']:>5} {s['win']:>6} "
              f"{s['dd']:>7} {s['exp']:>7} {worst:>11}")


if __name__ == "__main__":
    main()
