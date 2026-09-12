"""Vectorized technical indicators (pandas). Pure functions, no state."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def stoch_rsi(series: pd.Series, rsi_period: int = 14, stoch_period: int = 14,
              k_smooth: int = 3, d_smooth: int = 3):
    """Stochastic RSI. Returns (%K, %D), both in 0..1.
    %K = smoothed stochastic of RSI; %D = smoothed %K."""
    r = rsi(series, rsi_period)
    lo = r.rolling(stoch_period).min()
    hi = r.rolling(stoch_period).max()
    stoch = (r - lo) / (hi - lo).replace(0, np.nan)
    k = stoch.rolling(k_smooth).mean()
    d = k.rolling(d_smooth).mean()
    return k.fillna(0.5), d.fillna(0.5)


def bollinger(series: pd.Series, period: int = 20, num_std: float = 2.0):
    mid = sma(series, period)
    std = series.rolling(period).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    return lower, mid, upper


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range in price units. Expects columns high/low/close."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Return (macd_line, signal_line, histogram)."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line, macd_line - signal_line


def donchian(df: pd.DataFrame, period: int = 20):
    """Return (lower, upper) Donchian channel of the PRIOR `period` bars
    (shifted by 1 so the current bar's own high/low don't leak in)."""
    upper = df["high"].rolling(period).max().shift(1)
    lower = df["low"].rolling(period).min().shift(1)
    return lower, upper


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (trend strength, 0-100). >~25 = trending."""
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move

    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)


def session_vwap(df: pd.DataFrame):
    """Session-anchored VWAP + rolling sigma bands. Needs a 'volume' column and a
    'time' column; VWAP resets each calendar day. Returns (vwap, sigma)."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df.get("volume")
    if vol is None or vol.sum() == 0:
        vol = pd.Series(1.0, index=df.index)      # fallback: equal weight
    date = df["time"].dt.date
    g = pd.DataFrame({"date": date, "pv": tp * vol, "v": vol, "pv2": tp * tp * vol})
    cum = g.groupby("date").cumsum()
    vwap = cum["pv"] / cum["v"]
    var = (cum["pv2"] / cum["v"]) - vwap ** 2
    sigma = np.sqrt(var.clip(lower=0))
    return vwap, sigma


def efficiency_ratio(series: pd.Series, period: int = 20) -> pd.Series:
    """Kaufman Efficiency Ratio (0-1). High = clean trend, low = chop."""
    change = (series - series.shift(period)).abs()
    volatility = series.diff().abs().rolling(period).sum()
    return (change / volatility.replace(0, np.nan)).fillna(0.0)
