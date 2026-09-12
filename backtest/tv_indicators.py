"""THE POPULAR TRADINGVIEW INDICATORS WE HAVE NEVER TESTED.

WHY THESE AND NOT OTHERS
    Already covered elsewhere in this project: RSI (momentum and reversion), MACD,
    Bollinger (breakout and reversion), EMA/MA cross, Donchian, Stochastic RSI,
    VWAP, z-score, ROC momentum, Kaufman efficiency ratio, VSA, level fade,
    liquidity sweep.

    The families below are the ones genuinely absent, chosen because each asks a
    structurally DIFFERENT question rather than being another oscillator on close:

      supertrend      ATR-offset trend flip. The most-used script on TradingView.
      ichimoku        multi-component cloud; conversion/base/span construction is
                      unlike anything tested here.
      keltner         ATR bands rather than standard-deviation bands. Whether the
                      band should scale with TRUE RANGE or with dispersion of
                      closes is a real question, not a cosmetic one.
      ttm_squeeze     Bollinger INSIDE Keltner = volatility compression. Asks
                      "is a move coming", not "which way" - a different question.
      psar            accelerating stop, not a level.
      aroon           time SINCE the extreme, not distance FROM it. The only
                      formulation here that is not a price-distance measure.
      adx_dmi         trend STRENGTH with directional components.
      chandelier      ATR trail anchored to highest high.

WHAT IS DELIBERATELY NOT HERE
    CCI, Williams %R, MFI, Vortex, KST, Coppock. All are close-based oscillators
    and measured ~0.6-0.9 correlated with RSI/MACD variants in the sleeve study,
    so they would add search space without adding information. Order blocks and
    fair-value-gaps are genuinely different but need a discretionary definition
    that cannot be pinned down without fitting it, so they are left out rather
    than implemented in a form I would be choosing after the fact.

CAUSALITY
    Every function returns a series aligned to the bar it is computed on. Callers
    must shift before use - the engine (run_uncapped) enters at open[i] using
    signals derived from bar i-1 and earlier. The ATR look-ahead that once inflated
    MAR to 35 came from ignoring exactly this.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot.core.indicators import atr as atr_ind, ema, sma


def supertrend(df: pd.DataFrame, period: int = 10, mult: float = 3.0):
    """(trend, line). trend=+1 uptrend, -1 downtrend.

    Bands are ATR-offset from hl2 and RATCHET: the upper band only falls while in
    a downtrend, the lower only rises while in an uptrend. That path dependence is
    the whole indicator and cannot be vectorised away, hence the loop.
    """
    a = atr_ind(df, period)
    hl2 = (df["high"] + df["low"]) / 2.0
    up = (hl2 + mult * a).to_numpy(float)
    dn = (hl2 - mult * a).to_numpy(float)
    c = df["close"].to_numpy(float)
    n = len(df)
    tr = np.ones(n, dtype=int)
    fu, fl = up.copy(), dn.copy()
    for i in range(1, n):
        if not (np.isfinite(up[i]) and np.isfinite(dn[i])):
            tr[i] = tr[i - 1]
            continue
        fu[i] = min(up[i], fu[i - 1]) if c[i - 1] <= fu[i - 1] else up[i]
        fl[i] = max(dn[i], fl[i - 1]) if c[i - 1] >= fl[i - 1] else dn[i]
        if c[i] > fu[i - 1]:
            tr[i] = 1
        elif c[i] < fl[i - 1]:
            tr[i] = -1
        else:
            tr[i] = tr[i - 1]
    line = np.where(tr == 1, fl, fu)
    return (pd.Series(tr, index=df.index), pd.Series(line, index=df.index))


def keltner(df: pd.DataFrame, period: int = 20, mult: float = 2.0):
    """(mid, upper, lower) using EMA and ATR."""
    mid = ema(df["close"], period)
    a = atr_ind(df, period)
    return mid, mid + mult * a, mid - mult * a


def ttm_squeeze(df: pd.DataFrame, period: int = 20, bb_std: float = 2.0,
                kc_mult: float = 1.5):
    """(in_squeeze, momentum). in_squeeze=True when Bollinger sits INSIDE Keltner.

    Compression, not direction. The trade is the RELEASE: a squeeze ending while
    momentum is positive is the long setup.
    """
    c = df["close"]
    ma = c.rolling(period).mean()
    sd = c.rolling(period).std(ddof=0)
    bb_u, bb_l = ma + bb_std * sd, ma - bb_std * sd
    a = atr_ind(df, period)
    kc_u, kc_l = ma + kc_mult * a, ma - kc_mult * a
    inside = (bb_u < kc_u) & (bb_l > kc_l)
    # momentum: close vs the midpoint of the Donchian/MA average, linreg-free
    mid = (df["high"].rolling(period).max() + df["low"].rolling(period).min()) / 2
    mom = c - (mid + ma) / 2
    return inside, mom


def psar(df: pd.DataFrame, af0: float = 0.02, step: float = 0.02,
         af_max: float = 0.2) -> pd.Series:
    """Parabolic SAR. Returns +1 long / -1 short regime. Inherently sequential."""
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    n = len(df)
    trend = np.ones(n, dtype=int)
    sar = np.full(n, np.nan)
    if n < 3:
        return pd.Series(trend, index=df.index)
    up = True
    af = af0
    ep = h[0]
    sar[0] = l[0]
    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if up:
            if l[i] < sar[i]:
                up, sar[i], ep, af = False, ep, l[i], af0
            else:
                if h[i] > ep:
                    ep, af = h[i], min(af + step, af_max)
                sar[i] = min(sar[i], l[i - 1], l[i])
        else:
            if h[i] > sar[i]:
                up, sar[i], ep, af = True, ep, h[i], af0
            else:
                if l[i] < ep:
                    ep, af = l[i], min(af + step, af_max)
                sar[i] = max(sar[i], h[i - 1], h[i])
        trend[i] = 1 if up else -1
    return pd.Series(trend, index=df.index)


def aroon(df: pd.DataFrame, period: int = 25):
    """(aroon_up, aroon_down), 0-100.

    Measures BARS SINCE the extreme, not distance from it. The only formulation in
    this file that is not a price-distance measure, which is the main reason it is
    worth testing alongside the rest.
    """
    hi = df["high"].rolling(period + 1).apply(
        lambda x: float(np.argmax(x)), raw=True)
    lo = df["low"].rolling(period + 1).apply(
        lambda x: float(np.argmin(x)), raw=True)
    return (hi / period) * 100.0, (lo / period) * 100.0


def dmi(df: pd.DataFrame, period: int = 14):
    """(plus_di, minus_di, adx)."""
    h, l, c = df["high"], df["low"], df["close"]
    up = h.diff()
    dn = -l.diff()
    plus = ((up > dn) & (up > 0)) * up.clip(lower=0)
    minus = ((dn > up) & (dn > 0)) * dn.clip(lower=0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1 / period, adjust=False).mean()
    pdi = 100 * plus.ewm(alpha=1 / period, adjust=False).mean() / atr_
    mdi = 100 * minus.ewm(alpha=1 / period, adjust=False).mean() / atr_
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return pdi, mdi, dx.ewm(alpha=1 / period, adjust=False).mean()


def ichimoku(df: pd.DataFrame, conv: int = 9, base: int = 26, span_b: int = 52):
    """(tenkan, kijun, senkou_a, senkou_b).

    NOTE ON THE CLOUD: senkou spans are conventionally plotted SHIFTED FORWARD by
    `base` bars. Plotting forward is a display convention; using the forward-shifted
    value as a signal at the current bar would read the future. These are returned
    UNSHIFTED, so a caller comparing price to the cloud is comparing against values
    computed from past data only.
    """
    hi, lo = df["high"], df["low"]
    tenkan = (hi.rolling(conv).max() + lo.rolling(conv).min()) / 2
    kijun = (hi.rolling(base).max() + lo.rolling(base).min()) / 2
    sen_a = (tenkan + kijun) / 2
    sen_b = (hi.rolling(span_b).max() + lo.rolling(span_b).min()) / 2
    return tenkan, kijun, sen_a, sen_b


def chandelier(df: pd.DataFrame, period: int = 22, mult: float = 3.0):
    """(long_stop, short_stop) — ATR trail anchored to the rolling extreme."""
    a = atr_ind(df, period)
    return (df["high"].rolling(period).max() - mult * a,
            df["low"].rolling(period).min() + mult * a)
