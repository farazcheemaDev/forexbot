"""VALIDATING THE POINT-IN-TIME BOOK, AND SWEEPING THE ONE RULE NEVER SWEPT.

    python -m backtest.pit_validate

WHAT NEEDS SETTLING
    pit_blend.py found the point-in-time universe earning +8.86%/month in 2026 against
    the deployed book's +0.46% (which still owes a 3x haircut, while PIT owes none). Four
    things were flagged as unfinished, and three of them are here.

    1. IS THE ADVANTAGE A TREND OR ONE LUCKY WINDOW?
       "Recent" was chosen as the evaluation window AFTER seeing that recent is where PIT
       wins. That is selection. The defence is not an argument, it is a shape: if the
       universe genuinely settled over time, the PIT-minus-FIXED gap must move smoothly
       from negative to positive across the years. If it is noise, it will jump around
       and merely happen to be positive in 2026.

    2. THE SELECTION RULE ITSELF HAS NEVER BEEN SWEPT.
       TOP=12 was chosen only to match the deployed book size. The ranking window (one
       prior month) and the ranking metric (dollar volume) were never varied either.
       These are the three free parameters of the idea and all three were set by default.

       SWEPT ON 2020-2024 ONLY, TESTED ON 2025-2026. That ordering is the whole point:
       picking a rule on the same window used to report the result is what invalidated
       the slot count, and it is not repeated here.

    3. MCPT AND BLOCK BOOTSTRAP on whatever survives.
       MCPT asks whether the edge beats the same rules run on permuted markets.
       The bootstrap resamples trades in BLOCKS OF 20 so loss clustering survives -
       drawdown is a property of ordering, and an i.i.d. resample destroys it and
       flatters the drawdown badly.

    SURVIVORSHIP NEEDS NO SEPARATE TEST HERE, and that is a real strength of the design
    rather than an omission: the point-in-time universe is drawn from all 284 coins
    INCLUDING the 202 delisted ones, and a coin that later died is still ranked, still
    traded, and still allowed to lose money. The bias is absent by construction instead
    of corrected after the fact.

EFFICIENCY NOTE
    Trades depend only on WHICH COINS exist, never on the selection rule. So the sleeves
    are built ONCE for the union of every candidate set, and each rule is then just a
    different eligibility filter over the same trade stream. Without that the sweep would
    rebuild 100k+ trades per cell.

REGISTERED PREDICTIONS (2026-09-14, before running)
    A  The gap trends. Negative early, positive late, with 2024 the ugly exception
       already seen on the simple engine.
    B  The best rule chosen on 2020-2024 does NOT hold up on 2025-2026 at +8.86%. I
       expect the honest out-of-sample figure to land nearer +4-5%/month, which is what
       the unfiltered PIT book gave before the PEPE/ETH exclusion flattered it.
    C  A SHORTER ranking window (1 month) beats longer ones, because crypto volume
       rotates fast and a 3-month average is stale by the time it is used.
    D  MCPT passes (p < 0.05). The signal is the same one already validated; only the
       universe changed, and a permuted market has no volume-ranking structure to exploit.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend                                        # noqa: E402
from backtest.pit_blend import (DEPLOYED, RULES, SLOTS,           # noqa: E402
                                portfolio, trades_for_book)
from backtest.pit_universe import load_all, monthly_volume        # noqa: E402
from backtest.regime_blend import set_lookback                    # noqa: E402

TOO_BIG = {"PEPEUSDT", "ETHUSDT"}      # per-coin need above what $221 supports
SPLIT = pd.Timestamp("2025-01-01")     # sweep before, test after. Fixed, not tuned.
rng = np.random.default_rng(11)


def rank_frames(frames):
    """Monthly dollar volume, and a monthly realised-range table for the alt metrics."""
    vol = monthly_volume(frames)
    rngs = {}
    for s, df in frames.items():
        if df is None or len(df) < 100:
            continue
        g = df.set_index(pd.DatetimeIndex(df["time"]))
        m = (g["high"].resample("ME").max() - g["low"].resample("ME").min()) / \
            g["close"].resample("ME").last()
        rngs[s] = m
    R = pd.DataFrame(rngs)
    if len(R):
        R.index = pd.PeriodIndex(pd.DatetimeIndex(R.index), freq="M")
    V = vol.copy()
    if not isinstance(V.index, pd.PeriodIndex):
        V.index = pd.PeriodIndex(pd.DatetimeIndex(V.index), freq="M")
    return V, R


def eligibility(vol, rg, top, window, metric, drop):
    """{period -> eligible symbols}, ranked on the PRIOR `window` months only."""
    if metric == "volume":
        base = vol
    elif metric == "range":
        base = rg.reindex(columns=vol.columns)
    else:                                     # volume x range: active AND moving
        base = vol * rg.reindex(columns=vol.columns).reindex(index=vol.index)
    base = base.astype(float)
    # monthly_volume() and the resample("ME") range table do NOT agree on index type -
    # one is a PeriodIndex, the other a DatetimeIndex - and `per + 1` means "next month"
    # only on a PeriodIndex. Normalise here rather than at every call site.
    base = base.copy()
    base.index = pd.PeriodIndex(pd.DatetimeIndex(
        [p.to_timestamp() if hasattr(p, "to_timestamp") else p for p in base.index]),
        freq="M")
    base = base.groupby(level=0).mean().sort_index()
    roll = base.rolling(window, min_periods=1).mean()
    out = {}
    for per in roll.index:
        s = roll.loc[per].dropna().sort_values(ascending=False)
        if drop:
            s = s[[i for i in s.index if i not in drop]]
        out[per + 1] = set(s.head(top).index)   # +1 => never reads its own month
    return out


def main():
    print(__doc__.split("REGISTERED PREDICTIONS")[0].rstrip())
    print("\nREGISTERED: (A) the gap trends; (B) the swept rule lands nearer +4-5%/mo")
    print("out of sample, not +8.86%; (C) a 1-month ranking window wins; (D) MCPT passes.\n")

    print("loading every coin, alive and delisted...", flush=True)
    frames = load_all(verbose=False)
    vol, rg = rank_frames(frames)
    set_lookback(1000)
    bear = blend.btc_bear()

    # union of every candidate any rule could pick, so sleeves are built once
    grids = [(t, w, m) for t in (6, 9, 12, 18) for w in (1, 2, 3) for m in
             ("volume", "range", "volxrange")]
    union: set = set()
    elig_cache = {}
    for t, w, m in grids:
        e = eligibility(vol, rg, t, w, m, TOO_BIG)
        elig_cache[(t, w, m)] = e
        union |= set().union(*e.values())
    print(f"  {len(frames)} coins loaded; {len(union)} ever eligible under ANY rule")
    print("building sleeves once for that union (slow, then everything is cheap)...",
          flush=True)
    tr_all = trades_for_book(sorted(union), frames)
    tr_fix = trades_for_book(DEPLOYED)
    print(f"  {len(tr_all):,} candidate trades, {len(tr_fix):,} deployed-book trades\n")

    # ---- 1. is the gap a trend? ------------------------------------------
    print("=" * 100)
    print("1. IS THE PIT ADVANTAGE A TREND, OR ONE LUCKY WINDOW?")
    print("=" * 100)
    base_e = elig_cache[(12, 1, "volume")]
    print(f"  {'year':<7}{'FIXED meanR':>13}{'PIT meanR':>12}{'gap':>9}   direction")
    gaps = {}
    for y in range(2020, 2027):
        a = portfolio(tr_fix, None, bear, pd.Timestamp(f"{y}-01-01"))
        b = portfolio(tr_all, base_e, bear, pd.Timestamp(f"{y}-01-01"))
        # restrict to that calendar year by also cutting the top
        ta = [x for x in tr_fix if pd.Timestamp(x[0]).year == y]
        tb = [x for x in tr_all if pd.Timestamp(x[0]).year == y]
        a = portfolio(ta, None, bear)
        b = portfolio(tb, base_e, bear)
        if not (a and b):
            print(f"  {y:<7}{'(too few trades)':>28}")
            continue
        g = b["meanR"] - a["meanR"]
        gaps[y] = g
        print(f"  {y:<7}{a['meanR']:>13.3f}{b['meanR']:>12.3f}{g:>+9.3f}   "
              f"{'PIT better' if g > 0 else 'FIXED better'}")
    if len(gaps) >= 5:
        ys = sorted(gaps)
        r = np.corrcoef(ys, [gaps[y] for y in ys])[0, 1]
        print(f"\n  correlation of gap with year: {r:+.2f}")
        print("  " + ("A TREND, not one window - the advantage grows monotonically "
                      "enough" if r > 0.5 else
                      "NOT a clean trend. The 2026 win may be one window."))

    # ---- 2. sweep the rule on 2020-2024, test on 2025+ --------------------
    print("\n" + "=" * 100)
    print(f"2. SWEEP THE SELECTION RULE ON 2020-2024, TEST ON 2025-2026")
    print("=" * 100)
    print(f"  {'top':>4}{'win':>5}{'metric':>11}{'IS /mo':>10}{'IS meanR':>10}"
          f"{'|':>3}{'OOS /mo':>10}{'OOS meanR':>11}{'OOS DD':>8}")
    rows = []
    for key in grids:
        e = elig_cache[key]
        i = portfolio(tr_all, e, bear, t_from=None)
        # in-sample = strictly before SPLIT
        ti = [x for x in tr_all if pd.Timestamp(x[0]) < SPLIT]
        i = portfolio(ti, e, bear)
        o = portfolio(tr_all, e, bear, t_from=SPLIT)
        if not (i and o):
            continue
        rows.append((key, i, o))
        t, w, m = key
        print(f"  {t:>4}{w:>5}{m:>11}{i['mo']:>+9.2f}%{i['meanR']:>10.3f}{'|':>3}"
              f"{o['mo']:>+9.2f}%{o['meanR']:>11.3f}{o['dd']:>7.1f}%")
    if not rows:
        print("  nothing ran")
        return
    best = max(rows, key=lambda r: r[1]["mo"])          # chosen on IN-SAMPLE only
    (bt, bw, bm), bi, bo = best
    print(f"\n  BEST ON 2020-2024 (chosen without seeing 2025+): top {bt}, "
          f"{bw}-month window, {bm}")
    print(f"    in-sample  {bi['mo']:+.2f}%/mo   meanR {bi['meanR']:.3f}")
    print(f"    OUT OF SAMPLE {bo['mo']:+.2f}%/mo   meanR {bo['meanR']:.3f}   "
          f"DD {bo['dd']:.1f}%   win months {bo['win']:.0f}%")
    dflt = next((r for r in rows if r[0] == (12, 1, "volume")), None)
    if dflt:
        print(f"    (the default top 12 / 1 month / volume gives "
              f"{dflt[2]['mo']:+.2f}%/mo out of sample)")

    # ---- 3. block bootstrap on the OOS trades of the chosen rule ---------
    print("\n" + "=" * 100)
    print("3. BLOCK BOOTSTRAP on the chosen rule's out-of-sample trades")
    print("=" * 100)
    e = elig_cache[(bt, bw, bm)]
    open_until, seq = [], []
    for a, b, r, _rule, c in tr_all:
        ta = pd.Timestamp(a)
        if ta < SPLIT:
            continue
        ok = e.get(ta.to_period("M"))
        if ok is None or c not in ok:
            continue
        open_until = [u for u in open_until if u > a]
        if len(open_until) >= SLOTS:
            continue
        open_until.append(b)
        seq.append(r)
    seq = np.asarray(seq)
    print(f"  {len(seq)} out-of-sample trades, mean R {seq.mean():+.3f}")
    if len(seq) >= 100:
        B, sims = 20, 4000
        nb = max(len(seq) // B, 1)
        means, dds = [], []
        for _ in range(sims):
            starts = rng.integers(0, max(len(seq) - B, 1), size=nb)
            s = np.concatenate([seq[i:i + B] for i in starts])
            means.append(s.mean())
            eq = np.cumprod(1 + s * 0.003)
            pk = np.maximum.accumulate(eq)
            dds.append(float((1 - eq / pk).max() * 100))
        means, dds = np.asarray(means), np.asarray(dds)
        print(f"  blocks of {B} (loss clustering preserved), {sims} resamples:")
        print(f"    mean R    5th {np.percentile(means,5):+.3f}   median "
              f"{np.median(means):+.3f}   95th {np.percentile(means,95):+.3f}")
        print(f"    P(mean R <= 0) = {100*(means<=0).mean():.1f}%")
        print(f"    drawdown  median {np.median(dds):.1f}%   95th "
              f"{np.percentile(dds,95):.1f}%   worst {dds.max():.1f}%")

    print("\n" + "=" * 100)
    print("READ THIS BEFORE BELIEVING ANY NUMBER ABOVE")
    print("=" * 100)
    print("  The rule was chosen on 2020-2024 and the OOS column is 2025-2026, so the")
    print("  OOS figure is the only one that means anything. The in-sample column is")
    print("  printed solely so the size of the shrinkage is visible.")
    print("  MCPT is NOT in this file: permuting 284 coins x 3 timeframes through the")
    print("  pyramid engine is hours of compute, not minutes. It is the remaining gate.")


if __name__ == "__main__":
    main()
