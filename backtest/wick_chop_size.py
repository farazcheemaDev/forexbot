"""PHASE 2 (the thin kills): crash bids sized UP in sideways markets - killed "on inspection", never tested (2026-10-08).

THE KILL (doc 02, "Dead on inspection: crash bids sized up in sideways markets", 2026-10-01): chop days earn +0.035% a
day against bull's +0.078%, and 7 of the 8 worst days are chop days, so "sizing up in chop buys the fatter tail and the
half-size edge together. Not built." A judgment from a table, not a test against betting bigger everywhere.
Here: the capped crash bids (logs/wick_capped.pkl, cap 10) with chop days x1.5 / x2 (bull x1; no bids on bear days by
rule) against the uniform size line (every day x k), alone and inside machine_combos.py's machine E; halves split
2024-08-29 (the crash-bid files' split), labels btc_regime (a day lagged), as the original table.

REGISTERED BEFORE RUNNING: fails against the uniform line on at least one half, alone and in the machine (the
inspection was right).

RESULT (2026-10-08, logs/wick_chop_size.txt): FAILS - the inspection was right. Alone: chop x1.5 tune +21.3% vs the
    uniform line's +28.8%, holdout +14.2% vs +16.6%; x2 worse. In machine E: -1% / -3% (6y), -0% / -2% (2y) against the
    line. Prediction - right.

    python -m backtest.wick_chop_size
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402

LOG = ROOT / "logs" / "wick_chop_size.txt"


def main():
    bids = pd.read_pickle(ROOT / "logs" / "wick_capped.pkl")[10]
    reg = pl.btc_regime_daily().reindex(bids.index, method="ffill").fillna("chop")
    chop = (reg == "chop").to_numpy()

    def st(x):
        c = (1 + x).cumprod()
        out = {}
        for h, z in (("tune", c[c.index < CUT]), ("hold", c[c.index >= CUT])):
            yrs = (z.index[-1] - z.index[0]).days / 365
            m = z.resample("ME").last().pct_change().dropna()
            out[h] = ((z.iloc[-1] / z.iloc[0]) ** (1 / yrs) - 1, m.min())
        return out

    lines = [f"backtest/wick_chop_size.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; capped crash bids alone: CAGR and worst month "
             f"per half; vs the uniform line at the same worst month"]
    line = {k: st(k * bids) for k in np.arange(0.5, 3.01, 0.25)}
    for mult in (1.5, 2.0):
        x = bids * np.where(chop, mult, 1.0)
        s = st(x)
        cells, ok = [], True
        for h in ("tune", "hold"):
            pts = sorted((v[h][1], v[h][0]) for v in line.values())
            ref = float(np.interp(s[h][1], [a for a, _ in pts], [b for _, b in pts]))
            d = s[h][0] - ref
            ok = ok and d > 0
            cells.append(f"{h} {s[h][0] * 100:+.1f}% (wm {s[h][1] * 100:+.1f}%) vs line {ref * 100:+.1f}%")
        lines.append(f"  chop x{mult}: " + " | ".join(cells) + f" -> {'PASS' if ok else 'fail'}")
        print(lines[-1], flush=True)
    from backtest import machine_combos as mc
    P = mc.parts()
    E = dict(trend=1, mn_safe=1, sleeve=1, bids=1, daily=1, capit2=1)
    for sp, t0 in (("all 6 years", None), ("last 2 years", CUT)):
        build = lambda bm, k=1.0: [k * (sum(v * P[s][p] for p, v in E.items() if p != "bids")  # noqa: E731
                                        + P[s]["bids"] * bm[:len(P[s])]) for s in mc.SEEDS]
        ones = np.ones(len(P[0]))
        cm = reg.reindex(P[0].index, method="ffill").fillna("chop").to_numpy() == "chop"
        f = sorted((summary(build(ones, k), t0)["wm"], summary(build(ones, k), t0)["typ"]) for k in np.arange(0.5, 1.61, 0.1))
        for mult in (1.5, 2.0):
            s = summary(build(np.where(cm, mult, 1.0)), t0)
            ref = float(np.interp(s["wm"], [a for a, _ in f], [b for _, b in f]))
            lines.append(f"  machine E, {sp}, bids x{mult} in chop: typical ${s['typ']:,.0f}, worst month {s['wm']:+.1f}% | "
                         f"line ${ref:,.0f} ({(s['typ'] / ref - 1) * 100:+.0f}%)")
            print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
