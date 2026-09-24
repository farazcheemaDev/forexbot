"""THE WORST MONTH: what makes it, what shrinks it, and whether the account comes back on its own.

Asked 2026-09-24, after doc 15: "try to evaluate how you can reduce the worst month, and hypothetically
if there is a worse month, can the capital go back up again on its own". The book is the final version
plus the wick bids (wick_combo.py: $300, worst month -29% -> -36% with the wicks).

A. WHAT MAKES THE WORST MONTHS: the six worst calendar months (mean over 10 orderings), and each
   book's own return in them.
B. WHAT SHRINKS THEM, judged against "just bet smaller" (the whole mix scaled by g = 0.5-0.9: the
   frontier every fix in doc 14 had to beat). A fix PASSES only if, at its worst month, it has a
   better typical year than the frontier does at that worst month, on BOTH halves.
   - a monthly brake on the trend book (re-simulated): once the trend book is down X% this calendar
     month, new positions are sized x m until the month ends (X 10/15/20%, m 0 / 0.25), and a
     rolling version (down X% over 30 days);
   - an account brake: once the whole account is down X% this month (known at the previous close),
     every book is cut to m of its size until the month ends (X 10/15/20%, m 0 / 0.5);
   - the wick book at half size, and wick rules from wick_better.py.
C. COMING BACK.
   1. History: every fall of 20% or more, how deep, and how long to a new high.
   2. A shock that never happened: at the start of every month from 2020-01 to 2024-09, the account
      ($300) loses S = 30 / 40 / 50 / 60 / 70% at once, then lives through the real days that followed.
      Small balances trade worse, from min_capital.py: the trend book loses 2.8% of its R at $221,
      9.6% at $150, 13.7% at $100, 42.5% at $50 (assumed 80% at $25, all of it at $10); the MN book
      cannot trade under $60 (12 positions x $5); the wick book keeps only the coins a $5 bid allows
      (balance / $5 of its N coins, so its return is scaled by that share - an approximation).
      Measured: the share of starts back at $300 within 6 / 12 / 24 months, and the median time;
      with no withdrawals, with $20 a month, and with $20 a month paused while under $300.

The trend book's gains are shrunk for hindsight and its losses kept whole (max_mix.py); the other
books are raw, as in wick_combo.py.

REGISTERED PREDICTION (2026-09-24, before running):
  A. the worst months are trend-book months after booms (2021-05, 2022-05/06); the wick book costs
     5-7 points in 2022-05 (LUNA).
  B. both brakes shrink the worst month by 3-8 points and FAIL the frontier on the typical year, as
     ddcut did in doc 14; the wick book at half size lands on the frontier (it is a size dial).
  C1. every 20%+ fall of the final version recovered; median 3-6 months, longest 12-18 (2022).
  C2. after a -50% shock ~60% of starts are back within 12 months and ~80% within 24; after -70%,
     ~35% within 24 months, because under $100 the $5 minimum bites. $20/month withdrawals cut the
     24-month share by 10-20 points; pausing them while under water recovers most of that.
ADDED after wick_better.py --combos was read, before this file first ran to completion: the NEW
wick book (top-40, skip BEAR days) at x1 / x1.5 / x2. Prediction: it passes B and makes the account's
worst month no worse than the final version without wicks (-29%), with a typical year above $1,937.
ADDED after wick_5m.py and joint_worst_hour.py were read (the uncapped wick book leaves 10% of the
account in the 2025-10-10 hour): the NEW book with its bids cancelled after the first 10 / 20 fills
in an hour (logs/wick_capped.pkl, from wick_5m.py --save). C1/C2 run on the cap-10 plan, which is
the one recommended. Prediction: cap 10 passes B; the account's worst month within 1 point of the
final version without wicks; typical year +$100-200 over no wicks.
STRESS (--stress), added after C2 read 100% recovery within 24 months after a -50% shock: that speed is
only as good as the backtest's gains. FIRST VERSION, kept as a record (logs/worst_month_stress_gains_
halved.txt): every positive day halved, losses whole. Registered: after -50%, ~65% back within 24
months. Result: 12%, and the balance FELL without any shock - because halving every up-day is not
"earning half", it removes the edge entirely (a volatile book's up-days only slightly outweigh its
down-days). The prediction was wrong because the stress was the wrong question.
SECOND VERSION (this code): positive days shrunk by the factor that makes the plan GROW at 0.5x and
0.25x its own backtest rate - the same method as the hindsight haircut. Registered before running:
at 0.5x, after -50% ~85% back within 24 months, median ~8 months; at 0.25x, ~55%, median ~18 months.
THIRD (--stress --flat), added after the second read +487%/yr for the plan (so 0.25x is still +122%):
growth fixed at +50% and +25% a year, what a disappointing live bot might make. Registered before
running: after -50%, +50%/yr brings ~50% of starts back within 24 months; +25%/yr ~25%.

    python -m backtest.worst_month
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.dd_fixes as D  # noqa: E402
import backtest.max_mix as M  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.expectations import month_ends, windows  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wick_better import book as wick_book, fills, load_all  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TCACHE = ROOT / "strategy_analysis" / "data" / "worst_month_trend.pkl"
CAP = 300.0
CUT = pd.Timestamp("2024-08-29")
SEEDS = tuple(range(10))
DAY = D.DAY

# small-account penalties (min_capital.py): share of the trend book's R lost at a balance
TREND_LOST = ((10, 1.0), (25, 0.80), (50, 0.425), (100, 0.137), (150, 0.096), (221, 0.028), (300, 0.0))
MN_MIN = 60.0
DOC15 = "wick bids (doc 15)"
NEW = "NEW wicks: top-40, skip BEAR x1"
CAP10 = "NEW wicks, cancel after 10 fills/hour"


def trend_lost(v):
    xs, ys = zip(*TREND_LOST)
    return float(np.interp(np.log(max(v, 1.0)), np.log(xs), ys))


def month_start_ns(t):
    ts = pd.Timestamp(int(t))
    return pd.Timestamp(ts.year, ts.month, 1).value


def brake_size(X, m, rolling=False):
    """21-day anchor, then x m once the trend book is down X this calendar month (or over 30 days)."""
    def f(t, eq, ctx):
        base = min(eq, ctx.mean_over(t, 21))
        ref = ctx.eq_at(t - 30 * DAY) if rolling else ctx.eq_at(month_start_ns(t) - 1)
        return base * (m if eq / max(ref, 1e-12) - 1 <= -X else 1.0)
    return f


def account_brake(parts, X, m):
    """parts: DataFrame of daily book returns. From the day after the account's month-to-date return
    first reaches -X, every book is x m until the month ends."""
    tot = parts.sum(axis=1)
    out, mtd, cut, cur = [], 1.0, False, None
    for t, r in tot.items():
        if cur != (t.year, t.month):
            cur, mtd, cut = (t.year, t.month), 1.0, False
        k = m if cut else 1.0
        out.append(k * r)
        mtd *= 1 + k * r
        if mtd - 1 <= -X:
            cut = True
    return pd.Series(out, index=tot.index)


def summary(lst, t0=None, t1=None):
    W12, WM, UP = [], [], []
    for x in lst:
        y = x if t0 is None else x[x.index >= t0]
        y = y if t1 is None else y[y.index < t1]
        c = (1 + y).cumprod()
        me = month_ends(c)
        mo = (me / me.shift(1)).dropna().to_numpy() - 1
        W12.append(windows(me, 12)); WM.append(mo.min()); UP.append((mo > 0).mean())
    w = np.concatenate(W12)
    return dict(typ=CAP * np.median(w), bad=CAP * np.percentile(w, 25), wm=np.mean(WM) * 100, up=np.mean(UP) * 100)


def worst_months(plan_name, parts):
    print(f"\nA. THE SIX WORST MONTHS of {plan_name} (mean over 10 orderings) and each book's own return in them")
    mon = pd.concat([(1 + p).groupby(p.index.to_period("M")).prod() - 1 for p in parts]).groupby(level=0).mean()
    tot = pd.concat([(1 + p.sum(axis=1)).groupby(p.index.to_period("M")).prod() - 1 for p in parts]).groupby(level=0)
    tm, tw = tot.mean(), tot.min()
    print(f"  {'month':<9}{'account':>9}{'trend':>9}{'MN':>8}{'sleeve':>8}{'wick':>8}   worst ordering")
    for per in tm.nsmallest(6).index:
        print(f"  {str(per):<9}{tm[per]*100:>+8.1f}%{mon.loc[per, 'trend']*100:>+8.1f}%{mon.loc[per, 'mn']*100:>+7.1f}%"
              f"{mon.loc[per, 'sleeve']*100:>+7.1f}%{mon.loc[per, 'wick']*100:>+7.1f}%   {tw[per]*100:+.1f}%")


def variants_report(variants):
    halves = (("all 6 years", None, None), ("TUNE (to 2024-08-29)", None, CUT), ("HOLDOUT (after)", CUT, None))
    S = {name: {h: summary(lst, a, b) for h, a, b in halves} for name, lst in variants.items()}
    fr = [n for n in S if n.startswith("frontier")] + ["FINAL + doc 15 wicks (the plan so far)"]

    def vs_frontier(name, h):
        pts = sorted((S[n][h]["wm"], S[n][h]["typ"]) for n in fr)
        return S[name][h]["typ"] - float(np.interp(S[name][h]["wm"], [p[0] for p in pts], [p[1] for p in pts]))

    print("\nB. WHAT SHRINKS THE WORST MONTH ($300; typical / bad 12 months, worst month (mean of 10 orderings), "
          "months up; 'vs smaller' = typical year minus what just betting smaller gives at the same worst month)")
    for h, _, _ in halves:
        print(f"\n  {h}")
        print(f"  {'':<50}{'typical':>9}{'bad':>8}{'worst mo':>10}{'up':>6}{'vs smaller':>12}")
        for name in variants:
            r = S[name][h]
            v = "" if name in fr else f"{vs_frontier(name, h):+10.0f}$"
            print(f"  {name:<50}${r['typ']:>7,.0f}${r['bad']:>6,.0f}{r['wm']:>+9.1f}%{r['up']:>5.0f}%{v:>12}")
    print("\n  VERDICT (passes = better than just betting smaller on BOTH halves):")
    for name in variants:
        if name in fr:
            continue
        a, b = vs_frontier(name, halves[1][0]), vs_frontier(name, halves[2][0])
        print(f"    {name:<50} tune {a:+6.0f}$  holdout {b:+6.0f}$  -> {'PASS' if a > 0 and b > 0 else 'fail'}")


def recovery(plan_name, parts, wick_n, gain=1.0):
    print(f"\nC1. HISTORY, {plan_name}: every fall of 20%+ (10 orderings pooled): depth, days down, days back to the old high")
    eps = []
    for sd, p in zip(SEEDS, parts):
        c = (1 + p.sum(axis=1)).cumprod()
        peak, pk_t, low, low_t, inside = c.iloc[0], c.index[0], c.iloc[0], c.index[0], False
        for t, v in c.items():
            if v >= peak:
                if inside and 1 - low / peak >= 0.20:
                    eps.append((sd, pk_t, low_t, t, 1 - low / peak))
                peak, pk_t, low, low_t, inside = v, t, v, t, False
            else:
                inside = True
                if v < low:
                    low, low_t = v, t
        if inside and 1 - low / peak >= 0.20:
            eps.append((sd, pk_t, low_t, pd.NaT, 1 - low / peak))
    E = pd.DataFrame(eps, columns=["seed", "peak", "low", "back", "depth"])
    E["back"] = pd.to_datetime(E["back"])
    E["down_d"] = (E.low - E.peak).dt.days
    E["back_d"] = (E.back - E.low).dt.days
    rec = E[E.back.notna()]
    print(f"  {len(E)} falls of 20%+ across 10 orderings; recovered {len(rec)}, still under water at the end "
          f"{E.back.isna().sum()}")
    print(f"  days from the low back to the old high: median {rec.back_d.median():.0f}, 3 in 4 within "
          f"{rec.back_d.quantile(0.75):.0f}, longest {rec.back_d.max():.0f}")
    print("  by depth: " + " | ".join(
        f"{lo*100:.0f}-{hi*100:.0f}%: {len(g)} falls, median {g.back_d.median():.0f} days back"
        for lo, hi in ((0.2, 0.3), (0.3, 0.4), (0.4, 0.6), (0.6, 1.0))
        for g in [rec[(rec.depth >= lo) & (rec.depth < hi)]] if len(g)))
    print("  the deepest ones (ordering 0):")
    for _, r in E[E.seed == 0].nlargest(5, "depth").iterrows():
        if pd.notna(r.back):
            print(f"    peak {r.peak:%Y-%m-%d}  low {r.low:%Y-%m-%d} (-{r.depth*100:.0f}%, {r.down_d:.0f} days down)  "
                  f"back {r.back:%Y-%m-%d} ({r.back_d:.0f} days)")
        else:
            print(f"    peak {r.peak:%Y-%m-%d}  low {r.low:%Y-%m-%d} (-{r.depth*100:.0f}%)  NOT back by the end of the data")
    shock_test(plan_name, parts, wick_n, gain)


def slow_factor(r, f):
    """s such that shrinking every positive day by s makes the plan grow at f x its own CAGR
    (f <= 1), or at a fixed rate f - 1 a year (f > 1: 1.25 = +25%/yr)."""
    target = f * M.cagr((1 + r).cumprod()) if f <= 1 else (f - 1)
    lo, hi = 0.0, 1.0
    for _ in range(40):
        s = (lo + hi) / 2
        g = M.cagr(pd.Series(np.cumprod(1 + np.where(r > 0, s * r, r)), index=r.index))
        lo, hi = (s, hi) if g < target else (lo, s)
    return (lo + hi) / 2


def shock_test(plan_name, parts, wick_n, gain=1.0):
    print(f"\nC2. {plan_name}: A SHOCK THAT NEVER HAPPENED - $300 loses S at the start of a month, then lives the "
          "real days that followed (small-balance penalties on). Starts 2020-01..2024-09 x 10 orderings.")
    starts = pd.date_range("2020-01-01", "2024-09-01", freq="MS")
    for plan in ("no withdrawals", "$20/month", "$20/month, paused under $300"):
        print(f"\n  {plan}")
        print(f"  {'shock':>7}{'left':>7}{'back to $300 in 6 mo':>22}{'12 mo':>8}{'24 mo':>8}{'median months':>15}"
              f"{'balance after 24 mo: typical':>30}{'bad (1 in 4)':>14}   2022+ starts: 24 mo")
        for S_ in (0.30, 0.40, 0.50, 0.60, 0.70):
            months, final, late = [], [], []
            for p in parts:
                P = p[["trend", "mn", "sleeve", "wick"]].to_numpy(float)
                g_ = gain if not isinstance(gain, tuple) else slow_factor(p.sum(axis=1), gain[1])
                P = np.where(P > 0, g_ * P, P)
                idx = p.index
                me = np.r_[idx[1:].month != idx[:-1].month, True]
                for st in starts:
                    i = idx.searchsorted(st)
                    v, got, t_end = CAP * (1 - S_), None, st + pd.DateOffset(months=24)
                    while i < len(idx) and idx[i] < t_end:
                        tr, m_, sl, wk = P[i]
                        r = (tr * (1 - trend_lost(v)) + (m_ if v >= MN_MIN else 0.0) + sl
                             + wk * min(1.0, v / 5.0 / wick_n))
                        v = max(v * (1 + r), 0.0)
                        if me[i] and plan != "no withdrawals" and (plan == "$20/month" or v >= CAP) and v >= 20.0:
                            v -= 20.0
                        if got is None and v >= CAP:
                            got = (idx[i] - st).days / 30.44
                        i += 1
                    months.append(got if got is not None else np.inf)
                    final.append(v)
                    late.append(st >= pd.Timestamp("2022-01-01"))
            mo, fi, la = np.array(months), np.array(final), np.array(late)
            print(f"  {-S_*100:>6.0f}%${CAP*(1-S_):>5.0f}{(mo <= 6).mean()*100:>21.0f}%{(mo <= 12).mean()*100:>7.0f}%"
                  f"{(mo <= 24).mean()*100:>7.0f}%{np.median(mo):>14.1f} ${np.median(fi):>28,.0f}"
                  f"${np.percentile(fi, 25):>12,.0f}   {(mo[la] <= 24).mean()*100:>5.0f}%")


def main():
    # ---------------------------------------------------------------- the books
    X, _, bear_day = load_all()
    X20, X40 = X[X.in20], X[X.in40]
    wick_rules = {
        DOC15: (fills(X20), 20, 1.0),
        "wick bids, no 2nd fill <24h": (fills(X20, no_repeat=True), 20, 1.0),
        "wick bids, skip coins -25%/24h": (fills(X20, max_drop24=0.25), 20, 1.0),
        NEW: (fills(X40, skip_bear=bear_day), 40, 1.0),
        "NEW wicks: top-40, skip BEAR x1.5": (fills(X40, skip_bear=bear_day), 40, 1.5),
        "NEW wicks: top-40, skip BEAR x2": (fills(X40, skip_bear=bear_day), 40, 2.0),
    }
    wick = {k: wick_book(Y, n, mult)[0].pct_change().fillna(0.0) for k, (Y, n, mult) in wick_rules.items()}
    capped = pd.read_pickle(ROOT / "logs" / "wick_capped.pkl")
    wick[CAP10] = capped[10]
    wick["NEW wicks, cancel after 20 fills/hour"] = capped[20]
    W0 = wick[DOC15]

    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    trows = D.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))

    cache = pickle.loads(TCACHE.read_bytes()) if TCACHE.exists() else {}

    def trend(key, sd, s, size_fn=None, g=1.0):
        if (key, sd) not in cache:
            r = D.sim(trows, bn, bv, sd, lev=9.0, size_fn=size_fn or D.anchor(21), g=g).pct_change().fillna(0.0)
            cache[(key, sd)] = pd.Series(np.where(r > 0, s * r, r), index=r.index)
            TCACHE.write_bytes(pickle.dumps(cache))
        return cache[(key, sd)]

    def frame(t1, g=1.0, w=W0):
        idx = t1.index
        return pd.DataFrame({"trend": t1, "mn": g * mn_d.reindex(idx).fillna(0.0),
                             "sleeve": g * sleeve.reindex(idx).fillna(0.0),
                             "wick": g * w.reindex(idx).fillna(0.0)})

    shrink = {}
    for sd in SEEDS:
        if ("shrink", sd) not in cache:
            cache[("shrink", sd)] = M.shrink_factor(D.sim(trows, bn, bv, sd).pct_change().fillna(0.0))
        shrink[sd] = cache[("shrink", sd)]
    base_parts = [frame(trend("anchor", sd, shrink[sd])) for sd in SEEDS]
    print("  base built", flush=True)
    new_parts = [p.assign(wick=wick[CAP10].reindex(p.index).fillna(0.0)) for p in base_parts]
    if "--stress" in sys.argv:
        stress = (0.5, 0.25) if "--flat" not in sys.argv else (1.50, 1.25)
        for f in stress:
            r0 = new_parts[0].sum(axis=1)
            what = f"{f} x the backtest's rate" if f <= 1 else f"+{(f - 1)*100:.0f}% a year"
            print()
            print(f"  growing at {what}: ordering 0 goes {M.cagr((1 + r0).cumprod())*100:+.0f}%/yr -> "
                  f"{(f * M.cagr((1 + r0).cumprod()) if f <= 1 else f - 1)*100:+.0f}%/yr "
                  f"(every positive day x{slow_factor(r0, f):.3f})")
            shock_test(f"STRESS - cap-10 plan growing at {what} (gains shrunk, losses whole)",
                       new_parts, 40, gain=("cagr", f))
        return

    variants = {
        "FINAL + doc 15 wicks (the plan so far)": [p.sum(axis=1) for p in base_parts],
        "FINAL, no wicks": [p.drop(columns="wick").sum(axis=1) for p in base_parts],
    }
    for g in (0.5, 0.6, 0.7, 0.8, 0.9):
        variants[f"frontier: everything x{g}"] = [frame(trend(f"g{g}", sd, shrink[sd], g=g), g=g).sum(axis=1)
                                                   for sd in SEEDS]
    print("  frontier built", flush=True)
    for k in wick:
        if k != DOC15:
            variants[f"FINAL + {k}"] = [p.trend + p.mn + p.sleeve + wick[k].reindex(p.index).fillna(0.0)
                                        for p in base_parts]
    variants["FINAL + doc 15 wicks at half size"] = [p.trend + p.mn + p.sleeve + 0.5 * p.wick for p in base_parts]
    for X_ in (0.10, 0.15, 0.20):
        for m in (0.0, 0.5):
            variants[f"account brake: -{X_*100:.0f}% this month -> x{m}"] = [account_brake(p, X_, m) for p in base_parts]
    for X_ in (0.10, 0.15, 0.20):
        for m in (0.0, 0.25):
            variants[f"trend brake: -{X_*100:.0f}% this month -> x{m}"] = [
                frame(trend(f"brake{X_}_{m}", sd, shrink[sd], size_fn=brake_size(X_, m))).sum(axis=1) for sd in SEEDS]
    for X_ in (0.15, 0.25):
        variants[f"trend brake: -{X_*100:.0f}% over 30 days -> x0.25"] = [
            frame(trend(f"roll{X_}", sd, shrink[sd], size_fn=brake_size(X_, 0.25, rolling=True))).sum(axis=1)
            for sd in SEEDS]
    for X_ in (0.10, 0.15):
        variants[f"cap-10 wicks + account brake -{X_*100:.0f}% -> x0.5"] = [account_brake(p, X_, 0.5) for p in new_parts]
    print("  variants built", flush=True)

    for plan_name, parts in (("final + doc 15 wicks", base_parts), ("final + NEW wicks, cap 10", new_parts)):
        worst_months(plan_name, parts)
    variants_report(variants)
    recovery("FINAL + doc 15 wicks", base_parts, 20)
    recovery("FINAL + NEW wicks, cancel after 10 fills/hour", new_parts, 40)


if __name__ == "__main__":
    main()
