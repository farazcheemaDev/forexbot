"""RENKO + A WIDE UNIVERSE — fixing the one thing wrong with Renko.

THE IDEA
    backtest/barsampling.py found Renko bricks earn +0.517 mean R against the 1h time
    bar's +0.229 - more than double per trade, with the fat tail intact. It still lost
    overall, because it fires 48 times a year per coin against 1h's 165, and trade
    count is what compounds.

    But trade count is not fixed. It is coins x frequency. Renko at ~34 coins fires as
    often as 1h at 10, and if mean R holds anywhere near +0.5 the total edge is
    roughly 2.3x the control.

    There is a second reason the two fit together. With 12 coins on 1h bars the 8-slot
    cap already overflows badly - 5,394 trades DECLINED against 2,782 taken. Renko's
    lower per-coin frequency means many more coins can share the same 8 slots before
    they crowd each other. The earlier breadth rule ("peak where COINS ~= SLOTS + 1")
    was measured on 1h bars and should not transfer.

    And the capital floor should NOT rise: execution stays on the real 1h OHLC with a
    2xATR(1h) stop in every variant, so the stop fraction - which is what sets the
    floor alongside the minimum order - is unchanged by the bar type.

WHY IT MIGHT FAIL
    Adding coins means adding LESS LIQUID coins, and that has already burned this
    project once: ranking purely by tiny minimum order surfaced ILV, ICX, CVC and
    friends at $30k-170k of volume per bar, and every book built from them drew down
    99.6-100%. So the pool here is ranked by LIQUIDITY and the table reports where
    adding coins stops helping - if mean R collapses as the universe widens, the
    Renko edge was a property of the ten good coins, not of the bar type.

REGISTERED PREDICTION (2026-09-14, before running)
    Renko at 30-40 coins beats the 1h 12-coin book on total return AND drawdown,
    because the slot cap stops binding and the per-trade edge is genuinely better.
    Mean R decays as the universe widens but stays above +0.35 at 30 coins. If mean R
    falls below the 1h control's +0.229 by 30 coins, the edge was the coins.

    python -m backtest.wide_renko
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.barsampling import bars_renko, bars_time, signals_on  # noqa: E402
from backtest.cheap_wide import mexc_min_orders  # noqa: E402
from backtest.convex import run_uncapped  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
SL_MULT, BE_AT = 2.0, 3.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MAX_UNITS, ADD_EVERY = 5, 2.0
RISK, SLOTS = 0.30, 8
HINDSIGHT = 3.0
MIN_BARS = 20000
_D: dict = {}
_TR: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def coin_trades(sym, builder, key):
    """Trades for one coin under one bar type. Execution ALWAYS on the real 1h OHLC,
    so entries, stops, trails and fees are at prices that existed."""
    ck = (sym, key)
    if ck in _TR:
        return _TR[ck]
    real = load(sym)
    if real is None or len(real) < MIN_BARS:
        _TR[ck] = []
        return []
    bars = builder(real)
    if bars is None or len(bars) < 60:
        _TR[ck] = []
        return []
    sl, ss = signals_on(bars, len(real))
    t = real["time"].to_numpy()
    out = []
    if int((sl != Action.HOLD).sum()):
        R, idx, _u, held = run_pyramid(real, sl, sl_mult=SL_MULT, trail=LONG_TRAIL,
                                       max_units=MAX_UNITS, add_every=ADD_EVERY,
                                       fee_bp=FEE_BP, breakeven_at=BE_AT)
        out += [(t[max(int(i) - int(h), 0)], t[int(i)], float(r), "L")
                for r, i, h in zip(R, idx, held)]
    if int((ss != Action.HOLD).sum()):
        R, idx, bars_h, _d = run_uncapped(real, ss, sl_mult=SL_MULT, fee_bp=FEE_BP,
                                          mode="trail_atr", trail=SHORT_TRAIL,
                                          be_at=BE_AT)
        out += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r), "S")
                for r, i, b in zip(R, idx, bars_h)]
    _TR[ck] = out
    return out


def book(syms, builder, key, mins, t_from=None, t_to=None):
    tr = []
    for s in syms:
        tr += coin_trades(s, builder, key)
    if len(tr) < 30:
        return None
    tr.sort(key=lambda x: x[0])
    f = RISK / 100.0
    eq, curve, times, opens = 1.0, [], [], []
    Rs, declined, ruined = [], 0, False
    for a_, b_, r, _side in tr:
        if t_from is not None and a_ < t_from:
            continue
        if t_to is not None and a_ >= t_to:
            continue
        opens = [u for u in opens if u > a_]
        if len(opens) >= SLOTS:
            declined += 1
            continue
        opens.append(b_)
        Rs.append(r)
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
    worst = 0.0
    for s in syms:
        d = load(s)
        if d is None:
            continue
        a = (atr_ind(d, 14) / d["close"]).replace([np.inf, -np.inf], np.nan).dropna()
        if len(a):
            worst = max(worst, mins.get(s, 5.0) * float(a.median()) * SL_MULT)
    floor = (worst / (RISK / 100.0) / (1 - dd / 100.0)) if dd < 99.0 and worst \
        else float("nan")
    return dict(n=len(R), declined=declined, mean=float(R.mean()), dd=dd,
                per_yr=len(R) / yrs, ruined=ruined, floor=floor,
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", type=int, default=45)
    args = ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: Renko at 30-40 coins beats the 1h 12-coin book on")
    print("return AND drawdown; mean R decays but stays above +0.35 at 30 coins. Below")
    print("the 1h control's +0.229 by 30 coins means the edge was the coins.\n")

    print("building the candidate pool (MEXC minimum <= $2.50, ranked by "
          "liquidity)...", flush=True)
    raw = mexc_min_orders(2.50, args.pool * 3)
    cand = []
    for b in raw:
        s = f"{b}USDT"
        d = load(s)
        if d is None or len(d) < MIN_BARS:
            continue
        cand.append((float((d["close"] * d["volume"]).median()), s, raw[b][0]))
    cand.sort(reverse=True)
    cand = cand[:args.pool]
    mins = {s: mo for _dv, s, mo in cand}
    order = [s for _dv, s, _mo in cand]
    print(f"  {len(order)} coins with >= {MIN_BARS:,} bars\n")
    print("  " + ", ".join(s.replace("USDT", "") for s in order[:45]))

    ts_all = pd.DatetimeIndex(sorted(
        x[0] for s in order[:12] for x in coin_trades(s, lambda d: bars_time(d, 1),
                                                      "t1")))
    cut = ts_all[int(len(ts_all) * 0.6)]
    print(f"\ntime split at {cut.date()}\n")

    variants = [("1h time", lambda d: bars_time(d, 1), "t1"),
                ("RENKO 1xATR", lambda d: bars_renko(d, 1.0), "r1"),
                ("RENKO 2xATR", lambda d: bars_renko(d, 2.0), "r2")]
    sizes = [n for n in (12, 20, 30, 45) if n <= len(order)]
    print("=" * 118)
    print(f"{'bars':<13} {'coins':>5} {'meanR':>8} {'trades/yr':>10} {'decl':>7} "
          f"| {'TUNE /mo':>9} {'DD':>7} | {'OUT /mo':>9} {'DD':>7} {'floor':>8}")
    print("=" * 118)
    rows = []
    for label, b, key in variants:
        for n in sizes:
            syms = order[:n]
            full = book(syms, b, key, mins)
            a = book(syms, b, key, mins, t_to=cut)
            o = book(syms, b, key, mins, t_from=cut)
            if not (full and a and o):
                print(f"{label:<13} {n:>5} (insufficient)")
                continue
            rows.append((label, n, full, a, o))
            print(f"{label:<13} {n:>5} {full['mean']:>+8.3f} "
                  f"{full['per_yr']:>10,.0f} {full['declined']:>7,} "
                  f"| {a['hpm']:>+8.2f}% {a['dd']:>6.1f}% "
                  f"| {o['hpm']:>+8.2f}% {o['dd']:>6.1f}% {o['floor']:>8,.0f}",
                  flush=True)
        print()

    if not rows:
        return
    base = next((r for r in rows if r[0] == "1h time" and r[1] == 12), None)
    print("=" * 118)
    print("VERDICT — against the current $221 book (1h time, 12 coins)")
    print("=" * 118)
    if not base:
        return
    print(f"  baseline out of sample: {base[4]['hpm']:+.2f}%/mo  "
          f"DD {base[4]['dd']:.1f}%  floor ${base[4]['floor']:,.0f}  "
          f"meanR {base[2]['mean']:+.3f}")
    keep = [r for r in rows if r is not base
            and r[4]["hpm"] > base[4]["hpm"] and r[4]["dd"] <= base[4]["dd"]
            and np.isfinite(r[4]["floor"])]
    if not keep:
        print("\n  Nothing beat it on both return and drawdown out of sample.")
        print("  Widening the universe did not rescue Renko: check the meanR column")
        print("  as coins increase — if it fell toward the 1h control, the per-trade")
        print("  edge was a property of the ten liquid coins, not of the bar type.")
    else:
        keep.sort(key=lambda r: -r[4]["hpm"])
        for label, n, full, a, o in keep:
            print(f"  {label:<13} {n:>2} coins  OUT {o['hpm']:+6.2f}%/mo  "
                  f"DD {o['dd']:5.1f}%  floor ${o['floor']:,.0f}  "
                  f"meanR {full['mean']:+.3f}")
        print(f"\n  {len(keep)} of {len(rows)} cells. Believe one only if the")
        print("  neighbouring universe sizes improved too — a single good coin count")
        print("  is a fitted number.")


if __name__ == "__main__":
    main()
