"""TWO WAYS TO STOP PAYING THE FUNDING BILL - spot routing, and a funding-extreme trail.

funding_cost.py measured the bill: longs pay 21% of their lifetime R in funding (12h sleeve
46%, 4h 25%, 1h 13%), and Bitget's funding ran ABOVE Binance's on all 11 book coins over the
three months its API serves, so the bill measured on Binance is a floor for this account.

A. SPOT ROUTING
    A spot long pays no funding. Bitget spot costs 0.10% taker a side (20bp round trip)
    against 6bp a side on the perp, so routing a sleeve to spot trades 8bp more fee per unit
    for zero funding. The 12h sleeve's stop is ~11% of price, so 8bp is ~0.007R a unit
    against ~3R of funding per 12h position. On paper that is free money.

    The catch is capital, and it is the whole question: spot cannot be levered, so the
    routed sleeve's GROSS NOTIONAL has to fit in cash alongside the perp margin. Reported
    as the routed sleeve's notional / equity at the 99th percentile and the max. Anything
    above ~0.5x does not fit next to a perp book that already runs 8.7x gross at p99
    (needing ~0.45x of equity as margin at 20x).

B. TIGHTEN THE TRAIL WHEN THE COIN'S FUNDING GOES EXTREME
    btc_exit.py showed an exit rule can work when its information comes from OUTSIDE the
    position (BTC's trend), unlike the eleven dead rules keyed on the position's own R. A
    coin's funding rate is outside information too, and an extreme rate is both a cost and
    the BIS "carry predicts crash risk" signal. Rule: while the mean of the last 3 settled
    funding rates is above a threshold, open longs trail at 5xATR instead of 20x (the tight
    book's mechanics, with the same "must switch off before it can arm" rule).

REGISTERED PREDICTIONS (before running)
    A. 12h to spot adds ~+1.5%/mo on the tune half and ~+0.2% on the holdout, and its gross
       notional fits (p99 < 0.5x). Routing 4h too adds more but will NOT fit.
    B. Thresholds 0.03% and 0.05% per 8h. It helps the tune half (2021) and is flat on the
       holdout, where extreme funding was rare. Net: not adopted, because the evidence would
       be one regime.

Causal t0, funding charged, 12 slots, 1000h gate, 5 orderings, 3x haircut.

    python -m backtest.funding_routes
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.engine_variants import BASE_RULES, SEEDS, long_walk, rows_for, run, shorts_for  # noqa: E402
from backtest.entry_features import fund_series  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

SPOT_EXTRA_BP = 8.0          # Bitget spot 10bp/side vs perp 6bp/side


def route_to_spot(rows, rules):
    """Longs on these sleeves: no funding, and 8bp more fee per unit per round trip."""
    out = []
    for r in rows:
        if r["side"] == "long" and r["rule"] in rules:
            # R already carries 12bp per unit: add the extra 8bp, drop the funding
            extra = SPOT_EXTRA_BP / 1e4 * len(r["adds"]) / r["sf"]   # in R, per unit ~ e/r
            out.append(dict(r, fund=0.0, R=r["R"] - extra))
        else:
            out.append(r)
    return out


def gross_of(rows, bear, rules):
    """p99 / max of the routed sleeve's gross notional / equity, through the real slot
    allocator: every other row still takes its slot but contributes no notional."""
    masked = [dict(r, sf=(r["sf"] if (r["side"] == "long" and r["rule"] in rules) else 1e9))
              for r in rows]
    grid = pd.date_range(pd.Timestamp(masked[0]["t0"]).floor("h"),
                         pd.Timestamp(max(r["t1"] for r in masked)).ceil("h"), freq="h")
    s = evaluate(masked, bear, grid=grid)
    return s.get("lev99", 0.0), s.get("levmax", 0.0)


def fund_extreme_map(coin, df, rule, thr):
    """Per bar of df: is the mean of the last 3 funding rates SETTLED by this bar's end
    above thr? Bar end is time+1h for every sleeve (1h rows carry the open, resampled rows
    the right label, which closes one hour after it)."""
    f = fund_series(coin)
    m = f.rolling(3).mean()
    m = m[~m.index.duplicated(keep="last")]
    ends = pd.DatetimeIndex(df["time"]) + pd.Timedelta(hours=1)
    v = m.reindex(m.index.union(ends)).ffill().reindex(ends).to_numpy(float)
    return np.nan_to_num(v, nan=0.0) > thr


def rows_fund_tight(thr):
    rows = []
    for rule in BASE_RULES:
        rows += shorts_for(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            tb = fund_extreme_map(coin, df, rule, thr)
            rows += long_walk(df, rule, coin, tb=tb)
    return rows


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    base = real_t0(short_funding(long_funding(rows_for(BASE_RULES))))
    print(f"tune < {cut:%Y-%m-%d} <= holdout | causal t0, funding charged, 5 orderings\n")
    print(f"  {'book':<44}{'TUNE/mo':>9}{'DD':>5}{'HOLD/mo':>9}{'DD':>5}{'worst':>8}"
          f"{'gross p99':>11}{'max':>7}")

    def show(lab, rows, rules=()):
        a = run(rows, bear, cut, "tune"); b = run(rows, bear, cut, "hold")
        g = gross_of(rows, bear, rules) if rules else (np.nan, np.nan)
        print(f"  {lab:<44}{a[0]:>+8.2f}%{a[1]:>4.0f}%{b[0]:>+8.2f}%{b[1]:>4.0f}%{b[2]:>+7.1f}%"
              f"{g[0]:>10.2f}x{g[1]:>6.2f}x")

    show("deployed (all perp), funding charged", charged(base))
    show("A. 12h longs on spot", charged(route_to_spot(base, {"12h"})), {"12h"})
    show("A. 4h + 12h longs on spot", charged(route_to_spot(base, {"4h", "12h"})),
         {"4h", "12h"})
    show("A. all longs on spot (upper bound)", charged(route_to_spot(base, set(BASE_RULES))),
         set(BASE_RULES))
    for thr in (0.0003, 0.0005):
        rr = real_t0(short_funding(long_funding(rows_fund_tight(thr))))
        show(f"B. tighten to 5xATR while funding > {thr*100:.2f}%/8h", charged(rr))


if __name__ == "__main__":
    main()
