"""Deep walk-forward validation of the systematic fade strategies on LOTS of data:
BTC 5m (1yr, Binance) and NASDAQ 1h (2yr, yfinance). Many folds across regimes ->
if a positive number survives here, it's far more trustworthy than the 60d test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402
from bot.strategies.level_fade import LevelFade  # noqa: E402
from bot.strategies.liquidity_sweep import LiquiditySweep  # noqa: E402
from bot.strategies.vwap_reversion import VwapReversion  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def load_btc():
    d = json.load(open(ROOT / "strategy_analysis/data/btc_5m_1y.json"))
    df = pd.DataFrame(d)
    df["time"] = pd.to_datetime(df["t"], unit="ms")
    return df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})[
        ["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def load_nq():
    d = yf.download("NQ=F", interval="1h", period="730d", progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.reset_index()
    tcol = "Datetime" if "Datetime" in d.columns else "Date"
    return pd.DataFrame({
        "time": pd.to_datetime(d[tcol]).dt.tz_localize(None),
        "open": d["Open"].astype(float), "high": d["High"].astype(float),
        "low": d["Low"].astype(float), "close": d["Close"].astype(float),
        "volume": d["Volume"].astype(float)}).dropna().reset_index(drop=True)


def walk(df, sig_fn, cfg, train, test):
    pnl, fold_ret = [], []
    start = 0
    run_eq = cfg.start_equity
    while start + train + test <= len(df):
        te = df.iloc[start + train:start + train + test].reset_index(drop=True)
        cfg.start_equity = run_eq
        res = run_backtest(te, sig_fn(te), cfg)
        if res.trades:
            pnl += [t.pnl for t in res.trades]
            run_eq = float(res.equity_curve.iloc[-1])
            fold_ret.append(res.metrics().get("return_pct", 0))
        start += test
    pnl = np.array(pnl)
    if len(pnl) < 20:
        return None
    eq = cfg.start_equity + 0  # not used
    wins = pnl[pnl > 0]; losses = pnl[pnl < 0]
    gw, gl = wins.sum(), -losses.sum()
    return {
        "trades": len(pnl), "pf": round(gw / gl, 2) if gl > 0 else 99,
        "win": round((pnl > 0).mean() * 100, 1),
        "exp": round(pnl.mean(), 3),
        "folds": len(fold_ret), "folds_pos": round(np.mean([r > 0 for r in fold_ret]) * 100),
    }


def run_market(name, df, cfg, train, test, round_step):
    print(f"\n=== {name}: {len(df)} bars, {df.time.iloc[0].date()}..{df.time.iloc[-1].date()} "
          f"(train={train}/test={test}) ===")
    strats = {
        "liquidity_sweep": lambda d: LiquiditySweep(20, True).signals(d),
        "vwap_reversion":  lambda d: VwapReversion(2.0, 14, 65, 35).signals(d),
        "level_fade":      lambda d: LevelFade(round_step, round_step * 0.08, 14, 68, 32, True).signals(d),
        "donchian_trend":  lambda d: DonchianBreakout(20, 200, True, long_only=False).signals(d),
    }
    print(f"  {'strategy':17} {'trades':>7} {'pf':>5} {'win%':>6} {'exp':>7} {'folds+%':>8}")
    for sname, fn in strats.items():
        import copy
        r = walk(df, fn, copy.copy(cfg), train, test)
        if r is None:
            print(f"  {sname:17} (too few trades)")
        else:
            flag = "  <-- edge" if r["pf"] > 1.05 and r["folds_pos"] >= 60 else ""
            print(f"  {sname:17} {r['trades']:>7} {r['pf']:>5} {r['win']:>6} {r['exp']:>7} {r['folds_pos']:>7}%{flag}")


def main():
    # BTC 5m — realistic taker-fee scalp cost (~0.06% ~ $ at price)
    btc = load_btc()
    cfg_btc = BacktestConfig(pip_size=1.0, pip_value_per_lot=1.0, spread_pips=15,
                             slippage_pips=8, commission_per_lot=25, exit_mode="atr",
                             atr_sl_mult=2.0, atr_tp_mult=1.2, risk_per_trade_pct=1.0,
                             start_equity=10000)
    run_market("BTC 5m (1yr)", btc, cfg_btc, 20000, 10000, round_step=500)

    # NQ 1h — tight futures cost
    try:
        nq = load_nq()
        cfg_nq = BacktestConfig(pip_size=1.0, pip_value_per_lot=20.0, spread_pips=0.75,
                                slippage_pips=0.25, commission_per_lot=4, exit_mode="atr",
                                atr_sl_mult=2.0, atr_tp_mult=1.2, risk_per_trade_pct=1.0,
                                start_equity=10000)
        run_market("NQ 1h (2yr)", nq, cfg_nq, 3000, 1500, round_step=100)
    except Exception as e:
        print("NQ load failed:", e)


if __name__ == "__main__":
    main()
