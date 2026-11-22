"""THE '$20 ORDER BOOK BOT' SPEC'S TRADE BRACKET, FROM RANDOM ENTRIES (a baseline check, not a strategy test).

WHY
    The user's spec (Downloads/Orderbook Bot 20usd Claude Spec.md.pdf, written with another agent) enters on order-book signals and
    exits at +0.25% (take-profit), -0.35% (stop) or after 180 s. CLAUDE.md s2: a signal is judged against what a RANDOM entry
    with the same bracket does. This file measures that baseline: how often the target / the stop / neither is touched in
    3 one-minute bars from a random minute, and the expected value per trade in basis points with no signal at all.

METHOD
    Entry at a bar's close; the next 3 bars' high / low decide (a bar touching both counts as the STOP - pessimistic); no
    touch = timeout, exit at the 3rd bar's close. Long and short, Binance perp 1-minute bars 2022-01..2026-08
    (strategy_analysis/data/min1: DOGE and BTC; the spec's XRP is not cached). No spread, no fill selection (a resting limit
    fills only when price comes to it, which makes real entries WORSE - book_hist.py, passive_markout.py), no slippage.
    Costs per trade in bp: maker side m (entry, and the take-profit), taker side k (stop, and the timeout exit):
    zero-fee venue m = k = 0; Hyperliquid's published base rates m = 1.5, k = 4.5.

PREDICTED BEFORE RUNNING (2026-11-06): DOGE target first 3-8%, stop first 1-3%, timeout over 88%.
RESULT (logs/spec_bracket_baseline.txt): WRONG on DOGE - target first 13.8% long / 14.6% short, stop first 7.9% / 7.3%, timeout 78%
    (DOGE moves more than I scaled). BTC: 4.6% / 2.1%, timeout 93%. Random entries earn -0.0 to -0.2 bp a trade with no fees and
    -5.6 to -5.9 bp a trade at Hyperliquid's rates, on both coins and both sides. Of the trades that touch a level, random entries hit the target first 64-69% (above the 58.3% break-even
    for the bracket, 65.1% at Hyperliquid's fees); the loss is the TIMEOUTS: 78-93% of trades exit with no gain and
    still pay about 6 bp (1.5 maker in + 4.5 taker out). The year-by-year target-first share swings 8-19% on DOGE (volatility).

    python backtest/spec_bracket_baseline.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TP, SL, N = 0.0025, 0.0035, 3          # the spec: +0.25% target, -0.35% stop, 180 s = 3 one-minute bars


def load(sym):
    d = pd.read_parquet(ROOT / "strategy_analysis" / "data" / "min1" / f"{sym}USDT_1m.parquet").sort_values("time").reset_index(drop=True)
    d = d.rename(columns={"time": "t", "o": "open", "h": "high", "l": "low", "c": "close"})
    gap = d.t.diff().dt.total_seconds().fillna(60)
    print(f"   (bars with a gap over 2 min before them: {(gap > 120).sum()})")
    return d[["t", "open", "high", "low", "close"]]


def run(d, side):
    h, l, c = (d[k].to_numpy(float) for k in ("high", "low", "close"))
    n = len(c) - N
    c0 = c[:n]
    out = np.zeros(n, int)       # 0 timeout, 1 target first, -1 stop first
    done = np.zeros(n, bool)
    for k in range(1, N + 1):
        hk, lk = h[k:k + n], l[k:k + n]
        if side == "long":
            tp_hit = hk >= c0 * (1 + TP)
            sl_hit = lk <= c0 * (1 - SL)
        else:
            tp_hit = lk <= c0 * (1 - TP)
            sl_hit = hk >= c0 * (1 + SL)
        sl_now = sl_hit & ~done                      # a bar touching both counts as the stop (pessimistic)
        tp_now = tp_hit & ~sl_hit & ~done
        out[sl_now] = -1
        out[tp_now] = 1
        done |= sl_now | tp_now
    ret = (c[N:N + n] / c0 - 1) * (1 if side == "long" else -1)
    return out, ret


def main():
    for sym in ("DOGE", "BTC"):
        d = load(sym)
        print(f"\n{sym}: {len(d):,} one-minute bars {d.t.iloc[0]:%Y-%m-%d} .. {d.t.iloc[-1]:%Y-%m-%d}")
        for side in ("long", "short"):
            o, r = run(d, side)
            p_tp, p_sl, p_to = (o == 1).mean(), (o == -1).mean(), (o == 0).mean()
            to = r[o == 0] * 1e4

            def ev(maker, taker):
                return (p_tp * (TP * 1e4 - 2 * maker) + p_sl * (-SL * 1e4 - maker - taker)
                        + p_to * (to.mean() - maker - taker))
            print(f"  {side:5}: target first {p_tp:6.2%} | stop first {p_sl:6.2%} | timeout {p_to:6.2%}"
                  f" (timeout move mean {to.mean():+.2f} bp, sd {to.std():.1f} bp)"
                  f" | EV/trade: zero-fee {ev(0, 0):+.2f} bp, Hyperliquid(1.5/4.5) {ev(1.5, 4.5):+.2f} bp")
            yrs = d.t.iloc[:len(o)].dt.year.to_numpy()
            print("         target-first by year: " + ", ".join(f"{y} {(o[yrs == y] == 1).mean():.1%}" for y in sorted(set(yrs))))
        print(f"  break-even target-first share at zero cost, ignoring timeouts: {SL / (TP + SL):.1%}"
              f"  (with Hyperliquid fees: {(SL * 1e4 + 6) / (TP * 1e4 - 3 + SL * 1e4 + 6):.1%})")


if __name__ == "__main__":
    main()
