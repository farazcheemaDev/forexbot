"""PHASE 2 (re-testing thin kills): crypto PAIRS stat-arb on settings never tried (2026-10-08).

THE KILL (doc 02, "six strategies for BEAR and CHOP", test 2; bear_chop.pairs_book): Engle-Granger pairs on the PIT
top-30, 10 pairs a month, z 2 -> 0, stop at |z| 4, filled at the next close: -0.38%/month, both halves negative, and
72% of trades exit at the stop - the "cointegrated" pairs broke apart within the month. 4 settings were run (fill
lag 0/1, entry 2.5, 365-day formation). Never tried: a SHORTER formation (60 / 90 days - relationships in crypto
change fast, which is what the 72% stops say), no stop at all, a lower entry, a wider universe.

REGISTERED BEFORE RUNNING: the primary reproduces -0.38%/month (self-check); every new setting is negative on at least
one half; no-stop is the worst (the broken pairs never come back); shorter formation does not fix it.

RESULT (2026-10-08, logs/pairs_revisit.txt): THE KILL STANDS. The primary reproduces -0.38%/month. 60/90-day
    formation, no stop, entry z 1.5, top-60: -0.42 to -1.21%/month, every one negative on BOTH halves; stops 73-82%
    where a stop exists. Predictions: all negative on a half - right; no-stop the worst - WRONG (second best); shorter
    formation no fix - right.

    python -m backtest.pairs_revisit
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.bear_chop import pairs_book, per_month, tag  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "pairs_revisit.txt"


def main():
    C, F, first = load_panel()
    F.index = C.index
    reg = btc_regime(C)
    e30, e60 = drop_non_crypto(eligibility(30)), drop_non_crypto(eligibility(60))
    V = {"primary as killed (180d, z 2, stop 4)": (e30, dict(lag=1)),
         "60-day formation": (e30, dict(lag=1, win=60)),
         "90-day formation": (e30, dict(lag=1, win=90)),
         "90-day, NO stop": (e30, dict(lag=1, win=90, z_stop=99.0)),
         "90-day, entry z 1.5": (e30, dict(lag=1, win=90, z_in=1.5)),
         "90-day, PIT top-60": (e60, dict(lag=1, win=90))}
    lines = [f"backtest/pairs_revisit.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; %/month ALL / TUNE / HOLD (split 2024-08-29), "
             f"trades, win, share stopped"]
    for nm, (el, kw) in V.items():
        daily, tr = pairs_book(C, F, first, el, **kw)
        d = tag(pd.DataFrame(dict(t=daily.index, net=daily.to_numpy())), reg)
        pm = lambda x: per_month(x, "net", 1)  # noqa: E731
        lines.append(f"  {nm:40} {pm(d):+.2f}% / {pm(d[d.half == 'tune']):+.2f}% / {pm(d[d.half == 'hold']):+.2f}% | "
                     f"{len(tr)} trades, win {(tr.ret > 0).mean() * 100:.0f}%, stopped {(tr.why == 'stop').mean() * 100:.0f}%")
        print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
