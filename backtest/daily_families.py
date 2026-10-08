"""PHASE 2 (re-testing thin kills): the long indicator families on DAILY bars, point-in-time top-40 (2026-10-08).

THE CLAIM BEING RE-TESTED (doc 02, "Dead: sounded good, measured badly"): "19 of 19 families profitable long ... they
all detect the same phenomenon. Searching for more indicators is exhausted." Its backing: LONGS measured on 9 coins
that are big TODAY (hindsight), on hourly bars. The short side was later re-run fairly (short_families.py, 365 PIT
coins, 1h/4h/12h); the long side never was on daily bars. And today the one big no-hindsight result
(tv_indicators.py -> daily_phase.py) came from exactly that cell: Bollinger(30, 1.5) on DAILY bars of the PIT top-40.
tv_indicators.py covered 12 TradingView indicators there; these 9 families were left out:
    donchian20 / donchian55   close above the prior 20 / 55-day high
    ma_cross                  EMA20 crosses above EMA50
    macd                      MACD(12,26) crosses above its 9-day signal while above zero
    roc                       20-day rate of change crosses above zero
    keltner                   close above EMA20 + 2 x ATR(14)
    aroon                     Aroon-up(25) crosses above 70 with Aroon-down < 30
    adx_dmi                   +DI crosses above -DI with ADX(14) > 20
    rsi_mom                   RSI(14) crosses above 60
  and one filter on the bb entry: Kaufman efficiency ratio(30) >= 0.3 (the "momentum + ER" survivor doc 02 dropped
  for its portfolio correlation, never tried on this book)
Same machinery as daily_combos.py: the daily book's exit (close under the 30-day mean, 30-day cap), 8 slots, 1x,
marked to market, 3 day boundaries x 10 orders, judged against the bb base's leverage line on both halves.

REGISTERED BEFORE RUNNING: the breakout families (donchian20/55, keltner) land within +-30% of bb's CAGR and one of
them may pass; the cross families (ma_cross, macd, roc, aroon, adx_dmi) enter late and lose to bb on the line;
rsi_mom sits near bb; the ER filter fails (fewer trades, same per-trade). At most 1 of 10 passes - i.e. on daily
PIT bars the claim "the indicator does not matter much" survives, but it was not tested where it should have been.

RESULT (2026-10-08, logs/daily_families.txt): 0 of 10 beat bb. Keltner is closest (holdout above the line at all 3
    boundaries, tune below at 2); donchian55 and bb+ER the same holdout-only pattern; the cross families (ma_cross,
    roc, aroon, adx_dmi) lose the holdout outright. With tv_indicators.py, bb(30,1.5) is first of 22 daily entries on
    the PIT top-40: the claim now has the backing it lacked. Predictions: at most 1 passes - right; breakout families
    within 30% - keltner only; cross families lose - right; ER fails - right.

    python -m backtest.daily_families
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import daily_combos as dc  # noqa: E402

LOG = ROOT / "logs" / "daily_families.txt"


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def cross_up(a, b):
    return np.r_[False, (a[1:] > b[1:]) & (a[:-1] <= b[:-1])]


def donchian(n):
    return lambda P: P["c"] > pd.Series(P["h"]).rolling(n).max().shift(1).to_numpy()


def ma_cross(P):
    return cross_up(ema(P["c"], 20), ema(P["c"], 50))


def macd(P):
    m = ema(P["c"], 12) - ema(P["c"], 26)
    return cross_up(m, ema(m, 9)) & (m > 0)


def roc(P):
    c = P["c"]
    r = np.r_[np.full(20, np.nan), c[20:] / c[:-20] - 1]
    return cross_up(np.nan_to_num(r, nan=-1.0), np.zeros(len(c)))


def keltner(P):
    return P["c"] > ema(P["c"], 20) + 2 * P["atr"]


def aroon(P, n=25):
    h, l = pd.Series(P["h"]), pd.Series(P["l"])
    up = h.rolling(n + 1).apply(lambda x: 100 * x.argmax() / n, raw=True).to_numpy()
    dn = l.rolling(n + 1).apply(lambda x: 100 * x.argmin() / n, raw=True).to_numpy()
    return cross_up(np.nan_to_num(up), np.full(len(up), 70.0)) & (dn < 30)


def adx_dmi(P, n=14):
    h, l, c = P["h"], P["l"], P["c"]
    up, dn = np.r_[0, h[1:] - h[:-1]], np.r_[0, l[:-1] - l[1:]]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr = P["atr"]
    sm = lambda x: pd.Series(x).ewm(alpha=1 / n, adjust=False).mean().to_numpy()  # noqa: E731
    pdi, mdi = 100 * sm(pdm) / atr, 100 * sm(mdm) / atr
    dx = 100 * np.abs(pdi - mdi) / np.where(pdi + mdi > 0, pdi + mdi, np.nan)
    adx = sm(np.nan_to_num(dx))
    return cross_up(np.nan_to_num(pdi), np.nan_to_num(mdi)) & (adx > 20)


def rsi_mom(P):
    return cross_up(np.nan_to_num(P["r"]), np.full(len(P["r"]), 60.0))


def bb_er(P):
    c = P["c"]
    m = pd.Series(c).rolling(30).mean().to_numpy()
    sd = pd.Series(c).rolling(30).std(ddof=0).to_numpy()
    d = np.abs(np.r_[np.nan, np.diff(c)])
    er = np.abs(np.r_[np.full(30, np.nan), c[30:] - c[:-30]]) / pd.Series(d).rolling(30).sum().to_numpy()
    return (c > m + 1.5 * sd) & (er >= 0.3)


FAM = {"donchian20": donchian(20), "donchian55": donchian(55), "ma_cross 20/50": ma_cross, "macd": macd, "roc": roc,
       "keltner": keltner, "aroon": aroon, "adx_dmi": adx_dmi, "rsi_mom": rsi_mom, "bb + ER(30) >= 0.3": bb_er}


def main():
    base, btr = dc.run(dc.BASE, dc.LEVS)

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in dc.SEEDS])

    line = {off: sorted((agg(base, off, "fall", lv), agg(base, off, "tune", lv), agg(base, off, "hold", lv)) for lv in dc.LEVS)
            for off in dc.PHASES}
    lines = [f"backtest/daily_families.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-40 daily, the daily book's exit, 8 slots "
             f"1x, marked to market, 3 day boundaries x 10 orders", "",
             f"  {'entry':20} {'trades':>6} {'per trade tune/hold':>20} | {'CAGR tune':>9} {'hold':>6} {'fall':>5} {'worst mo':>8} | "
             f"vs bb's line tune/hold by boundary -> verdict"]
    rows = [("bb(30,1.5) BASE", None)] + list(FAM.items())
    for nm, fn in rows:
        r, tr = (base, btr) if fn is None else dc.run(dict(dc.BASE, entry=fn))
        cells, ok = [], True
        for off in dc.PHASES:
            fa = agg(r, off, "fall")
            f = [a for a, _, _ in line[off]]
            dt = agg(r, off, "tune") - np.interp(fa, f, [b for _, b, _ in line[off]])
            dh = agg(r, off, "hold") - np.interp(fa, f, [c for _, _, c in line[off]])
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
        lines.append(f"  {nm:20} {np.mean([tr[o][0] for o in dc.PHASES]):6.0f} {np.nanmean([tr[o][1] for o in dc.PHASES]) * 100:+9.2f}% / "
                     f"{np.nanmean([tr[o][2] for o in dc.PHASES]) * 100:+5.2f}% | {np.mean([agg(r, o, 'tune') for o in dc.PHASES]) * 100:+8.0f}% "
                     f"{np.mean([agg(r, o, 'hold') for o in dc.PHASES]) * 100:+5.0f}% {np.mean([agg(r, o, 'fall') for o in dc.PHASES]) * 100:4.0f}% "
                     f"{np.mean([agg(r, o, 'wm') for o in dc.PHASES]) * 100:+7.1f}% | {'  '.join(cells)} -> "
                     f"{'-' if fn is None else ('PASS' if ok else 'fail')}")
        print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
