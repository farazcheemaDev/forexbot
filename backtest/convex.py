"""UNCAPPED WINNERS — retesting the killed families without the profit cap.

THE FLAW THIS CORRECTS, AND IT AFFECTS EVERY PRIOR VERDICT
-----------------------------------------------------------
Every strategy tested in this project closed its trade at a fixed target:

    rtest.py            tp_mult = 3.0
    mass_search.py      EXITS = [(2.0, 3.0), (1.5, 2.0), (2.0, 1.2)]

So a winner was force-closed at 1.2R to 3R and never allowed to run. For a
trend-following or momentum family that is not a detail, it is the whole result:

  * Trend following earns its living from the RARE enormous trade. Capping at 3R
    deletes precisely the trades that pay for everything else.
  * A 3R target on a 2R stop needs >40% winners merely to break even. An uncapped
    runner can win 25% of the time and still compound hard. The cap forces the
    strategy into a high-win-rate shape it was never designed for.
  * "PF 1.05, marginal" may therefore be a verdict on the EXIT RULE rather than on
    the signal.

AND THE GRADING WAS WRONG TOO
    Everything was ranked by mean R and Sharpe. Sharpe divides by TOTAL
    volatility, including upside volatility, so it actively penalises a strategy
    that makes its year on three explosive trades. That is the exact shape wanted
    here. Two symmetric-vs-skewed strategies can share a Sharpe and have very
    different compounded growth, because growth depends on E[log(1+r)], not on
    mean/sd.

    So this file reports, alongside mean R for comparability:
        median R, SKEW, max trade R, P(trade > 10R)
        compounded growth at fixed-fractional sizing
        the MONTHLY distribution and P(month > +10%)  <- the actual objective

EXITS TESTED (no fixed target anywhere)
    trail_atr   stop trails at k x ATR behind the best price reached
    trail_pct   stop trails at a fixed percentage behind the best price
    breakeven   initial stop, moved to entry after +1R, then trails
    timed       no target and no trail; exit after N bars (pure signal decay test)

HONESTY NOTES
    * Stops still win ties within a bar - we cannot see intrabar order, so the
      pessimistic assumption stands.
    * A trailing stop is checked against bar HIGH/LOW, which assumes the trail
      updated before the adverse move inside that same bar. That is mildly
      OPTIMISTIC on a bar that both extends and reverses; the alternative
      (updating only on close) is mildly pessimistic. Both are reported so the
      gap is visible rather than assumed away.
    * Fees charged round-trip. No fixed target means FEWER trades, so the fee
      drag per unit of return falls - part of any improvement will be that, not
      signal, and the trade count is printed to make it checkable.

    python -m backtest.convex
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import FILTERS, fetch, gen_signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
         "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
FEE_BP = 10.0


def run_uncapped(df: pd.DataFrame, sig: pd.Series, *, sl_mult: float = 2.0,
                 mode: str = "trail_atr", trail: float = 3.0,
                 max_bars: int = 2000, breakeven_at: float = 0.0,
                 fee_bp: float = FEE_BP, atr_period: int = 14,
                 trail_on_close: bool = False,
                 close_at_end: str | None = None):
    """R per trade with NO profit target. Same causality rules as rtest.run_r:
    entry at open[i] sized from atr[i-1]; stops beat targets on ties."""
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    a = atr_ind(df, atr_period).to_numpy(float)
    n = len(df)
    fee = fee_bp / 10000.0

    Rs, idx, bars, dirs = [], [], [], []
    pos = None
    for i in range(1, n):
        if pos is None and s[i] != Action.HOLD and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            d = 1 if s[i] == Action.BUY else -1
            e = o[i]
            risk = sl_mult * a[i - 1]
            pos = dict(d=d, e=e, risk=risk, stop=e - d * risk, best=e, bar=i,
                       be=False)
        if pos is None:
            continue
        d, e, risk = pos["d"], pos["e"], pos["risk"]
        # stop check FIRST, against this bar's extreme
        hit = (lo[i] <= pos["stop"]) if d == 1 else (h[i] >= pos["stop"])
        if hit:
            px = pos["stop"]
        elif i - pos["bar"] >= max_bars:
            px = c[i]
        else:
            # advance the trail on the favourable extreme (or close, if asked)
            ref = c[i] if trail_on_close else (h[i] if d == 1 else lo[i])
            pos["best"] = max(pos["best"], ref) if d == 1 else min(pos["best"], ref)
            gain_r = (pos["best"] - e) * d / risk
            if mode == "trail_atr":
                cand = pos["best"] - d * trail * a[i - 1]
            elif mode == "trail_pct":
                cand = pos["best"] * (1 - d * trail / 100.0)
            elif mode == "breakeven":
                cand = (pos["best"] - d * trail * a[i - 1]
                        if gain_r >= breakeven_at else pos["stop"])
                if gain_r >= breakeven_at and not pos["be"]:
                    cand = max(cand, e) if d == 1 else min(cand, e)
                    pos["be"] = True
            else:                                   # timed
                cand = pos["stop"]
            # a stop only ever ratchets toward profit
            pos["stop"] = max(pos["stop"], cand) if d == 1 else min(pos["stop"], cand)
            continue
        R = (px - e) * d / risk - (fee * e) / risk
        Rs.append(R); idx.append(i); bars.append(i - pos["bar"]); dirs.append(d)
        pos = None

    # A position still open when the data ENDS was previously dropped silently.
    # Harmless on a long backtest (one trade), but on a DELISTED coin it is the
    # single most important trade - the one where the coin died while we held it.
    # Discarding it would delete the exact catastrophe that dead-coin data exists
    # to measure, making a survivorship fix itself survivorship-biased.
    #   close_at_end="close" -> exit at the last available close. Roughly right for
    #       an ANNOUNCED delisting, where Binance gives notice and perps are
    #       force-settled near mark.
    #   close_at_end="stop"  -> exit at the stop. Right for a COLLAPSE (LUNA-style)
    #       that gaps straight through it.
    # Reporting both brackets the truth instead of assuming one.
    if pos is not None and close_at_end:
        d, e, risk = pos["d"], pos["e"], pos["risk"]
        px = c[n - 1] if close_at_end == "close" else pos["stop"]
        R = (px - e) * d / risk - (fee * e) / risk
        Rs.append(R); idx.append(n - 1); bars.append(n - 1 - pos["bar"])
        dirs.append(d)
    return (np.asarray(Rs), np.asarray(idx, dtype=int), np.asarray(bars),
            np.asarray(dirs, dtype=int))


def describe(R: np.ndarray, times: pd.Series, risk_pct: float,
             dirs: np.ndarray | None = None) -> dict | None:
    """Distribution + compounded growth + the MONTHLY objective.

    COMPOUNDING IS BY DATE, NOT BY TRADE. The first version of this function
    multiplied 23,539 pooled trades sequentially, as though 9 coins' trades had
    been taken one after another at full risk each. They overlap in time, so that
    both invented compounding that never happened and drove the curve to ruin
    (every table showed DD 100.0%, which is what made the error visible).

    Correct treatment: sum R*risk across all trades that CLOSED on the same day to
    get that day's portfolio return, then compound the daily series. Simultaneous
    trades then add, as they do in a real account.

    RUIN: once equity is <=0 the account is gone and every later percentage is
    meaningless, so compounding stops and `ruined` is set. A 'CAGR' printed past a
    wipeout is not a return, it is an artifact.
    """
    if len(R) < 30:
        return None
    f = risk_pct / 100.0
    day = pd.DatetimeIndex(times.values).normalize()
    daily = pd.Series(R * f, index=day).groupby(level=0).sum().sort_index()
    eq, curve, ruined = 1.0, [], False
    # PRACTICAL RUIN FLOOR, not mathematical zero.
    #
    # The old test (eq <= 1e-9) let a curve fall to a rounding error and then
    # compound back up, producing figures like "+12,854%/yr with a 100.0%
    # drawdown" - both true in a simulator with infinitely divisible positions,
    # and both fiction. A real account that is down 99.99% holds a few cents,
    # cannot meet any exchange minimum order, and never places another trade.
    #
    # 1% of starting equity is the floor: below that, no venue's minimum order is
    # reachable at any sane risk fraction, so the account is finished and every
    # later gain in the curve is imaginary.
    RUIN_FLOOR = 0.01
    for r in daily.to_numpy():
        if not ruined:
            eq *= (1 + r)
            if eq <= RUIN_FLOOR:
                eq, ruined = 0.0, True
        curve.append(eq)
    curve = np.asarray(curve)
    peak = np.maximum.accumulate(np.maximum(curve, 1e-12))
    dd = float((1 - curve / peak).max() * 100)
    yrs = max((times.iloc[-1] - times.iloc[0]).days / 365.25, 1e-9)
    cagr = (max(curve[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    mser = pd.Series(curve, index=daily.index)
    mo = mser.resample("30D").last().pct_change().dropna() * 100
    if ruined:                      # post-wipeout percentages are not returns
        mo = mo.iloc[:0]
    sd = R.std(ddof=1)
    lr = sr = float("nan")
    if dirs is not None and len(dirs) == len(R):
        if (dirs > 0).any():
            lr = float(R[dirs > 0].mean())
        if (dirs < 0).any():
            sr = float(R[dirs < 0].mean())
    return dict(
        n=len(R), mean=float(R.mean()), med=float(np.median(R)),
        sd=float(sd), skew=float(((R - R.mean()) ** 3).mean() / sd ** 3) if sd > 0 else 0.0,
        mx=float(R.max()), p10r=float((R > 10).mean() * 100),
        win=float((R > 0).mean() * 100),
        pf=float(R[R > 0].sum() / -R[R < 0].sum()) if (R < 0).any() else np.inf,
        cagr=float(cagr), dd=dd, mar=float(cagr / dd) if dd > 0.5 else 0.0,
        ruined=ruined, long_r=lr, short_r=sr,
        mo_med=float(mo.median()) if len(mo) else float("nan"),
        mo_over10=float((mo > 10).mean() * 100) if len(mo) else float("nan"),
        mo_best=float(mo.max()) if len(mo) else float("nan"),
        mo_worst=float(mo.min()) if len(mo) else float("nan"),
        t=float(R.mean() / (sd / np.sqrt(len(R)))) if sd > 0 else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--days", type=int, default=2400)
    ap.add_argument("--risk", type=float, default=3.0,
                    help="account %% risked per trade for the compounded columns")
    args = ap.parse_args()

    data = {}
    for cn in COINS:
        try:
            data[cn] = fetch(cn, args.tf, args.days)
        except Exception:
            continue
    print(f"UNCAPPED WINNERS   {len(data)} coins  {args.tf}  "
          f"risk {args.risk}%/trade  fee {FEE_BP}bp\n")
    print("Graded on the DISTRIBUTION, not the average. The objective is "
          "P(month > +10%).")
    print("Every prior verdict in this project used a 1.2-3R profit cap; none "
          "of these do.\n")

    # signal families worth retesting: the ones whose edge should live in the tail
    fams = [("donch", (20,)), ("donch", (50,)), ("donch", (100,)),
            ("bb_break", (30, 1.5)), ("roc_mom", (24, 0.0)),
            ("rsi_mom", (7, 40, 60)), ("ema_cross", (20, 100))]
    exits = [("capped 3R (the OLD rule)", dict(mode="timed", max_bars=10 ** 9)),
             ("trail 2xATR", dict(mode="trail_atr", trail=2.0)),
             ("trail 3xATR", dict(mode="trail_atr", trail=3.0)),
             ("trail 5xATR", dict(mode="trail_atr", trail=5.0)),
             ("trail 8xATR", dict(mode="trail_atr", trail=8.0)),
             ("BE@1R then 3xATR", dict(mode="breakeven", trail=3.0,
                                       breakeven_at=1.0))]

    print("=" * 126)
    print(f"{'family':<18} {'exit':<22} {'n':>5} {'win%':>5} {'meanR':>7} "
          f"{'skew':>6} {'maxR':>7} {'PF':>5} {'t':>6} {'longR':>7} "
          f"{'shortR':>7} {'CAGR':>8} {'DD':>6} {'mo>10%':>7}")
    rows = []
    for fam, p in fams:
        for tag, ex in exits:
            allR, allT, allD = [], [], []
            for cn, df in data.items():
                sig = gen_signals(df, fam, p)
                if sig is None:
                    continue
                if tag.startswith("capped"):
                    from backtest.rtest import run_r
                    R, idx = run_r(df, sig, sl_mult=2.0, tp_mult=3.0,
                                   fee_bp=FEE_BP)
                    dd_ = np.zeros(len(R), dtype=int)
                else:
                    R, idx, _b, dd_ = run_uncapped(df, sig, sl_mult=2.0,
                                                   fee_bp=FEE_BP, **ex)
                if len(R):
                    allR.append(R)
                    allT.append(df["time"].iloc[idx])
                    allD.append(dd_)
            if not allR:
                continue
            # sort trades into true chronological order before anything
            # date-dependent touches them
            order = np.argsort(np.concatenate([t.values for t in allT]))
            R = np.concatenate(allR)[order]
            D = np.concatenate(allD)[order]
            T = pd.Series(np.concatenate([t.values for t in allT])[order])
            d = describe(R, T, args.risk, dirs=(D if D.any() else None))
            if not d:
                continue
            rows.append((d["mo_over10"], d["cagr"], fam, str(p), tag, d))
            ruin = " RUIN" if d["ruined"] else ""
            print(f"{fam+str(p):<18} {tag:<22} {d['n']:>5} {d['win']:>5.1f} "
                  f"{d['mean']:>+7.3f} {d['skew']:>+6.2f} {d['mx']:>7.1f} "
                  f"{d['pf']:>5.2f} {d['t']:>+6.2f} {d['long_r']:>+7.3f} "
                  f"{d['short_r']:>+7.3f} {d['cagr']:>+7.1f}% {d['dd']:>5.1f}%"
                  f"{d['mo_over10']:>7.1f}%{ruin}", flush=True)

    if not rows:
        return
    print("\n" + "=" * 118)
    print("RANKED BY THE ACTUAL OBJECTIVE: share of 30-day blocks above +10%")
    print("=" * 118)
    rows.sort(reverse=True)
    for mo10, cagr, fam, p, tag, d in rows[:12]:
        print(f"{fam+p:<18} {tag:<22} mo>10% {mo10:>5.1f}%  median mo "
              f"{d['mo_med']:>+6.2f}%  CAGR {cagr:>+7.1f}%  DD {d['dd']:>5.1f}%  "
              f"skew {d['skew']:>+5.2f}  t {d['t']:>+5.2f}")
    print(f"\nsearched {len(rows)} family x exit cells — a best-of-{len(rows)} "
          f"figure, so judge the PATTERN across exits, not the top line.")
    print("KEY COMPARISON: does any uncapped exit beat 'capped 3R' for the SAME "
          "family?\nIf capping was the problem, that should hold broadly, not "
          "in one lucky cell.")


if __name__ == "__main__":
    main()
