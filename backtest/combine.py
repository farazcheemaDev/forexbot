"""DOES THE MARKET-NEUTRAL BOOK COMBINE WITH THE DEPLOYED TREND BOOK?

THE QUESTION
    Two books that both make money are only worth running together if they do not make it
    at the same times. Adding a second correlated book buys nothing but complexity; adding
    an uncorrelated one of half the return can still raise risk-adjusted return, because
    the drawdowns do not line up.

    So the only number that matters first is the CORRELATION, and it must be measured on
    the same clock for both books.

WHAT IS COMPARED
    * trend blend: the deployed config (bb_break 30/1.5, 3 sleeves, 12 slots, 1000h gate),
      daily fractional returns, seed-averaged over 5 orderings, divided by the 3x hindsight
      premium because its 12 coins were chosen with hindsight.
    * market-neutral: backtest/market_neutral.py, PIT top-60, 30d momentum, weekly. NOT
      haircut - its universe is point-in-time and survivorship-free, so there is no coin
      selection to haircut. That asymmetry FLATTERS the market-neutral book in the return
      column and is the main caveat on this table.

    Both are resampled to weekly sums and compounded weekly.

CAVEAT ON THE DRAWDOWN COLUMN
    Dividing a daily return series by 3 tames its drawdown too, so the trend blend reads
    ~23% here where the un-haircut book measures 58% (backtest/expectations.py). The
    drawdowns in this table are only comparable to EACH OTHER, not to the rest of the docs.

    python -m backtest.combine
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.market_neutral import btc_regime, load_panel, run  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

SEEDS = (0, 1, 2, 3, 4)
MIXES = (0.25, 0.50, 0.75)


def blend_weekly():
    """Deployed trend book as a weekly return series, haircut and seed-averaged."""
    bear = regimes()[1000]
    rows = rows_for(BASE_RULES)
    acc = []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
        acc.append(evaluate(o, bear)["daily"] / blend.HINDSIGHT)
    return pd.concat(acc, axis=1).mean(axis=1).resample("W").sum()


def mn_weekly(top_n=60, look=30, hold=7):
    C, F, first = load_panel()
    df = run(C, F, first, eligibility(top_n), look=look, hold=hold)
    return pd.Series(df.net.to_numpy(), index=pd.DatetimeIndex(df.t)).resample("W").sum(), C


def stats(x: pd.Series):
    cur = np.cumprod(1 + x.to_numpy())
    dd = float((1 - cur / np.maximum.accumulate(cur)).max() * 100)
    yrs = len(x) / 52.0
    ann = (max(cur[-1], 1e-9) ** (1 / yrs) - 1) * 100
    mo = ((1 + ann / 100) ** (1 / 12) - 1) * 100
    sh = float(x.mean() / x.std(ddof=1) * np.sqrt(52))
    return mo, ann, dd, sh, float((x > 0).mean() * 100)


def main():
    bl = blend_weekly()
    mn, C = mn_weekly()
    j = pd.DataFrame({"blend": bl, "mn": mn}).dropna()
    print(f"overlap: {len(j)} weeks, {j.index[0]:%Y-%m} .. {j.index[-1]:%Y-%m}\n")
    print(f"CORRELATION, trend blend vs market-neutral: {j.blend.corr(j.mn):+.3f}")
    print("  (below ~0.3 is the whole point: the two books are effectively independent)")

    reg = btc_regime(C)
    lab = pd.Series([reg.asof(t) if t >= reg.index[0] else "chop" for t in j.index],
                    index=j.index)
    print(f"\n  correlation by regime: " + "  ".join(
        f"{r} {j[lab == r].blend.corr(j[lab == r].mn):+.2f}" for r in ("bull", "bear", "chop")))

    print(f"\n  {'book':<26}{'/mo':>9}{'/yr':>9}{'DD*':>7}{'Sharpe':>8}{'wks up':>8}")
    def line(lb, x):
        mo, ann, dd, sh, up = stats(x)
        print(f"  {lb:<26}{mo:>+8.2f}%{ann:>+8.0f}%{dd:>6.0f}%{sh:>8.2f}{up:>7.0f}%")
    line("trend blend alone", j.blend)
    line("market-neutral alone", j.mn)
    for w in MIXES:
        line(f"blend {(1-w)*100:.0f}% / MN {w*100:.0f}%", j.blend * (1 - w) + j.mn * w)
    print("  *see the docstring: these drawdowns compare to each other, not to doc 00.")

    print("\n  BY REGIME, net weekly, to show WHERE the second book earns its place")
    print(f"  {'regime':<10}{'weeks':>7}{'blend':>10}{'MN':>10}{'50/50':>10}")
    for r in ("bull", "bear", "chop"):
        k = j[lab == r]
        if len(k) < 5:
            continue
        print(f"  {r:<10}{len(k):>7}{k.blend.mean()*100:>+9.3f}%{k.mn.mean()*100:>+9.3f}%"
              f"{(k.blend*0.5+k.mn*0.5).mean()*100:>+9.3f}%")


if __name__ == "__main__":
    main()
