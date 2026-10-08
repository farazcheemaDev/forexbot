"""THE CAPITULATION PASSERS, STACKED (2026-10-08). capit_combos.py: of 28 combinations, four beat the base's leverage line
on both halves in all 4 bar phases - BTC down >= 5% in 24h, the coin down >= 10% in 24h, a limit 2% under the signal
close (next bar only), a limit 4% under. Stacked here, same method (4 phases x 10 orders, the base's leverage line).

The last two rows (added after the first run, prediction: both still pass, the gain shrinking by under a third) fill a
limit only when the low trades 0.3% THROUGH it - a resting order at the touch is not always filled (maker_exec.py).

REGISTERED BEFORE RUNNING: BTC-drop + limit -2% passes and keeps at least half of the two gains added together; adding
the coin-drop filter on top adds nothing (it overlaps the BTC drop); the -4% limit stacked with a filter is too rare
(< 100 trades) and fails on at least one phase.

RESULT (2026-10-08, logs/capit_stack.txt): BTC-5% + limit -2%, coin-10% + limit -2%, all three, and "BTC OR coin" +
    limit all PASS; -4% limit + BTC filter fails (95 trades). Best and most even: coin down >= 10% + limit 2% under -
    ~30 trades a year, +3.9% / +4.4% a trade (base +2.4 / +3.1), 1x fall 4% (base 12%); still passes with a 0.3%
    trade-through fill rule. Stacks do not add beyond the limit entry alone. Predictions: BTC + limit passes - right;
    coin filter adds nothing - WRONG (coin + limit is the best stack); -4% fails - right; trade-through still passes -
    right.

    python -m backtest.capit_stack
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402

LOG = ROOT / "logs" / "capit_stack.txt"

V = {
    "BASE": {},
    "BTC down >= 5% (alone, for reference)": dict(filt=lambda S: S.btc24 <= -0.05),
    "limit -2% (alone, for reference)": dict(entry=("limit", 0.02, 1)),
    "BTC down >= 5% + limit -2%": dict(filt=lambda S: S.btc24 <= -0.05, entry=("limit", 0.02, 1)),
    "coin down >= 10% + limit -2%": dict(filt=lambda S: S.drop24 <= -0.10, entry=("limit", 0.02, 1)),
    "BTC -5% + coin -10% + limit -2%": dict(filt=lambda S: (S.btc24 <= -0.05) & (S.drop24 <= -0.10), entry=("limit", 0.02, 1)),
    "BTC down >= 5% + limit -4%": dict(filt=lambda S: S.btc24 <= -0.05, entry=("limit", 0.04, 1)),
    "BTC -5% OR coin -10%, + limit -2%": dict(filt=lambda S: (S.btc24 <= -0.05) | (S.drop24 <= -0.10), entry=("limit", 0.02, 1)),
    "limit -2%, fill only on a 0.3% trade-through": dict(entry=("limit", 0.02, 1, 0.003)),
    "coin -10% + limit -2%, 0.3% trade-through": dict(filt=lambda S: S.drop24 <= -0.10, entry=("limit", 0.02, 1, 0.003)),
}


def main():
    base, _ = cc.run(cc.BASE, cc.LEVS)

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in cc.SEEDS])

    line = {off: sorted((agg(base, off, "fall", lv), agg(base, off, "tune", lv), agg(base, off, "hold", lv)) for lv in cc.LEVS)
            for off in cc.PHASES}

    def line_at(off, fall, key):
        return float(np.interp(fall, [a for a, _, _ in line[off]], [b if key == "tune" else c for _, b, c in line[off]]))

    lines = [f"backtest/capit_stack.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; same method as capit_combos.py", ""]
    for nm, ch in V.items():
        cfg = dict(cc.BASE, **ch)
        r, tr = cc.run(cfg) if ch else (base, None)
        if tr is None:
            _, tr = cc.run(cfg)
        cells, ok = [], True
        for off in cc.PHASES:
            fa = agg(r, off, "fall")
            dt, dh = agg(r, off, "tune") - line_at(off, fa, "tune"), agg(r, off, "hold") - line_at(off, fa, "hold")
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.1f}/{dh * 100:+.1f}")
        lines.append(f"  {nm:36} trades {np.mean([tr[o][0] for o in cc.PHASES]):4.0f} | per trade {np.nanmean([tr[o][1] for o in cc.PHASES]) * 100:+.2f}% / "
                     f"{np.nanmean([tr[o][2] for o in cc.PHASES]) * 100:+.2f}% | CAGR 1x {np.mean([agg(r, o, 'tune') for o in cc.PHASES]) * 100:+.1f}% / "
                     f"{np.mean([agg(r, o, 'hold') for o in cc.PHASES]) * 100:+.1f}% fall {np.mean([agg(r, o, 'fall') for o in cc.PHASES]) * 100:.0f}% | "
                     f"vs line {'  '.join(cells)} -> {'-' if not ch else ('PASS' if ok else 'fail')}")
        print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
