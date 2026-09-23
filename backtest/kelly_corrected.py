"""HOW HARD CAN THIS BOOK BE BET? - the growth-optimal risk, recomputed on the fixed engine.

WHY THIS HAS TO BE REDONE
    ruin.py answered "what is the largest risk $221 can carry" on an engine that has since been
    found to overstate returns by roughly 2x (mistake #14, entry-sized compounding), to charge
    no funding (#13) and to read some entries from the future (#12). Overstated returns imply an
    overstated optimal bet size, so the old answer is not merely stale, it errs toward MORE
    leverage than the strategy can carry. That makes this a safety question, not an optimisation.

    graveyard_rescore.py also found that risk x1.33 beats main on BOTH halves (+0.65 +- 0.03
    tune, +0.36 +- 0.07 holdout) - one of only two rows that did. Doc 11 called it "a dial, not
    an edge", which is right as far as it goes. This file asks how far the dial actually turns.

THE CONSTRAINT THE DIAL FRAMING MISSES
    Notional per unit = risk_fraction x equity / stop_fraction, so equity cancels and GROSS
    LEVERAGE SCALES EXACTLY LINEARLY WITH THE RISK FRACTION. lev_test.py established that
    liquidation is free up to ~10x gross and destructive above it. If the deployed 0.30% already
    runs near 9x at its 99th percentile, then the tradable ceiling is barely above the deployed
    setting and no amount of backtested growth above it is reachable. So leverage is measured
    here per fraction, not assumed.

WHAT IS MEASURED, per risk fraction, on the corrected engine
    entry-sized compounding, causal entry times, funding charged, 10 orderings, 12 slots,
    1000h gate, tune/holdout split as everywhere else
      * geometric %/month, haircut 3x (12-coin book)
      * realised max drawdown
      * gross leverage, p99 and max, with the 10x line flagged
      * P(drawdown > 80%) over 3 years, by 30-day block bootstrap of the daily series

REGISTERED PREDICTIONS (before the run, 2026-09-23)
    1. Growth keeps rising past 0.30% in the BACKTEST - it usually does, because drawdown does
       not bite a log-utility curve until much later. So the backtest alone will "recommend"
       something well above the deployed setting.
    2. Gross leverage at 0.30% comes in between 7x and 10x at p99, so the tradable ceiling lands
       between 0.30% and 0.45% - i.e. the dial is already most of the way turned.
    3. If 2 holds, the honest answer to "can risk buy crazy returns" is NO, and the binding
       constraint is liquidation, not growth theory.
    4. The growth-optimal fraction will be HIGHER on the holdout than on the tune half, because
       the holdout is the flatter regime and flat regimes tolerate more size. That is a warning
       sign, not a recommendation.

    python -m backtest.kelly_corrected
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import bootstrap_dd, regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.mtm_sizing import attach_prices  # noqa: E402

SEEDS = tuple(range(10))
FRACTIONS = (0.10, 0.20, 0.30, 0.35, 0.45, 0.60, 0.90, 1.20, 1.80, 2.40)
LEV_CAP = 10.0            # lev_test.py: free below, destructive above
SLOTS = 12


def simulate(rows, bear, seed, risk_pct, t_from=None, t_to=None):
    """Entry-sized compounding at an arbitrary risk fraction, tracking gross leverage.

    A position's dollars are fixed when it OPENS, from equity standing at that moment, and do
    not grow with profits other trades bank while it is open (mistake #14). Gross leverage is
    the sum of open notional over equity; notional per unit is risk_usd / stop_fraction, so the
    ratio is independent of equity and scales linearly in risk_pct - which is the point."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    eq, open_, pts, levs = 1.0, [], [], []

    def bank(upto):
        nonlocal eq, open_
        keep = []
        for p in sorted(open_, key=lambda q: q["t1"]):
            if p["t1"] <= upto:
                eq = max(eq + p["dpr"] * p["R"], 0.0)
                pts.append((p["t1"], eq))
            else:
                keep.append(p)
        open_ = keep

    for r in o:
        t0 = pd.Timestamp(r["t0"])
        if (t_from is not None and t0 < t_from) or (t_to is not None and t0 >= t_to):
            continue
        bank(t0)
        if len(open_) >= SLOTS:
            continue
        try:
            ib = bool(bear.asof(t0))
        except Exception:
            ib = False
        f = risk_pct / 100.0 * (blend.REGIME_MULT if ib else 1.0)
        open_.append(dict(r, t1=pd.Timestamp(r["t1"]), dpr=f * eq, f=f))
        if eq > 0:
            # notional = dollars_at_risk / stop_fraction, summed over open units
            lev = sum(p["dpr"] / max(p["sf"], 1e-6) * len(p.get("adds", [1]))
                      for p in open_) / eq
            levs.append(lev)
    bank(pd.Timestamp("2100-01-01"))
    if len(pts) < 20:
        return None
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    cur = s.resample("D").last().ffill()
    return dict(curve=cur, lev99=float(np.percentile(levs, 99)) if levs else np.nan,
                levmax=float(np.max(levs)) if levs else np.nan)


def score(res_list):
    """Median geometric %/month (3x haircut) and drawdown across orderings."""
    hpm, dd, fin = [], [], []
    for r in res_list:
        if r is None:
            continue
        c = r["curve"]
        yrs = max((c.index[-1] - c.index[0]).days / 365.25, 0.1)
        mult = max(float(c.iloc[-1]), 1e-12)
        cagr = mult ** (1 / yrs) - 1
        hc = cagr / blend.HINDSIGHT
        hpm.append(((1 + hc) ** (1 / 12) - 1) * 100 if hc > -1 else -100.0)
        dd.append(float((1 - c / c.cummax()).max() * 100))
        fin.append(mult)
    if not hpm:
        return None
    return dict(hpm=float(np.median(hpm)), dd=float(np.median(dd)),
                ddmax=float(np.max(dd)), mult=float(np.median(fin)))


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print("building the corrected row set (causal t0 + funding charged)...")
    base = charged(real_t0(short_funding(long_funding(attach_prices(rows_for(BASE_RULES))))))
    tight = charged(real_t0(short_funding(long_funding(attach_prices(
        rows_for(BASE_RULES, tight=True))))))
    print(f"{len(base)} trades | {len(SEEDS)} orderings | tune < {cut:%Y-%m-%d} <= holdout")
    print("hpm = median geometric %/month after the 3x haircut")

    for name, rows in (("MAIN", base), ("TIGHT", tight)):
        print()
        print(f"{name} BOOK")
        print(f"  {'risk/unit':>10}{'TUNE/mo':>10}{'DD':>6}{'HOLD/mo':>10}{'DD':>6}"
              f"{'FULL/mo':>10}{'DD':>6}{'worstDD':>9}{'lev p99':>9}{'lev max':>9}  flag")
        rec = {}
        for fr in FRACTIONS:
            t = score([simulate(rows, bear, s, fr, t_to=cut) for s in SEEDS])
            h = score([simulate(rows, bear, s, fr, t_from=cut) for s in SEEDS])
            full = [simulate(rows, bear, s, fr) for s in SEEDS]
            f_ = score(full)
            lev99 = float(np.median([x["lev99"] for x in full if x]))
            levmax = float(np.median([x["levmax"] for x in full if x]))
            rec[fr] = dict(t=t, h=h, f=f_, lev99=lev99, curves=[x["curve"] for x in full if x])
            flag = ""
            if lev99 > LEV_CAP:
                flag = "  OVER 10x - NOT TRADABLE"
            elif f_ and f_["ddmax"] > 90:
                flag = "  a 90%+ DD in some ordering"
            dep = "  <- DEPLOYED" if abs(fr - blend.RISK) < 1e-9 else ""
            print(f"  {fr:>9.2f}%{t['hpm'] if t else float('nan'):>+9.2f}%"
                  f"{t['dd'] if t else float('nan'):>5.0f}%"
                  f"{h['hpm'] if h else float('nan'):>+9.2f}%"
                  f"{h['dd'] if h else float('nan'):>5.0f}%"
                  f"{f_['hpm'] if f_ else float('nan'):>+9.2f}%"
                  f"{f_['dd'] if f_ else float('nan'):>5.0f}%"
                  f"{f_['ddmax'] if f_ else float('nan'):>8.0f}%"
                  f"{lev99:>9.1f}x{levmax:>8.1f}x{flag}{dep}")

        # the ceiling, stated as a number
        safe = [fr for fr in FRACTIONS if rec[fr]["lev99"] <= LEV_CAP]
        if safe:
            top = max(safe)
            l0 = rec[blend.RISK]["lev99"] if blend.RISK in rec else float("nan")
            print(f"  gross leverage at the deployed {blend.RISK:.2f}% is {l0:.1f}x at p99,")
            print(f"  so the 10x line sits at about {blend.RISK * LEV_CAP / l0:.2f}% per unit")
            print(f"  and the largest SWEPT fraction that stays under it is {top:.2f}%.")
        best_t = max((fr for fr in FRACTIONS if rec[fr]["t"]),
                     key=lambda fr: rec[fr]["t"]["hpm"])
        best_h = max((fr for fr in FRACTIONS if rec[fr]["h"]),
                     key=lambda fr: rec[fr]["h"]["hpm"])
        print(f"  growth-optimal in the BACKTEST: tune {best_t:.2f}%, holdout {best_h:.2f}% "
              f"- ignore both if they are over the leverage line")

        print(f"  P(drawdown > 80%) over 3 years, 30-day block bootstrap:")
        for fr in (0.20, blend.RISK, 0.45, 0.90):
            if fr not in rec or not rec[fr]["curves"]:
                continue
            ps = []
            for c in rec[fr]["curves"][:5]:
                d = c.pct_change().fillna(0.0)
                ps.append(bootstrap_dd(d)["p80"])
            print(f"    {fr:>5.2f}%  {np.mean(ps):>5.1f}%"
                  + ("   (over the leverage line)" if rec[fr]["lev99"] > LEV_CAP else ""))

    print()
    print("  The question was whether risk can buy crazy returns. Read the leverage columns")
    print("  before the return columns: a fraction that breaches 10x gross is not a setting,")
    print("  it is a liquidation.")


if __name__ == "__main__":
    main()
