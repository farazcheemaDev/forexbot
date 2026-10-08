"""CAPITULATION + BREADTH + tp5_nw: by year, by distinct day, and account designs (2026-10-08).

capitulation_exits.py: the frozen breadth entry with "+5%, or out after 24 bars if not in profit" gave +2.4..+3.1% a
trade in all 4 bar phases, both halves positive, and a positive 3-slot account at 1-3x in every phase. Checked here:
by year, t by DISTINCT DAY, majors vs other coins, and accounts of 3 / 5 / 8 slots at 1-5x (equity / slots per
trade, skip while full, random same-bar order, liquidation from each trade's deepest dip), with the worst fall.

REGISTERED BEFORE RUNNING: every year positive except perhaps 2023; t by day > 3 in every phase; the best account
design at <= 3x makes +30..+80% a year averaged over phases, with a worst fall of 30-60%.

    python -m backtest.capitulation_tp5
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "capitulation_tp5.txt"
MAJORS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT")


def account(T, lev, slots, stake=10_000.0):
    """Returns (end, worst fall from a peak) for equity / slots per trade, skip while full."""
    liq = 1 / lev - 0.005 - 0.0006
    eq, peak, dd, open_ = stake, stake, 0.0, []
    for r in T.itertuples():
        for p in sorted([p for p in open_ if p[0] <= r.t_in]):
            eq += p[1]
            peak = max(peak, eq)
            dd = max(dd, 1 - eq / peak)
        open_ = [p for p in open_ if p[0] > r.t_in]
        if len(open_) >= slots or eq <= 0:
            continue
        size = eq / slots
        pnl = -size if r.worst >= liq else size * max(lev * r.net, -1.0)
        open_.append((r.t_out, pnl))
    for p in sorted(open_):
        eq += p[1]
        peak = max(peak, eq)
        dd = max(dd, 1 - eq / peak)
    return max(eq, 0.0), dd


def main():
    A = pd.read_csv(ROOT / "logs" / "capitulation_exits_trades.csv", parse_dates=["t_in", "t_out"])
    A = A[A.exit == "tp5_nw"]
    span = (A.t_in.max() - A.t_in.min()).days / 365
    lines = [f"backtest/capitulation_tp5.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; tp5_nw, {span:.1f} years", ""]
    for off, g in A.groupby("off"):
        per_day = g.groupby(g.t_in.dt.floor("D")).net.mean()
        td = per_day.mean() / (per_day.std(ddof=1) / np.sqrt(len(per_day)))
        yrs = " ".join(f"{y}:{x.net.mean() * 100:+.1f}%({len(x)})" for y, x in g.groupby(g.t_in.dt.year))
        maj, oth = g[g.coin.isin(MAJORS)], g[~g.coin.isin(MAJORS)]
        lines.append(f"phase +{off}m: {len(g)} trades on {len(per_day)} days, t by day {td:+.1f}, majors {maj.net.mean() * 100:+.2f}% "
                     f"({len(maj)}) others {oth.net.mean() * 100:+.2f}% ({len(oth)}), worst {g.net.min() * 100:+.1f}%, deepest dip "
                     f"{g.worst.max() * 100:.0f}%\n    by year: {yrs}")
    lines.append("\nACCOUNTS from 10,000 PKR (mean over 5 same-bar orders): % a year (CAGR) and worst fall, per phase")
    for slots in (3, 5, 8):
        for lev in (1, 2, 3, 5):
            cells = []
            for off, g in A.groupby("off"):
                ends, dds = [], []
                for sd in range(5):
                    gg = g.assign(k=np.random.default_rng(sd).random(len(g))).sort_values(["t_in", "k"], kind="stable")
                    e, dd = account(gg, lev, slots)
                    ends.append(e)
                    dds.append(dd)
                cagr = (np.mean(ends) / 10_000) ** (1 / span) - 1 if np.mean(ends) > 0 else -1.0
                cells.append(f"{cagr * 100:+5.0f}%/yr (fall {np.mean(dds):.0%})")
            lines.append(f"  {slots} slots {lev}x: " + " | ".join(cells))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
