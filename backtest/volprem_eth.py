"""THE VOLATILITY PREMIUM ON THE INSTRUMENT WE CAN ACTUALLY TRADE.

    python -m backtest.volprem_eth

WHY THIS FILE EXISTS
    backtest/volprem.py measured the vol risk premium on BTC and found the cleanest
    statistical edge in this project. docs/02-what-failed.md then filed it under
    "capital floor too high - needs ~$2,000 per contract" and closed it.

    That floor was a DERIBIT number and it is wrong. Verified live 2026-09-18:

        venue / underlying        min notional   24h option volume   ATM spread
        Deribit BTC (0.1 BTC)        $7,643            -                 -
        Deribit ETH (1 ETH)          $2,446            -                 -
        Binance BTC (0.01)             $764          $7.7M           0.5-1.4%
        Binance ETH (0.01)          >  $24.46 <      $2.5M           0.2-1.1%
        Binance SOL/DOGE/XRP/BNB     $1.50-9       $6k-12k        too thin
        Binance XAU (gold)             $43           $4.4k        too thin

    So the accessible instrument is BINANCE ETH, at a $24 minimum notional and
    spreads a quarter of what volprem.py assumed. But volprem.py tested BTC.
    ETH's premium has never been measured here, and the two are not the same
    asset: as of today ETH DVOL is 50.6 against BTC's 33.3.

THE SECOND REASON, WHICH MATTERS MORE
    Re-running volprem.py today prints something the doc does not mention:

        2026 YTD   mean +0.74 vol points, 63.4% positive
        and the worst 8 periods in the whole 5.5-year sample are ALL Jan 2026

    A 5.5-year average of +9.48 is worthless if the last 9 months are +0.74. So
    every table here breaks 2026 out rather than averaging it away.

METHOD, IDENTICAL TO volprem.py SO THE TWO ARE COMPARABLE
    For each day t:  earned = DVOL(t) - realised_vol(t .. t+30d)
    DVOL(t) is known at t; the realised vol is what happens next. Causal by
    construction, no look-ahead available.

THE ONE CONDITIONAL TEST, DECLARED BEFORE RUNNING
    Standard finance says the premium is LARGER when implied vol is already high
    (sellers are paid more for insurance precisely when fear is priced). That is
    testable and it is the only conditioning variable tested here - one test, not a
    sweep, because a sweep over filters on 66 independent windows would find
    something by chance. It is ranked on the first 2/3 of the sample by date and
    re-checked on the last 1/3, which never informed anything.

    If it holds it matters right now: ETH DVOL is 50.6, near the top of its range.

STRADDLE VEGA - volprem.py's APPROXIMATION IS EXACTLY HALF THE TRUTH
    volprem.py used 0.4 x sqrt(h/365) of notional per vol point. The correct ATM
    straddle vega is 0.8 x S x sqrt(T) x 0.01, which reproduces today's live market
    to the dollar:

        ETH 9-Oct-26 ATM straddle, 21d, IV 47.1%
        0.8 x 2446 x 0.471 x sqrt(21/365) = $221   |   actual bid $220.20

    So volprem.py's printed returns AND its printed tail losses are both understated
    2x. The RATIO between them - which is what decides the leverage - is unchanged,
    exactly as its docstring said. This file uses the correct vega.

REGISTERED PREDICTION (2026-09-18, before running)
    ETH carries a premium at least as large as BTC's, because ETH realised vol is
    higher and insurance on it is dearer. I expect the same 2026 collapse to appear
    in ETH, because Jan 2026 was a market-wide event, not a BTC one. And I expect
    the high-IV conditioning test to HOLD, which is the one prediction here that
    would change what we do next. If the 2026 collapse is present in ETH and the
    conditioning test fails, this category closes for good.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
HORIZON_D = 30
ANN = np.sqrt(365.0)
rng = np.random.default_rng(31)

# verified live 2026-09-18 from eapi.binance.com/eapi/v1/exchangeInfo + /ticker
MIN_UNITS = 0.01              # contracts; unit = 1 ETH
ETH_SPOT = 2446.05
SPREAD_FRAC = 0.011           # 1.1%, the WORST ATM spread measured live


def dvol(cur):
    d = json.load(open(DATA / f"dvol_{cur.lower()}_full.json"))
    s = pd.Series({pd.to_datetime(int(k), unit="ms"): float(v)
                   for k, v in d.items()}).sort_index()
    return s.resample("1D").last().dropna()


def spot(sym):
    for name in (f"{sym}_1h_2400d.json", f"{sym}_1h_1500d.json"):
        f = DATA / name
        if f.exists():
            d = pd.DataFrame(json.load(open(f)))
            d["t"] = pd.to_datetime(d["t"], unit="ms")
            return (d.set_index("t")["c"].astype(float)
                    .resample("1D").last().dropna())
    raise SystemExit(f"no cached bars for {sym}")


def forward_rv(px, days):
    r = np.log(px / px.shift(1))
    return (r[::-1].rolling(days).std()[::-1] * ANN * 100).shift(-1)


def premium(cur, sym):
    f = pd.DataFrame({"iv": dvol(cur), "rv": forward_rv(spot(sym), HORIZON_D)}).dropna()
    f["earned"] = f.iv - f.rv
    return f


def independent_t(x):
    """t on NON-overlapping windows only. A 30-day horizon on daily observations
    gives one independent window every 30 rows; anything else inflates t ~5.5x."""
    ind = x[::HORIZON_D]
    return len(ind), float(ind.mean() / (ind.std(ddof=1) / np.sqrt(len(ind))))


def vega_per_eth(s, h_days):
    """USD earned per 1 vol point on a 1-ETH ATM straddle. Validated against the
    live board in this file's docstring."""
    return 0.8 * s * np.sqrt(h_days / 365.0) * 0.01


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: ETH carries a premium >= BTC's; the 2026 collapse appears in")
    print("ETH too; and the high-IV conditioning test HOLDS. If 2026 is broken in ETH")
    print("AND conditioning fails, the category closes.\n")

    books = {c: premium(c, s) for c, s in (("ETH", "ETHUSDT"), ("BTC", "BTCUSDT"))}

    print("=" * 94)
    print("1. THE PREMIUM, ETH vs BTC  (vol points earned by a seller, 30d horizon)")
    print("=" * 94)
    print(f"  {'':6}{'n':>6}{'mean':>8}{'median':>8}{'pos%':>7}{'sd':>7}"
          f"{'WORST':>8}{'5th':>7}{'indep n':>9}{'honest t':>10}")
    for cur, f in books.items():
        x = f.earned.to_numpy()
        n_i, t_i = independent_t(x)
        print(f"  {cur:6}{len(f):>6}{x.mean():>+8.2f}{np.median(x):>+8.2f}"
              f"{100*(x>0).mean():>6.1f}%{x.std():>7.2f}{x.min():>+8.2f}"
              f"{np.percentile(x,5):>+7.2f}{n_i:>9}{t_i:>+10.2f}")
    print("\n  'honest t' uses non-overlapping 30-day windows only.")

    print("\n" + "=" * 94)
    print("2. BY YEAR - is 2026 broken on ETH as well?")
    print("=" * 94)
    print(f"  {'year':<6}{'ETH n':>7}{'ETH mean':>10}{'ETH pos%':>10}{'ETH worst':>11}"
          f"{'BTC mean':>11}{'BTC pos%':>10}{'BTC worst':>11}")
    for y in sorted({y for f in books.values() for y in f.index.year}):
        e = books["ETH"][books["ETH"].index.year == y].earned
        b = books["BTC"][books["BTC"].index.year == y].earned
        if len(e) == 0 or len(b) == 0:
            continue
        print(f"  {y:<6}{len(e):>7}{e.mean():>+10.2f}{100*(e>0).mean():>9.1f}%"
              f"{e.min():>+11.2f}{b.mean():>+11.2f}{100*(b>0).mean():>9.1f}%"
              f"{b.min():>+11.2f}")

    print("\n" + "=" * 94)
    print("3. THE TAIL - what one bad window costs, in units of a good one")
    print("=" * 94)
    for cur, f in books.items():
        x = f.earned.to_numpy()
        ratio = abs(x.min()) / x.mean() if x.mean() > 0 else float("nan")
        print(f"  {cur}: mean {x.mean():+.2f}  worst {x.min():+.2f}  "
              f"=> one worst window costs {ratio:.1f} average windows")
        for d_, r_ in f.nsmallest(4, "earned").iterrows():
            print(f"       {d_:%Y-%m-%d}  IV {r_.iv:5.1f}%  RV(next 30d) "
                  f"{r_.rv:5.1f}%  earned {r_.earned:+7.2f}")

    print("\n" + "=" * 94)
    print("4. THE ONE CONDITIONAL TEST - is the premium bigger when IV is already high?")
    print("=" * 94)
    f = books["ETH"]
    cut = f.index[int(len(f) * 2 / 3)]
    tr, te = f[f.index < cut], f[f.index >= cut]
    thresh = float(tr.iv.median())
    print(f"  split at {cut:%Y-%m-%d}: rank on {len(tr)} rows, hold out {len(te)}")
    print(f"  'high IV' = ETH DVOL above its in-sample median of {thresh:.1f}\n")
    print(f"  {'sample':<14}{'n high':>8}{'mean high':>11}{'n low':>8}"
          f"{'mean low':>11}{'diff':>9}{'p':>8}")
    for lab, g in (("in-sample", tr), ("HOLDOUT", te)):
        hi = g[g.iv > thresh].earned.to_numpy()
        lo = g[g.iv <= thresh].earned.to_numpy()
        if len(hi) < 30 or len(lo) < 30:
            print(f"  {lab:<14}too few on one side ({len(hi)}/{len(lo)})")
            continue
        hi_i, lo_i = hi[::HORIZON_D], lo[::HORIZON_D]
        obs_i = hi_i.mean() - lo_i.mean()
        allv = np.concatenate([hi_i, lo_i])
        k = len(hi_i)
        cnt = 0
        for _ in range(20000):
            p = rng.permutation(allv)
            if abs(p[:k].mean() - p[k:].mean()) >= abs(obs_i):
                cnt += 1
        print(f"  {lab:<14}{len(hi):>8}{hi.mean():>+11.2f}{len(lo):>8}"
              f"{lo.mean():>+11.2f}{hi.mean()-lo.mean():>+9.2f}{cnt/20000:>8.3f}")
    print(f"\n  ETH DVOL today: 50.6  =>  "
          f"{'ABOVE' if 50.6 > thresh else 'below'} the {thresh:.1f} threshold")

    print("\n" + "=" * 94)
    print("5. WHAT THIS EARNS AT A SIZE A $221 ACCOUNT CAN ACTUALLY TRADE")
    print("=" * 94)
    v1 = vega_per_eth(ETH_SPOT, HORIZON_D)
    min_notional = MIN_UNITS * ETH_SPOT
    e_all = books["ETH"].earned
    e_26 = e_all[e_all.index.year == 2026]
    cap = 221.0
    iv_now = float(books["ETH"].iv.iloc[-1])
    print(f"  Binance ETH min trade   {MIN_UNITS} contracts = "
          f"${min_notional:,.2f} of notional")
    print(f"  ATM straddle vega       ${v1:,.2f} per vol point per 1 ETH")
    print(f"  spread charged          {SPREAD_FRAC*100:.1f}% of premium "
          f"(worst ATM spread measured live)")
    print(f"  IV used for premium     {iv_now:.1f}% (latest ETH DVOL)\n")
    print(f"  {'sizing':<34}{'notional':>10}{'ETH':>7}"
          f"{'/mo 5.5y':>10}{'/mo 2026':>10}{'worst 30d':>11}")
    rows = [("1 min contract (0.01 ETH)", min_notional)]
    for frac in (0.25, 0.50):
        # notional such that the worst observed window costs `frac` of capital
        rows.append((f"worst window costs {int(frac*100)}% of cap",
                     frac * cap * ETH_SPOT / (abs(e_all.min()) * v1)))
    for lab, notional in rows:
        units = notional / ETH_SPOT
        per_pt = v1 * units
        gross = 0.8 * ETH_SPOT * (iv_now / 100) * np.sqrt(HORIZON_D / 365) * units
        cost = gross * SPREAD_FRAC
        print(f"  {lab:<34}{notional:>10,.0f}{units:>7.2f}"
              f"{(e_all.mean()*per_pt-cost)/cap*100:>+9.1f}%"
              f"{(e_26.mean()*per_pt-cost)/cap*100:>+9.1f}%"
              f"{e_all.min()*per_pt/cap*100:>+10.1f}%")
    print("\n  Below one minimum contract there is no smaller size: row 1 is the FLOOR,")
    print("  not a choice. If row 1's worst-30d exceeds your tolerance, the trade is")
    print("  not available to this account at any size.")

    print("\n" + "=" * 94)
    print("VERDICT")
    print("=" * 94)
    x = e_all.to_numpy()
    n_i, t_i = independent_t(x)
    print(f"  ETH premium over 5.5y: {x.mean():+.2f} vol points, honest t {t_i:+.2f} "
          f"on {n_i} independent windows")
    print(f"  ETH premium in 2026:   {e_26.mean():+.2f} vol points over {len(e_26)} days")
    if e_26.mean() < 2.0:
        print("\n  2026 IS BROKEN ON ETH TOO. The 5.5-year average is not a forecast; it")
        print("  is a description of a regime that ended. Do not deploy on the average.")
    else:
        print("\n  2026 holds up on ETH even though it broke on BTC - which would be the")
        print("  single most important result in this file. Re-check before believing it.")


if __name__ == "__main__":
    main()
