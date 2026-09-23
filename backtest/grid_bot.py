"""THE GRID BOT - what exchanges sell as the "money machine", measured, and as a MIX.

WHY TEST IT
    Bitget, Binance and every bot platform push futures grid bots: a ladder of buy orders
    below price and sell orders above, "profit from every swing, no prediction needed." It is
    also the obvious COMPLEMENT to this project's trend book, which bleeds in sideways markets
    - exactly where a grid earns. If a grid made money in the months the trend book loses, it
    would be the mix the mandate asks for.

    It is also a reversal bet in disguise: a grid is short volatility with inventory risk. It
    earns the spacing on every down-and-back-up, and in a trend it accumulates the losing side
    until the range breaks. doc 02 records 7+ dead reversal ideas; this is the one version
    nobody here had simulated.

THE SIMULATION (Bitget futures neutral grid)
    Geometric levels at centre x (1+s)^i, N = 20 levels (10 each side). State j = last level
    crossed; position = -j units (below centre: long; above: short). Falling to the next level
    down buys one unit, rising to the next level up sells one: each down-up pair banks one
    spacing. At +-10 levels the position is full and further moves only mark it. If price runs
    ONE level beyond the ladder, the grid is closed at that level (taker 6bp) and re-centred
    at the current price - the "rolling grid" most users run.
    Fills are maker, 2bp (Bitget futures maker). Funding is charged on the inventory at every
    settlement (the grid is long in selloffs and short in rallies, so it tends to RECEIVE
    in crowded markets). Intrabar path: O->L->H->C on up bars, O->H->L->C on down bars.
    Capital = the full ladder's notional on one side (10 units x centre price), unlevered;
    returns are on that capital. Levering it scales return AND drawdown.

    Coins: BTC, ETH, SOL, XRP, DOGE perps - large throughout, no hindsight selection.
    Spacings 0.5%, 1%, 2%, 3%. One pre-declared gated variant (below).

REGISTERED PREDICTIONS (before running)
    1. Every coin x spacing loses money over 2020-2026 after fees and funding: inventory losses
       in trends exceed the spacing income.
    2. Its monthly correlation with the trend book is NEGATIVE (-0.2 to -0.5) - that part of
       the brochure is true.
    3. Even in the trend book's LOSING months the grid averages under +1%/month, so as a mix
       it buys a smoother curve by losing money. Verdict: dead.
    GATED VARIANT, declared now and tested once: run the grid only while the coin's 7-day
    efficiency ratio (|net move| / sum of |hourly moves|, known at the bar) is below 0.15,
    i.e. while it is actually ranging; flatten (taker) when it rises above.

    python -m backtest.grid_bot
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PERPS = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
COINS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT")
SPACINGS = (0.005, 0.01, 0.02, 0.03)
N_SIDE = 10
MAKER, TAKER = 2 / 1e4, 6 / 1e4
ER_GATE = 0.15


def load(sym):
    h = pd.read_csv(PERPS / f"{sym}_1h.csv.gz", usecols=["time", "open", "high", "low", "close"])
    h["time"] = pd.to_datetime(h["time"]).astype("datetime64[ns]")
    fu = pd.read_csv(PERPS / f"{sym}_funding.csv.gz")
    fu["time"] = pd.to_datetime(fu["time"]).dt.floor("h").astype("datetime64[ns]")
    f = fu.groupby("time")["rate"].sum()
    h["fund"] = h["time"].map(f).fillna(0.0)          # settlement at this bar's open time
    c = h["close"].to_numpy(float)
    net = np.abs(pd.Series(c).diff(168))
    path = pd.Series(np.abs(np.diff(c, prepend=c[0]))).rolling(168).sum()
    h["er"] = (net / path).shift(1).to_numpy()        # known at the bar's open
    return h


def run(h, s, gated=False):
    """Daily P&L as a fraction of ladder capital (1.0 = one side's full notional), summed,
    not compounded. Equity = banked P&L + the open ladder marked at the close."""
    o, hi, lo, cl = (h[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    fund, er = h["fund"].to_numpy(float), h["er"].to_numpy(float)
    g = np.log1p(s)
    st = dict(active=False, centre=0.0, u=0.0, j=0, pos=0.0, cash=0.0, banked=0.0)

    def level(i):
        return st["centre"] * np.exp(i * g)

    def start(px):
        st.update(active=True, centre=px, u=1.0 / (N_SIDE * px), j=0, pos=0.0, cash=0.0)

    def flatten(px):
        st["banked"] += st["cash"] + st["pos"] * px - abs(st["pos"]) * px * TAKER
        st.update(active=False, pos=0.0, cash=0.0, j=0)

    def fill(px, units):                       # units > 0 buy, < 0 sell; maker fee
        st["pos"] += units
        st["cash"] -= units * px + abs(units) * px * MAKER

    eq = np.zeros(len(h))
    for i in range(len(h)):
        ok = (not gated) or (np.isfinite(er[i]) and er[i] < ER_GATE)
        if st["active"] and fund[i]:
            st["cash"] -= st["pos"] * o[i] * fund[i]      # long pays +rate, short receives
        if st["active"] and not ok:
            flatten(o[i])
        just_started = False
        if ok and not st["active"]:
            start(o[i]); just_started = True
        if st["active"]:
            path = (o[i], lo[i], hi[i], cl[i]) if cl[i] >= o[i] else (o[i], hi[i], lo[i], cl[i])
            if i > 0 and not just_started:
                path = (cl[i - 1],) + path                # the gap from the last close counts too
            for a, b in zip(path[:-1], path[1:]):
                if b < a:
                    while b <= level(st["j"] - 1):
                        px = level(st["j"] - 1)
                        if st["j"] > -N_SIDE:
                            fill(px, st["u"]); st["j"] -= 1
                        else:                             # one level past the ladder
                            flatten(px); start(px)
                elif b > a:
                    while b >= level(st["j"] + 1):
                        px = level(st["j"] + 1)
                        if st["j"] < N_SIDE:
                            fill(px, -st["u"]); st["j"] += 1
                        else:
                            flatten(px); start(px)
        eq[i] = st["banked"] + ((st["cash"] + st["pos"] * cl[i]) if st["active"] else 0.0)
    pnl = np.diff(eq, prepend=0.0)
    return pd.Series(pnl, index=pd.DatetimeIndex(h["time"])).resample("D").sum()


def stats(d):
    m = d.resample("ME").sum()
    cum = d.cumsum()
    dd = float((cum.cummax() - cum).max())
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    return dict(ann=float(d.sum() / yrs * 100), dd=dd * 100, up=float((m > 0).mean() * 100),
                sh=float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else np.nan, m=m)


def main():
    from backtest.bull_boost import regimes
    from backtest.causal_t0 import real_t0
    from backtest.engine_variants import BASE_RULES, rows_for
    from backtest.funding_cost import charged, long_funding, short_funding
    from backtest.mtm_sizing import attach_prices, simulate as entry_sized

    bear = regimes()[1000]
    tight = charged(real_t0(short_funding(long_funding(attach_prices(
        rows_for(BASE_RULES, tight=True))))))
    curves = [entry_sized(tight, bear, sd, "realised", want_curve=True) for sd in range(5)]
    tr = pd.concat([c.resample("ME").last().pct_change() for c in curves], axis=1).mean(axis=1)
    tr.index = tr.index.to_period("M")

    print("GRID BOT: unlevered return on ladder capital, simple (not compounded) sums")
    print("trend = tight book, entry-sized, raw monthly (5 orderings)\n")
    print(f"  {'coin':<10}{'spacing':>8}{'gate':>6}{'ann %':>9}{'maxDD %':>9}{'mo up':>7}{'Sharpe':>8}"
          f"{'corr w/ trend':>15}{'in trend-down mo':>18}  by year (%)")
    allm = {}
    for sym in COINS:
        h = load(sym)
        for s in SPACINGS:
            for gated in (False, True):
                if gated and s not in (0.01, 0.02):
                    continue
                d = run(h, s, gated)
                st = stats(d)
                m = st["m"].copy(); m.index = m.index.to_period("M")
                j = pd.concat([m.rename("g"), tr.rename("t")], axis=1).dropna()
                corr = j.g.corr(j.t)
                down = j.g[j.t < 0].mean() * 100
                yr = d.groupby(d.index.year).sum() * 100
                allm[(sym, s, gated)] = m
                print(f"  {sym:<10}{s*100:>7.1f}%{'ER' if gated else '-':>6}{st['ann']:>+9.1f}"
                      f"{st['dd']:>9.0f}{st['up']:>6.0f}%{st['sh']:>8.2f}{corr:>+15.2f}"
                      f"{down:>+17.2f}%  " + " ".join(f"{y % 100:02d}:{v:+.0f}" for y, v in yr.items()))
        print()


if __name__ == "__main__":
    main()
