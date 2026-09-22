"""THE ONLY QUESTION THAT MATTERS FOR A LOW-DRAWDOWN VARIANT: levered to today's risk,
does it beat today's book?

engine_variants.py found that filling pyramid adds on PULLBACKS instead of at fixed +2R
breakout levels cuts drawdown roughly in half (55% -> 28-30% tune, 57% -> 34-41% holdout)
and the worst month from -34% to -12%, while lowering return. btc_exit.py found the same
shape for the BTC-break tight trail. Lower drawdown is not a result by itself - it is
LEVERAGE CAPACITY. So each variant is scaled up until its drawdown matches the deployed
book's, and the returns are compared there. That is the apples-to-apples test.

Both halves are reported, and everything is averaged over 5 random orderings of
simultaneous entries (that ordering alone swings a run by 3-5%/mo).

    python -m backtest.variant_leverage
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402

SEEDS = (0, 1, 2, 3, 4)


def stat(rows, bear, cut, half, mult=1.0):
    hpm, dd, wm = [], [], []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        o = [dict(rows[i], R=rows[i]["R"] * mult)
             for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
        s = evaluate(o, bear, t_to=cut) if half == "tune" else evaluate(o, bear, t_from=cut)
        hpm.append(s["hpm"]); dd.append(s["dd"]); wm.append(s["worst_mo"])
    return float(np.mean(hpm)), float(np.mean(dd)), float(np.mean(wm))


def lever_to(rows, bear, cut, half, target_dd):
    """Largest multiplier whose drawdown still sits at or under target."""
    best = None
    for m in np.linspace(1.0, 4.0, 31):
        r, dd, wm = stat(rows, bear, cut, half, m)
        if dd <= target_dd:
            best = (m, r, dd, wm)
        else:
            break
    return best


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    variants = [
        ("BASE (deployed)", dict()),
        ("pullback adds 0.5xATR", dict(add_mode="pullback", pull_atr=0.5)),
        ("pullback adds 1xATR", dict(add_mode="pullback", pull_atr=1.0)),
        ("tight exit only", dict(tight=True)),
        ("pullback 0.5 + tight exit", dict(add_mode="pullback", pull_atr=0.5, tight=True)),
        ("pullback 1 + tight exit", dict(add_mode="pullback", pull_atr=1.0, tight=True)),
    ]
    R = {lab: rows_for(BASE_RULES, **kw) for lab, kw in variants}
    base_t = stat(R["BASE (deployed)"], bear, cut, "tune")
    base_h = stat(R["BASE (deployed)"], bear, cut, "hold")
    print(f"deployed: tune {base_t[0]:+.2f}%/mo at {base_t[1]:.0f}% DD | "
          f"holdout {base_h[0]:+.2f}%/mo at {base_h[1]:.0f}% DD, worst mo {base_h[2]:+.1f}%\n")
    print(f"  {'variant':<28}| {'at 1x risk: TUNE':>17}{'DD':>5}{'HOLD':>8}{'DD':>5} | "
          f"{'levered to deployed DD':>23}")
    print(f"  {'':<28}| {'':>17}{'':>5}{'':>8}{'':>5} | {'x':>5}{'TUNE':>8}{'HOLD':>8}{'worst':>7}")
    for lab, _kw in variants:
        rows = R[lab]
        t = stat(rows, bear, cut, "tune"); h = stat(rows, bear, cut, "hold")
        lt = lever_to(rows, bear, cut, "tune", base_t[1])
        lh = lever_to(rows, bear, cut, "hold", base_h[1])
        m = min(lt[0], lh[0]) if (lt and lh) else 1.0
        tm = stat(rows, bear, cut, "tune", m); hm = stat(rows, bear, cut, "hold", m)
        print(f"  {lab:<28}| {t[0]:>+16.2f}%{t[1]:>4.0f}%{h[0]:>+7.2f}%{h[1]:>4.0f}% | "
              f"{m:>5.2f}{tm[0]:>+7.2f}%{hm[0]:>+7.2f}%{hm[2]:>+7.1f}%")
    print("\n  'levered' uses the SMALLER of the two multipliers that keep each half at or")
    print("  under the deployed book's drawdown, so neither half is flattered. A variant")
    print("  wins only if BOTH levered columns beat the deployed row by more than ~2%/mo.")


if __name__ == "__main__":
    main()
