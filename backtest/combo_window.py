"""IS THE COMBO PAPER BOOK'S START UNUSUAL? Its first 11 days against every 11-day stretch of its own backtest.

combo_paper.py on the VM (pre-registered 2026-09-24, verdict ~2027-03-24) read on 2026-10-05, day 11:
$221 -> $188.07 (-14.9%; trend -$19.62, market-neutral -$13.03, sleeve idle), in a BULL regime (BTC +7.2% over
its 1000h average) while breadth20 fell 0.97 -> 0.78. A forward test is judged at its verdict, not on day 11 -
but whether day 11 is already outside what the backtest allows is a fair question, and it is answered by the
backtest's own 11-day returns.
Series as machine.py: trend = the triple, 21-day anchor, 9x guard, gains shrunk for hindsight and losses whole
(worst_month.TCACHE, 10 orderings); MN 1x and the bear sleeve 1x raw; NO crash bids (combo_paper has none).
The shrink makes bad windows slightly MORE common than the unshrunk book, so the shares below lean pessimistic.

REGISTERED PREDICTION (2026-10-05, before running): an 11-day loss of 15% or worse happens in 5-10% of all
11-day windows, and in 3-6% of windows that start in a BULL regime.

    python -m backtest.combo_window
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_chop import fast_run  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402
from backtest.worst_month import TCACHE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEEDS = tuple(range(10))
LIVE = -0.149          # combo_paper --status on the VM, 2026-10-05, day 11
DAYS = 11
# 2026-10-08, day 14: $175.56 (-20.56%), trend -$31.77, MN -$13.25; BTC +1.8% over its 1000h average, a 4h trail
# break at 04:00 UTC that day. REGISTERED before running `--days 14 --live -0.2056`: the live book sits at the
# 5th-8th percentile of 14-day windows that start in BULL, and the 3rd-5th of all windows.


def main():
    cache = pickle.loads(TCACHE.read_bytes())
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    reg = None
    rows = []
    for sd in SEEDS:
        t = cache[("anchor", sd)]
        r = t + mn_d.reindex(t.index).fillna(0.0) + sleeve.reindex(t.index).fillna(0.0)
        if reg is None:
            reg = btc_regime(C).reindex(r.index).ffill()
        c = (1 + r).cumprod()
        w = (c.shift(-DAYS) / c - 1).dropna()
        rows.append(pd.DataFrame({"w": w, "reg": reg.reindex(w.index), "sd": sd}))
    W = pd.concat(rows)
    out = [f"combo (trend + MN + sleeve, no bids), every {DAYS}-day window, 10 orderings: {len(W):,} windows, "
           f"{W.index.min():%Y-%m-%d} .. {W.index.max():%Y-%m-%d}", "",
           f"  {'windows starting in':<20}{'n':>8}{'<= -20%':>9}{'<= -15%':>9}{'<= -10%':>9}{'median':>9}"
           f"{'5th pct':>9}{'1st pct':>9}"]
    for lab, m in (("any regime", W.w.notna()), ("BULL", W.reg == "bull"), ("CHOP", W.reg == "chop"), ("BEAR", W.reg == "bear")):
        x = W.w[m]
        out.append(f"  {lab:<20}{len(x):>8,}{np.mean(x <= -0.20)*100:>8.1f}%{np.mean(x <= -0.15)*100:>8.1f}%"
                   f"{np.mean(x <= -0.10)*100:>8.1f}%"
                   f"{x.median()*100:>+8.1f}%{np.percentile(x, 5)*100:>+8.1f}%{np.percentile(x, 1)*100:>+8.1f}%")
    out.append(f"\n  the live book's first {DAYS} days: {LIVE*100:+.1f}% -> percentile among BULL windows: "
               f"{np.mean(W.w[W.reg == 'bull'] <= LIVE)*100:.1f}%, among all: {np.mean(W.w <= LIVE)*100:.1f}%")
    after = []
    for sd in SEEDS:                                            # what came AFTER a start this bad (same series)
        t = cache[("anchor", sd)]
        r = t + mn_d.reindex(t.index).fillna(0.0) + sleeve.reindex(t.index).fillna(0.0)
        c = (1 + r).cumprod()
        w = c.shift(-DAYS) / c - 1
        nxt = c.shift(-182) / c.shift(-DAYS) - 1                # from day DAYS to day 182 (the verdict)
        tot = c.shift(-182) / c - 1
        sel = w <= LIVE
        after.append(pd.DataFrame({"rest": nxt[sel], "total": tot[sel]}).dropna())
    A = pd.concat(after)
    if len(A):
        out.append(f"  windows that started this badly ({len(A):,}): from day {DAYS} to day 182 the median was "
                   f"{A.rest.median()*100:+.0f}%; the full 182 days ended above the start in "
                   f"{np.mean(A.total > 0)*100:.0f}%, median {A.total.median()*100:+.0f}%")
    txt = "\n".join(out)
    print(txt)
    name = "combo_window.txt" if DAYS == 11 else f"combo_window_{DAYS}d.txt"
    (ROOT / "logs" / name).write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    if "--days" in sys.argv:
        DAYS = int(sys.argv[sys.argv.index("--days") + 1])
    if "--live" in sys.argv:
        LIVE = float(sys.argv[sys.argv.index("--live") + 1])
    main()
