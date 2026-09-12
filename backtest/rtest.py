"""Scale-free R-multiple backtest. No position sizing, no lot clamps, no bugs.

WHY THIS EXISTS
---------------
run_backtest() sizes positions in lots and clamps them to broker min/max. That
is correct for live trading but poison for measurement: the actual dollars
risked per trade then varies with price level, so

    R = pnl / (assumed fixed risk)

is wrong, and profit factor computed from those dollar P&Ls is dominated by
whichever trades happened to get the biggest lots.

It bit us twice. On 2026-09-11 the holdout sweep reported mean R = +2.15 for
rsi_mom on BTC - arithmetically impossible with a 2 ATR stop and 3 ATR target,
where a win caps at +1.5R - while the same equity curve went to zero. Low-priced
assets (DOGE +0.0002, ADA +0.0011) pinned against the lot cap and looked flat.

THE FIX. Risk one unit per trade, by definition, and measure the outcome in
units of the stop distance:

    R = (exit - entry) * direction / stop_distance      stop_distance = SL x ATR

Now a stop-out is exactly -1R and the target is exactly +TP/SL R on every asset
at every price, so numbers are comparable across BTC at $70,000 and DOGE at
$0.08. Costs are charged in the same units: a round trip of `fee_bp` basis
points of notional is (fee_bp/10000) * entry / stop_distance in R.

Entries are at the NEXT bar's open after a signal (signals are already shifted
by 1 upstream, so reading open[i] is causal). Stops are checked before targets
within a bar - the pessimistic assumption, since we cannot see intrabar order.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot.core.indicators import atr as atr_ind
from bot.strategies.base import Action


def run_r(df: pd.DataFrame, sig: pd.Series, sl_mult: float = 2.0,
          tp_mult: float = 3.0, fee_bp: float = 10.0,
          atr_period: int = 14, fee_abs: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Return (R per trade, exit bar index per trade).

    fee_bp:  round-trip cost as basis points of notional (crypto/percentage fees)
    fee_abs: round-trip cost in PRICE UNITS (index/forex spreads quoted in points
             or pips). Both are charged; use whichever fits the instrument.
    """
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    a = atr_ind(df, atr_period).to_numpy(float)
    n = len(df)
    fee = fee_bp / 10000.0

    Rs, idx = [], []
    pos = None
    for i in range(1, n):
        # ENTRY FIRST, sized from a[i-1]. Using a[i] would be LOOK-AHEAD: ATR at
        # bar i contains bar i's own high/low/close, which are unknown at its
        # open. That leak let the strategy widen its stop on bars that turned out
        # volatile and tighten on quiet ones - worth ~0.25R/trade of pure
        # fiction (MAR 35). Found 2026-09-11; same class as the filter
        # look-ahead fixed earlier in mass_search.
        if pos is None and s[i] != Action.HOLD and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            d = 1 if s[i] == Action.BUY else -1
            e = o[i]                      # signals are pre-shifted: open[i] is causal
            risk = sl_mult * a[i - 1]
            pos = (d, e, risk, e - d * risk, e + d * tp_mult * a[i - 1])
        # then exits, INCLUDING on the entry bar itself - a real position can be
        # stopped out by the very bar it opened in.
        if pos is not None:
            d, e, risk, stop, targ = pos
            hit_sl = (lo[i] <= stop) if d == 1 else (h[i] >= stop)
            hit_tp = (h[i] >= targ) if d == 1 else (lo[i] <= targ)
            px = stop if hit_sl else (targ if hit_tp else None)   # stop wins ties
            if px is not None:
                R = (px - e) * d / risk - (fee * e + fee_abs) / risk
                Rs.append(R); idx.append(i)
                pos = None
    return np.asarray(Rs), np.asarray(idx, dtype=int)


def stats(R: np.ndarray, times: pd.Series | None = None,
          risk_pct: float = 1.0) -> dict | None:
    """Expectancy plus compounded CAGR / drawdown / MAR at a given risk fraction."""
    if len(R) == 0:
        return None
    gw, gl = R[R > 0].sum(), -R[R < 0].sum()
    eq, curve = 1.0, [1.0]
    for r in R:
        eq *= (1 + r * risk_pct / 100.0)
        curve.append(max(eq, 1e-12))
    c = np.array(curve)
    peak = np.maximum.accumulate(c)
    dd = float(((peak - c) / peak).max() * 100)
    out = dict(n=int(len(R)), meanR=float(R.mean()), sumR=float(R.sum()),
               medR=float(np.median(R)), win=float((R > 0).mean()),
               pf=float(gw / gl) if gl > 0 else float("inf"),
               worst=float(R.min()), best=float(R.max()),
               final=float(c[-1]), dd=dd)
    if times is not None and len(times) > 1:
        yrs = float(pd.Timedelta(pd.Timestamp(times.iloc[-1])
                                 - pd.Timestamp(times.iloc[0])).days) / 365.25
        if yrs > 0:
            out["yrs"] = yrs
            out["tpd"] = len(R) / (yrs * 365.25)
            out["cagr"] = (float(c[-1] ** (1 / yrs) - 1) * 100
                           if c[-1] > 0 else -100.0)
            out["mar"] = out["cagr"] / dd if dd > 0 else float("inf")
    return out


def sanity_check(assets=("BTCUSDT", "DOGEUSDT")) -> None:
    """GROSS R must be bounded by the exit scheme: wins <= tp/sl, losses >= -1.

    Net R legitimately breaches -1 because the fee is charged in R units:
    fee_R = (fee_bp/10000) * entry / stop_distance. When volatility is low
    relative to price that term is large - which is itself worth seeing, since
    it is a cost that scales with price/ATR, not with the trade's outcome.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backtest.mass_search import FILTERS, fetch, gen_signals

    print(f"{'asset':9} {'family':10} {'n':>5} {'grossR':>8} {'netR':>8} "
          f"{'feeR':>7} {'best':>7} {'worst':>7} {'PF':>6}  bounds")
    for a in assets:
        df = fetch(a, "1h", 900)
        for fam, p in (("rsi_mom", (7, 30, 60)), ("bb_break", (30, 1.5))):
            sig = FILTERS["none"](df, gen_signals(df, fam, p))
            g, _ = run_r(df, sig, fee_bp=0.0)
            net, _ = run_r(df, sig, fee_bp=10.0)
            sg, sn = stats(g), stats(net)
            ok = sg["best"] <= 1.5 + 1e-9 and sg["worst"] >= -1.0 - 1e-9
            print(f"{a:9} {fam:10} {sn['n']:>5} {sg['meanR']:>+8.4f} "
                  f"{sn['meanR']:>+8.4f} {sg['meanR']-sn['meanR']:>7.4f} "
                  f"{sg['best']:>+7.3f} {sg['worst']:>+7.3f} {sn['pf']:>6.3f}  "
                  f"{'OK' if ok else 'VIOLATED'}")


if __name__ == "__main__":
    print("scale-free R engine — GROSS bounds must hold (win <= +1.5R, loss = -1R)\n")
    sanity_check()
