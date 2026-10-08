"""ONE MORE COMBINATION the re-test opened (2026-10-09): the market-neutral book ranked half by 30-day momentum and half
by RSI(14) - two books on one account, each at 0.5x, both with the +50% short-leg exit, on all 7 rebalance days.

moderate_retests.py --xs: RSI-ranking alone has Sharpe +1.45 / +1.22 (momentum +1.06 / +1.33) and no wipe-out on any
rebalance day even uncapped. If the two rankings pick different names, half of each could beat either alone.
REGISTERED BEFORE RUNNING: the blend's mean Sharpe beats momentum on the tune half and ties it (+-0.1) on the holdout;
its worst day beats momentum's on both; weekly correlation of the two books +0.5..+0.8.

    python -m backtest.mn_blend_rsi
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import mn_combos as m  # noqa: E402
from backtest.moderate_retests import scored_run  # noqa: E402

LOG = ROOT / "logs" / "mn_blend_rsi.txt"


def main():
    D = m.data()
    C = pd.DataFrame(D["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    rows = []
    for o in range(7):
        a = scored_run(mom, start=o, stop="short_only", short_stop=0.5)
        b = scored_run(rsi, start=o, stop="short_only", short_stop=0.5)
        idx = a.index.union(b.index)
        a, b = a.reindex(idx).fillna(0.0), b.reindex(idx).fillna(0.0)
        rows.append((m.stats(a, 7), m.stats(b, 7), m.stats(0.5 * a + 0.5 * b, 7), a.corr(b)))
    lines = [f"backtest/mn_blend_rsi.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; 7 rebalance days, +50% short-leg exit on both; "
             f"Sharpe tune / holdout (split {m.HOLDOUT:%Y-%m-%d})"]
    for k, nm in ((0, "momentum alone"), (1, "RSI alone"), (2, "half each")):
        st = [r[k] for r in rows]
        lines.append(f"  {nm:16} Sharpe mean {np.mean([s['tune'] for s in st]):+.2f} / {np.mean([s['hold'] for s in st]):+.2f}, "
                     f"worst day {min(s['tune'] for s in st):+.2f} / {min(s['hold'] for s in st):+.2f} | ann "
                     f"{np.nanmean([s['tune_ann'] for s in st]) * 100:+.0f}% / {np.nanmean([s['hold_ann'] for s in st]) * 100:+.0f}% | falls "
                     f"{min(s['fall'] for s in st) * 100:.0f}-{max(s['fall'] for s in st) * 100:.0f}%")
    lines.append(f"  weekly correlation, momentum book vs RSI book: {np.mean([r[3] for r in rows]):+.2f} (mean over the 7 days)")
    print("\n".join(lines))
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
