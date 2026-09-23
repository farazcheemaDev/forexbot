"""TRADING BTC ITSELF ON THE MARKET-TIMING SIGNALS - does any beat the plain trend rule?

btc_signals.py found two signals that held their predicted sign on both halves (Coinbase
premium and BTC's own multi-horizon momentum). btc_dial.py showed that using them to size the
alt book does not beat a uniform bet on both halves, and that using them to tighten exits
hurts. The remaining use is the most direct one: trade BTC on them. This also answers the
question the bot's own gate raises - is "BTC above its 1000h average" (what the bot uses) the
best simple read of where BTC is going, or does a signal from outside the price do better?

RULES (daily, decided at 00:00 UTC from data through the previous day; btc_signals.features)
    HOLD    buy and hold
    MA1000  long while BTC > its 1000-hour average (the bot's gate, read at 00:00), else flat
    TSMOM   long while sign(7d)+sign(28d)+sign(90d) >= +1, else flat
    CBPREM  long while the 7-day Coinbase premium > 0, else flat
    BULL    long while TSMOM and CBPREM both agree (btc_dial.regime() == BULL), else flat
    L/S     long in BULL, SHORT in BEAR, flat in NEUTRAL
    Perp execution: 5bp per side on every change of position, actual BTC funding (a long pays
    it, a short receives it). 1x notional; a 2x line for the best rule shows what leverage does.

REGISTERED PREDICTIONS (before running)
    1. Every timing rule beats HOLD on drawdown; none clearly beats it on return over 2020-2026.
    2. BULL has the best Sharpe of the long/flat rules on BOTH halves; MA1000 is second.
    3. L/S is worse than BULL (doc 02: crypto shorts are a hedge, not a profit source).

    python -m backtest.btc_timing
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PERPS = ROOT / "strategy_analysis" / "data" / "perps"
COST = 5 / 1e4


def load():
    F = pd.read_csv(ROOT / "logs" / "btc_signals_features.csv.gz", index_col=0, parse_dates=True)
    d = blend.load("BTCUSDT")
    h = pd.Series(d["close"].to_numpy(float), index=pd.DatetimeIndex(d["time"]))
    o = pd.Series(d["open"].to_numpy(float), index=pd.DatetimeIndex(d["time"]))
    day_open = o.resample("D").first()
    ret = day_open.shift(-1) / day_open - 1                 # 00:00 -> next 00:00
    ma = h.rolling(1000).mean()
    above = (h > ma).resample("D").last().shift(1)          # state at the end of D-1
    fu = pd.read_csv(PERPS / "BTCUSDT_funding.csv.gz", parse_dates=["time"])
    fday = fu.groupby(fu.time.dt.floor("D"))["rate"].sum()
    X = pd.DataFrame({"ret": ret, "fund": fday, "ma": above}).join(F[["tsmom", "cb_prem"]])
    X = X[X.index >= "2020-03-01"].dropna(subset=["ret"])
    X["fund"] = X["fund"].fillna(0.0)
    return X


def positions(X):
    bull = (X.tsmom >= 1) & (X.cb_prem > 0)
    bear = (X.tsmom <= -1) & (X.cb_prem < 0)
    return {
        "HOLD": pd.Series(1.0, index=X.index),
        "MA1000": X.ma.astype(float).fillna(0.0),
        "TSMOM": (X.tsmom >= 1).astype(float),
        "CBPREM": (X.cb_prem > 0).astype(float),
        "BULL": bull.astype(float),
        "L/S": bull.astype(float) - bear.astype(float),
        "BULL 2x": 2.0 * bull.astype(float),
    }


def stats(p, X):
    r = p * (X.ret - X.fund) - p.diff().abs().fillna(p.abs()) * COST
    eq = (1 + r).cumprod()
    yrs = len(r) / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (1 - eq / eq.cummax()).max()
    sh = r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else np.nan
    return cagr, dd, sh, r


def main():
    X = load()
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)].normalize()
    P = positions(X)
    print(f"BTC daily, {X.index[0]:%Y-%m-%d} .. {X.index[-1]:%Y-%m-%d}, 5bp per change, funding charged "
          f"| tune < {cut:%Y-%m-%d} <= holdout\n")
    print(f"  {'rule':<9}{'in mkt':>7}{'CAGR':>8}{'DD':>6}{'Sharpe':>8} |{'TUNE CAGR':>10}{'Sh':>6}"
          f"{'DD':>5} |{'HOLD CAGR':>10}{'Sh':>6}{'DD':>5}")
    yearly = {}
    for k, p in P.items():
        c, dd, sh, r = stats(p, X)
        a = stats(p[X.index < cut], X[X.index < cut]); b = stats(p[X.index >= cut], X[X.index >= cut])
        print(f"  {k:<9}{(p != 0).mean()*100:>6.0f}%{c*100:>+7.0f}%{dd*100:>5.0f}%{sh:>8.2f} |"
              f"{a[0]*100:>+9.0f}%{a[2]:>6.2f}{a[1]*100:>4.0f}% |{b[0]*100:>+9.0f}%{b[2]:>6.2f}{b[1]*100:>4.0f}%")
        yearly[k] = r.groupby(r.index.year).apply(lambda x: (np.prod(1 + x) - 1) * 100)
    print("\n  by calendar year (%):")
    Y = pd.DataFrame(yearly).round(0)
    print(Y.to_string())


if __name__ == "__main__":
    main()
