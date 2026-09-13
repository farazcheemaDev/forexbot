"""RE-RUNNING TODAY'S CONCLUSIONS UNDER A PESSIMISTIC FILL.

THE ASSUMPTION BEING CORRECTED
    Every engine in this project advances the trailing stop using the CURRENT bar's
    favourable extreme, then checks that stop from the NEXT bar onward. A bar's high
    and low happen in unknown order, so if the newly advanced stop sits inside the
    same bar's range, it would in reality already have filled.

    convex.py has always documented this as "mildly optimistic". It is mild when the
    stop sits far from price - a 20xATR long trail. It is NOT mild for a 5xATR short
    trail, which sits close. backtest/exitlab.py measured the difference at ~0.07R per
    short trade, which is LARGER THAN THE SHORT SLEEVE'S ENTIRE EDGE: the sleeve went
    from +0.034 to -0.036.

    Every two-sided result produced today used the optimistic convention. That
    includes the $200 configuration, the drawdown reductions, and the timeframe
    blend's rescue of 2022 and 2025 - all of which lean on the short sleeve.

WHAT THIS FILE DECIDES
    Whether the short sleeve survives an honest fill. Three outcomes:
      * it survives           -> nothing changes, today's numbers stand
      * it goes to ~zero      -> shorts are a drawdown hedge, not a profit source,
                                 and the return figures must be restated long-only
      * it goes negative      -> the strategy is long-only plus a regime gate, and
                                 the bear-year rescue was an artifact

    Every comparison is run BOTH ways side by side so the size of the correction is
    visible rather than asserted.

WHY THE CORRECTION IS NOT ITSELF PESSIMISTIC-BIASED
    The strict rule can only ever CLOSE a position earlier than the optimistic rule,
    never later, so it is a strict lower bound rather than a different estimate. The
    truth sits between the two, and where exactly depends on the intrabar path, which
    hourly bars cannot show. Reporting both brackets it honestly; reporting only the
    optimistic one is what has been happening.

    It is applied to BOTH sleeves. Applying it to shorts alone would rig the
    comparison in the direction of the conclusion I now expect.

REGISTERED PREDICTION (2026-09-13, before running)
    The long sleeve loses under 0.01R (its trail is far from price). The short sleeve
    goes to zero or slightly negative. The two-sided book therefore loses roughly the
    short sleeve's whole contribution, and long-only-plus-regime-gate becomes the best
    configuration. The 2022 and 2025 rescue shrinks but does not vanish, because part
    of it came from shorts simply not being long during a fall.

    python -m backtest.strictfill
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
RISK, SLOTS = 0.30, 8
HINDSIGHT = 3.0
REGIME_MULT = 0.25
BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT"]
_D: dict = {}
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


def sleeve(rule, side, strict):
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
        if side in ("long", "both"):
            R, idx, _u, held = run_pyramid(df, signals(df, "long", "all"),
                                           sl_mult=SL_MULT, trail=LONG_TRAIL,
                                           max_units=MAX_UNITS,
                                           add_every=ADD_EVERY, fee_bp=FEE_BP,
                                           breakeven_at=BE_AT,
                                           strict_fill=strict)
            tr += [(t[max(int(i) - int(h), 0)], t[int(i)], float(r), "L")
                   for r, i, h in zip(R, idx, held)]
        if side in ("short", "both"):
            R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"),
                                            sl_mult=SL_MULT, fee_bp=FEE_BP,
                                            mode="trail_atr", trail=SHORT_TRAIL,
                                            be_at=BE_AT, strict_fill=strict)
            tr += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r), "S")
                   for r, i, b in zip(R, idx, bars)]
    tr.sort(key=lambda x: x[0])
    return tr, stops


def stats(tr, stops, slots=SLOTS, risk=RISK, regime=REGIME_MULT):
    if len(tr) < 30:
        return None
    bear = btc_bear() if regime > 0 else None
    f0 = risk / 100.0
    eq, curve, times, opens = 1.0, [], [], []
    Rs, sides = [], []
    ruined = False
    for a_, b_, r, side in tr:
        opens = [u for u in opens if u > a_]
        if len(opens) >= slots:
            continue
        opens.append(b_)
        f = f0
        if bear is not None:
            try:
                if bool(bear.asof(a_)):
                    f *= regime
            except Exception:
                pass
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
    return dict(n=len(R), mean=float(R.mean()), win=float((R > 0).mean() * 100),
                dd=dd, cagr=cagr, ruined=ruined, floor=floor, times=ts, R=R,
                nL=sides.count("L"), nS=sides.count("S"),
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0)


def line(tag, o, s):
    """One row: optimistic then strict, then the damage."""
    if not (o and s):
        return f"{tag:<30} (insufficient)"
    return (f"{tag:<30} {o['mean']:>+8.3f} {o['hpm']:>+8.2f}% {o['dd']:>6.1f}% "
            f"| {s['mean']:>+8.3f} {s['hpm']:>+8.2f}% {s['dd']:>6.1f}% "
            f"| {s['mean']-o['mean']:>+7.3f} {s['hpm']-o['hpm']:>+7.2f}pp")


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: longs lose <0.01R, shorts go to zero or negative,")
    print("long-only + regime gate becomes best, and the bear-year rescue shrinks but")
    print("does not vanish.\n")

    hdr = (f"{'configuration':<30} {'OPTIMISTIC (as reported)':^26} "
           f"| {'STRICT (pessimistic fill)':^26} | {'damage':^16}")
    sub = (f"{'':<30} {'meanR':>8} {'/mo':>9} {'DD':>7} "
           f"| {'meanR':>8} {'/mo':>9} {'DD':>7} | {'meanR':>8} {'/mo':>8}")

    print("=" * 118)
    print("1. WHICH SLEEVE PAYS FOR THE OPTIMISM?   1h bars, 12-coin book")
    print("=" * 118)
    print(hdr); print(sub)
    keep = {}
    for side, tag in (("long", "long only"), ("short", "short only"),
                      ("both", "long + short (the $200)")):
        o_tr, o_st = sleeve("1h", side, False)
        s_tr, s_st = sleeve("1h", side, True)
        o, s = stats(o_tr, o_st), stats(s_tr, s_st)
        keep[tag] = (o, s)
        print(line(tag, o, s), flush=True)
    print()

    print("=" * 118)
    print("2. THE TIMEFRAME BLEND — does the 2022/2025 rescue survive?")
    print("=" * 118)
    print(hdr); print(sub)
    blends = {}
    for rules, tag in ((("1h",), "1h both sleeves"),
                       (("1h", "4h"), "1h + 4h"),
                       (("1h", "4h", "12h"), "1h + 4h + 12h")):
        o_all, s_all, o_st, s_st = [], [], {}, {}
        for r in rules:
            a, st = sleeve(r, "both", False); o_all += a; o_st.update(st)
            b, st2 = sleeve(r, "both", True); s_all += b
            for k, v in st2.items():
                s_st[k] = max(s_st.get(k, 0.0), v)
        o_all.sort(key=lambda x: x[0]); s_all.sort(key=lambda x: x[0])
        o, s = stats(o_all, o_st), stats(s_all, s_st)
        blends[tag] = (o, s)
        print(line(tag, o, s), flush=True)
    print()

    print("=" * 118)
    print("3. BY YEAR UNDER THE STRICT FILL — the bear years are the whole point")
    print("=" * 118)
    rows = {}
    rows["long only"] = keep["long only"][1]
    rows["long + short"] = keep["long + short (the $200)"][1]
    rows["1h+4h+12h"] = blends["1h + 4h + 12h"][1]
    years = sorted({y for d in rows.values() if d for y in set(d["times"].year)})
    print(f"{'configuration':<18} " + " ".join(f"{y:>9}" for y in years)
          + f" {'DD':>7} {'/mo':>8} {'floor':>8}")
    for tag, d in rows.items():
        if not d:
            continue
        cells = []
        for y in years:
            m = d["times"].year == y
            cells.append(f"{d['R'][m].sum()*RISK/100*100:>+8.0f}%"
                         if m.sum() >= 10 else f"{'-':>9}")
        print(f"{tag:<18} " + " ".join(cells)
              + f" {d['dd']:>6.1f}% {d['hpm']:>+7.2f}% {d['floor']:>8,.0f}")
    print("\n  (yearly return at 0.30%/unit, summed R x risk, not compounded)")

    print("\n" + "=" * 118)
    print("VERDICT")
    print("=" * 118)
    lo_, ls = keep["long only"]
    so_, ss = keep["short only"]
    bo_, bs = keep["long + short (the $200)"]
    if not all((lo_, ls, so_, ss, bo_, bs)):
        return
    print(f"  long sleeve  : {lo_['mean']:+.3f} -> {ls['mean']:+.3f} "
          f"({ls['mean']-lo_['mean']:+.3f})")
    print(f"  short sleeve : {so_['mean']:+.3f} -> {ss['mean']:+.3f} "
          f"({ss['mean']-so_['mean']:+.3f})")
    print(f"  combined     : {bo_['mean']:+.3f} -> {bs['mean']:+.3f} "
          f"({bs['mean']-bo_['mean']:+.3f})")
    if ss["mean"] <= 0:
        print("\n  SHORTS DO NOT SURVIVE AN HONEST FILL. They are at best a drawdown")
        print("  hedge, not a profit source. Every two-sided figure reported today")
        print("  must be restated, and the comparison to run is long-only versus")
        print("  two-sided ON THE STRICT NUMBERS:")
        print(f"    long only    {ls['hpm']:+.2f}%/mo  DD {ls['dd']:.1f}%  "
              f"floor ${ls['floor']:,.0f}")
        print(f"    long + short {bs['hpm']:+.2f}%/mo  DD {bs['dd']:.1f}%  "
              f"floor ${bs['floor']:,.0f}")
        better = "long + short" if bs["floor"] < ls["floor"] else "long only"
        print(f"    -> on capital floor, {better} wins")
    else:
        print("\n  Shorts survive. Today's figures stand, shifted down by the")
        print("  amount in the damage column.")


if __name__ == "__main__":
    main()
