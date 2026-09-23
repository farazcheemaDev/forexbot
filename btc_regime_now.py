"""WHERE IS THE MARKET RIGHT NOW? - a read-only readout of the BTC signals that held up.

Public endpoints only (Binance spot klines, Binance futures funding, Coinbase candles). No
keys, no orders. Prints each signal, what it means, and what the bot does in this state.

WHICH SIGNALS, AND WHY THESE (docs/12-btc-signals.md)
    Used by the bot, validated on the corrected engine:
      GATE   BTC above / below its 1000-hour average -> long risk x1 / x0.25. As a pure BTC
             timing rule it beat every outside signal tested (btc_timing.py: Sharpe 1.12 vs
             0.68 for holding).
      BREAK  BTC's 4h trail break (close < highest close since the last break - 5 x ATR14) ->
             open longs switch to a 5xATR trail: the tight exit, the "know when to stop" rule.
    Context only - they predict BTC's direction weakly and add NOTHING to the bot on top of the
    two above (btc_signals.py, btc_dial.py). Shown because they say who is buying:
      TSMOM  sign(BTC 7d) + sign(28d) + sign(90d), -3..+3
      CBPREM Coinbase premium, 7-day mean: US spot demand vs offshore
      FUND   BTC perp funding, last 3 settlements: how crowded the longs are

    python btc_regime_now.py
"""
from __future__ import annotations

import json
import urllib.request

import numpy as np
import pandas as pd


def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(
        u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))


def binance_1h(n=2600):
    rows, end = [], None
    while len(rows) < n:
        u = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=1000"
        if end:
            u += f"&endTime={end}"
        d = get(u)
        if not d:
            break
        rows = d + rows
        end = d[0][0] - 1
    df = pd.DataFrame(rows, columns=list("tohlcv") + ["ct", "q", "n", "tb", "tq", "x"])
    df = df.drop_duplicates("t").sort_values("t")
    df["time"] = pd.to_datetime(df.t, unit="ms")
    for k in "ohlc":
        df[k] = df[k].astype(float)
    return df.iloc[:-1].set_index("time")                 # closed bars only


def atr(df, n=14):
    pc = df.c.shift(1)
    tr = pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def main():
    h = binance_1h()
    px = h.c.iloc[-1]
    ma = h.c.rolling(1000).mean().iloc[-1]
    gate_bull = px > ma

    b4 = h.resample("4h", label="right", closed="right").agg(
        {"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    a4 = atr(b4)
    best, broke, last_break = -np.inf, False, None
    for t, c, a in zip(b4.index, b4.c, a4):
        best = max(best, c)
        broke = bool(np.isfinite(a) and c < best - 5 * a)
        if broke:
            best, last_break = c, t
    level = best - 5 * a4.iloc[-1]

    d = h.c.resample("D").last()
    ts = int(sum(np.sign(d.iloc[-1] / d.iloc[-1 - k] - 1) for k in (7, 28, 90)))

    try:
        end = pd.Timestamp.now("UTC").floor("h").tz_localize(None)
        cb = get("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600"
                 f"&start={(end - pd.Timedelta(hours=168)):%Y-%m-%dT%H:%M:%SZ}&end={end:%Y-%m-%dT%H:%M:%SZ}")
        ut = get("https://api.exchange.coinbase.com/products/USDT-USD/candles?granularity=3600"
                 f"&start={(end - pd.Timedelta(hours=168)):%Y-%m-%dT%H:%M:%SZ}&end={end:%Y-%m-%dT%H:%M:%SZ}")
        cbs = pd.Series({pd.to_datetime(x[0], unit="s"): x[4] for x in cb})
        uts = pd.Series({pd.to_datetime(x[0], unit="s"): x[4] for x in ut})
        j = pd.concat([cbs.rename("cb"), h.c.rename("bn"), uts.rename("ut")], axis=1).dropna()
        prem = float((j.cb / (j.bn * j.ut) - 1).mean() * 100)
    except Exception:
        prem = float("nan")

    try:
        fr = get("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=3")
        fund = float(np.mean([float(x["fundingRate"]) for x in fr]) * 100)
    except Exception:
        fund = float("nan")

    print(f"BTC ${px:,.0f}   (last closed hour {h.index[-1]:%Y-%m-%d %H:%M} UTC)\n")
    print("USED BY THE BOT")
    print(f"  GATE   {'BULL' if gate_bull else 'BEAR'}: price {'above' if gate_bull else 'below'} the "
          f"1000h average ${ma:,.0f} ({(px / ma - 1) * 100:+.1f}%)")
    print(f"         -> new positions at {'full' if gate_bull else 'QUARTER'} risk "
          f"({0.30 if gate_bull else 0.075:.3f}% per unit)")
    print(f"  BREAK  {'BROKEN on the last 4h bar' if broke else 'intact'}; next break below "
          f"${level:,.0f} on a 4h close ({(level / px - 1) * 100:+.1f}% from here)"
          + (f"; last break {last_break:%Y-%m-%d %H:%M}" if last_break is not None else ""))
    print(f"         -> {'open longs switch to the 5xATR trail (tight book)' if broke else 'open longs keep the 20xATR trail'}")
    print("\nCONTEXT (weak predictors - they do NOT change what the bot does)")
    print(f"  TSMOM  {ts:+d} of 3  (BTC 7d/28d/90d trend signs)")
    print(f"  CBPREM {prem:+.3f}%  7-day Coinbase premium - {'US buying above offshore' if prem > 0 else 'US selling / no US bid'}")
    print(f"  FUND   {fund:+.4f}% per 8h  - {'longs paying (crowded long)' if fund > 0.01 else 'neutral / shorts paying'}")
    regime = "BULL" if (ts >= 1 and prem > 0) else ("BEAR" if (ts <= -1 and prem < 0) else "NEUTRAL")
    print(f"  REGIME {regime}  (both context signals agreeing; bot longs opened in BULL averaged "
          f"+2.2R, NEUTRAL +0.6R, BEAR +0.05R - btc_dial.py)")


if __name__ == "__main__":
    main()
