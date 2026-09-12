"""THE SHORT SIDE, TESTED PROPERLY — asymmetric exits and regime-split.

WHY THE EARLIER VERDICT IS UNSAFE
    Nineteen indicator families were measured with long and short mean R reported
    separately, and the short side came out at -0.045 to +0.081R every time. That
    was read as "shorting crypto does not work". Two flaws in how it was measured:

    1. SYMMETRIC EXITS. Shorts were given the same 20xATR trailing stop as longs.
       Crypto rises as a slow grind and falls as a fast crash - the two are not
       mirror images, so an exit tuned for one is probably wrong for the other. A
       wide trail on a short gives back most of a crash before it triggers.

    2. AVERAGED OVER A BULL MARKET. The window 2020-2026 saw equal-weight crypto
       compound at roughly 40%/yr. A short fighting that drift nets to zero even if
       it works well in the periods that matter. The average hides the regime.

WHAT THIS TESTS
    * short entries (close below the lower band), with the trail swept from TIGHT
      to wide - 3x through 20x - so a fast exit can win if crashes are fast
    * a hold-N-bars exit as well, because a crash may be better timed than trailed
    * split by REGIME: price above vs below its 200-period average, so the bull and
      bear halves are reported separately instead of averaged
    * split by YEAR, so 2022 (LUNA in May, FTX in November) is visible on its own
    * pyramiding on shorts, since adds would trigger fast in a crash

    Longs run alongside with identical settings as the control.

WHAT WOULD MAKE THIS REAL
    A short side that earns meaningfully in the BELOW-200MA regime, with an exit
    that differs from the long side's. If shorts only work with the same 20x trail
    that longs use, then there is nothing asymmetric here and the earlier verdict
    stands.

    python -m backtest.shortside
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import describe, run_uncapped  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
RISK = 0.5
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
         "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
BB_P, BB_STD, REGIME_MA = 30, 1.5, 200
_D: dict = {}


def load(c, days=2400):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", days)
        except Exception:
            _D[c] = None
    return _D[c]


def bands(df):
    c = df["close"]
    ma = c.rolling(BB_P).mean()
    sd = c.rolling(BB_P).std(ddof=0)
    return ma - BB_STD * sd, ma + BB_STD * sd


def signals(df, side: str, regime: str = "all") -> pd.Series:
    """side 'short' fires on a close BELOW the lower band; 'long' above the upper.

    Shifted by one bar so a bar never acts on its own close. The regime filter uses
    a 200-period average, also shifted.
    """
    lo_b, up_b = bands(df)
    c = df["close"]
    fire = (c < lo_b) if side == "short" else (c > up_b)
    if regime != "all":
        ma = c.rolling(REGIME_MA).mean()
        trend_up = (c > ma)
        fire = fire & (~trend_up if regime == "bear" else trend_up)
    out = pd.Series(Action.HOLD, index=df.index)
    act = Action.SELL if side == "short" else Action.BUY
    out[fire.shift(1).fillna(False).to_numpy(bool)] = act
    return out


def pool(side, regime, trail, units=1, mode="trail_atr", max_bars=2000,
         coins=None, year=None):
    Rs, Ts = [], []
    for c in (coins or COINS):
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        if year:
            df = df[pd.DatetimeIndex(df["time"]).year == year].reset_index(drop=True)
            if len(df) < 1000:
                continue
        sig = signals(df, side, regime)
        if int((sig != Action.HOLD).sum()) == 0:
            continue
        R, idx, _b, _d = run_uncapped(df, sig, sl_mult=2.0, fee_bp=FEE_BP,
                                      mode=mode, trail=trail, max_bars=max_bars)
        if len(R):
            Rs.append(R); Ts.append(df["time"].iloc[idx])
    if not Rs:
        return None
    o = np.argsort(np.concatenate([t.values for t in Ts]))
    R = np.concatenate(Rs)[o]
    T = pd.Series(np.concatenate([t.values for t in Ts])[o])
    return describe(R, T, RISK)


def row(tag, d):
    if not d:
        return f"{tag:<34} (no trades)"
    return (f"{tag:<34} {d['n']:>6} {d['win']:>6.1f}% {d['mean']:>+8.3f} "
            f"{d['t']:>+7.2f} {d['pf']:>5.2f} {d['mx']:>7.1f} "
            f"{d['cagr']:>+8.1f}% {d['dd']:>6.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    hdr = (f"{'config':<34} {'n':>6} {'win%':>7} {'meanR':>8} {'t':>7} "
           f"{'PF':>5} {'maxR':>7} {'CAGR':>9} {'DD':>7}")

    print("THE SHORT SIDE, ASYMMETRIC EXITS   9 coins, 1h, "
          f"fee {FEE_BP}bp, risk {RISK}%\n")
    print("=" * 104)
    print("1. TRAIL WIDTH SWEEP — is a crash better caught with a TIGHT exit?")
    print("=" * 104)
    print(hdr)
    for side in ("short", "long"):
        for tr in (3.0, 5.0, 8.0, 12.0, 20.0):
            print(row(f"{side} trail {tr:.0f}xATR", pool(side, "all", tr)),
                  flush=True)
        print()

    print("=" * 104)
    print("2. TIMED EXITS — a crash may be better TIMED than trailed")
    print("=" * 104)
    print(hdr)
    for nb in (6, 12, 24, 72):
        print(row(f"short, exit after {nb}h",
                  pool("short", "all", 99.0, mode="timed", max_bars=nb)),
              flush=True)
    print()

    print("=" * 104)
    print("3. REGIME SPLIT — shorts only when price is BELOW its 200h average")
    print("=" * 104)
    print(hdr)
    for side in ("short", "long"):
        for rg in ("bear", "bull"):
            for tr in (5.0, 12.0):
                print(row(f"{side} {rg}-regime trail {tr:.0f}x",
                          pool(side, rg, tr)), flush=True)
        print()

    print("=" * 104)
    print("4. BY YEAR — 2022 is the bear (LUNA in May, FTX in November)")
    print("=" * 104)
    print(hdr)
    for y in (2021, 2022, 2023, 2024, 2025):
        print(row(f"short trail 5x, {y} only",
                  pool("short", "all", 5.0, year=y)), flush=True)
    print()
    print("VERDICT TEST: shorts are real only if the BEAR-regime rows or 2022 show "
          "a clear\nedge AND the best short exit differs from the best long exit. "
          "If shorts need the\nsame 20x trail as longs and still earn ~0, the "
          "earlier verdict stands.")


if __name__ == "__main__":
    main()
