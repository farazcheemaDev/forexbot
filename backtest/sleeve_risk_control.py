"""THE MATCHED-RISK CONTROL for engine_rescore2.py's one pass: risk x1.5 / x1.0 / x0.5 by sleeve 1h / 4h / 12h (2026-10-08).

engine_rescore2.py: it beats MAIN (+0.47 / +0.98 %/mo) and the TRIPLE (+0.75 / +2.27) on both halves by > 2 se - but
it raises the biggest fall (main 54 -> 64%, triple 51 -> 62% holdout), and graveyard_rescore.py already showed risk
x1.33 is "a dial, not an edge". The control that made MAX_UNITS = 7 believable (CLAUDE.md s2): reach the same fall by
raising risk UNIFORMLY and compare the return. Uniform x1.0 .. x1.5 traces each base's line per half; the sleeve
weighting passes only if it is above that line at its own fall on BOTH halves. Then the bar-phase check is due.

REGISTERED BEFORE RUNNING: on MAIN it is holdout-only at matched risk (uniform x1.33 already gave +0.65 tune at 65%);
on the TRIPLE it beats the line on the holdout and ties or loses the tune half. Not a pass.

RESULT (2026-10-08, logs/sleeve_risk_control.txt): FAILS the control on both. MAIN: tune +5.35 at a 64% fall vs the
    uniform line's +5.45 (-0.10), holdout +5.85 vs +5.23 (+0.62). TRIPLE: tune +9.65 at 57% vs +10.32 (-0.67), holdout
    +13.03 at 62% vs +12.23 (+0.80). Holdout-only at matched risk - the mined-holdout shape. Prediction - right.

    python -m backtest.sleeve_risk_control
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import engine_rescore2 as E  # noqa: E402
from backtest import graveyard_rescore as G  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402

LOG = ROOT / "logs" / "sleeve_risk_control.txt"
W = {"1h": 1.5, "4h": 1.0, "12h": 0.5}


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    lines = [f"backtest/sleeve_risk_control.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; corrected engine, 10 orderings; per half: "
             f"%/mo (CAGR/3) and biggest fall"]
    for bname, bkw in (("MAIN", {}), ("TRIPLE", dict(tight=True, time_stop=(100, 2.0), max_units=7))):
        rs = E.rows2(**bkw)
        line = {}
        for m in (1.0, 1.1, 1.2, 1.3, 1.4, 1.5):
            S = G.score([dict(r, R=r["R"] * m) for r in rs], bear, cut)
            line[m] = {h: (S[h][:, 0].mean(), S[h][:, 1].mean()) for h in ("tune", "hold")}
        S = G.score([dict(r, R=r["R"] * W.get(r["rule"], 1.0)) for r in rs], bear, cut)
        cells, ok = [], True
        for h in ("tune", "hold"):
            ret, dd = S[h][:, 0].mean(), S[h][:, 1].mean()
            pts = sorted((v[h][1], v[h][0]) for v in line.values())
            ref = float(np.interp(dd, [a for a, _ in pts], [b for _, b in pts]))
            ok = ok and ret > ref
            cells.append(f"{h} {ret:+.2f}%/mo at fall {dd:.0f}% vs uniform line {ref:+.2f}%/mo ({ret - ref:+.2f})")
        lines.append(f"  {bname:6}: " + " | ".join(cells) + f" -> {'PASSES the control' if ok else 'fails the control'}")
        lines.append(f"          uniform line: " + "; ".join(f"x{m}: {v['tune'][0]:+.2f}/{v['tune'][1]:.0f}% & {v['hold'][0]:+.2f}/"
                                                            f"{v['hold'][1]:.0f}%" for m, v in line.items()))
        print("\n".join(lines[-2:]), flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
