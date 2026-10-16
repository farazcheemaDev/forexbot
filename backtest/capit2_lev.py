"""CAPIT2 WITH ROOM: leverage 1-5x and 8-24 slots, isolated liquidation per position (2026-10-16)

no_limits.py: the capitulation book is the one book that WANTS leverage (1-4 liquidations in 455 trades even at 3x;
holdout +23% -> +80%/yr from 1x to 3x) - its trades are bought after the fall and sold at +5% within days. capit2 is its
best version (capit_stack.py: coin down >= 10% in 24h, a limit 2% under, filled on a 0.3% trade-through; ~30 trades a
year, +3.0 / +4.3% a trade, 1x fall ~10%), and it was only ever run at 0.5-3x with 8 slots (capit_combos.LEVS).
Here, capital unconstrained: LEVERAGE 1 / 2 / 3 / 4 / 5 (a position is liquidated - its margin lost - when its worst
adverse move reaches 1/L - 0.56%), SLOTS 8 / 16 / 24, the same 4 bar phases x 10 orders, PIT top-40 with dead coins.
Equity booked at each trade's close (capit_combos.curve); a 3-5x book's worst fall INSIDE trades is deeper than shown.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. CAGR rises with leverage up to 3x on both halves; at 5x the liquidations (>= 5% of trades) cut the tune half.
    2. The worst fall at 3x stays under 40% (booked at close).
    3. More slots change little (capit2 rarely has more than 8 signals open at once).

RESULT (2026-10-16, logs/capit2_lev.txt) - 2x IS THE SWEET SPOT; prediction 2 right, 1 and 3 wrong.
    8 slots, tune / holdout CAGR, fall, worst month, liquidated: 1x +8.6 / +14.3%, 10%, -6.0%, 0.4% | 2x +20.0 / +29.9%,
    12%, -5.3%, 0.6% | 3x +17.6 / +43.6%, 33%, -27.3%, 1.9% | 4x +13.9 / +28.2%, 59% | 5x -6.9 / -29.3%, 75%.
    2x doubles the return on BOTH halves for 2 more points of fall; 3x helps the holdout only and the fall triples.
    (Prediction 1 wrong: the tune half peaks at 2x, not 3x; 5x liquidates 9.3%.) More slots smooth it (24 slots at 3x:
    +9.0 / +25.3%, fall 13%) but cost return at 2x (16 slots +11.9 / +22.7%) - prediction 3 wrong. One trade in each
    phase lost ~99% (a coin that collapsed while held): at 1x it costs one slot, an eighth of the book.

    python -m backtest.capit2_lev
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402

LOG = ROOT / "logs" / "capit2_lev.txt"
LEVS = (1.0, 2.0, 3.0, 4.0, 5.0)
SLOTS = (8, 16, 24)


def main():
    cfg = dict(cc.BASE, filt=lambda S: S.drop24 <= -0.10, entry=("limit", 0.02, 1, 0.003))
    out = [f"backtest/capit2_lev.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; capit2 (coin -10% + limit -2%, 0.3% "
           f"trade-through), 4 phases x 10 orders, isolated liquidation at 1/L - 0.56%", "",
           f"  {'lev':>5}{'slots':>6}{'tune CAGR':>11}{'holdout':>9}{'fall':>7}{'worst mo':>10}{'liquidated':>12}{'worst trade':>13}"]
    Ts = {off: cc.gen(off, cfg) for off in cc.PHASES}
    n = np.mean([len(T) for T in Ts.values()])
    R = {}
    for slots in SLOTS:
        dc.SLOTS = slots
        for lev in LEVS:
            liq = 1 / lev - 0.005 - 0.0006
            vals = []
            for off, T in Ts.items():
                for sd in cc.SEEDS:
                    tk = dc.allocate(T.assign(units=None), sd, lev, prio=False)
                    vals.append(dc.stats(cc.curve(T, tk)))
            agg = {k: float(np.mean([v[k] for v in vals])) for k in ("tune", "hold", "fall", "wm")}
            nl = np.mean([(T.worst >= liq).mean() for T in Ts.values()])
            wt = np.mean([(T.net * lev).clip(lower=-1).min() for T in Ts.values()])
            R[(lev, slots)] = (agg, nl)
            out.append(f"  {lev:>5.1f}{slots:>6}{agg['tune'] * 100:>+10.1f}%{agg['hold'] * 100:>+8.1f}%{agg['fall'] * 100:>6.0f}%"
                       f"{agg['wm'] * 100:>+9.1f}%{nl * 100:>11.1f}%{wt * 100:>+12.0f}%")
        out.append("")
    dc.SLOTS = 8
    t8 = [R[(L, 8)][0]["tune"] for L in LEVS]
    h8 = [R[(L, 8)][0]["hold"] for L in LEVS]
    p1 = t8[0] < t8[1] < t8[2] and h8[0] < h8[1] < h8[2] and R[(5.0, 8)][1] >= 0.05 and t8[4] < t8[2]
    p2 = R[(3.0, 8)][0]["fall"] < 0.40
    p3 = all(abs(R[(L, s)][0]["hold"] - R[(L, 8)][0]["hold"]) < 0.05 for L in LEVS for s in SLOTS)
    out += [f"  ~{n:.0f} trades per phase", "", "REGISTERED PREDICTIONS",
            f"  1 rises to 3x on both halves, 5x liquidations >= 5% cut the tune half -> {'RIGHT' if p1 else 'WRONG'}",
            f"  2 fall at 3x under 40% ({R[(3.0, 8)][0]['fall'] * 100:.0f}%) -> {'RIGHT' if p2 else 'WRONG'}",
            f"  3 more slots change the holdout by < 5 points -> {'RIGHT' if p3 else 'WRONG'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
