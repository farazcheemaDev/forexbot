"""LOOKING FOR THE BUG IN THE FUNDING-CARRY RESULT (bear_chop.py test 6).

bear_chop.test_carry printed +0.641%/wk net (~+39%/yr) for a weekly market-neutral book that
shorts the PIT top-60 decile with the highest 7-day funding and longs the lowest - with the
tune half +0.46 and the holdout +1.04%/wk, positive in 6 of 7 years, and +1.03%/wk in BEAR
regimes, five times the momentum book there. funding_xs.py had found 18 of 18 cells negative
on a narrow universe at 8-72h holds. Every large improvement in this repo was a bug until
proven otherwise, so this file tries to break it before anything is claimed.

CHECKS, and what each would reveal
  A. EXACT SETTLEMENT WINDOW. Daily funding sums cannot say whether the 00:00 settlement at the
     entry instant was earned. Rebuild funding from the raw settlements, binned (d, d+1] so
     the book earns only settlements strictly after entry and up to and including exit.
  B. RANK A DAY EARLIER (lag 1). If the edge lives in the freshest settlement, it is fragile.
  C. WINSORIZE funding at +-0.5% per settlement before BOTH ranking and crediting. If a
     handful of capped-out squeezes make the number, it vanishes.
  D. COSTS x3 (36bp round trip): the extreme-funding names are the thin ones.
  E. EACH LEG ALONE: is the money in shorting crowded longs or in longing crowded shorts?
  F. MIN AGE 180 days instead of 30: is it just fresh listings?
  G. RISK: weekly compounded equity, worst week, max drawdown, correlation with the momentum
     book (doc 10) - a carry book that is secretly momentum adds nothing.

REGISTERED PREDICTION (2026-09-24, before running): A and B each cost ~0.1%/wk; C cuts the
result by half or more (squeeze weeks carry it); D leaves it positive; the SHORT leg carries
most of the carry and most of the price loss; worst week worse than -10%. If C kills it, it
is a tail-harvest, not a book.

    python -m backtest.carry_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import bear_chop as bc  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import DATA, eligibility  # noqa: E402


def exact_funding(index, cols, clip=None):
    """Daily funding where row d = settlements in (d 00:00, d+1 00:00], so a book entered at
    close i (00:00 of day i+1) and exited at close i+hold earns rows i+1..i+hold exactly:
    nothing at its entry instant, the settlement at its exit instant included."""
    out = {}
    for s in cols:
        p = DATA / f"{s}_funding.csv.gz"
        if not p.exists():
            continue
        try:
            f = pd.read_csv(p)
        except Exception:
            continue
        if f.empty:
            continue
        t = pd.to_datetime(f["time"]).dt.round("min").astype("datetime64[ns]")
        r = f["rate"].astype(float)
        if clip is not None:
            r = r.clip(-clip, clip)
        ser = pd.Series(r.to_numpy(), index=t)
        ser = ser[~ser.index.duplicated()]
        out[s] = ser.resample("D", closed="right", label="left").sum()
    return pd.DataFrame(out).reindex(index).reindex(columns=cols).fillna(0.0)


def weekly_stats(d):
    x = d.net.to_numpy()
    eq = np.cumprod(1 + x)
    dd = (1 - eq / np.maximum.accumulate(eq)).max() * 100
    sh = x.mean() / x.std(ddof=1) * np.sqrt(52)
    return dd, x.min() * 100, sh


def show(lab, d):
    pw = lambda x, c="net": x[c].mean() * 100 if len(x) else np.nan  # noqa: E731
    dd, worst, sh = weekly_stats(d)
    print(f"  {lab:<40}{pw(d):>+7.3f}%{pw(d, 'gross'):>+7.3f}%{pw(d, 'carry'):>+7.3f}%"
          f"{pw(d[d.half == 'tune']):>+7.3f}%{pw(d[d.half == 'hold']):>+7.3f}%"
          + "".join(f"{pw(d[d.regime == r]):>+7.3f}%" for r in bc.REGS)
          + f"{sh:>6.2f}{dd:>5.0f}%{worst:>+7.1f}%")


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    reg = btc_regime(C)
    elig = drop_non_crypto(eligibility(60))
    Fx = exact_funding(C.index, C.columns)
    Fc = exact_funding(C.index, C.columns, clip=0.005)
    print("weekly market-neutral funding carry, PIT top-60, short the highest 7-day funding decile, long the lowest")
    print(f"  {'variant':<40}{'net':>8}{'gross':>8}{'carry':>8}{'TUNE':>8}{'HOLD':>8}"
          f"{'bull':>8}{'bear':>8}{'chop':>8}{'Shrp':>6}{'DD':>6}{'worst':>8}   (%/week)")

    def carry(Fr, Fp, win=7, lag=0, fshift=1, fee=None, min_age=None):
        score = -Fr.rolling(win, min_periods=win).sum().to_numpy()
        old_fee, old_age = bc.FEE, bc.MIN_AGE_D
        try:
            if fee is not None:
                bc.FEE = fee
            if min_age is not None:
                bc.MIN_AGE_D = min_age
            return bc.tag(bc.fast_run(C, Fp, first, elig, look=1, hold=7, lag=lag,
                                      score=score, fshift=fshift), reg)
        finally:
            bc.FEE, bc.MIN_AGE_D = old_fee, old_age

    base = carry(F, F)
    show("as printed by bear_chop test 6", base)
    a = carry(Fx, Fx)
    show("A. exact settlement window", a)
    show("B. A + ranked a day earlier", carry(Fx, Fx, lag=1))
    show("C. A + funding clipped at +-0.5%/settle", carry(Fc, Fc))
    show("C'. rank on clipped, earn the real rate", carry(Fc, Fx))
    show("D. A + costs x3 (36bp round trip)", carry(Fx, Fx, fee=36.0 / 1e4))
    show("F. A + min age 180 days", carry(Fx, Fx, min_age=180))
    show("   A with a 3-day funding rank", carry(Fx, Fx, win=3))
    show("   A with a 30-day funding rank", carry(Fx, Fx, win=30))

    # E. legs: the book is half long / half short; show each half's own return
    print("\n  E. each leg of A, as a return on the WHOLE account (each leg is half of it), %/week")
    a = a.copy()
    print(f"  {'':<14}{'all':>8}" + "".join(f"{r:>8}" for r in bc.REGS))
    # long_ret / short_ret are the legs' mean PRICE returns; the carry split needs the legs' own
    # funding, which fast_run does not return - so re-derive it: carry = 0.5*(-lf) + 0.5*sf
    for lab, col in (("long leg px", "long_ret"), ("short leg px", "short_ret")):
        sgn = 0.5 if col == "long_ret" else -0.5
        vals = [a[col].mean() * sgn * 100] + [a[a.regime == r][col].mean() * sgn * 100 for r in bc.REGS]
        print(f"  {lab:<14}" + "".join(f"{v:>+7.3f}%" for v in vals))

    # G. correlation with the momentum book, weekly, both on the exact window
    m = bc.tag(bc.fast_run(C, Fx, first, elig, look=30, hold=7, fshift=1), reg)
    show("\n  reference: 30d MOMENTUM, exact window", m)
    # the two books rebalance on different weekdays (look=1 vs look=30 start the 7-day grid on
    # different days), so align them on calendar weeks rather than on identical timestamps
    wk = lambda d: d.set_index("t").net.resample("W").sum()  # noqa: E731
    j = pd.DataFrame({"net_carry": wk(a), "net_mom": wk(m)}).dropna()
    j = j[(j.net_carry != 0) & (j.net_mom != 0)]
    print(f"\n  G. weekly correlation, carry vs momentum: {j.net_carry.corr(j.net_mom):+.2f} over {len(j)} weeks")
    both = (j.net_carry + j.net_mom) / 2
    x = both.to_numpy()
    eq = np.cumprod(1 + x)
    print(f"     50/50 of the two: {x.mean()*100:+.3f}%/wk, Sharpe {x.mean()/x.std(ddof=1)*np.sqrt(52):.2f}, "
          f"DD {(1 - eq/np.maximum.accumulate(eq)).max()*100:.0f}%, worst week {x.min()*100:+.1f}%")
    print("     by year, carry (A) %/wk: " + "  ".join(
        f"{y}: {a[a.t.dt.year == y].net.mean()*100:+.2f}" for y in sorted(a.t.dt.year.unique())))
    worst = a.nsmallest(5, "net")[["t", "net", "gross", "carry", "regime"]].copy()
    # the biggest mover among ALL coins over that hold - the squeeze a short leg would have met
    movers = []
    for t in worst.t:
        i = C.index.get_loc(t)
        w = (C.iloc[min(i + 7, len(C) - 1)] / C.iloc[i] - 1).dropna()
        movers.append(f"{w.idxmax()} {w.max()*100:+.0f}%")
    worst["biggest mover that week"] = movers
    worst[["net", "gross", "carry"]] *= 100
    print("\n  the five worst weeks of A (%):\n" + worst.to_string(index=False, float_format=lambda v: f"{v:+.2f}"))


if __name__ == "__main__":
    main()
