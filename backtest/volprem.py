"""THE VOLATILITY RISK PREMIUM — harvesting, not predicting.

WHY THIS FAMILY AND NOT ANOTHER INDICATOR
    Nineteen indicator families were tested and all nineteen found the same thing:
    crypto rising, with no short side. Indicator search is closed.

    The one thing in this project that ever worked by MECHANISM rather than by
    pattern was funding carry - structurally positive, profitable in 80-85% of all
    8h periods. It was small, but it was the only result that did not depend on
    predicting a price.

    Selling volatility is the same family. Implied vol trades above subsequent
    realised vol in essentially every market ever studied, because option buyers pay
    for insurance. You are not forecasting direction; you are collecting a risk
    premium. Deribit currently shows IV 40.7% against RV 34.2%.

WHAT IS MEASURED, AND WHY THIS IS THE HONEST TEST
    DVOL is Deribit's 30-day implied vol index for BTC (their VIX). For each day t:

        earned = DVOL(t)  -  realised vol over the NEXT 30 days

    That difference is, to first order, what a delta-hedged vol seller collects. It
    is causal by construction: DVOL(t) is known at t, and the realised vol is what
    happens afterwards. No look-ahead is possible.

    5.47 years of DVOL (2021-03 .. 2026-09) - crucially including the 2022 collapse
    (LUNA in May, FTX in November), which is exactly where short-vol strategies die.
    A test of this idea that excludes 2022 is worthless.

THE SHAPE OF THIS RISK IS THE OPPOSITE OF EVERYTHING ELSE HERE
    The trend strategy: ~24% win rate, rare enormous winners, positive skew.
    Selling vol: high win rate, rare enormous LOSERS, negative skew. Pennies in
    front of a steamroller.

    So the average premium is the least interesting number in the output. What
    matters is:
        - worst single period, because that is the one that ends the account
        - whether the premium survives 2022 specifically
        - what leverage the tail permits, not what the mean invites

    A strategy that earns +6 vol points 90% of the time and loses 60 in the other
    10% is not an edge, it is a delayed loss. The tail columns below decide this,
    not the mean.

MODEL LIMITS, STATED PLAINLY
    * Variance-swap approximation: P&L ~ (IV^2 - RV^2). A real short straddle also
      carries path/gamma risk that this does not capture, and it hurts the seller
      when the path is jumpy rather than merely wide.
    * No bid-ask. Deribit option spreads are wide (often 2-5% of premium); a real
      seller receives less than mid. Stated, not modelled.
    * No margin/liquidation modelling. On Deribit a short option position can be
      liquidated before expiry even if it would have expired worthless, which is a
      real path risk this ignores.
    * Realised vol is close-to-close, which understates true variation for a
      jumpy asset, and therefore FLATTERS the seller.
    Every one of these biases points the same way: the real result is worse than
    what this prints.

    python -m backtest.volprem
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import fetch  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
HORIZON_D = 30          # DVOL is a 30-day implied vol
ANN = np.sqrt(365.0)


def load_dvol() -> pd.Series:
    d = json.load(open(DATA / "dvol_btc.json"))
    s = pd.Series({pd.to_datetime(int(k), unit="ms"): float(v)
                   for k, v in d.items()}).sort_index()
    return s.resample("1D").last().dropna()


def realised_vol_forward(px: pd.Series, days: int) -> pd.Series:
    """Annualised close-to-close realised vol over the NEXT `days` days."""
    r = np.log(px / px.shift(1))
    # forward-looking window: reverse, roll, reverse back
    fwd = r[::-1].rolling(days).std(ddof=0)[::-1] * ANN * 100
    return fwd.shift(-1)        # from tomorrow, so today is not included


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=HORIZON_D)
    args = ap.parse_args()

    dvol = load_dvol()
    btc = fetch("BTCUSDT", "1h", 2400)
    px = (btc.drop_duplicates("time").set_index("time")["close"]
          .resample("1D").last().dropna())
    rv = realised_vol_forward(px, args.horizon)

    df = pd.DataFrame({"iv": dvol, "rv_fwd": rv}).dropna()
    df["earned"] = df["iv"] - df["rv_fwd"]
    # variance-swap P&L is in variance units, not vol units
    df["var_pnl"] = (df["iv"] ** 2 - df["rv_fwd"] ** 2) / 1e4

    print(f"VOLATILITY RISK PREMIUM — BTC, {args.horizon}-day horizon")
    print(f"  {len(df)} overlapping daily observations, "
          f"{df.index[0]:%Y-%m-%d} .. {df.index[-1]:%Y-%m-%d}")
    print(f"  IV = DVOL (known at t). RV = realised over the NEXT "
          f"{args.horizon} days.\n")

    e = df["earned"]
    print("=" * 88)
    print("THE PREMIUM (vol points earned by a seller)")
    print("=" * 88)
    print(f"  mean            {e.mean():+7.2f} vol points")
    print(f"  median          {e.median():+7.2f}")
    print(f"  positive        {(e > 0).mean()*100:6.1f}% of observations")
    print(f"  std dev         {e.std(ddof=1):7.2f}")
    print(f"  BEST period     {e.max():+7.2f}")
    print(f"  WORST period    {e.min():+7.2f}   <- the one that ends the account")
    print(f"  5th percentile  {e.quantile(0.05):+7.2f}")
    print(f"  1st percentile  {e.quantile(0.01):+7.2f}")
    t = e.mean() / (e.std(ddof=1) / np.sqrt(len(e)))
    # overlapping windows inflate t badly; effective n ~ len/horizon
    n_eff = max(len(e) / args.horizon, 1)
    t_eff = e.mean() / (e.std(ddof=1) / np.sqrt(n_eff))
    print(f"\n  nominal t {t:+.2f} on {len(e)} overlapping windows")
    print(f"  HONEST t  {t_eff:+.2f} using {n_eff:.0f} independent windows "
          f"(30d horizon, daily obs)")

    print("\n" + "=" * 88)
    print("BY YEAR — does it survive 2022 (LUNA in May, FTX in November)?")
    print("=" * 88)
    print(f"{'year':>6} {'n':>5} {'mean':>8} {'median':>8} {'pos%':>7} "
          f"{'worst':>8} {'best':>8}")
    for y, g in e.groupby(e.index.year):
        print(f"{y:>6} {len(g):>5} {g.mean():>+8.2f} {g.median():>+8.2f} "
              f"{(g > 0).mean()*100:>6.1f}% {g.min():>+8.2f} {g.max():>+8.2f}")

    print("\n" + "=" * 88)
    print("WORST 8 SINGLE PERIODS — the steamroller")
    print("=" * 88)
    w = e.nsmallest(8)
    for d_, v in w.items():
        print(f"  {d_:%Y-%m-%d}  IV {df.loc[d_,'iv']:6.1f}%  "
              f"RV(next {args.horizon}d) {df.loc[d_,'rv_fwd']:6.1f}%  "
              f"earned {v:+7.2f}")

    print("\n" + "=" * 88)
    print("WHAT LEVERAGE THE TAIL PERMITS")
    print("=" * 88)
    # a short straddle's loss scales roughly with (RV-IV); size so the worst
    # observed period costs a stated fraction of capital
    worst = abs(e.min())
    print(f"  worst observed loss: {worst:.1f} vol points")
    for ruin_pct in (25, 50, 100):
        # vol points -> % of notional is roughly (vol pts / 100) * sqrt(h/365) * 0.8
        # for an ATM straddle; use a conservative 0.4 factor
        loss_frac = worst / 100 * np.sqrt(args.horizon / 365) * 0.4
        lev = ruin_pct / 100 / loss_frac if loss_frac > 0 else float("nan")
        gain = (e.mean() / 100 * np.sqrt(args.horizon / 365) * 0.4) * lev * 100
        per_yr = gain * (365 / args.horizon)
        print(f"  sized so the worst period costs {ruin_pct:>3}% of capital -> "
              f"{lev:4.1f}x notional, ~{per_yr:+6.1f}%/yr expected")
    print("\n  (straddle P&L per vol point approximated at 0.4 x sqrt(h/365) of")
    print("   notional. Order of magnitude only - the point is the RATIO between")
    print("   the mean and the tail, which no approximation changes much.)")


if __name__ == "__main__":
    main()
