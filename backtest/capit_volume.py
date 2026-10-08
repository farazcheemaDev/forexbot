"""PHASE 2 (re-testing thin kills): IS VOLUME USELESS IN CRYPTO? Tested in the one book that uses it (2026-10-08).

THE CLAIM (doc 02 / CLAUDE.md 2026-10-06): "volume stays anti-useful in crypto" - from VSA on hourly breakouts
(05-vsa.md), a volume-surge filter, and one_shot.py's 1-minute setups. But the capitulation book REQUIRES a volume
spike (> 2x its 20-bar average) and was never run without it: the claim and the book disagree, and nothing measured
which is right. Here the capitulation signal (4h RSI(14) cross under 20, >= 5 coins in 24h, breadth counted on the
SAME definition) with no volume rule, and with > 1.5x / 2x / 3x; on the base book (tp5_nw, in at the next open) and
on the improved one (coin down >= 10% in 24h, limit 2% under). Same method as capit_combos.py: 4 phases x 10 orders,
judged against the 2x base's leverage line.

REGISTERED BEFORE RUNNING: removing the volume rule adds signals and LOWERS the average a trade on both halves (the
volume spike marks forced selling, which is what bounces): no-volume fails the line in at least 2 of 4 phases; 3x
ties 2x. If no-volume ties or wins, the volume rule is decoration and the claim "anti-useful" was closer to right.

RESULT (2026-10-08, logs/capit_volume.txt): in the BASE book the volume rule matters - without it 575 trades, +1.99%
    / +2.85% a trade (with it +2.36 / +3.11), below the line in all 4 phases; 1.5x and 3x fail. In the IMPROVED book
    (coin down >= 10%) it is redundant - without it 311 trades, +3.53 / +4.22% a trade, PASSES in all 4 phases with a
    larger margin in 3. "Volume is anti-useful in crypto" is wrong as a general claim: a volume spike marks forced
    selling; once the price drop measures that directly, the spike adds nothing. Prediction (no-volume fails in >= 2
    phases) - right for the base, WRONG for the improved book.

    python -m backtest.capit_volume

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

from backtest import capit_combos as cc  # noqa: E402

LOG = ROOT / "logs" / "capit_volume.txt"
BETTER = dict(filt=lambda S: S.drop24 <= -0.10, entry=("limit", 0.02, 1))
V = {"base, volume > 2x (as built)": {}, "base, NO volume rule": dict(vmin=0.0), "base, volume > 1.5x": dict(vmin=1.5),
     "base, volume > 3x": dict(vmin=3.0), "improved, volume > 2x": BETTER, "improved, NO volume rule": dict(BETTER, vmin=0.0)}


def main():
    base, _ = cc.run(cc.BASE, cc.LEVS)

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in cc.SEEDS])

    line = {off: sorted((agg(base, off, "fall", lv), agg(base, off, "tune", lv), agg(base, off, "hold", lv)) for lv in cc.LEVS)
            for off in cc.PHASES}
    lines = [f"backtest/capit_volume.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; vs the 2x-volume base's leverage line"]
    for nm, ch in V.items():
        r, tr = cc.run(dict(cc.BASE, **ch))
        cells, ok = [], True
        for off in cc.PHASES:
            fa = agg(r, off, "fall")
            f = [a for a, _, _ in line[off]]
            dt = agg(r, off, "tune") - np.interp(fa, f, [b for _, b, _ in line[off]])
            dh = agg(r, off, "hold") - np.interp(fa, f, [c for _, _, c in line[off]])
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.1f}/{dh * 100:+.1f}")
        lines.append(f"  {nm:30} trades {np.mean([tr[o][0] for o in cc.PHASES]):4.0f} | per trade {np.nanmean([tr[o][1] for o in cc.PHASES]) * 100:+.2f}% / "
                     f"{np.nanmean([tr[o][2] for o in cc.PHASES]) * 100:+.2f}% | CAGR 1x {np.mean([agg(r, o, 'tune') for o in cc.PHASES]) * 100:+.1f}% / "
                     f"{np.mean([agg(r, o, 'hold') for o in cc.PHASES]) * 100:+.1f}% fall {np.mean([agg(r, o, 'fall') for o in cc.PHASES]) * 100:.0f}% | "
                     f"vs line {'  '.join(cells)} -> {'PASS' if ok else 'fail'}")
        print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
