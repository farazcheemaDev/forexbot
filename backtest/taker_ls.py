"""CROSS-SECTIONAL LONG/SHORT ON TAKER FLOW — is the spread a trade?

    python -m backtest.taker_ls

WHAT backtest/positioning.py ESTABLISHED
    Aggressive taker buying predicts 4-hour continuation. Top-minus-bottom quintile,
    within-coin trailing ranks, significance across coins: -0.094% in tune and
    -0.142% in holdout (sign inverted because the feature was declared as exhaustion),
    10 of 11 coins agreeing both times, Holm p=0.002.

    A quintile spread is not a trade. This turns it into one and charges it properly.

THE THREE THINGS THAT COULD KILL IT, AND HOW EACH IS HANDLED
    1. COSTS WERE UNDERCHARGED IN THE QUINTILE TEST. That test subtracted 12bp once
       from a spread that has TWO legs. A real long/short pays a fee on every leg it
       turns over. Here the cost is `sum_i |w_i,t - w_i,t-1| x one_way_fee`, so it is
       charged on measured TURNOVER, not assumed. If the taker rank is persistent the
       turnover is far below 100% per period; if it is not, fees eat the edge. That is
       an empirical question and the turnover column answers it.
    2. THE RANKING IS A DIFFERENT CONSTRUCTION. positioning.py ranked each coin
       against its own trailing 90 days. A long/short book ranks coins against EACH
       OTHER at the same instant. That is the natural form for this trade and it is
       genuinely a re-test, not a replay - a within-coin effect need not survive
       cross-sectionally.
    3. FEES DECIDE THE SIGN HERE, UNLIKE THE BLEND. backtest/fee_sweep.py found the
       deployed blend almost fee-insensitive, because its average trade is +1.374R
       against ~0.02R of fees. This strategy is the opposite: the gross edge is ~0.2%
       per period, so a fee ladder is run and the rows are expected to disagree.

WHY THE CAPITAL FLOOR MAY BE THE GOOD NEWS
    Every floor in this project came from `min_order x stop_fraction / risk`, where the
    stop fraction is 8-15% and the risk fraction 0.30% - a ~40x amplifier. This book
    has NO STOP. Position size is a fraction of equity directly, so the floor is just
    the sum of the minimum orders across open positions. That should be tens of
    dollars, not hundreds.

AND THE QUESTION THAT MATTERS MORE THAN ITS SHARPE
    The deployed blend is a directional, long-biased trend book on 12 correlated alts -
    ~1.5 independent bets, which is its measured ceiling. This is market-neutral, at a
    4-hour horizon, driven by flow rather than price. If their monthly returns are
    uncorrelated, the pair is worth more than either alone, and the diversification is
    worth more than any improvement we found to the blend itself all week.
    Correlation is computed on CALENDAR months ("ME"), because a 30-day resample
    anchors bins to each series' own first timestamp and produced a NaN correlation
    matrix once already in this repo.

REGISTERED PREDICTION (2026-09-20, before running)
    Turnover will be high - taker flow is a fast variable - and at 12bp round trip the
    net will be at or below zero, with the 3bp row positive. The cross-sectional
    ranking will be weaker than the within-coin version. And the correlation with the
    blend will be LOW, under 0.2, because one book is long-only trend on daily
    horizons and the other is market-neutral flow on 4-hour horizons. If the net is
    positive at 3bp AND the correlation is low, this is the first genuinely additive
    thing found here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.positioning import load_bars, load_metrics  # noqa: E402
from backtest.timeframes import MIN_ORDER  # noqa: E402

HOLD_H = 4                       # rebalance and holding period, from positioning.py
KS = (2, 3, 4)                   # coins per side
FEES = ((12.0, "Bitget taker"), (9.0, "Hyperliquid taker"),
        (3.0, "Hyperliquid maker"), (0.0, "zero (gross)"))


def panel():
    """4-hourly close and taker ratio for every coin with both."""
    px, tk = {}, {}
    for c in blend.BOOK:
        m, p = load_metrics(c), load_bars(c)
        if m is None or p is None or "sum_taker_long_short_vol_ratio" not in m:
            continue
        j = pd.DataFrame({"px": p}).join(
            m[["sum_taker_long_short_vol_ratio"]], how="inner").dropna()
        if len(j) < 24 * 200:
            continue
        g = j.resample(f"{HOLD_H}h").last().dropna()
        px[c], tk[c] = g.px, g.sum_taker_long_short_vol_ratio
    return pd.DataFrame(px).dropna(how="all"), pd.DataFrame(tk).dropna(how="all")


def run_ls(PX, TK, k, fee_bp, t_from=None, t_to=None):
    """Equal-weight long top-k / short bottom-k on the cross-sectional taker rank.

    Signal at t uses only values at t; the return is realised from t to t+1, so
    nothing after the decision informs it.
    """
    idx = PX.index
    if t_from is not None:
        idx = idx[idx >= t_from]
    if t_to is not None:
        idx = idx[idx < t_to]
    one_way = fee_bp / 2.0 / 1e4
    ret = PX.pct_change().shift(-1)          # return from t to t+1, known after t
    w_prev = pd.Series(0.0, index=PX.columns)
    eq, curve, times, turns, grosses = 1.0, [], [], [], []
    for t in idx:
        s = TK.loc[t].dropna()
        r = ret.loc[t]
        s = s[s.index.isin(r.dropna().index)]
        if len(s) < 2 * k:
            continue
        rk = s.rank()
        w = pd.Series(0.0, index=PX.columns)
        w[rk.nlargest(k).index] = 0.5 / k         # taker BUYING -> long (continuation)
        w[rk.nsmallest(k).index] = -0.5 / k
        gross = float((w * r.fillna(0.0)).sum())
        turn = float((w - w_prev).abs().sum())
        net = gross - turn * one_way
        eq *= (1 + net)
        curve.append(eq)
        times.append(t)
        turns.append(turn)
        grosses.append(gross)
        w_prev = w
    if len(curve) < 200:
        return None
    cur = np.asarray(curve)
    ts = pd.DatetimeIndex(times)
    pk = np.maximum.accumulate(cur)
    dd = float((1 - cur / pk).max() * 100)
    per_yr = 365 * 24 / HOLD_H
    rets = np.diff(np.concatenate([[1.0], cur])) / np.concatenate([[1.0], cur])[:-1]
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (cur[-1] ** (1 / yrs) - 1) * 100
    sharpe = (rets.mean() / rets.std() * np.sqrt(per_yr)) if rets.std() > 0 else 0.0
    return dict(n=len(cur), cagr=cagr, dd=dd, sharpe=sharpe,
                turn=float(np.mean(turns)), gross=float(np.mean(grosses)) * 100,
                net=float(np.mean(rets)) * 100,
                monthly=pd.Series(rets, index=ts).resample("ME").sum(),
                times=ts, equity=cur)


def floor_for(k, coins):
    """No stop, so the floor is just the minimum orders of the open positions."""
    mo = sorted((MIN_ORDER.get(c, 5.0) for c in coins), reverse=True)[:2 * k]
    return sum(mo) * (2 * k) / max(len(mo), 1) if mo else float("nan")


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: turnover high, net <=0 at 12bp and positive at 3bp; the")
    print("cross-sectional rank weaker than the within-coin one; correlation with the")
    print("blend under 0.2. Positive at 3bp AND low correlation = first additive result.\n")

    PX, TK = panel()
    print(f"  {PX.shape[1]} coins, {len(PX):,} {HOLD_H}-hour periods, "
          f"{PX.index[0]:%Y-%m-%d} .. {PX.index[-1]:%Y-%m-%d}")
    cut = PX.index[int(len(PX) * 0.6)]
    print(f"  tune before {cut:%Y-%m-%d}, decide after\n")

    print("=" * 104)
    print("1. THE FEE LADDER — this is where the sign is decided")
    print("=" * 104)
    print(f"  {'fee':>5} {'venue':<20}{'k':>3}{'turnover':>10}{'gross/pd':>10}"
          f"{'net/pd':>9}{'CAGR':>9}{'maxDD':>8}{'Sharpe':>8}")
    best = None
    for fee, name in FEES:
        for k in KS:
            d = run_ls(PX, TK, k, fee, t_to=cut)
            if not d:
                continue
            if fee == 3.0 and (best is None or d["sharpe"] > best[0]):
                best = (d["sharpe"], k)
            print(f"  {fee:>4.0f}b {name:<20}{k:>3}{d['turn']:>10.3f}"
                  f"{d['gross']:>+10.4f}{d['net']:>+9.4f}{d['cagr']:>+8.1f}%"
                  f"{d['dd']:>7.1f}%{d['sharpe']:>8.2f}")
    print("\n  turnover is the mean fraction of the book traded per 4h period; 1.0 means")
    print("  the whole book turns over every period. gross/net are % per 4h period.")

    if best is None:
        print("\n  nothing produced enough periods to evaluate")
        return
    k = best[1]
    print("\n" + "=" * 104)
    print(f"2. HOLDOUT at k={k} — data that never informed the choice")
    print("=" * 104)
    print(f"  {'fee':>5} {'venue':<20}{'net/pd':>9}{'CAGR':>9}{'maxDD':>8}"
          f"{'Sharpe':>8}{'months>0':>10}")
    hold = {}
    for fee, name in FEES:
        d = run_ls(PX, TK, k, fee, t_from=cut)
        if not d:
            continue
        hold[fee] = d
        m = d["monthly"]
        print(f"  {fee:>4.0f}b {name:<20}{d['net']:>+9.4f}{d['cagr']:>+8.1f}%"
              f"{d['dd']:>7.1f}%{d['sharpe']:>8.2f}"
              f"{100*(m>0).mean():>9.0f}%")

    print("\n" + "=" * 104)
    print("3. THE CAPITAL FLOOR — no stop, so the 40x amplifier does not apply")
    print("=" * 104)
    for kk in KS:
        print(f"  k={kk} ({2*kk} positions): floor ~ ${floor_for(kk, PX.columns):,.0f} "
              f"at 1x gross exposure")
    print("  (sum of the largest minimum orders across the open positions, MEXC table.")
    print("   Compare the blend's $377, which is min_order x stop / risk / (1-DD).)")

    print("\n" + "=" * 104)
    print("4. DOES IT DIVERSIFY THE BLEND? — the question that matters most")
    print("=" * 104)
    blend.FEE_BP = 12.0
    blend._S.clear()
    b = blend.run(["1h", "4h", "12h"], 12)
    bm = pd.Series(b["R"], index=b["times"]).resample("ME").sum()
    for fee in (12.0, 3.0):
        d = hold.get(fee) or run_ls(PX, TK, k, fee)
        if not d:
            continue
        lm = d["monthly"]
        j = pd.DataFrame({"blend_R": bm, "taker_ls": lm}).dropna()
        if len(j) < 12:
            print(f"  {fee:>4.0f}bp: only {len(j)} overlapping months")
            continue
        c = float(j.blend_R.corr(j.taker_ls))
        print(f"  {fee:>4.0f}bp  monthly correlation with the blend: {c:+.3f} "
              f"over {len(j)} months"
              f"   -> {'GENUINELY DIFFERENT STREAM' if abs(c) < 0.3 else 'overlapping'}")
        both = int(((j.blend_R > 0) & (j.taker_ls > 0)).sum())
        neither = int(((j.blend_R <= 0) & (j.taker_ls <= 0)).sum())
        print(f"         both up {both}/{len(j)} months, both down {neither}/{len(j)}"
              f"  (independent would be ~{len(j)/4:.0f} each)")

    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)
    h12, h3 = hold.get(12.0), hold.get(3.0)
    if h12 and h12["cagr"] > 0 and h12["sharpe"] > 0.5:
        print(f"  Positive at Bitget taker fees ({h12['cagr']:+.1f}%/yr, Sharpe "
              f"{h12['sharpe']:.2f}) - tradable where we already are.")
    elif h3 and h3["cagr"] > 0 and h3["sharpe"] > 0.5:
        print(f"  Dead at 12bp, alive at 3bp ({h3['cagr']:+.1f}%/yr, Sharpe "
              f"{h3['sharpe']:.2f}). This is the strategy class where the venue")
        print("  decides the sign - the opposite of the blend. Maker fills are then")
        print("  the whole question, and maker_r.py is the file that answers it.")
    else:
        print("  Negative even at zero fees or at 3bp. The quintile spread did not")
        print("  survive becoming a portfolio - the within-coin effect does not")
        print("  translate cross-sectionally, or turnover eats it.")


if __name__ == "__main__":
    main()


# --------------------------------------------------------------------------- #
#  ADDED 2026-09-20, after the cross-sectional version came out negative at
#  ZERO fees. Diagnosis: positioning.py ranked each coin against its OWN
#  trailing history; run_ls above ranks coins against EACH OTHER at one
#  instant. Those are different signals. Crypto flow is highly correlated
#  across coins, so at any moment most coins are high or low together and the
#  relative ordering among them may carry nothing. This is the time-series
#  form - the one positioning.py actually measured - with turnover charged.
# --------------------------------------------------------------------------- #
def run_ts(PX, TK, fee_bp, win_p=540, neutral=False, t_from=None, t_to=None):
    """Per-coin: long its own top trailing quintile, short its own bottom.

    win_p is in 4-hour periods (540 ~ 90 days), matching positioning.py's window.
    neutral=True subtracts the cross-sectional mean weight each period, removing
    market exposure so the result is comparable to the long/short book above.
    """
    from backtest.positioning import causal_quintile
    Q = pd.DataFrame({c: causal_quintile(TK[c].dropna(), win_p)
                      for c in TK.columns}).reindex(TK.index)
    ret = PX.pct_change().shift(-1)
    idx = PX.index
    if t_from is not None:
        idx = idx[idx >= t_from]
    if t_to is not None:
        idx = idx[idx < t_to]
    one_way = fee_bp / 2.0 / 1e4
    w_prev = pd.Series(0.0, index=PX.columns)
    eq, curve, times, turns, grosses = 1.0, [], [], [], []
    for t in idx:
        q = Q.loc[t].dropna()
        r = ret.loc[t]
        q = q[q.index.isin(r.dropna().index)]
        if len(q) < 3:
            continue
        raw = pd.Series(0.0, index=PX.columns)
        raw[q[q == 1.0].index] = 1.0
        raw[q[q == 0.0].index] = -1.0
        act = raw[raw != 0]
        if not len(act):
            w = pd.Series(0.0, index=PX.columns)
        else:
            if neutral:
                raw[q.index] = raw[q.index] - raw[q.index].mean()
                act = raw[raw.abs() > 1e-12]
            w = raw / max(act.abs().sum(), 1e-12)
        gross = float((w * r.fillna(0.0)).sum())
        turn = float((w - w_prev).abs().sum())
        eq *= (1 + gross - turn * one_way)
        curve.append(eq); times.append(t); turns.append(turn); grosses.append(gross)
        w_prev = w
    if len(curve) < 200:
        return None
    cur = np.asarray(curve); ts = pd.DatetimeIndex(times)
    pk = np.maximum.accumulate(cur)
    rets = np.diff(np.concatenate([[1.0], cur])) / np.concatenate([[1.0], cur])[:-1]
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    per_yr = 365 * 24 / HOLD_H
    return dict(n=len(cur), cagr=(max(cur[-1], 1e-9) ** (1 / yrs) - 1) * 100,
                dd=float((1 - cur / pk).max() * 100),
                sharpe=(rets.mean() / rets.std() * np.sqrt(per_yr)) if rets.std() else 0,
                turn=float(np.mean(turns)), gross=float(np.mean(grosses)) * 100,
                net=float(np.mean(rets)) * 100,
                monthly=pd.Series(rets, index=ts).resample("ME").sum())


def ts_main():
    PX, TK = panel()
    cut = PX.index[int(len(PX) * 0.6)]
    print(f"TIME-SERIES FORM — each coin against its own trailing 90 days")
    print(f"{PX.shape[1]} coins, {len(PX):,} 4h periods, holdout from {cut:%Y-%m-%d}\n")
    for neutral in (False, True):
        print(f"--- {'market-NEUTRAL (cross-sectionally demeaned)' if neutral else 'DIRECTIONAL (net exposure allowed)'} ---")
        print(f"  {'fee':>5}{'window':>8}{'turnover':>10}{'gross/pd':>10}{'net/pd':>9}"
              f"{'CAGR':>9}{'maxDD':>8}{'Sharpe':>8}  half")
        for fee, _ in FEES:
            for lab, kw in (("tune", dict(t_to=cut)), ("HOLD", dict(t_from=cut))):
                d = run_ts(PX, TK, fee, neutral=neutral, **kw)
                if not d:
                    continue
                print(f"  {fee:>4.0f}b{540:>8}{d['turn']:>10.3f}{d['gross']:>+10.4f}"
                      f"{d['net']:>+9.4f}{d['cagr']:>+8.1f}%{d['dd']:>7.1f}%"
                      f"{d['sharpe']:>8.2f}  {lab}")
        print()
