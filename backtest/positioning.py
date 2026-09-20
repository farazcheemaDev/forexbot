"""IS POSITIONING DATA WORTH ANYTHING? — the first non-price test in this project.

    python -m backtest.positioning

WHAT IS NEW HERE
    Every other test in this repo predicts price from price. This one uses Binance's
    free positioning archive (backtest/metrics_fetch.py), which carries information
    that does not exist in a bar:

        sum_open_interest                 how many contracts are outstanding
        count_long_short_ratio            what share of ALL accounts are long
        count_toptrader_long_short_ratio  top traders, weighted by ACCOUNT
        sum_toptrader_long_short_ratio    top traders, weighted by POSITION SIZE
        sum_taker_long_short_vol_ratio    which side is hitting the market

    A rally on rising open interest is new money. The identical rally on FALLING open
    interest is shorts covering - no new demand, just forced buying that ends. Price
    cannot tell those apart. That is the whole reason to be here.

THE FOUR FAMILIES, DECLARED BEFORE LOOKING
    oi_div      sign(24h price change) x sign(24h OI change), as one signed feature:
                positive when the move is CONFIRMED by OI, negative when divergent.
    crowd       count_long_short_ratio - the share of all accounts long. Tested as a
                CONTRARIAN feature (high crowd long -> expect worse forward returns).
    size_gap    sum_toptrader_ratio / count_toptrader_ratio. Above 1 means the big
                positions are more long than the account count implies - large money
                and small money disagree. Only obtainable from this dataset.
    taker       sum_taker_long_short_vol_ratio - aggressor imbalance, tested as
                exhaustion (extreme buying pressure -> worse forward returns).

    Three horizons: 4h, 12h, 24h. Four families x three horizons = 12 tests, so
    p-values are Holm-corrected across the whole family and the decision is read off
    a holdout that never informed anything.

THE TWO WAYS THIS COULD FAKE A RESULT, AND WHAT STOPS THEM
    1. POOLING. Twelve crypto coins are not twelve independent observations - this
       project already traced one of its two "significant" results to that error. So
       nothing is pooled for significance: the top-minus-bottom quintile spread is
       computed PER COIN, and the t-test is across COINS (n<=12), not across rows.
    2. LOOK-AHEAD IN THE RANKING. A feature's quintile is computed against a trailing
       90-day window of that coin's own history, strictly before the bar. Using a
       full-sample quantile would leak the future into the threshold.

    Costs: the spread trade is charged 12bp round trip, the convention used
    throughout this repo for Binance-class venues.

REGISTERED PREDICTION (2026-09-20, before running)
    oi_div is the likeliest to be real, because it is the only one of the four with a
    mechanism rather than a sentiment story: a move on falling open interest is
    mechanically short-covering and has no new buyer behind it. crowd is the one
    everybody already trades, so I expect it to be arbitraged flat. taker at a 4-24h
    horizon should be noise - aggressor imbalance decays in minutes. size_gap I want
    to work and expect to be too coarse, since "top traders" is an opaque aggregate.

    I expect AT MOST ONE family to survive Holm correction across 12 tests, and
    given this project's record, most likely none.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MET = ROOT / "strategy_analysis" / "data" / "metrics"
BOOK = blend.BOOK
HORIZONS = (4, 12, 24)
FAMILIES = ("oi_div", "crowd", "size_gap", "taker")
RANK_WIN_D = 90
FEE_BP = 12.0
Q = 5                      # quintiles


def load_metrics(sym):
    f = MET / f"{sym}.csv.gz"
    if not f.exists():
        return None
    d = pd.read_csv(f, parse_dates=["create_time"]).set_index("create_time")
    d = d[~d.index.duplicated()].sort_index()
    return d.resample("1h").last().dropna(how="all")


def load_bars(sym):
    d = blend.load(sym)
    if d is None:
        return None
    s = pd.Series(d["close"].to_numpy(float), index=pd.DatetimeIndex(d["time"]))
    return s[~s.index.duplicated()].sort_index()


def features(m, px):
    """All four features, on the hourly grid, using only data at or before each bar."""
    j = pd.DataFrame({"px": px}).join(m, how="inner").dropna(
        subset=["px", "sum_open_interest", "count_long_short_ratio"])
    if len(j) < 24 * 200:
        return None
    oi = j.sum_open_interest
    dpx = np.log(j.px / j.px.shift(24))
    doi = np.log(oi / oi.shift(24))
    f = pd.DataFrame(index=j.index)
    # positive = move confirmed by OI, negative = divergent (short-covering shape)
    f["oi_div"] = np.sign(dpx) * doi
    f["crowd"] = -j.count_long_short_ratio                    # contrarian: negate
    f["size_gap"] = (j.sum_toptrader_long_short_ratio
                     / j.count_toptrader_long_short_ratio.replace(0, np.nan))
    f["taker"] = -j.sum_taker_long_short_vol_ratio             # exhaustion: negate
    f["px"] = j.px
    return f.replace([np.inf, -np.inf], np.nan)


def causal_quintile(s, win_h):
    """Which quintile the current value sits in, against its own trailing window.
    Uses closed='left' so the current bar never enters its own threshold."""
    r = s.rolling(win_h, min_periods=win_h // 3, closed="left")
    lo = r.quantile(1.0 / Q)
    hi = r.quantile(1.0 - 1.0 / Q)
    out = pd.Series(np.nan, index=s.index)
    out[s <= lo] = 0.0
    out[s >= hi] = 1.0
    return out


def coin_spread(f, fam, h):
    """Top-minus-bottom quintile forward return for ONE coin, net of costs."""
    q = causal_quintile(f[fam], RANK_WIN_D * 24)
    fwd = (f.px.shift(-h) / f.px - 1.0) * 100.0
    ok = q.notna() & fwd.notna()
    if ok.sum() < 400:
        return None
    top = fwd[ok & (q == 1.0)]
    bot = fwd[ok & (q == 0.0)]
    if len(top) < 150 or len(bot) < 150:
        return None
    return top.mean() - bot.mean() - FEE_BP / 100.0, len(top), len(bot)


def holm(ps):
    o = np.argsort(ps)
    m = len(ps)
    out = np.empty(m)
    prev = 0.0
    for r, i in enumerate(o):
        prev = max(prev, min(1.0, (m - r) * ps[i]))
        out[i] = prev
    return out


def ttest_across_coins(x):
    x = np.asarray([v for v in x if np.isfinite(v)])
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    # two-sided p from the t distribution
    from scipy import stats
    return t, float(2 * stats.t.sf(abs(t), len(x) - 1)), len(x)


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: oi_div likeliest (it has a mechanism, not a sentiment story);")
    print("crowd already arbitraged; taker is noise at 4-24h; size_gap too coarse.")
    print("At most one family survives Holm across 12 tests; most likely none.\n")

    F, skipped = {}, []
    for c in BOOK:
        m, px = load_metrics(c), load_bars(c)
        if m is None or px is None:
            skipped.append(c)
            continue
        f = features(m, px)
        if f is None:
            skipped.append(c)
            continue
        F[c] = f
    if len(F) < 5:
        raise SystemExit(f"only {len(F)} coins usable - run metrics_fetch first")
    span = (min(f.index.min() for f in F.values()),
            max(f.index.max() for f in F.values()))
    print(f"  {len(F)} coins with positioning + bars, {span[0]:%Y-%m-%d} .. "
          f"{span[1]:%Y-%m-%d}" + (f"   (skipped {', '.join(skipped)})" if skipped else ""))
    tot = sum(len(f) for f in F.values())
    print(f"  {tot:,} hourly observations, quintiles ranked on a trailing "
          f"{RANK_WIN_D}-day window\n")

    cut = span[0] + (span[1] - span[0]) * 0.60
    print(f"  tune before {cut:%Y-%m-%d}, decide after\n")

    print("=" * 100)
    print("1. TUNE — top-minus-bottom quintile forward return, per coin, t across COINS")
    print("=" * 100)
    print(f"  {'family':<10}{'h':>4}{'coins':>7}{'mean spread':>13}{'coins>0':>9}"
          f"{'t':>8}{'p':>8}{'Holm':>8}")
    raw, cells = [], []
    for fam in FAMILIES:
        for h in HORIZONS:
            sp = []
            for c, f in F.items():
                r = coin_spread(f[f.index < cut], fam, h)
                if r:
                    sp.append(r[0])
            t, p, n = ttest_across_coins(sp)
            if not np.isfinite(p):
                print(f"  {fam:<10}{h:>4}{n:>7}   too few coins")
                continue
            raw.append(p)
            cells.append((fam, h, n, float(np.mean(sp)),
                          int(sum(1 for v in sp if v > 0)), t, p))
    hp = holm(np.array(raw)) if raw else []
    for (fam, h, n, mu, pos, t, p), hh in zip(cells, hp):
        star = " **" if hh < .05 else (" *" if p < .05 else "")
        print(f"  {fam:<10}{h:>4}{n:>7}{mu:>+13.3f}%{pos:>8}/{n}"
              f"{t:>8.2f}{p:>8.3f}{hh:>8.3f}{star}")
    print("\n  ** survives Holm across all 12   |   * uncorrected only")
    print("  spread is net of 12bp. 'coins>0' is how many of the coins agreed in sign -")
    print("  that column matters more than the t, because the coins are correlated.")

    surv = [(c, hh) for c, hh in zip(cells, hp) if hh < .05]
    print("\n" + "=" * 100)
    print("2. HOLDOUT — survivors re-tested on data that never informed the choice")
    print("=" * 100)
    if not surv:
        print("  Nothing survived Holm, so there is nothing to hold out. Uncorrected")
        print("  hits are what 12 tests on 12 correlated coins produce by chance.")
    else:
        print(f"  {'family':<10}{'h':>4}{'coins':>7}{'mean spread':>13}"
              f"{'coins>0':>9}{'t':>8}{'p':>8}   verdict")
        for (fam, h, _n, mu_t, _pos, _t, _p), _hh in surv:
            sp = []
            for c, f in F.items():
                r = coin_spread(f[f.index >= cut], fam, h)
                if r:
                    sp.append(r[0])
            t, p, n = ttest_across_coins(sp)
            ok = (np.isfinite(p) and p < .05
                  and np.sign(np.mean(sp)) == np.sign(mu_t))
            print(f"  {fam:<10}{h:>4}{n:>7}{np.mean(sp):>+13.3f}%"
                  f"{sum(1 for v in sp if v > 0):>8}/{n}{t:>8.2f}{p:>8.3f}"
                  f"   {'HOLDS' if ok else 'does NOT hold'}")

    print("\n" + "=" * 100)
    print("3. AS A GATE ON THE DEPLOYED BLEND — does positioning at entry predict R?")
    print("=" * 100)
    blend._S.clear()
    tr, _ = blend.sleeve("1h")
    rows = []
    for a_, _b_, r, _rule, coin in tr:
        f = F.get(coin)
        if f is None:
            continue
        i = f.index.searchsorted(pd.Timestamp(a_), side="right") - 1
        if i < 1:
            continue
        rows.append(dict(coin=coin, R=r, **{k: f[k].iloc[i] for k in FAMILIES}))
    if not rows:
        print("  no blend trades line up with the positioning window")
        return
    T = pd.DataFrame(rows).dropna()
    print(f"  {len(T):,} 1h-sleeve trades with positioning data at entry, "
          f"{T.coin.nunique()} coins\n")
    print(f"  {'family':<10}{'bottom third R':>16}{'top third R':>14}"
          f"{'diff':>9}{'coins agreeing':>16}")
    for fam in FAMILIES:
        agree, diffs = 0, []
        for c, g in T.groupby("coin"):
            if len(g) < 60:
                continue
            lo, hi = g[fam].quantile([1 / 3, 2 / 3])
            a, b = g[g[fam] <= lo].R, g[g[fam] >= hi].R
            if len(a) < 20 or len(b) < 20:
                continue
            diffs.append(b.mean() - a.mean())
            agree += b.mean() > a.mean()
        if not diffs:
            print(f"  {fam:<10}   too few trades per coin")
            continue
        lo, hi = T[fam].quantile([1 / 3, 2 / 3])
        print(f"  {fam:<10}{T[T[fam] <= lo].R.mean():>+16.3f}"
              f"{T[T[fam] >= hi].R.mean():>+14.3f}{float(np.mean(diffs)):>+9.3f}"
              f"{agree:>11}/{len(diffs)}")
    print("\n  A usable gate needs the coins to AGREE, not just the pooled means to")
    print("  differ. 6 of 12 agreeing is a coin flip however large the pooled gap is.")


if __name__ == "__main__":
    main()
