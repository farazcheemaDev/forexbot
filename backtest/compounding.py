"""THREE WAYS THIS REPO COMPOUNDS THE SAME TRADES, AND WHICH ONE THE BOT ACTUALLY LIVES.

Found 2026-09-23 when equity_filter.py's no-filter row read +13.50%/mo on the holdout while
honest_rescore.py read +8.37% for the same book. Same trades, same slots, same gate, same
sizing fraction. The difference is only how P&L becomes equity:

  SEQUENTIAL  eq *= (1 + R x f) at each close, in close order.
              small_capital.simulate -> expectations.py -> doc 00's planning table.
  DAILY SUM   equity_day_end = equity_day_start x (1 + sum of R x f closing that day).
              bull_boost.evaluate -> engine_variants / composite / regime_gate / most docs.
  ENTRY-SIZED dollars = R x f x (closed-trade equity AT ENTRY); equity is the running sum.
              What blend_paper.py and the live bot do: a position's notional is fixed when
              it opens (and its adds use the same unit), so its dollar P&L does not grow
              with profits other trades bank while it is open.

SEQUENTIAL is wrong whenever big winners close close together: each later close is scaled by
equity that already contains the earlier ones, which it was never sized on. One holdout
ordering has five trades closing 2024-12-09 for +420% of equity summed - sequential turns
the book's x36 holdout into x105. DAILY SUM is the same error confined within a day. ENTRY-
SIZED is the physically correct one given the bot sizes on closed equity.

REGISTERED PREDICTION: ENTRY-SIZED reads BELOW daily-sum (a long pyramid's entry equity is
smaller than the equity it closes into), and both are far below sequential. So every figure
from small_capital.py / expectations.py is inflated, and the evaluate()-based figures
slightly so.

    python -m backtest.compounding
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


def taken(rows, bear, seed, t_from=None, t_to=None, slots=12):
    """The slot allocator, identical to bull_boost.evaluate: (t0, t1, R x f) per taken trade."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    opens, out = [], []
    for r in o:
        if (t_from is not None and r["t0"] < t_from) or (t_to is not None and r["t0"] >= t_to):
            continue
        opens = [u for u in opens if u > r["t0"]]
        if len(opens) >= slots:
            continue
        opens.append(r["t1"])
        f = blend.RISK / 100.0 * (blend.REGIME_MULT if bool(bear.asof(r["t0"])) else 1.0)
        out.append((pd.Timestamp(r["t0"]), pd.Timestamp(r["t1"]), r["R"] * f))
    return out


def curve(tr, how):
    """Daily equity curve (start 1.0) under one compounding convention."""
    if how == "daily_sum":
        s = pd.Series([x[2] for x in tr], index=pd.DatetimeIndex([x[1] for x in tr]))
        d = s.resample("D").sum()
        return pd.Series(np.cumprod(np.maximum(1 + d.to_numpy(), 0)), index=d.index)
    ev = sorted([(x[1], 1, i) for i, x in enumerate(tr)] + [(x[0], 0, i) for i, x in enumerate(tr)])
    eq, at_entry, pts = 1.0, {}, []
    for t, kind, i in ev:                      # entries (kind 0) before closes at equal t
        if kind == 0:
            at_entry[i] = eq
        else:
            if how == "sequential":
                eq = max(eq * (1 + tr[i][2]), 0.0)
            else:                              # entry_sized
                eq = max(eq + at_entry[i] * tr[i][2], 0.0)
            pts.append((t, eq))
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    return s.resample("D").last().ffill()


def summarize(c):
    dd = float((1 - c / c.cummax()).max() * 100)
    yrs = max((c.index[-1] - c.index[0]).days / 365.25, 0.1)
    fin = max(float(c.iloc[-1]), 1e-12)
    cagr = (fin ** (1 / yrs) - 1) * 100
    hpm = ((1 + cagr / blend.HINDSIGHT / 100) ** (1 / 12) - 1) * 100
    raw = (fin ** (1 / (yrs * 12)) - 1) * 100
    return hpm, raw, dd, fin


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    books = {"main": charged(real_t0(short_funding(long_funding(rows_for(BASE_RULES))))),
             "tight": charged(real_t0(short_funding(long_funding(
                 rows_for(BASE_RULES, tight=True)))))}
    print(f"causal t0, funding charged, {len(SEEDS)} orderings | tune < {cut:%Y-%m-%d} <= holdout")
    print("hpm = CAGR/3 per month (the docs' convention); raw = un-haircut per month\n")
    print(f"  {'book':<7}{'half':<9}{'method':<13}{'hpm':>8}{'raw':>9}{'DD':>6}{'x final':>11}")
    for bk, rows in books.items():
        for half, kw in (("tune", dict(t_to=cut)), ("holdout", dict(t_from=cut))):
            trs = [taken(rows, bear, sd, **kw) for sd in SEEDS]
            for how in ("sequential", "daily_sum", "entry_sized"):
                v = np.array([summarize(curve(t, how)) for t in trs])
                print(f"  {bk:<7}{half:<9}{how:<13}{v[:,0].mean():>+7.2f}%{v[:,1].mean():>+8.2f}%"
                      f"{v[:,2].mean():>5.0f}%{np.median(v[:,3]):>11.1f}")


if __name__ == "__main__":
    main()
