"""VALIDATING THE $200 CONFIGURATION — the three tests it has not passed yet.

THE CONFIGURATION UNDER TEST
    12 cheap-but-reputable alts, 8 shared slots, 0.30%/unit, breakeven at 3R,
    long pyramid 5 units / 20xATR trail, short 1 unit / 5xATR trail.
    Measured: +13.93%/month honest, 87.6% drawdown, ~$200 capital floor on MEXC.

    That figure comes from ONE pass over ONE history with parameters chosen after
    seeing that history. Before it gets real money it needs to survive tests that
    can actually fail.

THREE TESTS
    1. MCPT, shared-index permutation. Shuffle the bars so every coin keeps its
       return distribution and its correlation to the others, but loses all serial
       structure. If the real result is not clearly outside the permuted
       distribution, the strategy is reading noise.

       SHARED index, not per-coin: permuting each coin separately would destroy
       contemporaneous correlation too, which makes the permuted world far easier to
       beat and the p-value meaninglessly optimistic.

       Run on the 8 of 12 coins with long history. get_permutation_multi requires an
       identical index, and intersecting all 12 would collapse the window to ENA's
       21,443 bars - the exact trap that made an earlier MCPT test a 190-day stub and
       produced an unusable p-value. 8 coins keeps ~46,800 bars (5.3 years).

    2. SURVIVORSHIP. Run the identical rules on the 199 DELISTED coins, closing any
       position open at the end. The 12 coins in the book are alive today; if the
       edge only exists on survivors it will vanish here. This is the test the alt
       book most needs, because 12 alts is precisely where survivorship hides.

    3. TIME SPLIT. Parameters (0.30% risk, BE@3R, 8 slots, the two trail widths) were
       all chosen with this history visible. Split 60/40 and also report per year, so
       a result that only exists in one regime is visible.

WHAT WOULD CONSTITUTE FAILURE - written before running
    1. MCPT p > 0.05 on mean R.
    2. Dead-coin mean R <= 0. (A LOWER mean than the live book is expected and fine:
       these coins died. NEGATIVE means the edge needs survivors.)
    3. Either time half negative, or the result concentrated in a single year.

    Any of those and the $200 configuration is not fit for real money regardless of
    what the headline said.

    python -m backtest.val200 --perms 150
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import run_uncapped  # noqa: E402
from backtest.dead_fetch import DEAD  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.permute import get_permutation_multi  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.shortside import signals  # noqa: E402

FEE_BP = 12.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MAX_UNITS, ADD_EVERY, BE_AT = 5, 2.0, 3.0
SL_MULT = 2.0
RISK = 0.30
SLOTS = 8
HINDSIGHT = 3.0

BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT"]
# the 8 with enough history for a permutation window worth having
LONG_HIST = ["XRPUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
             "SHIBUSDT", "NEARUSDT", "DOTUSDT"]
_D: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def trades(df, close_at_end=None):
    """(entry_time, exit_time, R) for both sleeves, identical rules everywhere."""
    t = df["time"].to_numpy()
    out = []
    R, idx, _u, held = run_pyramid(df, signals(df, "long", "all"),
                                   sl_mult=SL_MULT, trail=LONG_TRAIL,
                                   max_units=MAX_UNITS, add_every=ADD_EVERY,
                                   fee_bp=FEE_BP, breakeven_at=BE_AT)
    out += [(t[max(int(i) - int(h), 0)], t[int(i)], float(r))
            for r, i, h in zip(R, idx, held)]
    R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"),
                                    sl_mult=SL_MULT, fee_bp=FEE_BP,
                                    mode="trail_atr", trail=SHORT_TRAIL,
                                    be_at=BE_AT, close_at_end=close_at_end)
    out += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r))
            for r, i, b in zip(R, idx, bars)]
    return out


def portfolio(frames, risk=RISK, slots=SLOTS, close_at_end=None):
    tr = []
    for df in frames:
        if df is None or len(df) < 3000:
            continue
        tr += trades(df, close_at_end)
    if len(tr) < 30:
        return None
    tr.sort(key=lambda x: x[0])
    f = risk / 100.0
    eq, curve, times, opens, Rs = 1.0, [], [], [], []
    ruined = False
    for a, b, r in tr:
        opens = [u for u in opens if u > a]
        if len(opens) >= slots:
            continue
        opens.append(b)
        Rs.append(r)
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 0.01:
                eq, ruined = 0.0, True
        curve.append(eq); times.append(b)
    if len(Rs) < 30:
        return None
    R = np.asarray(Rs); cur = np.asarray(curve)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    hc = cagr / HINDSIGHT if cagr > -100 else -100.0
    return dict(n=len(R), mean=float(R.mean()), win=float((R > 0).mean() * 100),
                pf=float(R[R > 0].sum() / -R[R < 0].sum()) if (R < 0).any() else np.inf,
                cagr=cagr, dd=dd, ruined=ruined, times=ts, R=R,
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0)


def common_frames(names):
    """Identical time index across coins — required by get_permutation_multi."""
    fr = {}
    for c in names:
        d = load(c)
        if d is not None and len(d) > 3000:
            fr[c] = d.set_index("time")
    if len(fr) < 2:
        return None, None
    idx = None
    for d in fr.values():
        idx = d.index if idx is None else idx.intersection(d.index)
    if idx is None or len(idx) < 5000:
        raise SystemExit(f"common index only {0 if idx is None else len(idx)} bars — "
                         "too short to permute; drop a short-history coin")
    out = [fr[c].loc[idx].reset_index() for c in fr]
    return out, idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perms", type=int, default=150)
    args = ap.parse_args()
    print(__doc__.split("WHAT WOULD CONSTITUTE FAILURE")[0].rstrip())
    print("\nFAILURE CRITERIA, FIXED NOW: MCPT p>0.05 | dead-coin mean R <= 0 |")
    print("either time half negative. Any one of those and $200 is not fit for "
          "real money.\n")

    base = portfolio([load(c) for c in BOOK])
    if not base:
        raise SystemExit("baseline produced nothing")
    print("=" * 110)
    print("BASELINE — the configuration as quoted")
    print("=" * 110)
    print(f"  {base['n']:,} trades  mean R {base['mean']:+.4f}  win {base['win']:.1f}%"
          f"  PF {base['pf']:.2f}  CAGR {base['cagr']:+.1f}%  DD {base['dd']:.1f}%"
          f"  honest {base['hpm']:+.2f}%/month")

    # ---------------- 1. MCPT --------------------------------------------
    print("\n" + "=" * 110)
    print(f"1. MCPT — shared-index permutation, {args.perms} permutations")
    print("=" * 110)
    frames, idx = common_frames(LONG_HIST)
    print(f"  {len(frames)} coins, common index {len(idx):,} bars "
          f"({(idx[-1]-idx[0]).days/365.25:.2f} years) "
          f"{idx[0].date()} -> {idx[-1].date()}")
    real = portfolio(frames)
    if not real:
        raise SystemExit("real run on the common index produced nothing")
    print(f"  REAL on this subset: mean R {real['mean']:+.4f}  "
          f"CAGR {real['cagr']:+.1f}%  n {real['n']:,}")
    start = 400                      # leave warm-up for BB(30) and ATR(14)
    perm_mean, perm_cagr = [], []
    for i in range(args.perms):
        try:
            pf_ = get_permutation_multi(frames, start_index=start, seed=1000 + i)
            d = portfolio(pf_)
        except Exception as e:
            print(f"    perm {i} failed: {type(e).__name__}: {str(e)[:70]}")
            continue
        if d:
            perm_mean.append(d["mean"]); perm_cagr.append(d["cagr"])
        if (i + 1) % 25 == 0:
            pm = np.asarray(perm_mean)
            print(f"    {i+1:>4}/{args.perms}  permuted mean R "
                  f"{pm.mean():+.4f} +/- {pm.std(ddof=1):.4f}   "
                  f"beaten by real: {int((pm >= real['mean']).sum())}", flush=True)
    pm = np.asarray(perm_mean); pc = np.asarray(perm_cagr)
    if len(pm) < 10:
        print("  too few successful permutations to judge")
    else:
        k_m = int((pm >= real["mean"]).sum())
        k_c = int((pc >= real["cagr"]).sum())
        p_m = (k_m + 1) / (len(pm) + 1)
        p_c = (k_c + 1) / (len(pc) + 1)
        print(f"\n  permuted mean R : {pm.mean():+.4f} +/- {pm.std(ddof=1):.4f}  "
              f"(real {real['mean']:+.4f})")
        print(f"  permuted CAGR   : {pc.mean():+.1f}% +/- {pc.std(ddof=1):.1f}%  "
              f"(real {real['cagr']:+.1f}%)")
        print(f"  p(mean R) = {p_m:.4f}   ({k_m} of {len(pm)} permutations "
              f"matched or beat the real result)")
        print(f"  p(CAGR)   = {p_c:.4f}   ({k_c} of {len(pc)})")
        print(f"  VERDICT: {'PASS' if p_m <= 0.05 else 'FAIL'} at the "
              f"pre-registered 0.05 bar")

    # ---------------- 2. SURVIVORSHIP ------------------------------------
    print("\n" + "=" * 110)
    print("2. SURVIVORSHIP — identical rules on the 199 DELISTED coins")
    print("=" * 110)
    dead = []
    for f in sorted(DEAD.glob("*_1h.csv.gz")):
        try:
            d = pd.read_csv(f, parse_dates=["time"])
        except Exception:
            continue
        if len(d) >= 3000:
            dead.append(d)
    print(f"  {len(dead)} delisted coins with >= 3000 bars")
    for mode, label in (("close", "exit at last close (announced delisting)"),
                        ("stop", "exit at the stop (collapse)")):
        d = portfolio(dead, close_at_end=mode)
        if not d:
            print(f"  {label}: no result")
            continue
        print(f"  {label}")
        print(f"    {d['n']:,} trades  mean R {d['mean']:+.4f}  "
              f"win {d['win']:.1f}%  PF {d['pf']:.2f}  DD {d['dd']:.1f}%"
              f"{'  RUIN' if d['ruined'] else ''}")
    print(f"\n  live book mean R for comparison: {base['mean']:+.4f}")
    print("  A LOWER mean on dead coins is expected and fine - they died. NEGATIVE")
    print("  would mean the edge needs survivors, which is the failure case.")

    # ---------------- 3. TIME SPLIT --------------------------------------
    print("\n" + "=" * 110)
    print("3. TIME SPLIT — parameters were chosen with all of this visible")
    print("=" * 110)
    T, R = base["times"], base["R"]
    cut = T[int(len(T) * 0.6)]
    for label, m in (("first 60%", T < cut), ("last 40%", T >= cut)):
        r = R[m]
        if len(r) < 30:
            continue
        se = r.std(ddof=1) / np.sqrt(len(r))
        print(f"  {label:<10} {T[m][0].date()} -> {T[m][-1].date()}  "
              f"n {len(r):>6}  mean R {r.mean():+.4f} +/- {se:.4f}  "
              f"t {r.mean()/se:+.2f}  win {float((r>0).mean())*100:.1f}%")
    print()
    for y in sorted(set(T.year)):
        m = T.year == y
        r = R[m]
        if len(r) < 30:
            continue
        print(f"  {y}  n {len(r):>6}  mean R {r.mean():+.4f}  "
              f"win {float((r>0).mean())*100:>5.1f}%  "
              f"sumR {r.sum():>+9.1f}")
    print("\n  A result carried by ONE year is a regime, not an edge.")


if __name__ == "__main__":
    main()
