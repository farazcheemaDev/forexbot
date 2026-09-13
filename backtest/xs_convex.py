"""CROSS-SECTIONAL MOMENTUM WITH THE EXITS IT NEVER GOT.

WHY THIS IS WORTH REOPENING
    Cross-sectional market-neutral momentum passed the two hardest tests in this
    project - MCPT at p=0.0033 (0 of 300 permutations beat it) and an unseen 500-day
    holdout (+12.6% against long-only's -7.3%). It was then set aside as "too small",
    Sharpe 0.62.

    That judgement was made BEFORE the discovery that position management was worth
    2-9x on the trend book: uncapped trailing exits took trend families from 3/11
    profitable to 11/11, and pyramiding improved return AND drawdown together.

    And the cross-sectional engine contains the same class of error that caused the
    original false negatives. It holds every position for exactly `hold` bars and
    then closes it:

        signal at close[t] -> trade at open[t+1] -> hold to open[t+1+hold]

    `hold=24` force-closes every position after 24 hours regardless of what it is
    doing. That is a PROFIT CAP IN TIME FORM. For a strategy whose profit is
    concentrated in rare large moves - the trend book's top 25 of 6,054 trades made
    102% of its profit - truncating at a fixed horizon deletes exactly the trades
    that pay.

    It is also the sleeve most worth having: market-neutral by construction, so it
    does not need crypto to rise. The 1h trend book earned 2.5% of its lifetime
    profit in 2025-2026 precisely because crypto stopped trending.

THREE TESTS
    1. HOLD SWEEP in the original engine. If a fixed horizon is truncating winners,
       longer holds should improve results monotonically. This is the cheap, direct
       test of the time-cap hypothesis and it needs no new machinery.

    2. RANK AS ENTRY, TRAIL AS EXIT. Convert it to a trade-based strategy: a coin
       ENTERING the top k opens a long with the trend book's 20xATR trail and 5-unit
       pyramid; a coin entering the bottom k opens a short with a 5xATR trail.
       Positions leave on their own stops rather than on a rebalance clock.

       THE HONEST COST OF THIS: the book is no longer dollar-neutral. Legs exit at
       different times, so market exposure drifts, and the market-neutrality that
       made this sleeve attractive is partly given up. That is the trade being
       measured, not a detail to hide - the reported long/short trade counts show how
       far from balanced it runs.

    3. RANK AS A FILTER on the breakout signal. Keep the trend book exactly as it is
       and only take a long if the coin is also top-k on relative momentum. This
       keeps neutrality out of it and asks a narrower question: does cross-sectional
       rank add information to a breakout?

    Then the only thing that actually matters: CORRELATION with the 1h trend book.
    A sleeve worth adding must be uncorrelated. 1h vs 4h came out at 0.178, which is
    what made that blend worth having.

REGISTERED PREDICTION (2026-09-13, before running)
    The hold sweep improves out to several hundred bars - the time cap is real.
    Design 2 earns more than the original but loses the neutrality, so its
    correlation to the trend book rises above 0.5 and it stops being a diversifier.
    Design 3 is the one I expect to be useless, because 19 indicator families already
    showed that entry timing is not where the edge lives.

    If design 2 comes out BOTH profitable and correlated below ~0.3, that is the
    missing sleeve and it matters more than anything else measured today.

    python -m backtest.xs_convex
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import run_uncapped  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.shortside import signals as bb_signals  # noqa: E402
from backtest.timeframes import MIN_ORDER  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
SL_MULT, BE_AT = 2.0, 3.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MAX_UNITS, ADD_EVERY = 5, 2.0
RISK, SLOTS = 0.30, 8
HINDSIGHT = 3.0
LB, K = 168, 4                 # lookback and coins per side, from CENTRAL
# THE 8 WITH LONG HISTORY, not the 12.
#
# The first run of this file used all 12 and the panel - an INTERSECTION, because
# cross-sectional ranking needs every coin present on every bar - collapsed to
# 2024-04 -> 2026-09 because ENA lists from April 2024. Every rank design was then
# measured on 2.4 weak years while the "unfiltered control" ran the full 6.5 years
# including 2021, so the comparison was meaningless. Same trap as the 190-day MCPT
# stub earlier in this project: an intersection is only as long as its newest member.
#
# Dropping ENA, SUI, WLD and ARB gives ~5.3 years. k is capped at 4 (8 coins, 4 per
# side leaves nothing in the middle).
BOOK = ["XRPUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "SHIBUSDT", "NEARUSDT", "DOTUSDT"]
_D: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def panel():
    """Close matrix on the intersection of the book's timestamps."""
    fr = {}
    for c in BOOK:
        d = load(c)
        if d is not None and len(d) > 3000:
            fr[c] = d.set_index("time")["close"]
    C = pd.DataFrame(fr).dropna()
    return C


def rank_signals(C, lb=LB, k=K):
    """BUY the bar a coin ENTERS the top k, SELL the bar it enters the bottom k.

    Shifted one bar: the rank is known at close[t] and acted on at open[t+1], which
    is the same causality the rest of the project uses. Using the unshifted rank
    would be trading on information from the bar being traded.
    """
    mom = C / C.shift(lb) - 1.0
    r_hi = mom.rank(axis=1, ascending=False)
    r_lo = mom.rank(axis=1, ascending=True)
    top = (r_hi <= k) & mom.notna()
    bot = (r_lo <= k) & mom.notna()
    ent_l = top & ~top.shift(1).fillna(False)
    ent_s = bot & ~bot.shift(1).fillna(False)
    return ent_l.shift(1).fillna(False), ent_s.shift(1).fillna(False)


def to_series(df, mask_col):
    """Align a boolean column from the panel onto one coin's own frame."""
    s = pd.Series(False, index=pd.DatetimeIndex(df["time"]))
    common = s.index.intersection(mask_col.index)
    s.loc[common] = mask_col.loc[common].to_numpy(bool)
    return s.to_numpy(bool)


def trades_from(mask_l, mask_s, filt_l=None, filt_s=None, use_bb=False):
    """Build trades for every coin from boolean entry masks."""
    tr, stops = [], {}
    for c in BOOK:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        a = (atr_ind(df, 14) / df["close"]).replace([np.inf, -np.inf],
                                                    np.nan).dropna()
        if len(a):
            stops[c] = float(a.median()) * SL_MULT
        t = df["time"].to_numpy()
        if use_bb:
            sig_l = bb_signals(df, "long", "all").to_numpy()
            sig_s = bb_signals(df, "short", "all").to_numpy()
            if filt_l is not None:
                sig_l = np.where(to_series(df, filt_l[c]), sig_l, Action.HOLD)
                sig_s = np.where(to_series(df, filt_s[c]), sig_s, Action.HOLD)
            sl_ = pd.Series(sig_l, index=df.index)
            ss_ = pd.Series(sig_s, index=df.index)
        else:
            L = to_series(df, mask_l[c]); S = to_series(df, mask_s[c])
            sl_ = pd.Series(np.where(L, Action.BUY, Action.HOLD), index=df.index)
            ss_ = pd.Series(np.where(S, Action.SELL, Action.HOLD), index=df.index)
        if int((sl_ != Action.HOLD).sum()):
            R, idx, _u, held = run_pyramid(df, sl_, sl_mult=SL_MULT,
                                           trail=LONG_TRAIL, max_units=MAX_UNITS,
                                           add_every=ADD_EVERY, fee_bp=FEE_BP,
                                           breakeven_at=BE_AT)
            tr += [(t[max(int(i) - int(h), 0)], t[int(i)], float(r), "L")
                   for r, i, h in zip(R, idx, held)]
        if int((ss_ != Action.HOLD).sum()):
            R, idx, bars, _d = run_uncapped(df, ss_, sl_mult=SL_MULT,
                                            fee_bp=FEE_BP, mode="trail_atr",
                                            trail=SHORT_TRAIL, be_at=BE_AT)
            tr += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r), "S")
                   for r, i, b in zip(R, idx, bars)]
    tr.sort(key=lambda x: x[0])
    return tr, stops


def book_stats(tr, stops, slots=SLOTS, risk=RISK):
    f = risk / 100.0
    eq, curve, times, opens = 1.0, [], [], []
    Rs, sides = [], []
    ruined = False
    for a_, b_, r, side in tr:
        opens = [u for u in opens if u > a_]
        if len(opens) >= slots:
            continue
        opens.append(b_)
        Rs.append(r); sides.append(side)
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 0.01:
                eq, ruined = 0.0, True
        curve.append(eq); times.append(b_)
    if len(Rs) < 30:
        return None
    R = np.asarray(Rs); cur = np.asarray(curve)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    hc = cagr / HINDSIGHT if cagr > -100 else -100.0
    floor = (max(MIN_ORDER[c] * stops[c] for c in stops) / (risk / 100.0)
             / (1 - dd / 100.0)) if dd < 99.0 and stops else float("nan")
    return dict(n=len(R), nL=sides.count("L"), nS=sides.count("S"),
                mean=float(R.mean()), win=float((R > 0).mean() * 100),
                dd=dd, cagr=cagr, ruined=ruined, floor=floor, times=ts, R=R,
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0)


def monthly(d):
    return pd.Series(d["R"], index=d["times"]).resample("ME").sum()


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: the hold sweep improves (time cap is real);")
    print("design 2 earns more but loses neutrality so correlation rises above 0.5;")
    print("design 3 is useless. A profitable design 2 with correlation under 0.3 is")
    print("the missing sleeve.\n")

    C = panel()
    print(f"panel: {C.shape[1]} coins x {len(C):,} bars  "
          f"{C.index[0].date()} -> {C.index[-1].date()}\n")

    # ---- 1. is the fixed hold a TIME CAP? --------------------------------
    print("=" * 112)
    print("1. TIME-CAP TEST — original rebalancing engine, hold swept")
    print("=" * 112)
    try:
        from backtest.xs_momentum import simulate as xs_sim
        O = pd.DataFrame({c: load(c).set_index("time")["open"] for c in BOOK})
        Cl = pd.DataFrame({c: load(c).set_index("time")["close"] for c in BOOK})
        F = pd.DataFrame(0.0, index=Cl.index, columns=Cl.columns)
        idx = O.dropna().index.intersection(Cl.dropna().index)
        O, Cl, F = O.loc[idx], Cl.loc[idx], F.loc[idx]
        print(f"{'hold (bars)':>12} {'sharpe':>8} {'CAGR':>9} {'DD':>7} "
              f"{'turnover':>9}")
        for h in (24, 48, 96, 168, 336, 720):
            s = xs_sim(O, Cl, F, lb=LB, hold=h, k=K, er_min=0.0, invvol=False,
                       fee_bp=FEE_BP)
            if not s:
                continue
            print(f"{h:>12} {s.get('sharpe', float('nan')):>+8.3f} "
                  f"{s.get('cagr', float('nan')):>+8.1f}% "
                  f"{s.get('dd', float('nan')):>6.1f}% "
                  f"{s.get('turn', float('nan')):>9.2f}", flush=True)
    except Exception as e:
        print(f"  original engine unavailable here: {type(e).__name__}: "
              f"{str(e)[:120]}")
        print("  (panels 2 and 3 do not depend on it)")
    print()

    # ---- 2. rank as entry, trail as exit --------------------------------
    print("=" * 112)
    print("2. RANK AS ENTRY, TRAIL AS EXIT — pyramid + 20x/5x trails, 8 slots")
    print("=" * 112)
    hdr = (f"{'design':<34} {'n':>6} {'L/S':>11} {'meanR':>8} {'win%':>6} "
           f"{'HONEST /mo':>11} {'DD':>7} {'floor $':>9}")
    print(hdr)
    res = {}
    for k in (1, 2, 3, 4):
        el, es = rank_signals(C, LB, k)
        tr, st = trades_from({c: el[c] for c in BOOK}, {c: es[c] for c in BOOK})
        d = book_stats(tr, st)
        if d:
            res[f"rank k={k}"] = d
            print(f"{'rank entry k='+str(k):<34} {d['n']:>6} "
                  f"{d['nL']:>5}/{d['nS']:<5} {d['mean']:>+8.3f} {d['win']:>6.1f} "
                  f"{d['hpm']:>+10.2f}% {d['dd']:>6.1f}% {d['floor']:>9,.0f}",
                  flush=True)
    print()

    # ---- 3. rank as a FILTER on the breakout ----------------------------
    print("=" * 112)
    print("3. RANK AS A FILTER on the breakout signal")
    print("=" * 112)
    print(hdr)
    mom = C / C.shift(LB) - 1.0
    for k in (2, 3, 4):
        r_hi = mom.rank(axis=1, ascending=False)
        r_lo = mom.rank(axis=1, ascending=True)
        fl = ((r_hi <= k) & mom.notna()).shift(1).fillna(False)
        fs = ((r_lo <= k) & mom.notna()).shift(1).fillna(False)
        tr, st = trades_from(None, None, {c: fl[c] for c in BOOK},
                             {c: fs[c] for c in BOOK}, use_bb=True)
        d = book_stats(tr, st)
        if d:
            res[f"bb+rank k={k}"] = d
            print(f"{'bb_break, top/bottom '+str(k)+' only':<34} {d['n']:>6} "
                  f"{d['nL']:>5}/{d['nS']:<5} {d['mean']:>+8.3f} {d['win']:>6.1f} "
                  f"{d['hpm']:>+10.2f}% {d['dd']:>6.1f}% {d['floor']:>9,.0f}",
                  flush=True)
    # UNFILTERED CONTROL, RESTRICTED TO THE PANEL'S WINDOW. Without this clamp the
    # control trades 2020-2026 while every filtered variant can only trade inside the
    # panel, so the control wins on having owned 2021 rather than on being unfiltered.
    allow = pd.DataFrame(True, index=C.index, columns=C.columns)
    tr, st = trades_from(None, None, {c: allow[c] for c in BOOK},
                         {c: allow[c] for c in BOOK}, use_bb=True)
    ctl = book_stats(tr, st)
    if ctl:
        res["bb unfiltered"] = ctl
        print(f"{'bb_break UNFILTERED (control)':<34} {ctl['n']:>6} "
              f"{ctl['nL']:>5}/{ctl['nS']:<5} {ctl['mean']:>+8.3f} "
              f"{ctl['win']:>6.1f} {ctl['hpm']:>+10.2f}% {ctl['dd']:>6.1f}% "
              f"{ctl['floor']:>9,.0f}")
    print()

    # ---- 4. THE ONLY THING THAT MATTERS: correlation --------------------
    print("=" * 112)
    print("4. CORRELATION WITH THE TREND BOOK — a sleeve is only worth adding if "
          "it is uncorrelated")
    print("=" * 112)
    if "bb unfiltered" not in res or len(res) < 2:
        print("  not enough sleeves to correlate")
        return
    m = pd.DataFrame({k: monthly(v) for k, v in res.items()}).dropna()
    if len(m) < 12:
        print(f"  only {len(m)} overlapping months — UNMEASURABLE, no conclusion")
        return
    base = m["bb unfiltered"]
    print(f"  {len(m)} overlapping months, against the unfiltered breakout book\n")
    print(f"{'sleeve':<20} {'corr':>7} {'own /mo':>9} {'own DD':>8}  verdict")
    for k in m.columns:
        if k == "bb unfiltered":
            continue
        c = float(np.corrcoef(m[k], base)[0, 1])
        d = res[k]
        v = ("DIVERSIFIER" if c < 0.3 and d["hpm"] > 0 else
             "same bet" if c >= 0.6 else "partial")
        print(f"{k:<20} {c:>+7.3f} {d['hpm']:>+8.2f}% {d['dd']:>7.1f}%  {v}")
    print("\n  For reference, 1h vs 4h trend measured +0.178 and that blend turned")
    print("  two losing years positive. Anything under ~0.3 with a positive return")
    print("  is worth blending; above 0.6 it is the same bet with extra fees.")


if __name__ == "__main__":
    main()
