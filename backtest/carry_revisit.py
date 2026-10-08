"""PHASE 2 (re-testing thin kills): FUNDING CARRY with the short-leg exit (2026-10-08).

THE KILL BEING RE-TESTED (doc 02, "six strategies for BEAR and CHOP", test 6; carry_check.py): market-neutral funding
carry - every 7 days on the PIT top-60, short the top decile by trailing 7-day funding, long the bottom decile - made
+0.78%/week on average and was killed by ONE week: short MYX while it rose +1,137% (2025-09), -107% of the account.
Its backing for "untradeable" is that week (plus fragility checks that ran on the same one rebalance day). Today's
mn_combos.py found the same failure in the momentum book on one of seven rebalance days, and a fix that costs
nothing on average: a short-leg BOOK exit at +50% (out of that name until the next rebalance, filled at the level,
or at the open on a gap through it). The carry book was never run with that exit, or on the other six days.

Here, all 7 rebalance days: the original (uncapped), with the +50% / +100% short exit, and the fragility check that
carry_check ran (rank on the day BEFORE - a one-day lag must not kill a real carry).

REGISTERED BEFORE RUNNING:
    - start day 0 reproduces bear_chop.fast_run's carry exactly (self-check).
    - uncapped, at least one of the 7 days is wiped out (fall >= 90%) - the MYX week.
    - with the +50% exit no day falls 90%; mean Sharpe > +0.8 tune and > +0.5 holdout; worst day positive on both.
    - the one-day lag keeps at least two-thirds of the Sharpe (carry is slow).
    - correlation with the momentum MN (+50% exit) below +0.3 weekly: it would be a separate book.

RESULT (2026-10-08, logs/carry_revisit.txt): THE KILL STANDS, on better backing. Start day 0 reproduces fast_run
    exactly. Uncapped: falls 68-142% (wiped on several days), holdout Sharpe +0.04. With the +50% short exit: worst week
    -22% (was -122%) but holdout Sharpe +0.28 mean, -0.24 on the worst day, ~+6%/yr, falls 50-74%; the tune half is
    +1.27. A day's lag keeps most of it (+1.14 / +0.23). Correlation with the momentum MN +0.10. It was not only the MYX
    week: the carry has faded on the holdout. Predictions: wiped uncapped - right; no 90% fall with the exit - right;
    holdout > +0.5 and worst day positive - WRONG; lag keeps two-thirds - right; correlation < 0.3 - right.

    python -m backtest.carry_revisit
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import mn_combos as m  # noqa: E402

LOG = ROOT / "logs" / "carry_revisit.txt"


def main():
    from backtest.bear_chop import fast_run
    from backtest.market_neutral import drop_non_crypto, load_panel
    from backtest.wide_book import eligibility
    D = m.data()
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fxd = pd.DataFrame(D["Fx"], index=D["idx"], columns=D["cols"])
    score = -Fxd.rolling(7, min_periods=7).sum().to_numpy()
    ref = fast_run(C, Fxd, first, drop_non_crypto(eligibility(60)), look=1, hold=7, score=score, fshift=1)
    ref = pd.Series(ref.net.to_numpy(), index=pd.DatetimeIndex(ref.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    mine = m.mn_run(look=1, score="funding7")
    common = ref.index.intersection(mine.index)
    gap = float((ref.reindex(common) - mine.reindex(common)).abs().max())
    lines = [f"backtest/carry_revisit.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-60, 1x gross; Sharpe tune / holdout "
             f"(split {m.HOLDOUT:%Y-%m-%d})", f"CHECK: start-day 0 reproduces bear_chop.fast_run's carry on {len(common)} of "
             f"{len(ref)} rebalances, max gap {gap:.1e}", ""]
    print(lines[1], flush=True)
    assert gap < 1e-9 and len(common) >= len(ref) - 2, "carry rebuild != fast_run"
    mom = pd.concat([m.mn_run(start=o, stop="short_only", short_stop=0.5) for o in range(7)], axis=1).mean(axis=1)
    V = {"carry as killed (uncapped)": dict(),
         "carry + short exit +50%": dict(stop="short_only", short_stop=0.5),
         "carry + short exit +100%": dict(stop="short_only", short_stop=1.0),
         "carry + exit +50%, ranked a day earlier": dict(stop="short_only", short_stop=0.5, lag=1)}
    for nm, kw in V.items():
        st, ws, ser = [], [], []
        for o in range(7):
            s = m.mn_run(look=1, score="funding7", start=o, **kw)
            st.append(m.stats(s, 7)); ws.append(s.min()); ser.append(s)
        cor = pd.concat(ser, axis=1).mean(axis=1).corr(mom)
        lines.append(f"  {nm:40} Sharpe mean {np.mean([x['tune'] for x in st]):+.2f} / {np.mean([x['hold'] for x in st]):+.2f}, "
                     f"worst day {min(x['tune'] for x in st):+.2f} / {min(x['hold'] for x in st):+.2f} | ann "
                     f"{np.nanmean([x['tune_ann'] for x in st]) * 100:+.0f}% / {np.nanmean([x['hold_ann'] for x in st]) * 100:+.0f}% | falls "
                     f"{min(x['fall'] for x in st) * 100:.0f}-{max(x['fall'] for x in st) * 100:.0f}% | worst week {min(ws) * 100:+.0f}% | "
                     f"corr with momentum MN {cor:+.2f}")
        print(lines[-1], flush=True)
        for o, x in enumerate(st):
            lines.append(f"      start +{o}d: Sharpe {x['tune']:+.2f} / {x['hold']:+.2f}, fall {x['fall'] * 100:.0f}%, worst week {ws[o] * 100:+.0f}%")
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
