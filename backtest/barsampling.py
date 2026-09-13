"""BAR CONSTRUCTION — the axis this project never touched.

THE GAP
    19 indicator families were tested and all 19 detected the same phenomenon, which
    closed the indicator search. But every one of those tests - and every test in this
    project - ran on TIME bars: 1h, 4h, 12h, 1D. Bar CONSTRUCTION was never varied.

    That is a different axis from "which indicator", and there is a real reason to
    expect it to matter. A time bar samples the market on a clock regardless of what
    is happening in it, so a dead Sunday hour and a hour containing an ETF approval
    get equal weight. Crypto activity swings by more than an order of magnitude, so
    time bars systematically oversample quiet stretches and undersample violent ones.
    Sampling on ACTIVITY instead of on the clock is the standard fix and is known to
    produce returns closer to IID with better signal-to-noise.

BAR TYPES TESTED
    time        1h, the control
    dollar      a new bar each time $X of volume has traded
    volume      a new bar each time N units have traded
    heikin      Heikin-Ashi smoothing of the 1h series
    renko       a new brick each time price moves k x ATR

THE TRAP THIS FILE IS BUILT TO AVOID
    Heikin-Ashi and Renko prices ARE NOT TRADEABLE PRICES. An HA close is an average
    of four numbers; a Renko brick closes at a synthetic level. Computing R from them
    would report profits at prices that never existed - the same class of error as the
    price-mirror bug, which flattered shorts 4x by trading a transformed series.

    So: SIGNALS are generated on the transformed bars, and EXECUTION - entry, stop,
    trail, fees - happens on the REAL 1h OHLC. A signal on a constructed bar is mapped
    back to the last underlying 1h bar it contains, and the trade opens at the next 1h
    open. Dollar and volume bars are aggregates of real 1h bars so their OHLC are real
    prices, but they are executed the same way for consistency.

    This also keeps the comparison honest in a second way: every bar type is executed
    by the same engine at the same 1h granularity, so a difference in the result is a
    difference in the SIGNAL, not in the fill model.

WHAT WOULD MAKE THIS INTERESTING
    Mean R materially above the time-bar control on the SAME trades-per-year scale. A
    bar type that trades a tenth as often and earns twice as much per trade has not
    improved anything - trade count is what compounds. So trades and mean R are
    reported together, and the micro-account odds are recomputed for the best cell,
    because that is where a better edge actually changes an outcome.

REGISTERED PREDICTION (2026-09-14, before running)
    Dollar bars beat time bars on mean R by a visible margin - this is the one with a
    mechanism behind it. Volume bars behave like dollar bars but worse, because a unit
    of SHIB and a unit of LTC are not comparable quantities. Heikin-Ashi looks
    excellent and is a trap: its smoothing removes exactly the noise that the stop has
    to survive, so signals fire cleanly on a series the account cannot trade, and once
    execution is on real prices the advantage should vanish. Renko roughly matches
    time bars, since a fixed-brick filter is close to what an ATR stop already does.

    python -m backtest.barsampling
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
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
SL_MULT, BE_AT = 2.0, 3.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
BB_PERIOD, BB_STD = 30, 1.5
HINDSIGHT = 3.0
BOOK = ["XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "SUIUSDT",
        "LTCUSDT", "SHIBUSDT", "ARBUSDT", "NEARUSDT"]
_D: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


# ---------------------------------------------------------------- bar builders
def bars_time(df, mult=1):
    """The control. `src` is the index of the last underlying 1h bar."""
    if mult == 1:
        out = df.copy()
        out["src"] = np.arange(len(df))
        return out
    g = np.arange(len(df)) // mult
    out = df.groupby(g).agg({"time": "last", "open": "first", "high": "max",
                             "low": "min", "close": "last", "volume": "sum"})
    out["src"] = df.groupby(g).apply(lambda x: x.index[-1]).to_numpy()
    return out.reset_index(drop=True)


def bars_activity(df, kind, target):
    """A new bar once cumulative dollar (or unit) volume crosses `target`.

    Bars are whole numbers of 1h bars - the coarsest possible dollar bar - because 1h
    is the finest data available here. A true dollar bar would split an hour; this
    cannot, so the effect measured is a LOWER BOUND on what proper dollar bars would
    give.
    """
    v = (df["close"] * df["volume"]).to_numpy(float) if kind == "dollar" \
        else df["volume"].to_numpy(float)
    rows, cum, start = [], 0.0, 0
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    t = df["time"].to_numpy()
    for i in range(len(df)):
        cum += v[i]
        if cum >= target or i == len(df) - 1:
            rows.append((t[i], o[start], h[start:i + 1].max(),
                         lo[start:i + 1].min(), c[i], v[start:i + 1].sum(), i))
            cum, start = 0.0, i + 1
    if not rows:
        return None
    return pd.DataFrame(rows, columns=["time", "open", "high", "low", "close",
                                       "volume", "src"])


def bars_heikin(df):
    """Heikin-Ashi. The OHLC here are SYNTHETIC — never execute on them."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    n = len(df)
    hc = (o + h + lo + c) / 4.0
    ho = np.empty(n); ho[0] = (o[0] + c[0]) / 2.0
    for i in range(1, n):
        ho[i] = (ho[i - 1] + hc[i - 1]) / 2.0
    hh = np.maximum.reduce([h, ho, hc])
    hl = np.minimum.reduce([lo, ho, hc])
    return pd.DataFrame({"time": df["time"].to_numpy(), "open": ho, "high": hh,
                         "low": hl, "close": hc,
                         "volume": df["volume"].to_numpy(float),
                         "src": np.arange(n)})


def bars_renko(df, k=1.0):
    """A brick each time the close moves k x ATR(14) from the last brick.

    Built from CLOSES only - intrabar wicks cannot be resolved at 1h - so the brick
    boundaries are approximate. Signals map back to the real 1h bar.
    """
    a = atr_ind(df, 14).to_numpy(float)
    c = df["close"].to_numpy(float)
    t = df["time"].to_numpy()
    rows = []
    anchor = None
    for i in range(len(df)):
        if not np.isfinite(a[i]) or a[i] <= 0:
            continue
        if anchor is None:
            anchor = c[i]
            continue
        brick = k * a[i]
        while abs(c[i] - anchor) >= brick:
            nxt = anchor + np.sign(c[i] - anchor) * brick
            rows.append((t[i], anchor, max(anchor, nxt), min(anchor, nxt), nxt,
                         0.0, i))
            anchor = nxt
    if len(rows) < 100:
        return None
    return pd.DataFrame(rows, columns=["time", "open", "high", "low", "close",
                                       "volume", "src"])


# --------------------------------------------------------------------- testing
def signals_on(bars, real_len):
    """bb_break on the constructed bars, mapped back to the 1h timeline.

    A signal at constructed bar j is knowable at the close of the last 1h bar it
    contains, src[j]; the trade must therefore open at 1h bar src[j] + 1. The engine
    enters at open[i] when sig[i] fires, so the signal is placed at src[j] + 1.
    """
    c = bars["close"]
    ma = c.rolling(BB_PERIOD).mean()
    sd = c.rolling(BB_PERIOD).std(ddof=0)
    up, lob = ma + BB_STD * sd, ma - BB_STD * sd
    fire_l = (c > up).to_numpy(bool) & np.isfinite(up.to_numpy())
    fire_s = (c < lob).to_numpy(bool) & np.isfinite(lob.to_numpy())
    src = bars["src"].to_numpy(int)
    sl = np.full(real_len, Action.HOLD, dtype=int)
    ss = np.full(real_len, Action.HOLD, dtype=int)
    for j in range(len(bars)):
        i = src[j] + 1
        if i >= real_len:
            continue
        if fire_l[j]:
            sl[i] = Action.BUY
        if fire_s[j]:
            ss[i] = Action.SELL
    return pd.Series(sl), pd.Series(ss)


def run_type(builder, label):
    """Every coin, both sleeves. Execution ALWAYS on the real 1h OHLC."""
    Rs, Ts = [], []
    nbars = []
    for c in BOOK:
        real = load(c)
        if real is None or len(real) < 3000:
            continue
        bars = builder(real)
        if bars is None or len(bars) < BB_PERIOD + 20:
            continue
        nbars.append(len(bars))
        sl, ss = signals_on(bars, len(real))
        for sig, trail in ((sl, LONG_TRAIL), (ss, SHORT_TRAIL)):
            if int((sig != Action.HOLD).sum()) == 0:
                continue
            R, idx, _b, _d = run_uncapped(real, sig, sl_mult=SL_MULT,
                                          fee_bp=FEE_BP, mode="trail_atr",
                                          trail=trail, be_at=BE_AT)
            if len(R):
                Rs.append(R); Ts.append(real["time"].iloc[idx].to_numpy())
    if not Rs:
        return None
    o = np.argsort(np.concatenate(Ts))
    R = np.concatenate(Rs)[o]
    T = pd.DatetimeIndex(np.concatenate(Ts)[o])
    yrs = max((T[-1] - T[0]).days / 365.25, 1e-9)
    honest = R.mean() / HINDSIGHT
    return dict(label=label, n=len(R), bars=int(np.mean(nbars)) if nbars else 0,
                per_yr=len(R) / yrs, mean=float(R.mean()), honest=float(honest),
                win=float((R > 0).mean() * 100), mx=float(R.max()),
                t=float(R.mean() / (R.std(ddof=1) / np.sqrt(len(R)))))


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: dollar bars beat time bars; volume bars worse;")
    print("Heikin-Ashi looks great and is a trap once execution is on real prices;")
    print("Renko ~ time bars.\n")

    # typical dollar volume per 1h bar, to scale the activity thresholds
    med = np.median([float((load(c)["close"] * load(c)["volume"]).median())
                     for c in BOOK if load(c) is not None])
    medv = np.median([float(load(c)["volume"].median())
                      for c in BOOK if load(c) is not None])
    print(f"median dollar volume per 1h bar across the book: ${med:,.0f}")
    print(f"median unit volume per 1h bar: {medv:,.0f}\n")

    builders = [
        (lambda d: bars_time(d, 1), "TIME 1h (control)"),
        (lambda d: bars_time(d, 4), "TIME 4h (control)"),
        (lambda d: bars_activity(d, "dollar", med * 1), "DOLLAR ~1h of volume"),
        (lambda d: bars_activity(d, "dollar", med * 4), "DOLLAR ~4h of volume"),
        (lambda d: bars_activity(d, "dollar", med * 12), "DOLLAR ~12h of volume"),
        (lambda d: bars_activity(d, "volume", medv * 4), "VOLUME ~4h of units"),
        (bars_heikin, "HEIKIN-ASHI on 1h"),
        (lambda d: bars_renko(d, 1.0), "RENKO brick 1xATR"),
        (lambda d: bars_renko(d, 2.0), "RENKO brick 2xATR"),
    ]
    print("=" * 118)
    print(f"{'bar type':<24} {'bars/coin':>10} {'trades':>8} {'trades/yr':>10} "
          f"{'meanR':>8} {'honest':>8} {'win%':>6} {'maxR':>9} {'t':>7}")
    print("=" * 118)
    res = []
    for b, label in builders:
        d = run_type(b, label)
        if not d:
            print(f"{label:<24} (no result)")
            continue
        res.append(d)
        print(f"{label:<24} {d['bars']:>10,} {d['n']:>8,} {d['per_yr']:>10,.0f} "
              f"{d['mean']:>+8.3f} {d['honest']:>+8.3f} {d['win']:>6.1f} "
              f"{d['mx']:>9.1f} {d['t']:>+7.2f}", flush=True)

    if not res:
        return
    ctl = next((r for r in res if r["label"].startswith("TIME 1h")), None)
    print("\n" + "=" * 118)
    print("AGAINST THE 1h CONTROL — a better mean R only helps if the trade count "
          "holds up")
    print("=" * 118)
    if ctl:
        print(f"  control: {ctl['mean']:+.3f} mean R on {ctl['per_yr']:,.0f} "
              f"trades/yr  (honest {ctl['honest']:+.3f})")
        for r in sorted(res, key=lambda x: -x["mean"]):
            if r is ctl:
                continue
            edge = r["mean"] - ctl["mean"]
            rate = r["per_yr"] / ctl["per_yr"]
            # a crude comparability score: edge per trade x how many trades you get
            score = r["mean"] * r["per_yr"] / (ctl["mean"] * ctl["per_yr"])
            flag = ""
            if score > 1.15 and r["t"] > 2:
                flag = "  <-- BEATS THE CONTROL"
            print(f"  {r['label']:<24} meanR {edge:>+7.3f}  trade rate "
                  f"{rate:>5.2f}x  total-edge {score:>5.2f}x{flag}")
    print("\nREAD 'total-edge': mean R x trades per year, relative to the control.")
    print("That is what compounds. A bar type with double the edge per trade and a")
    print("fifth of the trades scores 0.4x and is worse, however good the meanR looks.")
    print("\nAnd treat HEIKIN-ASHI with suspicion whatever it scores: its bars are")
    print("averages, not prices. Execution here is on real 1h OHLC precisely so that")
    print("its smoothing cannot pay for itself with fills that never existed.")


if __name__ == "__main__":
    main()
