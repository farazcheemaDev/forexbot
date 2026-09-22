"""TWO MORE ENGINE STONES: book-level volatility targeting, and sizing SHORTS by BTC weakness.

  A. VOLATILITY TARGETING. The standard managed-futures lever nobody has tried here: scale
     the whole book's risk by (target vol / recent realised vol of its own daily P&L), so the
     book bets less after violent stretches and more after quiet ones, with the long-run
     average held at 1. Causal - the vol used for a trade is measured strictly before its
     entry. Implemented in two passes (vol from the flat book, applied to the scaled book),
     which is the standard practical form.

  B. SHORTS SIZED BY BTC WEAKNESS. bear_side.py showed shorts earn in bears (+0.081R) and
     nothing in bulls, and short_families.py showed no short ENTRY signal beats random - the
     regime is the whole edge. btc_exit.py then validated a market-weakness signal (BTC's 4h
     trail breaking). Untested: size the short sleeve UP when that signal is on. It is the
     same validated signal used on the side it was never tried on.

Everything seed-averaged over 5 orderings, tune/holdout as bear_date.py, and every variant
is also compared LEVERED to the deployed book's drawdown, because a lower-drawdown variant
is only better if it wins at equal risk.

    python -m backtest.vol_target
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.btc_exit import btc_trail  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.variant_leverage import SEEDS, lever_to, stat  # noqa: E402


def daily_pnl(rows, bear):
    """Flat-risk daily P&L of the book, for measuring its own realised volatility."""
    o = sorted(rows, key=lambda r: r["t0"])
    s = evaluate(o, bear)
    return s["daily"]


def vol_scaled(rows, bear, lookback=30, cap=(0.5, 2.0)):
    """Each trade's R scaled by target/realised vol measured BEFORE its entry."""
    d = daily_pnl(rows, bear)
    rv = d.rolling(lookback).std().shift(1)          # strictly past
    target = float(rv.median())
    fac = (target / rv).clip(*cap).fillna(1.0)
    out = []
    for r in rows:
        f = float(fac.asof(pd.Timestamp(r["t0"]))) if len(fac) else 1.0
        if not np.isfinite(f):
            f = 1.0
        out.append(dict(r, R=r["R"] * f))
    return out


def short_boost(rows, mult):
    """Shorts sized up while BTC's 4h trail is broken (market weakness)."""
    br = btc_trail(5)
    out = []
    for r in rows:
        f = 1.0
        if r["side"] == "short":
            t = pd.Timestamp(r["t0"])
            on = bool(br.asof(t)) if t >= br.index[0] else False
            if on:
                f = mult
        out.append(dict(r, R=r["R"] * f))
    return out


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    base = rows_for(BASE_RULES)
    bt = stat(base, bear, cut, "tune"); bh = stat(base, bear, cut, "hold")
    print(f"deployed: tune {bt[0]:+.2f}%/mo @{bt[1]:.0f}% DD | holdout {bh[0]:+.2f}%/mo "
          f"@{bh[1]:.0f}% DD, worst {bh[2]:+.1f}%\n")
    print(f"  {'variant':<34}{'TUNE':>8}{'DD':>5}{'HOLD':>8}{'DD':>5} |{'x':>6}"
          f"{'TUNE':>8}{'HOLD':>8}{'worst':>7}")

    def show(lab, rows):
        t = stat(rows, bear, cut, "tune"); h = stat(rows, bear, cut, "hold")
        lt = lever_to(rows, bear, cut, "tune", bt[1]); lh = lever_to(rows, bear, cut, "hold", bh[1])
        m = min(lt[0], lh[0]) if (lt and lh) else 1.0
        tm = stat(rows, bear, cut, "tune", m); hm = stat(rows, bear, cut, "hold", m)
        print(f"  {lab:<34}{t[0]:>+7.2f}%{t[1]:>4.0f}%{h[0]:>+7.2f}%{h[1]:>4.0f}% |{m:>6.2f}"
              f"{tm[0]:>+7.2f}%{hm[0]:>+7.2f}%{hm[2]:>+7.1f}%")

    show("BASE (deployed)", base)
    print("\n  A. VOLATILITY TARGETING (risk x target/realised, capped 0.5-2.0)")
    for lb in (14, 30, 60):
        show(f"vol target, {lb}-day lookback", vol_scaled(base, bear, lb))

    print("\n  B. SHORTS SIZED UP WHILE BTC's 4h TRAIL IS BROKEN")
    for m in (2.0, 3.0, 5.0):
        show(f"shorts x{m:g} on BTC break", short_boost(base, m))

    print("\n  C. STACKED with the winner so far (pullback 0.5 adds + tight exit)")
    best = rows_for(BASE_RULES, add_mode="pullback", pull_atr=0.5, tight=True)
    show("pullback 0.5 + tight", best)
    show("  + vol target 30d", vol_scaled(best, bear, 30))
    show("  + shorts x3 on BTC break", short_boost(best, 3.0))


if __name__ == "__main__":
    main()
