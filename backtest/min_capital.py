"""WHAT IS THE MINIMUM CAPITAL FOR THE COMBINATION ON BITGET ($5 minimum per order)?

Asked 2026-09-24. CLAUDE.md's "capital does not change the percentage above ~$25" was measured
for the trend book against MEXC's per-coin minimums ($0.005-$2.28, blend_paper.MIN_ORDER).
Bitget's minimum is $5 an order (longtrend_bot.MIN_NOTIONAL), and the combination adds two books
with small orders of their own. Each part, measured:

  TREND   every unit of the triple book (tight + time stop + 7 units, dd_fixes.build), 2020-2026:
          its dollar notional at capital C is C x 0.30% x (0.25 while BTC < 1000h avg) x entry/risk.
          Share of units under $5, and the share of the book's total R those units carry.
  MN      6 longs + 6 shorts at 1x, half the account per side: C / 12 per position.
  SLEEVE  breadth_robust.small_account on the 5-coin basket at capital C: its return and the share
          of its orders skipped for size.
Account equity moves: after a 45% fall, $221 trades like $122. So each figure is also read at
the capital left at the bottom of a typical bad stretch.

REGISTERED PREDICTION (2026-09-24, before running): the sleeve binds first (its 1/7 daily steps
across 5 coins are C/35 each, $6.30 at $221); the full combination needs ~$175-225; the trend
book alone loses a few % of its units below $100 (the quarter-size bear units).

    python -m backtest.min_capital
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bull_boost import regimes  # noqa: E402
from backtest.dd_fixes import build  # noqa: E402

MIN = 5.0
CAPS = (50, 100, 150, 221, 300, 500, 1000)


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    rows = build()
    units = []                                  # (notional per $1 of capital, unit R)
    for r in rows:
        ib = bv[max(np.searchsorted(bn, r["t0"], side="right") - 1, 0)]
        f = 0.003 * (0.25 if ib else 1.0)
        for k, e in enumerate(r["ue"]):
            units.append((f * e / r["risk"], float(r["uR"][k]), ib, r["side"]))
    u = pd.DataFrame(units, columns=["per_dollar", "R", "bear", "side"])
    totR = u.R.sum()
    print("TREND (triple book, every unit 2020-2026): units whose order would be under $5")
    print(f"  {'capital':>8}{'units under $5':>16}{'of which bear-sized':>21}{'share of total R lost':>24}")
    for c in CAPS:
        small = u.per_dollar * c < MIN
        print(f"  ${c:>7,}{small.mean()*100:>15.1f}%{(small & u.bear).sum() / max(small.sum(), 1)*100:>20.0f}%"
              f"{u.R[small].sum() / totR * 100:>+23.1f}%")
    print(f"  median unit: {u.per_dollar.median()*100:.1f}% of capital (full size), "
          f"{u[u.bear].per_dollar.median()*100:.1f}% while BTC is below its 1000h average")

    print("\nMARKET-NEUTRAL at 1x: 12 positions, capital / 12 each")
    for c in CAPS:
        print(f"  ${c:>7,}: ${c/12:6.2f} per position {'OK' if c / 12 >= MIN else 'UNDER $5 - cannot trade'}")

    print("\nBEAR SLEEVE at 1x on the 5-coin basket (breadth_robust.small_account), 2020-2026:")
    from backtest.breadth_attack import ls_signal
    from backtest.breadth_robust import breadth_n, small_account
    from backtest.carry_check import exact_funding
    from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel
    from backtest.regime_signals import member_mask
    from backtest.wide_book import eligibility
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    reg = btc_regime(C).reindex(C.index)
    Fx = exact_funding(C.index, C.columns)
    X = C.to_numpy(float)
    m60 = member_mask(C, first, drop_non_crypto(eligibility(60))) & np.isfinite(X)
    sig = ls_signal(breadth_n(C, m60, 20), reg == "bear")
    e5 = drop_non_crypto(eligibility(5))
    months = C.index.strftime("%Y-%m")
    bym = {m: [s for s in C.columns if m in e5.get(s, ())] for m in sorted(set(months))}
    ci = {s: i for i, s in enumerate(C.columns)}

    def top5(d):
        return [s for s in bym[months[d]] if np.isfinite(X[d, ci[s]])][:5]
    base = None
    for c in (100_000,) + CAPS:
        eq, skip = small_account(C, Fx, first, sig, top5, cap=float(c))
        g = eq[eq.index >= pd.Timestamp("2020-03-01")]
        yrs = len(g) / 365
        cagr = ((g.iloc[-1] / g.iloc[0]) ** (1 / yrs) - 1) * 100
        if c == 100_000:
            base = cagr
            print(f"  no minimum binding (${c:,}): {cagr:+.1f}%/yr - the reference")
            continue
        print(f"  ${c:>7,}: {cagr:+6.1f}%/yr ({cagr - base:+.1f} vs no minimum), orders skipped for size {skip*100:4.0f}%")


if __name__ == "__main__":
    main()
