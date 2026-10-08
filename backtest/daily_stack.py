"""THE DAILY BOOK'S NEAR-MISSES, STACKED (2026-10-08) - post hoc, said so. daily_combos.py: nothing passed; three came
close by cutting the fall - the BTC exit (out when BTC closes under its 20-day mean: fall 64 -> 52%), the filter "BTC
above its 50-day mean" (fall 53%), and the exit under the 20-day mean (fall 59%, holdout +65%). Each failed on one
day boundary. Stacked here, same method and line as daily_combos.py.

REGISTERED BEFORE RUNNING: every stack still fails at least one of the 3 boundaries on one half (near-misses that each
fail somewhere rarely pass together); the falls drop to 45-50%.

RESULT (2026-10-08, logs/daily_stack.txt): all 4 stacks fail (falls 43-48%, holdout below the line at 1-3 boundaries).
    Predictions - right.

    python -m backtest.daily_stack
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import daily_combos as dc  # noqa: E402

LOG = ROOT / "logs" / "daily_stack.txt"
BTC50 = lambda F, P, i: F["btc_c"][i] > F["btc_m50"][i]  # noqa: E731
V = {"BTC exit + BTC above 50d": dict(btc_exit=True, filt=BTC50),
     "20-day-mean exit + BTC exit": dict(mean_n=20, btc_exit=True),
     "20-day-mean exit + BTC above 50d": dict(mean_n=20, filt=BTC50),
     "all three": dict(mean_n=20, btc_exit=True, filt=BTC50)}


def main():
    base, _ = dc.run(dc.BASE, dc.LEVS)

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in dc.SEEDS])

    line = {off: sorted((agg(base, off, "fall", lv), agg(base, off, "tune", lv), agg(base, off, "hold", lv)) for lv in dc.LEVS)
            for off in dc.PHASES}
    lines = [f"backtest/daily_stack.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}"]
    for nm, ch in V.items():
        r, tr = dc.run(dict(dc.BASE, **ch))
        cells, ok = [], True
        for off in dc.PHASES:
            fa = agg(r, off, "fall")
            f = [a for a, _, _ in line[off]]
            dt = agg(r, off, "tune") - np.interp(fa, f, [b for _, b, _ in line[off]])
            dh = agg(r, off, "hold") - np.interp(fa, f, [c for _, _, c in line[off]])
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
        lines.append(f"  {nm:36} CAGR {np.mean([agg(r, o, 'tune') for o in dc.PHASES]) * 100:+.0f}% / "
                     f"{np.mean([agg(r, o, 'hold') for o in dc.PHASES]) * 100:+.0f}% fall {np.mean([agg(r, o, 'fall') for o in dc.PHASES]) * 100:.0f}% "
                     f"worst month {np.mean([agg(r, o, 'wm') for o in dc.PHASES]) * 100:+.1f}% | vs line {'  '.join(cells)} -> "
                     f"{'PASS' if ok else 'fail'}")
        print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
