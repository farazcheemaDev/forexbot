"""Deep validation of the TREND edge (the one thing that survives) on higher
timeframes with lots of data: BTC resampled to 1h/4h (1yr) and NQ 1h/4h (2yr).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402
from bot.strategies.macd_trend import MacdTrend  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PERIODS = [10, 15, 20, 30, 40]


def load_btc():
    d = json.load(open(ROOT / "strategy_analysis/data/btc_5m_1y.json"))
    df = pd.DataFrame(d)
    df["time"] = pd.to_datetime(df["t"], unit="ms")
    return df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})


def resample(df, rule):
    r = df.set_index("time").resample(rule).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum")).dropna().reset_index()
    return r


def load_nq(interval):
    d = yf.download("NQ=F", interval=interval, period="730d", progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.reset_index()
    tcol = "Datetime" if "Datetime" in d.columns else "Date"
    return pd.DataFrame({
        "time": pd.to_datetime(d[tcol]).dt.tz_localize(None),
        "open": d["Open"].astype(float), "high": d["High"].astype(float),
        "low": d["Low"].astype(float), "close": d["Close"].astype(float),
        "volume": d["Volume"].astype(float)}).dropna().reset_index(drop=True)


def walk(df, make, cfg, train, test, optimize=True):
    pnl, fold_ret = [], []
    start, run_eq = 0, cfg.start_equity
    while start + train + test <= len(df):
        tr = df.iloc[start:start + train].reset_index(drop=True)
        te = df.iloc[start + train:start + train + test].reset_index(drop=True)
        p = 20
        if optimize:
            best_r = -1e9
            for pp in PERIODS:
                c = copy.copy(cfg); c.start_equity = run_eq
                m = run_backtest(tr, make(pp).signals(tr), c).metrics()
                r = m.get("return_pct", -1e9) if m.get("n_trades", 0) >= 8 else -1e9
                if r > best_r:
                    best_r, p = r, pp
        c = copy.copy(cfg); c.start_equity = run_eq
        res = run_backtest(te, make(p).signals(te), c)
        if res.trades:
            pnl += [t.pnl for t in res.trades]
            run_eq = float(res.equity_curve.iloc[-1])
            fold_ret.append(res.metrics().get("return_pct", 0))
        start += test
    pnl = np.array(pnl)
    if len(pnl) < 20:
        return None
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    total = run_eq / cfg.start_equity
    return dict(trades=len(pnl), pf=round(gw / gl, 2) if gl > 0 else 99,
                win=round((pnl > 0).mean() * 100, 1),
                ret=round((total - 1) * 100), folds=len(fold_ret),
                folds_pos=round(np.mean([r > 0 for r in fold_ret]) * 100))


def run(name, df, cfg, train, test):
    print(f"\n=== {name}: {len(df)} bars {df.time.iloc[0].date()}..{df.time.iloc[-1].date()} ===")
    print(f"  {'strategy':22} {'trades':>7} {'pf':>5} {'win%':>6} {'ret%':>7} {'folds+%':>8}")
    variants = {
        "donchian_LONG": lambda p: DonchianBreakout(p, 200, True, long_only=True),
        "donchian_both": lambda p: DonchianBreakout(p, 200, True, long_only=False),
        "macd_trend":    lambda p: MacdTrend(12, 26, 9, 200),
    }
    for vn, mk in variants.items():
        r = walk(df, mk, cfg, train, test, optimize=(vn != "macd_trend"))
        if r is None:
            print(f"  {vn:22} (few trades)")
        else:
            flag = "  <-- EDGE" if r["pf"] > 1.1 and r["folds_pos"] >= 60 else ""
            print(f"  {vn:22} {r['trades']:>7} {r['pf']:>5} {r['win']:>6} {r['ret']:>7} {r['folds_pos']:>7}%{flag}")


def main():
    btc = load_btc()
    cfg_btc = BacktestConfig(pip_size=1.0, pip_value_per_lot=1.0, spread_pips=15,
                             slippage_pips=8, commission_per_lot=25, exit_mode="atr",
                             atr_sl_mult=2.0, atr_tp_mult=3.0, risk_per_trade_pct=1.0, start_equity=10000)
    run("BTC 1h (1yr)", resample(btc, "1h"), cfg_btc, 3000, 1500)
    run("BTC 4h (1yr)", resample(btc, "4h"), cfg_btc, 800, 400)

    cfg_nq = BacktestConfig(pip_size=1.0, pip_value_per_lot=20.0, spread_pips=0.75,
                            slippage_pips=0.25, commission_per_lot=4, exit_mode="atr",
                            atr_sl_mult=2.0, atr_tp_mult=3.0, risk_per_trade_pct=1.0, start_equity=10000)
    try:
        run("NQ 1h (2yr)", load_nq("1h"), cfg_nq, 3000, 1500)
    except Exception as e:
        print("NQ 1h failed:", e)


if __name__ == "__main__":
    main()
