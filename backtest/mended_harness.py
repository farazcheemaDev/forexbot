"""THE MENDED ARCHITECTURE as a reusable harness - plug in a side, get a verdict (2026-10-16)

His trade architecture, mended with a hard stop (his_strategy.md s68, backtest/his_mended.py), with an empty SIGNAL SLOT.
Any candidate side - order flow, sentiment once it has months of history, anything - is a function
    signal(day_grid) -> np.ndarray of +1 / -1 / 0 per second (0 = no view), causal (reads only seconds <= i)
and is run through the SAME engine on 181 Exness USTECm tick days at the real spread:
    ENTRY   signal on, and the mid came back against it by >= 0.7 points in the last 3 s (his pullback);
            one position at a time; 10:00-16:00 New York
    EXIT    +7 take-profit at the real bid / ask, hard stop -S, 30-minute cap
    GATE    a stop QUALIFIES only if on BOTH halves (first 60% of days / last 40%) the win rate clears the Sharpe-2
            line for 500 trades a year, p >= p* + 2 sqrt(p(1-p) / 500) (p* = S / (7 + S)), the net per trade is positive
            and >= 100 holdout trades. A qualified signal goes to a forward PAPER record next - never straight to money
            (docs/22-decision-rule.md; ALLOW_REAL stays False).
The coin flip is built in as the control; it must fail the gate (it does: -2.1..-2.5 points a trade, his_mended.py).

    python -m backtest.mended_harness            run the coin control through the gate
    from backtest.mended_harness import qualify; qualify(my_signal, "name")
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.his_mended import STOPS, run, stats  # noqa: E402
from backtest.his_style_bot import day_grid  # noqa: E402


def needed(S, n=500, sharpe=2.0):
    """Win rate a +7 / -S trade needs for the given annual Sharpe at n trades a year."""
    from scipy.optimize import brentq
    ps = S / (7 + S)
    return brentq(lambda p: (p - ps) / np.sqrt(p * (1 - p)) - sharpe / np.sqrt(n), ps, 0.9999)


def qualify(signal, name="signal", stops=STOPS):
    cache = pickle.loads((ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    grids = {}
    for d in days:
        g = day_grid(cache[d])
        if len(g[0]) >= 7200:
            grids[d] = g
    lines = [f"mended_harness: {name}; {len(grids)} days, holdout from {cut:%Y-%m-%d}",
             f"  {'stop':>5}{'half':>9}{'trades':>8}{'won':>7}{'needed':>8}{'net/trade':>11}{'t':>7}"]
    verdict = {}
    for S in stops:
        ok = True
        for half in ("tune", "HOLDOUT"):
            a, rng = [], np.random.default_rng(11)
            for d, g in grids.items():
                if (d < cut) != (half == "tune"):
                    continue
                sig = signal(g) if signal is not None else None
                a += run(g[1], g[2], sig, 1800, 23400, S, rng)
            n, wr, m, t = stats(a)
            need = needed(S)
            ok &= bool(n >= (100 if half == "HOLDOUT" else 3) and wr >= need and m > 0)
            lines.append(f"  {S:>5}{half:>9}{n:>8}{wr * 100:>6.0f}%{need * 100:>7.0f}%{m:>+11.2f}{t:>+7.1f}")
        verdict[S] = ok
    q = [S for S, v in verdict.items() if v]
    lines.append(f"  GATE: {'QUALIFIES at stop ' + str(q) + ' -> forward paper record next' if q else 'FAILS at every stop'}")
    print("\n".join(lines))
    return verdict, lines


if __name__ == "__main__":
    v, lines = qualify(None, "coin flip (control)")
    (ROOT / "logs" / "mended_harness.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
