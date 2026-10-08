"""PHASE 2 (the thin kills): mn_scale.py's basket width, on all 7 rebalance days (2026-10-08).

THE KILL (doc 02, "two ways to make the market-neutral book bigger", mn_scale.py): wider baskets (top/bottom 15-50%
instead of 10%) lower the book's return faster than its tail, so the book stays at 10% width and 1x. Measured on ONE
rebalance day - the day mn_combos.py found to be lucky (on 1 of 7 days the 10% book is wiped out). A wider basket puts
less on each name, so it is exactly the change that should matter on the unlucky days. Here: width 10 / 15 / 20 / 25%
on all 7 days, uncapped and with the +50% short-leg book exit.

REGISTERED BEFORE RUNNING: uncapped, the wider baskets survive the bad day (no fall >= 90%) where 10% does not, but keep
lower mean Sharpe; with the exit, 10% stays best on mean Sharpe (the kill stands once the tail is handled).

RESULT (2026-10-08, logs/mn_width7.txt): THE KILL STANDS. With the +50% exit: width 10% Sharpe +1.06 / +1.31, 15%
    +1.19 / +1.03, 20% +1.04 / +0.86, 25% +1.02 / +0.86 - wider is better on the tune half and worse on the holdout;
    10% stays. Uncapped, every width still has a day falling 80-89%: width does not fix the tail, the exit does.
    Predictions: wider survives the bad day uncapped - only just (no 90% fall, but 81-89%); 10% best with the exit -
    on the holdout, not the tune half.

    python -m backtest.mn_width7
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import mn_combos as m  # noqa: E402

LOG = ROOT / "logs" / "mn_width7.txt"


def main():
    lines = [f"backtest/mn_width7.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-60, 30-day momentum, weekly, 1x; 7 rebalance days"]
    for frac in (0.10, 0.15, 0.20, 0.25):
        for nm, kw in (("uncapped", {}), ("+50% short exit", dict(stop="short_only", short_stop=0.5))):
            st, ws = [], []
            for o in range(7):
                s = m.mn_run(start=o, frac=frac, **kw)
                st.append(m.stats(s, 7)); ws.append(s.min())
            lines.append(f"  width {frac:.0%} {nm:16} Sharpe mean {np.mean([x['tune'] for x in st]):+.2f} / "
                         f"{np.mean([x['hold'] for x in st]):+.2f}, worst day {min(x['tune'] for x in st):+.2f} / "
                         f"{min(x['hold'] for x in st):+.2f} | ann {np.nanmean([x['tune_ann'] for x in st]) * 100:+.0f}% / "
                         f"{np.nanmean([x['hold_ann'] for x in st]) * 100:+.0f}% | falls {min(x['fall'] for x in st) * 100:.0f}-"
                         f"{max(x['fall'] for x in st) * 100:.0f}% | worst week {min(ws) * 100:+.0f}%")
            print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
