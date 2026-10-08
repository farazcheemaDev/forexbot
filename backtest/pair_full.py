"""THE PAIR, ITS FIXES TOGETHER, ACROSS EVERY MARKET TYPE AND BAR PHASE (2026-10-08).

From pair_lab.py --fixes and mn_capped.py:
    keep   the BTC 1000h gate on the DAILY book's entries (same CAGR, fall 31% -> 25%, bear months -2.1% -> +0.9%)
    keep   the market-neutral book as an overlay, CAPPED at +100% per coin-week (no single pump carries it)
    test   cap 60 days (it evened the halves) and the doc-13 bear breadth sleeve at 1x (logs/breadth_real_1x.pkl,
           replicated on the 2018 bear) as one more overlay for falling markets
Every candidate on 3 daily bar phases (00/08/16 UTC) x 2 capitulation phases (+0 / +120 min) x 10 same-day orders.

REGISTERED BEFORE RUNNING: the bear sleeve lifts bear months from ~0% to +2..+5% and adds +5..+15 points of CAGR
without deepening the fall; the full system's CAGR varies by under +-20 points across the 6 phase combinations.

RESULT (2026-10-08, logs/pair_full.txt + the session's no-gate run): over 3 daily x 2 capitulation phases x 10 orders -
    A pair +52%; B + 1000h gate +46% (holdout 35 -> 24: the gate is DROPPED); C + gate + MN(capped) x0.5 +82%;
    D + gate + MN x0.5 + bear sleeve x1 +123%; F MN x1 +164% with a 50% fall.
    THE SYSTEM - daily book + capitulation book (half each, 8 slots each, 1x) + MN capped x0.5 + bear sleeve x1, NO gate:
    +133%/yr (5th..95th +123..+144), tune +172 / holdout +83, fall 40%, months up 65%, median month +4.6%, average month
    bull +13.3 / chop +3.2 / bear +6.6; by year 2020 +124%, 2021 +799%, 2022 +64%, 2023 +39%, 2024 +21%, 2025 +100%,
    2026 to Sep +132%; months: 5th pct -10%, median +4.7%, 95th +36%; 40% of months >= +10%, 14% <= -5%.
    Predictions: sleeve +2..+5 bear points (WRONG: +5..+8), +5..+15 CAGR points (WRONG: +40), fall not deeper (WRONG:
    +4..+10 points), phase spread < +-20 (right).

    python -m backtest.pair_full
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest.mn_capped import mn_series  # noqa: E402

LOG = ROOT / "logs" / "pair_full.txt"


def main():
    reg = pl.btc_regime_daily()
    gate = pl.btc_gate_daily(1000).rename("btc1000")
    mn = mn_series(1.0)
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    lines = [f"backtest/pair_full.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; median of 10 same-day orders per phase combination", ""]
    configs = {
        "A base pair": dict(cap=30, gate=None, mn=0.0, sl=0.0),
        "B + 1000h gate": dict(cap=30, gate=gate, mn=0.0, sl=0.0),
        "C + gate + MN(capped) x0.5": dict(cap=30, gate=gate, mn=0.5, sl=0.0),
        "D + gate + MN x0.5 + bear sleeve x1": dict(cap=30, gate=gate, mn=0.5, sl=1.0),
        "E = D with cap 60": dict(cap=60, gate=gate, mn=0.5, sl=1.0),
        "F = D with MN x1": dict(cap=30, gate=gate, mn=1.0, sl=1.0),
    }
    for nm, cf in configs.items():
        per = []
        for off_h in (0, 8, 16):
            D = pl.daily_trades(off_h=off_h, gate=cf["gate"], cap=cf["cap"])
            for coff in (0, 120):
                C = pl.capit_trades(coff)
                extra = cf["mn"] * mn.reindex(pd.date_range("2020-01-01", "2026-09-30", freq="D")).fillna(0.0) \
                    + cf["sl"] * sleeve.reindex(pd.date_range("2020-01-01", "2026-09-30", freq="D")).fillna(0.0)
                ms = pd.DataFrame([pl.metrics(pl.account({"daily": (D, 0.5, 8), "capit": (C, 0.5, 8)}, seed=sd,
                                                        extra_daily=extra)[0], reg) for sd in range(10)]).median()
                per.append(ms)
        P = pd.DataFrame(per)
        lines.append(f"{nm:40} CAGR {P.cagr.median() * 100:+4.0f}% (phases {P.cagr.min() * 100:+.0f}..{P.cagr.max() * 100:+.0f}) | tune "
                     f"{P.tune.median() * 100:+.0f} / holdout {P.hold.median() * 100:+.0f} | fall {P.dd.median():.0%} (worst {P.dd.max():.0%}) | "
                     f"up {P.up.median():.0%} | median month {P.med.median() * 100:+.1f}% | worst month {P.worst.min() * 100:+.0f}% | "
                     f"bull {P.bull.median() * 100:+.1f} chop {P.chop.median() * 100:+.1f} bear {P.bear.median() * 100:+.1f}")
        print(lines[-1], flush=True)
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
