"""EQUITY-CURVE TRADING - cut risk while the book's own equity is below its average.

The most common retail "improvement" to a system: trade it at full size only while its
equity curve is above a moving average of itself, on the idea that losing streaks
cluster. It is a gate driven by the book's own closed P&L, so it is strictly causal.

REGISTERED PREDICTION: worse on both halves. vol_target.py already found this book's
quietest, worst stretches come right BEFORE its trends, so any rule that shrinks size after
losses will be small when the next trend starts. Declared cells: MA of 30 / 90 days of
closed-trade equity, risk x0.5 below it.

Causal t0, funding charged, 12 slots, 1000h gate, venue minimum ignored ($200+ it never
binds - small_capital.py), 10 orderings, CAGR/3 haircut as everywhere else. ENTRY-SIZED
compounding (compounding.py). The first run of this file compounded sequentially and is
superseded. Its direction was the same: filter rows lost return on both halves.
The filter only counts if it beats a UNIFORM risk cut at the same drawdown.

    python -m backtest.equity_filter
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402

SEEDS = tuple(range(10))


def sim(rows, bear, seed, ma_days=None, cut_mult=0.5, t_from=None, t_to=None, uniform=1.0):
    """ENTRY-SIZED (compounding.py): a trade's dollars are fixed from closed equity at entry.
    uniform scales every trade - the same-risk control the filter has to beat."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    eq, opens, pending = 1.0, [], []
    hist_t, hist_e = [], []                         # closed-trade equity path
    state = dict(k=0, j=0, csum=0.0)                # running window [k, j) over hist

    def realize(upto):
        nonlocal eq
        pending.sort(key=lambda x: x[0])
        while pending and pending[0][0] <= upto:
            t1, dollars = pending.pop(0)
            eq = max(eq + dollars, 0.0)
            hist_t.append(pd.Timestamp(t1)); hist_e.append(eq)

    for r in o:
        t0 = pd.Timestamp(r["t0"])
        if (t_from is not None and t0 < t_from) or (t_to is not None and t0 >= t_to):
            continue
        realize(t0)
        opens = [u for u in opens if pd.Timestamp(u) > t0]
        if len(opens) >= 12:
            continue
        f = blend.RISK / 100.0 * uniform
        if bool(bear.asof(t0)):
            f *= blend.REGIME_MULT
        if ma_days and hist_t:
            lo = t0 - pd.Timedelta(days=ma_days)
            # hist_t is appended in time order; walk the left edge forward monotonically
            while state["k"] < len(hist_t) and hist_t[state["k"]] < lo:
                state["csum"] -= hist_e[state["k"]]; state["k"] += 1
            while state["j"] < len(hist_e):
                state["csum"] += hist_e[state["j"]]; state["j"] += 1
            n = state["j"] - state["k"]
            if n >= 5 and eq < state["csum"] / n:
                f *= cut_mult
        opens.append(r["t1"])
        pending.append((pd.Timestamp(r["t1"]), r["R"] * f * eq))   # sized at entry
    realize(pd.Timestamp("2100-01-01"))
    s = pd.Series(hist_e, index=pd.DatetimeIndex(hist_t)).resample("D").last().ffill()
    dd = float((1 - s / s.cummax()).max() * 100)
    yrs = max((s.index[-1] - s.index[0]).days / 365.25, 0.1)
    cagr = (max(s.iloc[-1], 1e-12) ** (1 / yrs) - 1) * 100
    hpm = ((1 + cagr / blend.HINDSIGHT / 100) ** (1 / 12) - 1) * 100
    return hpm, dd


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    rows = charged(real_t0(short_funding(long_funding(rows_for(BASE_RULES)))))
    print(f"tune < {cut:%Y-%m-%d} <= holdout | causal, funding charged, {len(SEEDS)} orderings\n")
    print(f"  {'variant':<36}{'TUNE/mo':>9}{'DD':>5}{'HOLD/mo':>9}{'DD':>5}")
    for lab, ma, u in (("no filter (main, corrected)", None, 1.0),
                       ("equity < 30d mean -> x0.5", 30, 1.0),
                       ("equity < 90d mean -> x0.5", 90, 1.0),
                       ("control: every trade x0.7", None, 0.7),
                       ("control: every trade x0.5", None, 0.5)):
        a = np.mean([sim(rows, bear, s, ma, t_to=cut, uniform=u) for s in SEEDS], axis=0)
        b = np.mean([sim(rows, bear, s, ma, t_from=cut, uniform=u) for s in SEEDS], axis=0)
        print(f"  {lab:<36}{a[0]:>+8.2f}%{a[1]:>4.0f}%{b[0]:>+8.2f}%{b[1]:>4.0f}%")


if __name__ == "__main__":
    main()
