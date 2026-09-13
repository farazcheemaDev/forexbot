"""HIGHER TIMEFRAMES — the blind spot. Every test in this project used 1h.

THE GAP
    393 configs, 19 indicator families, every exit rule, every universe, the whole
    drawdown battery: all of it on ONE-HOUR bars. Lower timeframes were tested and
    killed on cost (1m/5m/15m). HIGHER ones were never tried at all.

    That is a strange omission, because classical trend following lives on DAILY
    bars, and the one cost metric this project trusts says longer bars should be
    cheaper to trade:

        fee toll in R = fee_fraction / stop_fraction

    ATR is a larger fraction of price on a longer bar, so the same 2xATR stop is a
    much wider percentage move, and the same 12bp round trip costs far less in R.
    Hourly: ATR ~1.22% -> 2xATR = 2.43% -> toll 0.049R.
    If daily ATR is ~4.5%, the stop is ~9% and the toll is ~0.013R - a quarter.

WHY IT MIGHT STILL LOSE
    * FAR fewer trades. Hourly gives ~6,500 across 12 coins; daily might give 400.
      Fewer compounding events means less growth even at a better mean R, and it
      also means any result rests on a much smaller sample.
    * The capital floor moves the WRONG way. notional = risk / stop_fraction, so a
      wider stop means a SMALLER position, which is harder to get above the venue's
      minimum order. Daily could raise the floor even while cutting drawdown.
    * 2020-2026 is ~6.5 years. On daily bars that is ~2,400 observations per coin -
      enough, but only just, and one trend cycle dominates.

WHAT IS HELD CONSTANT
    Identical rules at every timeframe: BB(30,1.5) entries, 2xATR stop, breakeven at
    3R, long pyramid 5 units adding every 2R with a 20xATR trail, short 1 unit with a
    5xATR trail, 8 slots, 0.30%/unit. Only the bar size changes. Trails stay in ATR
    units, which is the point - ATR rescales with the timeframe automatically.

    Bars are resampled from the SAME 1h source, so no new data and no new survivorship
    question enters.

REGISTERED PREDICTION (2026-09-13, before running)
    4h is the sweet spot: better mean R than 1h from the lower fee toll, still enough
    trades to compound. Daily has the best mean R and the worst total return because
    of trade count, and a HIGHER capital floor. If 1h wins outright, the timeframe
    blind spot is closed and the answer is that crypto's trends are short.

    python -m backtest.timeframes
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
from bot.core.indicators import atr as atr_ind  # noqa: E402

FEE_BP = 12.0
SL_MULT, BE_AT = 2.0, 3.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MAX_UNITS, ADD_EVERY = 5, 2.0
RISK, SLOTS = 0.30, 8
HINDSIGHT = 3.0
BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT"]
MIN_ORDER = {"XRPUSDT": 1.338, "SUIUSDT": 0.708, "ADAUSDT": 0.203,
             "LINKUSDT": 1.130, "AVAXUSDT": 0.729, "LTCUSDT": 0.535,
             "ENAUSDT": 1.388, "SHIBUSDT": 0.005, "WLDUSDT": 0.388,
             "NEARUSDT": 2.282, "DOTUSDT": 0.100, "ARBUSDT": 0.137}
_D: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def resample(df, rule):
    """1h -> rule. Aggregation must be OHLC-correct: first open, max high, min low,
    last close, summed volume. Getting `high` wrong here (e.g. taking last) would
    silently disable every stop and trail check."""
    if rule == "1h":
        return df
    d = df.set_index("time")
    out = d.resample(rule, label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"}).dropna()
    return out.reset_index()


def trades(df):
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
                                    mode="trail_atr", trail=SHORT_TRAIL, be_at=BE_AT)
    out += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r))
            for r, i, b in zip(R, idx, bars)]
    return out


def run_tf(rule, min_bars):
    tr, sfs = [], {}
    for c in BOOK:
        d = load(c)
        if d is None:
            continue
        df = resample(d, rule)
        if len(df) < min_bars:
            continue
        a = (atr_ind(df, 14) / df["close"]).replace([np.inf, -np.inf], np.nan).dropna()
        if len(a):
            sfs[c] = float(a.median()) * SL_MULT
        tr += trades(df)
    if len(tr) < 20 or not sfs:
        return None
    tr.sort(key=lambda x: x[0])
    f = RISK / 100.0
    eq, curve, times, opens, Rs = 1.0, [], [], [], []
    ruined = False
    for a_, b_, r in tr:
        opens = [u for u in opens if u > a_]
        if len(opens) >= SLOTS:
            continue
        opens.append(b_)
        Rs.append(r)
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 0.01:
                eq, ruined = 0.0, True
        curve.append(eq); times.append(b_)
    if len(Rs) < 20:
        return None
    R = np.asarray(Rs); cur = np.asarray(curve)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    hc = cagr / HINDSIGHT if cagr > -100 else -100.0
    sf_med = float(np.median(list(sfs.values())))
    floor = max(MIN_ORDER[c] * sfs[c] for c in sfs) / (RISK / 100.0)
    floor = floor / (1 - dd / 100.0) if dd < 99.0 else float("nan")
    return dict(n=len(R), mean=float(R.mean()), win=float((R > 0).mean() * 100),
                mx=float(R.max()), dd=dd, cagr=cagr, ruined=ruined,
                stop=sf_med, toll=(FEE_BP / 1e4) / sf_med, floor=floor,
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0,
                times=ts, R=R)


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: 4h is the sweet spot; daily has the best mean R,")
    print("the worst total return, and a HIGHER capital floor. If 1h wins outright,")
    print("crypto's trends are short and the blind spot is closed.\n")

    print("=" * 118)
    print(f"{'bars':>6} {'stop %':>8} {'fee toll R':>11} {'n':>6} {'meanR':>8} "
          f"{'win%':>6} {'maxR':>9} {'HONEST /mo':>11} {'DD':>7} {'floor $':>9}")
    print("=" * 118)
    res = {}
    for rule, label, mb in (("1h", "1h", 3000), ("4h", "4h", 1200),
                            ("12h", "12h", 500), ("1D", "1D", 300),
                            ("2D", "2D", 200)):
        d = run_tf(rule, mb)
        if not d:
            print(f"{label:>6} (insufficient bars)")
            continue
        res[label] = d
        ru = " RUIN" if d["ruined"] else ""
        print(f"{label:>6} {d['stop']*100:>7.2f}% {d['toll']:>11.3f} {d['n']:>6} "
              f"{d['mean']:>+8.3f} {d['win']:>6.1f} {d['mx']:>9.1f} "
              f"{d['hpm']:>+10.2f}% {d['dd']:>6.1f}% {d['floor']:>9,.0f}{ru}",
              flush=True)

    if not res:
        return
    # THE QUESTION THAT MATTERS: did the higher timeframes hold up in 2025-2026,
    # when the 1h book went flat? A timeframe that keeps working through the same
    # stretch is worth more than one with a better average.
    print("\n" + "=" * 118)
    print("BY YEAR — the 1h book made 2.5% of its profit in 2025-2026. "
          "Do longer bars survive that stretch?")
    print("=" * 118)
    years = sorted({y for d in res.values() for y in set(d["times"].year)})
    print(f"{'bars':>6} " + " ".join(f"{y:>10}" for y in years))
    for label, d in res.items():
        cells = []
        for y in years:
            m = d["times"].year == y
            cells.append(f"{d['R'][m].mean():>+10.2f}" if m.sum() >= 10 else
                         f"{'-':>10}")
        print(f"{label:>6} " + " ".join(cells))
    print("\n(mean R per trade, by year. '-' means fewer than 10 trades.)")
    best = max(res.items(), key=lambda kv: kv[1]["mean"])
    print(f"\nbest mean R: {best[0]} at {best[1]['mean']:+.3f} "
          f"(1h is {res['1h']['mean']:+.3f})" if "1h" in res else "")
    print("Judge on the BY-YEAR table, not the average. The whole reason for running")
    print("this is that the 1h book's average is carried by 2021 and 2024.")


if __name__ == "__main__":
    main()
