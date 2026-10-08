"""CAPITULATION WITH BREADTH - only buy once several coins have capitulated (AFTER-THE-FACT idea, 2026-10-08).

capitulation_freq.py's diagnostic: on a crash day the FIRST 3 capitulation signals averaged -0.65..+0.85% a trade over
the 4 bar phases, the LATER ones +1.1..+1.8%. A realistic 3-slot account fills with the early ones and skips the good
ones. The idea - only take a signal once at least K distinct coins (itself included) have signalled within the past
24 hours, i.e. a market-wide capitulation - came from LOOKING at that, so this is a check of a post-hoc idea, run on
the same data, all 4 bar phases, random same-bar order (5 seeds). Signals are approximated by capitulation_freq's
trades (one open trade per coin), so a coin with a trade open does not count toward breadth.

REGISTERED BEFORE RUNNING IT: with K = 3 the average is >= +1.0% a trade in ALL 4 phases (the +2h phase included),
and the 10,000 PKR 3-slot account makes +800 to +2,000 PKR a year at 1x in every phase.

RESULT (2026-10-08, logs/capitulation_breadth.txt): breadth raises the average in every phase, but K = 3 is NOT enough
    (top-40 vol>2x: +1.13 / +1.06 / +0.88 / +1.30% a trade; vol>3x +0.54% in the +2h phase) - prediction WRONG for K=3.
    K >= 5 (five coins capitulating within 24 hours), top-40, RSI<20, vol>2x: ~55 signals a year, +1.38 / +1.12 /
    +1.27 / +1.66% a trade, and the 10,000 PKR 3-slot account +636 / +574 / +971 / +1,255 PKR a year at 1x, +1,461 /
    +1,276 / +2,468 / +3,475 at 2x - positive in all 4 phases at both. K was chosen among 4 values after looking, on
    the data the idea came from: a forward record decides.

    python -m backtest.capitulation_breadth

RE-RUN 2026-10-09 on the FIXED loader (capitulation_wide.halt_cut): until then a data-archive hole cut 51 coins (XRP, SOL,
    LTC ...) at 2022-02-25. Where a RESULT above differs from this file's log, THE LOG IS CURRENT - doc 02, "The archive-hole bug".
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capitulation_freq as cf  # noqa: E402

LOG = ROOT / "logs" / "capitulation_breadth.txt"


def breadth(g):
    """Distinct coins (itself included) whose entry time is within the 24 hours up to and including this one."""
    t = g.t_in.to_numpy("datetime64[ns]").astype(np.int64)
    c = g.coin.to_numpy()
    out = np.zeros(len(g), int)
    lo = 0
    day = 24 * 3600 * 10 ** 9
    for k in range(len(g)):
        while t[lo] < t[k] - day:
            lo += 1
        hi = np.searchsorted(t, t[k], side="right")             # same-bar signals are visible at the close
        out[k] = len(set(c[lo:hi]))
    return out


def main():
    A = pd.read_csv(ROOT / "logs" / "capitulation_freq_trades.csv.gz", parse_dates=["t_in", "t_out"])
    span = (A.t_in.max() - A.t_in.min()).days / 365
    lines = [f"backtest/capitulation_breadth.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; post-hoc idea, {span:.1f} years; 3-slot "
             f"10,000 PKR account, random same-bar order (5 seeds)", ""]
    for uni in ("top40", "top100"):
        for vm in (2.0, 3.0):
            lines.append(f"{uni} 4h RSI<20 vol>{vm:.0f}x:")
            for K in (1, 2, 3, 5):
                cells = []
                for off in (0, 60, 120, 180):
                    g = A[(A.tf == "4h") & (A.off == off) & (A.X == 20) & (A.vm == vm) & (A.uni == uni)]
                    g = g.sort_values("t_in", kind="stable").reset_index(drop=True)
                    g = g[breadth(g) >= K]
                    pk = []
                    for sd in range(5):
                        gg = g.assign(k=np.random.default_rng(sd).random(len(g))).sort_values(["t_in", "k"], kind="stable")
                        pk.append({lev: (cf.account(gg, lev)[0] - cf.STAKE) / span for lev in (1, 2)})
                    cells.append(f"+{off:>3}m n {len(g) / span:4.0f}/yr avg {g.net.mean() * 100:+.2f}% "
                                 f"1x {np.mean([p[1] for p in pk]):+6,.0f} 2x {np.mean([p[2] for p in pk]):+7,.0f}")
                lines.append(f"  K>={K}: " + " | ".join(cells))
            lines.append("")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
