"""SILVER AS A SECOND BOOK — re-costed on Binance, and correlated against the blend.

    python -m backtest.silver_pair

WHY
    backtest/forex.py found exactly one non-crypto survivor: silver, positive in BOTH
    halves and stronger out of sample (meanR +0.226, PF 1.28 on 1h). It was parked as
    unfundable because Exness's smallest silver lot is 50 oz - $47.61 of risk on a 2xATR
    stop, which needs ~$15,869 of equity at 0.30% risk per unit.

    Binance lists XAGUSDT perps at a $5 minimum notional with a 0.001 step, $145M of
    24h volume across 73,130 trades. The same strategy needs **$25.22**. The floor was a
    broker artifact, exactly as the options premium's "$2,000 per contract" was a
    Deribit artifact when Binance's minimum was $24.46.

    So two questions, in order. Does silver survive BINANCE's costs rather than MT5's?
    And if it does, is it a genuinely different return stream from the crypto blend, or
    the same bet in a different wrapper?

THE COST MODEL, MEASURED NOT ASSUMED
    MT5:     9.52bp round-trip spread, swap 1.33bp per night      (forex.py, from
                                                                   mt5.symbol_info)
    Binance: taker 5bp/side = 10bp round trip, maker 2bp/side = 4bp,
             funding +0.322bp/8h mean = 0.97bp/night on LONGS      (500 periods of
                                                                   fundingRate history)

    So Binance taker is about the same as the MT5 spread and its funding is CHEAPER than
    Exness swap. Both are run. Funding is converted to R per trade using each trade's own
    entry ATR - a cost quoted as a fraction of price is a very different number of R in a
    calm market than a violent one, which is why forex.py's swap_R is reused rather than
    an average applied.

    A 20xATR trail holds for weeks, so the holding cost is 15-35x the spread for this
    strategy. It is the term that decides the result, not the fee.

THE CORRELATION IS THE WHOLE POINT
    A second stream that makes money and moves independently is the only thing in
    finance that cuts drawdown without cutting return. The crypto blend earns in 2021
    and 2024 and very little in 2025-2026; metals trended in 2025-2026. If the monthly
    correlation is low, the pair is worth more than either book alone.

    Computed on CALENDAR months ("ME"). A 30-day resample anchors its bins to each
    series' own first timestamp, which produced a NaN correlation matrix in this repo
    once already.

WHAT WOULD MAKE THIS A MIRAGE
    Silver's holdout half is ~6x stronger than its in-sample half, and that holdout is
    the metals bull market. It passes the test gold FAILED - gold was negative
    in-sample and +3.705 out, i.e. entirely one regime - but it is one instrument, one
    signal family, and a kind regime. The in-sample column below is the one to read.

REGISTERED PREDICTION (2026-09-20, before running)
    Silver survives Binance costs, because its funding is cheaper than the MT5 swap that
    forex.py already charged it and the fee is roughly unchanged. The correlation with
    the blend comes in LOW - under 0.3 - because the two books trade different assets
    with different drivers, and their good years do not overlap. The combined book should
    therefore show a lower drawdown than the blend alone at a similar return, which
    would be the first genuine risk improvement found in two weeks.

    The thing I expect to disappoint: silver's in-sample half is weak (+0.076R), so the
    combined return will be carried by crypto and silver will look like insurance rather
    than a second engine.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.convex import run_uncapped  # noqa: E402
from backtest.forex import atr_series, swap_R  # noqa: E402
from backtest.mass_search import gen_signals  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data"
RISK = 0.30                       # % per unit, the deployed number
TFS = ("1h", "4h")
# (label, fee_bp round trip, funding bp per night)
COSTS = (("MT5 (what forex.py charged)", 9.52, 1.33),
         ("Binance TAKER", 10.0, 0.966),
         ("Binance MAKER", 4.0, 0.966))


def bars(tf):
    f = DATA / f"XAGUSDm_{tf}_2400d.json"
    d = pd.DataFrame(json.load(open(f)))
    d["time"] = pd.to_datetime(d["t"], unit="ms")
    return (d.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close"})
            [["time", "open", "high", "low", "close"]].sort_values("time")
            .reset_index(drop=True))


def silver_trades(fee_bp, fund_bp):
    """The deployed config on silver: pyramided longs on a 20xATR trail, one-unit
    shorts on a 5xATR trail, breakeven at 3R. Funding charged per trade from the
    bars it was actually open."""
    out = []
    for tf in TFS:
        df = bars(tf)
        sig = gen_signals(df, "bb_break", (30, 1.5))
        t = df["time"].to_numpy()
        longs = pd.Series(np.where(sig.to_numpy() == 1, 1, 0), index=df.index)
        R, idx, _u, held = run_pyramid(
            df, longs, sl_mult=blend.SL_MULT, trail=blend.LONG_TRAIL,
            max_units=blend.MAX_UNITS, add_every=blend.ADD_EVERY,
            fee_bp=fee_bp, breakeven_at=blend.BE_AT)
        if len(R):
            R = R - swap_R(df, R, idx, held, tf, fund_bp, blend.SL_MULT)
            out += [(pd.Timestamp(t[int(i)]), float(r)) for r, i in zip(R, idx)]
        shorts = pd.Series(np.where(sig.to_numpy() == 2, 2, 0), index=df.index)
        R2, idx2, bars2, _d = run_uncapped(
            df, shorts, sl_mult=blend.SL_MULT, fee_bp=fee_bp,
            mode="trail_atr", trail=blend.SHORT_TRAIL, be_at=blend.BE_AT)
        if len(R2):
            # a short EARNS funding, so the sign flips
            R2 = R2 + swap_R(df, R2, idx2, bars2, tf, fund_bp, blend.SL_MULT)
            out += [(pd.Timestamp(t[int(i)]), float(r)) for r, i in zip(R2, idx2)]
    out.sort()
    return pd.Series([x[1] for x in out],
                     index=pd.DatetimeIndex([x[0] for x in out]))


def stats(monthly, label, width=30):
    if len(monthly) < 6:
        return f"  {label:<{width}} too few months"
    cur = np.cumprod(1.0 + monthly.values)
    dd = float((1 - cur / np.maximum.accumulate(np.maximum(cur, 1e-12))).max() * 100)
    mo = (max(cur[-1], 1e-12) ** (1 / len(monthly)) - 1) * 100
    return (f"  {label:<{width}}{len(monthly):>5}{mo:>+9.2f}%{dd:>8.1f}%"
            f"{100*(monthly>0).mean():>8.0f}%{monthly.min()*100:>+9.1f}%"
            f"{monthly.max()*100:>+9.1f}%")


HDR = (f"  {'book':<30}{'mths':>5}{'/month':>10}{'maxDD':>8}{'win%':>8}"
       f"{'worst':>9}{'best':>9}")


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: silver survives Binance costs (its funding is cheaper than the")
    print("MT5 swap already charged); correlation with the blend under 0.3; combined")
    print("drawdown lower at similar return. Expect silver to look like insurance, not")
    print("a second engine, because its in-sample half is weak.\n")

    print("=" * 92)
    print("1. DOES SILVER SURVIVE BINANCE'S COSTS?")
    print("=" * 92)
    print(f"  {'cost model':<30}{'trades':>8}{'meanR':>9}{'PF':>7}"
          f"{'in-sample':>11}{'holdout':>10}")
    books = {}
    for label, fee, fund in COSTS:
        s = silver_trades(fee, fund)
        if not len(s):
            print(f"  {label:<30} no trades")
            continue
        books[label] = s
        cut = s.index[int(len(s) * 0.6)]
        a, b = s[s.index < cut], s[s.index >= cut]
        pf = (s[s > 0].sum() / abs(s[s < 0].sum())) if (s < 0).any() else float("inf")
        print(f"  {label:<30}{len(s):>8}{s.mean():>+9.3f}{pf:>7.2f}"
              f"{a.mean():>+11.3f}{b.mean():>+10.3f}")
    print("\n  in-sample is the first 60% by date. Gold failed here (negative in-sample,")
    print("  hugely positive out) - that is the signature of one regime.")

    key = "Binance TAKER"
    if key not in books:
        print("\n  no Binance book to pair - stopping")
        return
    sil = books[key]
    sil_m = (sil.resample("ME").sum() * RISK / 100.0)

    print("\n" + "=" * 92)
    print("2. THE TWO BOOKS SIDE BY SIDE (monthly, 0.30% per unit, not hindsight-divided)")
    print("=" * 92)
    blend.FEE_BP = 12.0
    blend._S.clear()
    bl = blend.run(["1h", "4h", "12h"], 12)
    bl_m = (pd.Series(bl["R"], index=bl["times"]).resample("ME").sum() * RISK / 100.0)
    print(HDR)
    print(stats(bl_m, "crypto blend (12 slots)"))
    print(stats(sil_m, "silver (1h + 4h)"))

    j = pd.DataFrame({"crypto": bl_m, "silver": sil_m}).dropna()
    if len(j) < 12:
        print(f"\n  only {len(j)} overlapping months - cannot pair honestly")
        return
    c = float(j.crypto.corr(j.silver))
    print(f"\n  MONTHLY CORRELATION: {c:+.3f} over {len(j)} overlapping months")
    print(f"  crypto up / silver up      {int(((j.crypto>0)&(j.silver>0)).sum()):>3}")
    print(f"  crypto DOWN / silver UP    {int(((j.crypto<=0)&(j.silver>0)).sum()):>3}"
          f"   <- the months that matter")
    print(f"  crypto up / silver down    {int(((j.crypto>0)&(j.silver<=0)).sum()):>3}")
    print(f"  both down                  {int(((j.crypto<=0)&(j.silver<=0)).sum()):>3}")

    print("\n" + "=" * 92)
    print("3. THE COMBINED BOOK — does the pair beat the blend alone?")
    print("=" * 92)
    print(HDR)
    print(stats(j.crypto, "crypto only"))
    print(stats(j.silver, "silver only"))
    for w in (0.25, 0.50):
        print(stats(j.crypto * (1 - w) + j.silver * w,
                    f"{int((1-w)*100)}/{int(w*100)} crypto/silver"))
    print(stats(j.crypto + j.silver, "both at full risk (more total risk)"))

    print("\n" + "=" * 92)
    print("4. BY YEAR — do they earn at different times?")
    print("=" * 92)
    y = j.groupby(j.index.year).sum() * 100
    print(f"  {'year':<8}{'crypto':>11}{'silver':>11}{'50/50':>11}")
    for yr, row in y.iterrows():
        print(f"  {yr:<8}{row.crypto:>+10.1f}%{row.silver:>+10.1f}%"
              f"{(row.crypto+row.silver)/2:>+10.1f}%")

    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92)
    half = j.crypto * 0.5 + j.silver * 0.5
    cur_c = np.cumprod(1 + j.crypto.values)
    cur_h = np.cumprod(1 + half.values)
    dd_c = (1 - cur_c / np.maximum.accumulate(np.maximum(cur_c, 1e-12))).max() * 100
    dd_h = (1 - cur_h / np.maximum.accumulate(np.maximum(cur_h, 1e-12))).max() * 100
    mo_c = (max(cur_c[-1], 1e-12) ** (1 / len(j)) - 1) * 100
    mo_h = (max(cur_h[-1], 1e-12) ** (1 / len(j)) - 1) * 100
    print(f"  crypto alone : {mo_c:+.2f}%/month at {dd_c:.1f}% drawdown")
    print(f"  50/50 pair   : {mo_h:+.2f}%/month at {dd_h:.1f}% drawdown")
    if dd_h < dd_c and mo_h / max(dd_h, 1e-9) > mo_c / max(dd_c, 1e-9):
        print("\n  THE PAIR IS BETTER RISK-ADJUSTED. Check the in-sample column in")
        print("  section 1 before shipping: if silver's edge is only in its holdout,")
        print("  this is the metals bull market and not a second engine.")
    else:
        print("\n  The pair does NOT improve on crypto alone at this weighting. Read the")
        print("  correlation and the by-year table: if the correlation is low but the")
        print("  pair is worse, silver's return is simply too small to pay for itself.")


if __name__ == "__main__":
    main()
