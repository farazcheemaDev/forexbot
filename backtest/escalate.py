"""Bigger adds: should each pyramid unit be larger than the one before?

The idea (2026-09-21): unit 1 at normal size, then buy each add "with more leverage".
Leverage by itself changes only the margin posted, not the P&L, so what the idea
really means is a BIGGER NOTIONAL per add - unit k sized w_k times unit 1.

Why the answer is not obvious. The adds already carry more risk than unit 1. Unit 5
is bought 8R above the first entry, and the shared stop sits at best - 10R (20xATR
trail) floored at breakeven, so on the day it is bought it can lose up to 8R on its
own. A position stopped at breakeven already loses 0+2+4+6+8 = 20R at five equal
units. Scaling the adds up multiplies exactly that loss - and it multiplies the
runners too. giveback.py: 3.5% of positions produce +30,141R, but positions that
peak at 5R-50R close NEGATIVE on the median. Bigger adds make both of those larger.

The method. Weights do not change WHEN anything exits - adds trigger on price and
every unit exits at the shared trail - so the trade list, the slot cap and the
declines are identical in every variant. Only R per position changes. So the
position simulation runs once, keeps each unit's own contribution, and every weight
scheme is a dot product over the same positions. The guard asserts that equal weights
reproduce run_pyramid exactly.

Two framings, because they answer different questions:
  SAME FIRST BET - unit 1 unchanged, adds scaled up. The literal idea. It adds risk,
                   so its control is flat units at a higher risk - "just bet more".
  SAME BUDGET    - weights rescaled to sum to 5, so a fully built position risks
                   what it risks now; only the SHAPE moves. That is the clean test of
                   whether late units are better bets than early ones.

Compounded by CLOSE date (mistake #6 fixed). Tune/holdout split as bear_date.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

RULES, SLOTS, U = ["1h", "4h", "12h"], 12, blend.MAX_UNITS


def pyramid_units(df, sig, *, sl_mult, trail, max_units, add_every, fee_bp,
                  breakeven_at):
    """run_pyramid, but each closed position returns one R contribution PER UNIT
    (zero for units never bought). Logic copied line for line; the guard below
    checks the row sums against run_pyramid itself."""
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    n, fee = len(df), fee_bp / 1e4
    C, idx, held = [], [], []

    def close(pos, px, i):
        row = np.zeros(max_units)
        for k, e in enumerate(pos["entries"]):
            row[k] = (px - e) / pos["risk"] - fee * e / pos["risk"]
        C.append(row); idx.append(i); held.append(i - pos["bar"])

    pos = None
    for i in range(1, n):
        if pos is None and s[i] == 1 and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            r = sl_mult * a[i - 1]
            pos = dict(risk=r, stop=o[i] - r, best=o[i], bar=i, entries=[o[i]],
                       next_add=1)
        if pos is None:
            continue
        risk = pos["risk"]
        if lo[i] <= pos["stop"]:
            close(pos, pos["stop"], i); pos = None; continue
        if len(pos["entries"]) < max_units:
            if (h[i] - pos["entries"][0]) / risk >= pos["next_add"] * add_every:
                pos["entries"].append(pos["entries"][0]
                                      + pos["next_add"] * add_every * risk)
                pos["next_add"] += 1
        pos["best"] = max(pos["best"], h[i])
        cand = pos["best"] - trail * a[i - 1]
        if breakeven_at > 0 and (pos["best"] - pos["entries"][0]) / risk >= breakeven_at:
            cand = max(cand, pos["entries"][0])
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None:
        close(pos, c[n - 1], n - 1)
    return np.asarray(C).reshape(-1, max_units), np.asarray(idx, int), np.asarray(held, int)


def build():
    """Longs with per-unit contributions, shorts (1 unit, unchanged) as scalars."""
    rows = []
    checked = 0
    for rule in RULES:
        for c in blend.BOOK:
            d = blend.load(c)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            t = df["time"].to_numpy()
            kw = dict(sl_mult=blend.SL_MULT, trail=blend.LONG_TRAIL,
                      max_units=U, add_every=blend.ADD_EVERY, fee_bp=blend.FEE_BP,
                      breakeven_at=blend.BE_AT)
            sig = signals(df, "long", "all")
            C, idx, held = pyramid_units(df, sig, **kw)
            R0, idx0, _u, _h = run_pyramid(df, sig, **kw)
            assert len(R0) == len(C) and np.array_equal(idx0, idx), (rule, c)
            assert np.allclose(C.sum(1), R0, atol=1e-9), (rule, c)
            checked += len(R0)
            for row, i, hh in zip(C, idx, held):
                rows.append((t[max(int(i) - int(hh), 0)], t[int(i)], row, "long"))
        for a_, b_, r, _rule, _c, side in sleeve_sided(rule)[0]:
            if side == "short":
                one = np.zeros(U); one[0] = r
                rows.append((a_, b_, one, "short"))
    rows.sort(key=lambda x: x[0])
    print(f"guard: {checked} long positions, per-unit sums == run_pyramid exactly")
    return rows


def evaluate(rows, w, risk_mult=1.0, t_from=None, t_to=None):
    """Blend allocator (12 shared slots, x0.25 in bears), compounded by close date.
    Equal weights at risk_mult 1 is the deployed config."""
    bear = blend.btc_bear()
    # shorts are untouched in every scheme (1 unit, base risk); risk_mult and the
    # weights apply to the LONG pyramid only, which is what the question is about
    f0 = blend.RISK / 100.0
    w = np.asarray(w, float)
    opens, out, worst = [], [], 0.0
    for a_, b_, row, side in rows:
        if t_from is not None and a_ < t_from: continue
        if t_to is not None and a_ >= t_to: continue
        opens = [u for u in opens if u > a_]
        if len(opens) >= SLOTS: continue
        opens.append(b_)
        try: ib = bool(bear.asof(a_))
        except Exception: ib = False
        f = f0 * (blend.REGIME_MULT if ib else 1.0)
        r = float(row @ w) * risk_mult if side == "long" else float(row[0])
        out.append((pd.Timestamp(b_), r * f))
        worst = min(worst, r * f)
    s = pd.Series([x[1] for x in out], index=pd.DatetimeIndex([x[0] for x in out]))
    daily = s.resample("D").sum()
    cur = np.cumprod(np.maximum(1.0 + daily.values, 0.0))
    ruined = bool((cur <= 1e-6).any())
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    yrs = max((daily.index[-1] - daily.index[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 1e-12) ** (1 / yrs) - 1) * 100
    hc = cagr / blend.HINDSIGHT
    hpm = ((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0
    mon = daily.resample("ME").sum()
    return dict(hpm=hpm, dd=dd, worst_pos=worst * 100, worst_mo=float(mon.min() * 100),
                ruined=ruined)


def geo(ratio):
    return [ratio ** k for k in range(U)]


def budget(w):
    w = np.asarray(w, float)
    return list(w * U / w.sum())


def main():
    rows = build()
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    L = np.array([row for _a, _b, row, sd in rows if sd == "long"])
    nunits = (L != 0).sum(1)
    print(f"long positions {len(L)}: units reached "
          + "  ".join(f"{k}u {np.mean(nunits == k)*100:.1f}%" for k in range(1, U + 1)))
    print("mean R contributed per unit bought (unit 1 .. 5), equal weights:")
    for k in range(U):
        got = L[nunits > k, k]
        print(f"  unit {k+1}: n={len(got):>5}  mean {got.mean():+7.3f}R  "
              f"median {np.median(got):+7.3f}R  win {np.mean(got > 0)*100:5.1f}%  "
              f"sum {got.sum():+9.0f}R")

    schemes = [
        ("CURRENT flat 1,1,1,1,1", [1] * U, 1.0),
        ("-- same first bet, bigger adds --", None, None),
        ("adds x1.25 each", geo(1.25), 1.0),
        ("adds x1.5 each", geo(1.5), 1.0),
        ("adds x2 each", geo(2.0), 1.0),
        ("control: flat, risk x1.5", [1] * U, 1.5),
        ("control: flat, risk x2", [1] * U, 2.0),
        ("control: flat, risk x3", [1] * U, 3.0),
        ("-- same budget (sum=5), shape only --", None, None),
        ("back-loaded x1.25", budget(geo(1.25)), 1.0),
        ("back-loaded x1.5", budget(geo(1.5)), 1.0),
        ("back-loaded x2", budget(geo(2.0)), 1.0),
        ("front-loaded x0.75", budget(geo(0.75)), 1.0),
        ("front-loaded x0.5", budget(geo(0.5)), 1.0),
        ("no adds (1 unit, x5 size)", [5, 0, 0, 0, 0], 1.0),
    ]
    print(f"\ntune < {cut:%Y-%m-%d} <= holdout. %/mo after the 3x hindsight haircut, "
          f"compounded by close date")
    print(f"  {'scheme':<34}{'weights':<28}| {'TUNE/mo':>8}{'DD':>6} | "
          f"{'HOLD/mo':>8}{'DD':>6}{'worst mo':>9}{'worst pos':>10}")
    for name, w, rm in schemes:
        if w is None:
            print(f"  {name}"); continue
        a = evaluate(rows, w, rm, t_to=cut)
        b = evaluate(rows, w, rm, t_from=cut)
        ws = ",".join(f"{x:.2f}".rstrip("0").rstrip(".") for x in w)
        if rm != 1.0:
            ws += f" @{rm:g}x risk"
        flag = lambda d: "  RUIN" if d["ruined"] else ""
        print(f"  {name:<34}{ws:<28}| {a['hpm']:>+7.2f}%{a['dd']:>5.0f}% | "
              f"{b['hpm']:>+7.2f}%{b['dd']:>5.0f}%{b['worst_mo']:>+8.1f}%"
              f"{b['worst_pos']:>+9.1f}%{flag(a)}{flag(b)}")


if __name__ == "__main__":
    main()
