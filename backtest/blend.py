"""BLENDING TIMEFRAMES — two versions of one edge that do not fire together.

WHAT backtest/timeframes.py FOUND
    The same rules on different bar sizes are NOT the same strategy. Mean R per
    trade, by year:

        bars    2020    2021    2022    2023    2024    2025    2026
        1h     +1.34   +5.20   -0.49   +2.06   +3.04   +0.03   +0.26
        4h     +1.87  +17.78   +0.43   +0.19  +11.33   +0.58   +0.58
        12h    +2.54  +41.76   +1.44   -1.00   +2.38   -0.11   -0.50

    2023 was the 1h book's year and 4h did almost nothing. 2024 was 4h's year and
    1h barely moved. And 4h is the ONLY timeframe still positive in both 2025 and
    2026 - the stretch where the 1h book earned 2.5% of its lifetime profit.

    That pattern is what a genuinely different return stream looks like. Same signal,
    different sampling of it, and the years do not line up.

WHY THIS IS NOT JUST DOUBLING THE SAME BET
    A fair objection: it is one signal (Bollinger breakout) on one universe, so the
    sleeves must be correlated. They are - but not identically, and the by-year table
    is the evidence. A 1h bar closing above its band and a 4h bar closing above its
    band are different events, happen at different times, and get different stops
    because ATR scales with the bar.

    The test reports the CORRELATION of the two sleeves' monthly returns, so the
    diversification is measured rather than assumed. If it comes out above ~0.8 the
    blend is mostly one bet and the drawdown will not improve.

WHAT IS TESTED
    Sleeves share ONE slot cap, so the blend cannot secretly run double exposure -
    the trap that would make any combination look good. Slot counts are swept because
    two sleeves generate more signals than one and the inherited 8 may now bind.

    The one validated improvement from opt200.py - cut risk to a quarter while BTC is
    below its 200h average - is carried into every row.

    Split 60/40 in time: tune on the first, decide on the last.

REGISTERED PREDICTION (2026-09-13, before running)
    The blend beats 1h alone on DRAWDOWN and on the 2025-2026 stretch, and lands
    between the two sleeves on total return. Monthly correlation ~0.5-0.7. If the
    correlation comes out above 0.85, the blend is one bet and this is a dead end.

    python -m backtest.blend
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
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import MIN_ORDER, resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

FEE_BP = 12.0
SL_MULT, BE_AT = 2.0, 3.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MAX_UNITS, ADD_EVERY = 5, 2.0
RISK = 0.30
HINDSIGHT = 3.0
REGIME_MULT = 0.25              # validated in opt200.py
BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT"]
_D: dict = {}
_S: dict = {}
_BTC = None


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def btc_bear():
    global _BTC
    if _BTC is None:
        d = load("BTCUSDT")
        ma = d["close"].rolling(200).mean()
        _BTC = pd.Series((d["close"] < ma).shift(1).fillna(False).to_numpy(bool),
                         index=pd.DatetimeIndex(d["time"]))
    return _BTC


def sleeve(rule):
    """Trades for one timeframe, tagged with it. Cached — each sleeve is built once
    and then reused across every slot count and combination."""
    if rule in _S:
        return _S[rule]
    tr, stops = [], {}
    for c in BOOK:
        d = load(c)
        if d is None:
            continue
        df = resample(d, rule)
        if len(df) < 300:
            continue
        a = (atr_ind(df, 14) / df["close"]).replace([np.inf, -np.inf],
                                                    np.nan).dropna()
        if len(a):
            stops[c] = float(a.median()) * SL_MULT
        t = df["time"].to_numpy()
        R, idx, _u, held = run_pyramid(df, signals(df, "long", "all"),
                                       sl_mult=SL_MULT, trail=LONG_TRAIL,
                                       max_units=MAX_UNITS, add_every=ADD_EVERY,
                                       fee_bp=FEE_BP, breakeven_at=BE_AT)
        tr += [(t[max(int(i) - int(h), 0)], t[int(i)], float(r), rule, c)
               for r, i, h in zip(R, idx, held)]
        R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"),
                                        sl_mult=SL_MULT, fee_bp=FEE_BP,
                                        mode="trail_atr", trail=SHORT_TRAIL,
                                        be_at=BE_AT)
        tr += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r), rule, c)
               for r, i, b in zip(R, idx, bars)]
    _S[rule] = (tr, stops)
    return _S[rule]


def run(rules, slots, t_from=None, t_to=None, regime=REGIME_MULT):
    tr, stops = [], {}
    for r in rules:
        a, s = sleeve(r)
        tr += a
        for k, v in s.items():
            stops[k] = max(stops.get(k, 0.0), v)   # worst stop across sleeves
    tr.sort(key=lambda x: x[0])
    bear = btc_bear() if regime > 0 else None
    f0 = RISK / 100.0
    eq, curve, times, opens = 1.0, [], [], []
    Rs, tags = [], []
    declined = 0
    ruined = False
    for a_, b_, r, tag, _c in tr:
        if t_from is not None and a_ < t_from:
            continue
        if t_to is not None and a_ >= t_to:
            continue
        opens = [u for u in opens if u > a_]
        if len(opens) >= slots:
            declined += 1
            continue
        opens.append(b_)
        f = f0
        if bear is not None:
            try:
                if bool(bear.asof(a_)):
                    f *= regime
            except Exception:
                pass
        Rs.append(r); tags.append(tag)
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
    floor = max(MIN_ORDER[c] * stops[c] for c in stops) / (RISK / 100.0)
    floor = floor / (1 - dd / 100.0) if dd < 99.0 else float("nan")
    return dict(n=len(R), declined=declined, mean=float(R.mean()), dd=dd,
                cagr=cagr, ruined=ruined, floor=floor, times=ts, R=R,
                tags=np.asarray(tags),
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0)


def monthly(d):
    """Monthly R sum — the series used for the sleeve correlation.

    CALENDAR months ("ME"), not "30D". A 30-day resample anchors its bins to each
    series' OWN first timestamp, so two sleeves that start days apart get bin edges
    that never coincide; joining them produced zero overlapping rows and a NaN
    correlation matrix, off which the script then printed "genuinely different
    streams". Calendar months give both sleeves identical bin edges.
    """
    s = pd.Series(d["R"], index=d["times"])
    return s.resample("ME").sum()


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: the blend wins on DRAWDOWN and on 2025-2026,")
    print("lands between the sleeves on return, monthly correlation 0.5-0.7. Above")
    print("0.85 and it is one bet and a dead end.\n")

    # --- is it actually diversification? measure it before anything else ------
    print("=" * 118)
    print("1. ARE THE SLEEVES ACTUALLY DIFFERENT? monthly-return correlation")
    print("=" * 118)
    solo = {}
    for r in ("1h", "4h", "12h"):
        d = run([r], 8)
        if d:
            solo[r] = d
            print(f"  {r:<4} n {d['n']:>6}  mean R {d['mean']:>+7.3f}  "
                  f"DD {d['dd']:>5.1f}%  honest {d['hpm']:>+6.2f}%/mo")
    if len(solo) >= 2:
        m = pd.DataFrame({k: monthly(v) for k, v in solo.items()}).dropna()
        print(f"\n  monthly correlation ({len(m)} overlapping 30-day blocks):")
        print("    " + str(m.corr().round(3)).replace("\n", "\n    "))
        c14 = float(m.corr().loc["1h", "4h"]) if {"1h", "4h"} <= set(m.columns) else np.nan
        if not np.isfinite(c14) or len(m) < 12:
            print(f"\n  1h vs 4h = UNMEASURABLE ({len(m)} overlapping months) — "
                  f"draw NO conclusion about diversification from this run")
        else:
            print(f"\n  1h vs 4h = {c14:.3f} over {len(m)} months -> "
                  f"{'ONE BET, dead end' if c14 > 0.85 else 'genuinely different streams'}")
    print()

    # --- the blend, swept on slots, with a holdout ---------------------------
    all1 = sleeve("1h")[0]
    ts_all = pd.DatetimeIndex(sorted(x[0] for x in all1))
    cut = ts_all[int(len(ts_all) * 0.6)]
    print("=" * 118)
    print(f"2. THE BLEND — sleeves share ONE slot cap.  split at {cut.date()}")
    print("=" * 118)
    print(f"{'combination':<22} {'slots':>5} | {'TUNE (first 60%)':^32} | "
          f"{'DECIDE (last 40%)':^32}")
    print(f"{'':<22} {'':>5} | {'/mo':>9} {'DD':>7} {'floor':>8} {'n':>5} | "
          f"{'/mo':>9} {'DD':>7} {'floor':>8} {'n':>5}")
    rows = []
    combos = [(("1h",), "1h only"), (("4h",), "4h only"),
              (("1h", "4h"), "1h + 4h"), (("1h", "4h", "12h"), "1h + 4h + 12h")]
    for rules, label in combos:
        for slots in (8, 12, 16):
            a = run(rules, slots, t_to=cut)
            b = run(rules, slots, t_from=cut)
            if not (a and b):
                continue
            rows.append((label, rules, slots, a, b))
            print(f"{label:<22} {slots:>5} | {a['hpm']:>+8.2f}% {a['dd']:>6.1f}% "
                  f"{a['floor']:>8,.0f} {a['n']:>5} | {b['hpm']:>+8.2f}% "
                  f"{b['dd']:>6.1f}% {b['floor']:>8,.0f} {b['n']:>5}", flush=True)
        print()

    # --- the year-by-year test, which is the real point ---------------------
    print("=" * 118)
    print("3. BY YEAR — does the blend survive 2025-2026, where 1h went flat?")
    print("=" * 118)
    full = {}
    for rules, label in combos:
        d = run(rules, 12)
        if d:
            full[label] = d
    years = sorted({y for d in full.values() for y in set(d["times"].year)})
    print(f"{'combination':<22} " + " ".join(f"{y:>9}" for y in years)
          + f" {'DD':>7} {'/mo':>8}")
    for label, d in full.items():
        cells = []
        for y in years:
            m = d["times"].year == y
            if m.sum() < 10:
                cells.append(f"{'-':>9}")
            else:
                # yearly return at the live risk, not mean R, so the years are
                # comparable in the units that matter
                cells.append(f"{d['R'][m].sum()*RISK/100*100:>+8.0f}%")
        print(f"{label:<22} " + " ".join(cells)
              + f" {d['dd']:>6.1f}% {d['hpm']:>+7.2f}%")
    print("\n  (yearly return at 0.30%/unit, summed R x risk - not compounded, so")
    print("   the columns are comparable rather than exact.)")

    print("\n" + "=" * 118)
    print("VERDICT")
    print("=" * 118)
    base = next((r for r in rows if r[0] == "1h only" and r[2] == 8), None)
    if not base:
        return
    print(f"  1h alone, out of sample: {base[4]['hpm']:+.2f}%/month  "
          f"DD {base[4]['dd']:.1f}%  floor ${base[4]['floor']:,.0f}")
    keep = [r for r in rows if r[0] != "1h only"
            and r[4]["hpm"] >= base[4]["hpm"] and r[4]["dd"] <= base[4]["dd"]]
    if not keep:
        print("  Nothing beat it on both return and drawdown out of sample.")
        print("  The sleeves differ by year but the blend does not pay for itself -")
        print(f"  and {len(rows)} cells were searched, so a marginal winner would be")
        print("  noise anyway.")
    else:
        keep.sort(key=lambda r: r[4]["floor"])
        for label, rules, slots, a, b in keep:
            print(f"  {label:<22} {slots:>2} slots  OUT {b['hpm']:+6.2f}%/mo  "
                  f"DD {b['dd']:5.1f}%  floor ${b['floor']:,.0f}")
        print(f"\n  {len(keep)} of {len(rows)} cells. Believe one only if its")
        print("  neighbouring slot counts improved too.")


if __name__ == "__main__":
    main()
