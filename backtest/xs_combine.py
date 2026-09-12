"""SLEEVE BLENDING — where extra return actually comes from.

THE ARITHMETIC, STATED FIRST SO THE OUTPUT CAN BE READ HONESTLY
---------------------------------------------------------------
Combining strategies does not stack returns. It raises SHARPE, and Sharpe is what
buys leverage at a fixed drawdown tolerance. For N sleeves of equal Sharpe S and
average pairwise correlation rho:

    blended Sharpe  =  S * sqrt( N / (1 + (N-1) * rho) )

    N=4, rho=0.6  -> 1.20 x S        diversification mostly already spent
    N=4, rho=0.3  -> 1.45 x S
    N=2, rho=0.0  -> 1.41 x S
    N=2, rho=-0.3 -> 1.69 x S        negative correlation is the real prize

So the question is never "is this sleeve good", it is "is this sleeve good AND
different". A sleeve with half the Sharpe and zero correlation can beat a sleeve
with equal Sharpe and 0.8 correlation.

WHY VSA IS NOT IN HERE
    VSA passed MCPT (p=0.0099) but FAILED the cross-asset gate (16/28), and its
    pre-registered forward test is at n=2 closed trades. Its edge is unestablished.
    Blending an unestablished sleeve into a book that cleared p=0.0033 spends real
    fees and variance for an unknown return. It gets added if and when its own
    forward test clears - not before. Same rule for anything else unvalidated.

WEIGHTING IS EQUAL-RISK, DELIBERATELY NOT OPTIMISED
    Mean-variance optimal weights are the single most overfit object in finance:
    they load on whichever sleeve got luckiest in-sample and on the least stable
    entries of the covariance matrix. Inverse-vol (equal risk contribution) uses
    only volatilities, which estimate far more reliably than means or
    correlations. The blend is therefore chosen by RULE, not fitted.

DISCIPLINE
    * DEV WINDOW ONLY. The 500-day holdout is spent (2 looks, see the
      contamination ledger). Nothing here may be validated on it. A blend that
      looks good here goes to xs_paper.py for a forward test on data that did not
      exist yet, which is the only honest test left.
    * Every sleeve carries full taker fees on its own turnover. Blending does NOT
      net turnover between sleeves - two sleeves wanting opposite sides of the
      same coin both pay, unless netted explicitly, which is reported separately.
    * Sleeve count is reported next to every Sharpe, because picking the best
      blend out of many is itself a search.

    python -m backtest.xs_combine
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.xs_momentum import (HOLDOUT_DAYS, LONG_UNIVERSE,  # noqa: E402
                                  TAKER_BP, build_panel, simulate)

ANN = np.sqrt(24 * 365.25)

# Sleeves, declared up front. Momentum horizons span 1 day to 1 month; reversal
# horizons are short because that is where the bounce lives.
SLEEVES = {
    "mom_24h":    dict(lb=24,  hold=24, k=5, invvol=False),
    "mom_48h":    dict(lb=48,  hold=24, k=5, invvol=False),
    "mom_96h":    dict(lb=96,  hold=24, k=5, invvol=False),
    "mom_168h":   dict(lb=168, hold=24, k=5, invvol=False),
    "mom_336h":   dict(lb=336, hold=24, k=5, invvol=False),
    "mom_720h":   dict(lb=720, hold=24, k=5, invvol=False),
    "momsh_168h": dict(lb=168, hold=24, k=5, invvol=False, rank_by="sharpe"),
    "momsh_336h": dict(lb=336, hold=24, k=5, invvol=False, rank_by="sharpe"),
    "rev_6h":     dict(lb=6,   hold=6,  k=5, invvol=False, reverse=True),
    "rev_12h":    dict(lb=12,  hold=12, k=5, invvol=False, reverse=True),
    "rev_24h":    dict(lb=24,  hold=24, k=5, invvol=False, reverse=True),
    "rev_48h":    dict(lb=48,  hold=24, k=5, invvol=False, reverse=True),
    "idxh_168h":  dict(lb=168, hold=24, k=5, invvol=False, hedge_index=True),
    "disp_168h":  dict(lb=168, hold=24, k=5, invvol=False, disp_min=0.50),
}


def stats(r: pd.Series) -> dict:
    live = r != 0
    x = r[live]
    if len(x) < 50 or x.std(ddof=1) == 0:
        return dict(sharpe=0.0, cagr=0.0, dd=0.0, t=0.0, n=len(x))
    eq = (1 + r).cumprod()
    yrs = len(r) / (24 * 365.25)
    return dict(
        sharpe=float(x.mean() / x.std(ddof=1) * ANN),
        cagr=float((eq.iloc[-1] ** (1 / yrs) - 1) * 100) if yrs > 0 else 0.0,
        dd=float((1 - eq / eq.cummax()).max() * 100),
        t=float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))),
        n=int(len(x)))


def blend(rets: dict[str, pd.Series], names: list[str],
          vol_lb: int = 24 * 30) -> pd.Series:
    """Equal-risk blend: each sleeve scaled by its own TRAILING vol, shifted so a
    bar's weight never uses that bar's own volatility. Gross is renormalised to
    1.0 so the blend is comparable with a single sleeve and not secretly levered.
    """
    R = pd.DataFrame({n: rets[n] for n in names}).fillna(0.0)
    iv = 1.0 / R.rolling(vol_lb, min_periods=24 * 7).std().shift(1)
    iv = iv.replace([np.inf, -np.inf], np.nan)
    w = iv.div(iv.sum(axis=1), axis=0).fillna(0.0)
    return (R * w).sum(axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fee", type=float, default=TAKER_BP)
    ap.add_argument("--days", type=int, default=2400)
    args = ap.parse_args()

    O, C, F = build_panel(args.days, LONG_UNIVERSE)
    cut = O.index[-1] - pd.Timedelta(days=HOLDOUT_DAYS)
    Od, Cd, Fd = O.loc[:cut], C.loc[:cut], F.loc[:cut]
    print(f"SLEEVE BLENDING   {len(C.columns)} coins   DEV ONLY "
          f"{Cd.index[0]:%Y-%m-%d}..{cut:%Y-%m-%d} ({len(Cd):,} bars)")
    print(f"  holdout is SPENT - nothing here is validated, only generated")
    print(f"  {len(SLEEVES)} sleeves, equal-risk blending, {args.fee}bp/side\n")

    rets: dict[str, pd.Series] = {}
    print("=" * 88)
    print("INDIVIDUAL SLEEVES (dev)")
    print("=" * 88)
    print(f"{'sleeve':<12} {'CAGR':>8} {'DD':>7} {'Sharpe':>8} {'t':>7} "
          f"{'MAR':>6} {'fee/y':>6} {'beta':>6}")
    for name, cfg in SLEEVES.items():
        full = dict(er_min=0.0, **cfg)
        s = simulate(Od, Cd, Fd, fee_bp=args.fee, **full)
        rets[name] = s["net"]
        st = stats(s["net"])
        print(f"{name:<12} {st['cagr']:>+7.1f}% {st['dd']:>6.1f}% "
              f"{st['sharpe']:>+8.2f} {st['t']:>+7.2f} "
              f"{st['cagr']/st['dd'] if st['dd']>0.5 else 0:>+6.2f} "
              f"{s['fee_yr']:>6.1f} {s['beta']:>+6.2f}", flush=True)

    # ---- correlation: the number that decides whether blending helps ---------
    R = pd.DataFrame(rets).fillna(0.0)
    daily = R.resample("24h").sum()          # daily, so hold periods line up
    Cm = daily.corr()
    print("\n" + "=" * 88)
    print("SLEEVE CORRELATION (daily returns) — the thing that decides everything")
    print("=" * 88)
    names = list(SLEEVES)
    print("             " + " ".join(f"{n[:7]:>7}" for n in names))
    for a in names:
        print(f"{a:<12} " + " ".join(f"{Cm.loc[a,b]:>+7.2f}" for b in names))

    pos = [n for n in names if stats(rets[n])["sharpe"] > 0]
    print(f"\npositive-Sharpe sleeves: {len(pos)}/{len(names)}")
    if len(pos) >= 2:
        sub = Cm.loc[pos, pos].to_numpy()
        off = sub[~np.eye(len(pos), dtype=bool)]
        print(f"mean pairwise correlation among them: {off.mean():+.3f}  "
              f"(min {off.min():+.2f}, max {off.max():+.2f})")
        print(f"  -> theoretical blend multiplier sqrt(N/(1+(N-1)r)) = "
              f"{np.sqrt(len(pos)/(1+(len(pos)-1)*off.mean())):.2f}x")

    # ---- blends, by RULE not by fitting -------------------------------------
    print("\n" + "=" * 88)
    print("BLENDS (equal-risk, gross renormalised to 1.0 — not levered)")
    print("=" * 88)
    print(f"{'blend':<34} {'n':>3} {'CAGR':>8} {'DD':>7} {'Sharpe':>8} {'t':>7} {'MAR':>6}")

    def show(tag, names_):
        names_ = [n for n in names_ if n in rets]
        if len(names_) < 2:
            return None
        b = blend(rets, names_)
        st = stats(b)
        print(f"{tag:<34} {len(names_):>3} {st['cagr']:>+7.1f}% {st['dd']:>6.1f}% "
              f"{st['sharpe']:>+8.2f} {st['t']:>+7.2f} "
              f"{st['cagr']/st['dd'] if st['dd']>0.5 else 0:>+6.2f}")
        return st

    base = stats(rets["mom_168h"])
    print(f"{'[single] mom_168h (reference)':<34} {1:>3} {base['cagr']:>+7.1f}% "
          f"{base['dd']:>6.1f}% {base['sharpe']:>+8.2f} {base['t']:>+7.2f} "
          f"{base['cagr']/base['dd'] if base['dd']>0.5 else 0:>+6.2f}")
    mom_all = [n for n in names if n.startswith("mom_")]
    rev_all = [n for n in names if n.startswith("rev_")]
    show("momentum horizons only", mom_all)
    show("reversal horizons only", rev_all)
    show("momentum + reversal", mom_all + rev_all)
    show("all positive-Sharpe sleeves", pos)
    show("mom_168h + best reversal",
         ["mom_168h", max(rev_all, key=lambda n: stats(rets[n])["sharpe"])])
    show("mom 96/168/336 + rev 12/24",
         ["mom_96h", "mom_168h", "mom_336h", "rev_12h", "rev_24h"])
    show("everything", names)

    # ---- the pair that helps most, and whether it is a correlation story -----
    print("\n" + "=" * 88)
    print("BEST PAIRS by blended Sharpe (both sleeves must be individually positive)")
    print("=" * 88)
    print(f"{'pair':<28} {'corr':>7} {'S_a':>6} {'S_b':>6} {'blend':>7} {'gain':>7}")
    rows = []
    for a, b in itertools.combinations(pos, 2):
        sa, sb = stats(rets[a])["sharpe"], stats(rets[b])["sharpe"]
        bl = stats(blend(rets, [a, b]))["sharpe"]
        rows.append((bl, a, b, Cm.loc[a, b], sa, sb))
    rows.sort(reverse=True)
    for bl, a, b, c, sa, sb in rows[:12]:
        print(f"{a+'+'+b:<28} {c:>+7.2f} {sa:>+6.2f} {sb:>+6.2f} {bl:>+7.2f} "
              f"{bl/max(sa,sb):>+7.2f}x")

    print("\nNOTE: 'gain' is vs the BETTER of the two sleeves. A gain below ~1.1x "
          "means\nthe pair is too correlated to be worth the extra fees and "
          "complexity.")
    print("NOTE: these blends were SELECTED on dev. Any of them that looks good "
          "must be\nforward-tested - the holdout cannot judge it.")


if __name__ == "__main__":
    main()
