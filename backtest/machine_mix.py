"""MACHINE v2 x MACHINE v3 - can a mix keep v2's big years with v3's smaller falls? (2026-10-08)

The parts, each a daily return series on one account (machine.py's overlay method), 10 orderings:
    trend   v2's triple trend book (12 hand-picked coins, 21-day anchor, 9x guard), gains SHRUNK for hindsight and losses
            whole (worst_month.TCACHE, as machine.py)
    pair    v3's daily Bollinger book + capitulation book (half each, 8 slots each, 1x; pair_lab.account), point-in-time
    mn      the market-neutral book: v2 runs it uncapped at 1x; v3 capped (+100% a coin-week) at 0.5x
    sleeve  the bear breadth sleeve 1x (both machines)
    bids    the capped crash bids (v2 only; logs/wick_capped.pkl)
Yardstick: machine.summary - $300 after 12 months (typical / bad 1-in-4 / worst), years under $300, worst month, biggest
fall, months up - on all 6 years and the last 2.

REGISTERED BEFORE RUNNING: the mixes land between v2 and v3; the trend book and the daily book move together, so a mix
diversifies less than its parts suggest; the best mix keeps most of v2's typical year with a worst month nearer v3's.

RESULT (2026-10-08, logs/machine_mix.txt; 6 years / last 2 years)
    v2: $1,812 / $1,625 typical, worst month -29% / -25%, fall 57% / 45%.   v3: $547 / $650, -12.5% / -9.5%, 36% / 28%.
    MIX B (v3 + v2's trend book at 0.5 + v2's crash bids): $1,406 / $1,355 typical, bad $722 / $1,029, WORST $290 / $480
    (better than v2's $222 / $454), worst month -16% / -16%, fall 45% / 38%, months up 64% / 68%.
    MIX C (everything at full size): $1,971 / $1,831 typical but -25% / -24% worst month and a 58% fall.
    Only switching v2's MN to v3's capped 0.5x: $1,441 / $1,111 (v2's MN gains lean on the 2026 pumps).
    Correlation trend-pair +0.41 (moderate - both trend-follow), everything else ~0 or negative.
    Prediction (between v2 and v3; the best mix keeps most of v2's typical year with a worst month nearer v3's): right -
    MIX B keeps 78% / 83% of v2's typical year with about half its worst month.

    python -m backtest.machine_mix

RE-RUN 2026-10-09 on the FIXED loader (capitulation_wide.halt_cut): until then a data-archive hole cut 51 coins (XRP, SOL,
    LTC ...) at 2022-02-25. Where a RESULT above differs from this file's log, THE LOG IS CURRENT - doc 02, "The archive-hole bug".
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402
from backtest.mn_capped import mn_series  # noqa: E402
from backtest.worst_month import TCACHE  # noqa: E402

LOG = ROOT / "logs" / "machine_mix.txt"


def main():
    cache = pickle.loads(TCACHE.read_bytes())
    mn_raw, mn_cap = pl.mn_daily(), mn_series(1.0)
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    bids = pd.read_pickle(ROOT / "logs" / "wick_capped.pkl")[10]
    D, C = pl.daily_trades(), pl.capit_trades(0)
    parts = {}
    for sd in range(10):
        t = cache[("anchor", sd)]
        idx = t.index
        pair = pl.account({"daily": (D, 0.5, 8), "capit": (C, 0.5, 8)}, seed=sd)[0].pct_change().reindex(idx).fillna(0.0)
        parts[sd] = pd.DataFrame({"trend": t, "pair": pair, "mn_raw": mn_raw.reindex(idx).fillna(0.0),
                                  "mn_cap": mn_cap.reindex(idx).fillna(0.0), "sleeve": sleeve.reindex(idx).fillna(0.0),
                                  "bids": bids.reindex(idx).fillna(0.0)})
    P0 = parts[0]
    corr = P0.resample("ME").apply(lambda x: (1 + x).prod() - 1).corr()
    lines = [f"backtest/machine_mix.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; $300, 10 orderings; trend gains shrunk for hindsight, "
             f"the other parts raw", "",
             f"monthly correlation (ordering 0): trend-pair {corr.loc['trend', 'pair']:+.2f}, trend-mn {corr.loc['trend', 'mn_raw']:+.2f}, "
             f"pair-mn {corr.loc['pair', 'mn_cap']:+.2f}, trend-sleeve {corr.loc['trend', 'sleeve']:+.2f}, pair-sleeve "
             f"{corr.loc['pair', 'sleeve']:+.2f}", ""]
    W = {
        "v2 (trend + MN 1x + sleeve + bids)": dict(trend=1, pair=0, mn_raw=1, mn_cap=0, sleeve=1, bids=1),
        "v3 (pair + MN capped 0.5 + sleeve)": dict(trend=0, pair=1, mn_raw=0, mn_cap=0.5, sleeve=1, bids=0),
        "MIX A: v2 with MN capped 0.5 + pair 0.5": dict(trend=1, pair=0.5, mn_raw=0, mn_cap=0.5, sleeve=1, bids=1),
        "MIX B: v3 + trend 0.5 + bids": dict(trend=0.5, pair=1, mn_raw=0, mn_cap=0.5, sleeve=1, bids=1),
        "MIX C: trend 1 + pair 1 + MN capped 0.5 + sleeve + bids": dict(trend=1, pair=1, mn_raw=0, mn_cap=0.5, sleeve=1, bids=1),
        "v2 with MN capped 0.5 (only the MN change)": dict(trend=1, pair=0, mn_raw=0, mn_cap=0.5, sleeve=1, bids=1),
    }
    for span, t0 in (("all 6 years", None), ("last 2 years", CUT)):
        lines.append(f"{span}: $300 after 12 months - typical / bad / worst | years < $300 | worst month | biggest fall | months up")
        for nm, w in W.items():
            xs = [sum(w[k] * parts[sd][k] for k in w) for sd in range(10)]
            s = summary(xs, t0)
            lines.append(f"  {nm:52} ${s['typ']:>7,.0f} / ${s['bad']:>6,.0f} / ${s['worst']:>6,.0f} | {s['below']:3.0f}% | "
                         f"{s['wm']:+6.1f}% | {s['dd']:3.0f}% | {s['up']:3.0f}%")
        lines.append("")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
