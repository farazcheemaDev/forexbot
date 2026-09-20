"""DO SHORTS EARN IN BEAR REGIMES? — and is the regime gate pointed the wrong way?

    python -m backtest.bear_side

THE OBSERVATION THAT PROMPTED THIS
    The deployed config applies ONE regime multiplier to BOTH sides: while BTC is below
    its 1000-hour average, every trade is quarter-sized, long and short alike.

        f = f0
        if bool(bear.asof(a_)):
            f *= regime          # 0.25, applied to longs AND shorts

    That is symmetric, and there is no reason it should be. A bear regime is exactly
    when a short ought to work and a long ought not. If shorts earn in bears and lose in
    bulls, the gate is throwing away the short side's only good weather and the fix is
    one line.

    docs/02 records that 19 of 19 indicator families found a long edge and none found a
    short edge, and that shorts only became usable once exits were tuned per direction -
    landing at -0.036R per trade, a drawdown hedge rather than a profit source. But that
    is a figure averaged across ALL regimes. Nobody has split it.

WHAT IS MEASURED
    1. Mean R by SIDE x REGIME, which is the whole question in one table. Sleeves are
       rebuilt with the side kept as a tag - blend.sleeve() discards it, which is why
       this split has never been available.
    2. Then asymmetric gates. Each variant is a (long, short) pair of multipliers for
       bear regimes, with bull regimes left at (1.0, 1.0):

         current      (0.25, 0.25)   what is deployed
         free_short   (0.25, 1.00)   stop punishing shorts in their own weather
         lean_short   (0.25, 2.00)   actively lean short in a bear
         flat_long    (0.00, 1.00)   no longs at all in a bear
         all_in_bear  (1.00, 1.00)   no gate - the control that shows what the gate buys

    Regime is `blend.btc_bear()`: BTC's last CLOSED hourly bar below its trailing
    1000-hour mean, shifted, so the decision at a trade's open uses only prior bars.

THE TRAP THIS COULD FALL INTO
    Bear regimes are a minority of the sample and they cluster - 2022 is one long bear.
    So a "shorts earn in bears" result could be one year's crash, not a repeatable
    property. Every cell is therefore reported per-year as well as pooled, and the
    tune/holdout split is by date. A variant that only wins in 2022 is reported as a
    variant that only wins in 2022.

REGISTERED PREDICTION (2026-09-20, before running)
    Shorts will be positive in bear regimes and negative in bull regimes, because that
    is nearly tautological for a trend-following short - the question is the SIZE. I
    expect the split to be modest, something like +0.2R in bears against -0.3R in bulls,
    not the +2R that would make a short book worth running on its own.

    On the variants: free_short should beat current slightly. lean_short probably not -
    doubling into a regime that is a minority of the sample adds variance faster than
    return. flat_long will cut drawdown and cost return, like every other protection
    tested this week. And all_in_bear will be WORSE than current, which is the check
    that the existing gate is doing something real.

    If shorts in bears come back strongly positive, the honest read is still to look at
    2022 alone before believing it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.convex import run_uncapped  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import MIN_ORDER, resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

RULES, SLOTS = ["1h", "4h", "12h"], 12
VARIANTS = {"current      (0.25L, 0.25S)": (0.25, 0.25),
            "free_short   (0.25L, 1.00S)": (0.25, 1.00),
            "lean_short   (0.25L, 2.00S)": (0.25, 2.00),
            "flat_long    (0.00L, 1.00S)": (0.00, 1.00),
            "all_in_bear  (1.00L, 1.00S)": (1.00, 1.00)}
_S: dict = {}


def sleeve_sided(rule):
    """blend.sleeve, but the SIDE is kept. blend.sleeve drops it, which is why the
    side x regime split below has never been available."""
    if rule in _S:
        return _S[rule]
    tr, stops = [], {}
    for c in blend.BOOK:
        d = blend.load(c)
        if d is None:
            continue
        df = resample(d, rule)
        if len(df) < 300:
            continue
        a = (atr_ind(df, 14) / df["close"]).replace([np.inf, -np.inf],
                                                    np.nan).dropna()
        if len(a):
            stops[c] = float(a.median()) * blend.SL_MULT
        t = df["time"].to_numpy()
        R, idx, _u, held = run_pyramid(df, signals(df, "long", "all"),
                                       sl_mult=blend.SL_MULT, trail=blend.LONG_TRAIL,
                                       max_units=blend.MAX_UNITS,
                                       add_every=blend.ADD_EVERY,
                                       fee_bp=blend.FEE_BP, breakeven_at=blend.BE_AT)
        tr += [(t[max(int(i) - int(h), 0)], t[int(i)], float(r), rule, c, "long")
               for r, i, h in zip(R, idx, held)]
        R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"),
                                        sl_mult=blend.SL_MULT, fee_bp=blend.FEE_BP,
                                        mode="trail_atr", trail=blend.SHORT_TRAIL,
                                        be_at=blend.BE_AT)
        tr += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r), rule, c, "short")
               for r, i, b in zip(R, idx, bars)]
    _S[rule] = (tr, stops)
    return _S[rule]


def all_trades():
    tr, stops = [], {}
    for r in RULES:
        a, s = sleeve_sided(r)
        tr += a
        for k, v in s.items():
            stops[k] = max(stops.get(k, 0.0), v)
    tr.sort(key=lambda x: x[0])
    return tr, stops


def run(tr, stops, mults, t_from=None, t_to=None):
    """The blend allocator with SEPARATE bear multipliers for longs and shorts."""
    bear = blend.btc_bear()
    lm, sm = mults
    f0 = blend.RISK / 100.0
    eq, curve, times, opens = 1.0, [], [], []
    Rs = []
    for a_, b_, r, _rule, _c, side in tr:
        if t_from is not None and a_ < t_from:
            continue
        if t_to is not None and a_ >= t_to:
            continue
        opens = [u for u in opens if u > a_]
        if len(opens) >= SLOTS:
            continue
        try:
            is_bear = bool(bear.asof(a_))
        except Exception:
            is_bear = False
        f = f0 * ((lm if side == "long" else sm) if is_bear else 1.0)
        if f <= 0:
            continue                      # not taken at all, so it frees no slot
        opens.append(b_)
        Rs.append(r)
        eq *= (1 + r * f)
        if eq <= 0.01:
            eq = 0.0
        curve.append(eq)
        times.append(b_)
    if len(Rs) < 30:
        return None
    cur = np.asarray(curve)
    ts = pd.DatetimeIndex(times)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100
    hc = cagr / blend.HINDSIGHT
    floor = max(MIN_ORDER[c] * stops[c] for c in stops if c in MIN_ORDER) / f0
    return dict(n=len(Rs), dd=dd, meanR=float(np.mean(Rs)),
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100,
                floor=floor / (1 - dd / 100) if dd < 99 else float("nan"),
                R=np.asarray(Rs), times=ts)


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: shorts positive in bears and negative in bulls, but modest")
    print("(~+0.2R vs -0.3R, not +2R). free_short beats current slightly; lean_short")
    print("does not; flat_long cuts drawdown and costs return; all_in_bear is WORSE,")
    print("which is the check that the existing gate does something.\n")

    tr, stops = all_trades()
    bear = blend.btc_bear()
    rows = []
    for a_, _b, r, rule, c, side in tr:
        try:
            ib = bool(bear.asof(a_))
        except Exception:
            ib = False
        rows.append((pd.Timestamp(a_), r, side, "bear" if ib else "bull", rule))
    T = pd.DataFrame(rows, columns=["t", "R", "side", "regime", "rule"])
    print(f"  {len(T):,} sleeve trades across {len(RULES)} timeframes, "
          f"{T.t.min():%Y-%m-%d} .. {T.t.max():%Y-%m-%d}")
    print(f"  {100*(T.regime=='bear').mean():.0f}% of trades open in a BEAR regime\n")

    print("=" * 92)
    print("1. THE TABLE THAT ANSWERS THE QUESTION — mean R by side and regime")
    print("=" * 92)
    print(f"  {'':<8}{'n':>8}{'mean R':>10}{'win%':>8}{'total R':>11}   (all trades, "
          f"before the slot cap)")
    for side in ("long", "short"):
        for reg in ("bull", "bear"):
            g = T[(T.side == side) & (T.regime == reg)]
            if not len(g):
                continue
            print(f"  {side+' '+reg:<8}{len(g):>8}{g.R.mean():>+10.3f}"
                  f"{100*(g.R>0).mean():>7.0f}%{g.R.sum():>+11.0f}")
    sb = T[(T.side == "short") & (T.regime == "bear")]
    su = T[(T.side == "short") & (T.regime == "bull")]
    print(f"\n  SHORTS: {sb.R.mean():+.3f}R in bears vs {su.R.mean():+.3f}R in bulls"
          f"   difference {sb.R.mean()-su.R.mean():+.3f}R")

    print("\n" + "=" * 92)
    print("2. IS IT ONE YEAR? — short-in-bear mean R by year")
    print("=" * 92)
    print(f"  {'year':<8}{'n':>7}{'mean R':>10}{'total R':>11}")
    for y, g in sb.groupby(sb.t.dt.year):
        print(f"  {y:<8}{len(g):>7}{g.R.mean():>+10.3f}{g.R.sum():>+11.0f}")
    print("  A result living in one year is a result about that year.")

    print("\n" + "=" * 92)
    print("3. ASYMMETRIC GATES — tune on the first 60% by date, decide on the last 40%")
    print("=" * 92)
    ts_all = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts_all[int(len(ts_all) * 0.6)]
    print(f"  split at {cut.date()}\n")
    print(f"  {'variant':<28}| {'TUNE /mo':>9}{'DD':>7}{'floor':>7}{'n':>6} | "
          f"{'HOLD /mo':>9}{'DD':>7}{'floor':>7}{'n':>6}")
    res = {}
    for lab, m in VARIANTS.items():
        a = run(tr, stops, m, t_to=cut)
        b = run(tr, stops, m, t_from=cut)
        if not (a and b):
            print(f"  {lab:<28}  too few trades")
            continue
        res[lab] = (a, b)
        print(f"  {lab:<28}|{a['hpm']:>+9.2f}%{a['dd']:>6.1f}%{a['floor']:>7.0f}"
              f"{a['n']:>6} |{b['hpm']:>+9.2f}%{b['dd']:>6.1f}%{b['floor']:>7.0f}"
              f"{b['n']:>6}")

    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92)
    base = res.get("current      (0.25L, 0.25S)")
    if not base:
        print("  no baseline to compare against")
        return
    bt, bh = base
    winners = []
    for lab, (a, b) in res.items():
        if lab.startswith("current"):
            continue
        better = (b["hpm"] > bh["hpm"] and b["dd"] <= bh["dd"] * 1.02
                  and a["hpm"] > bt["hpm"])
        if better:
            winners.append(lab)
    if winners:
        print(f"  BEATS THE DEPLOYED GATE on the holdout: {', '.join(winners)}")
        print("  Before shipping: check section 2. If short-in-bear R lives in 2022,")
        print("  this is a bet that the next bear looks like that one.")
    else:
        print("  Nothing beats the symmetric gate on both halves. The short side does")
        print("  not earn enough in bear regimes to be worth leaning into, and the")
        print("  existing 0.25 multiplier on both sides stands.")


if __name__ == "__main__":
    main()
