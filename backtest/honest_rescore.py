"""THE PAPER BOOKS RE-SCORED ON THE CORRECTED ENGINE, 20 ORDERINGS, PAIRED.

Two corrections found on 2026-09-23 change every backtest figure for these books:
  causal_t0.py     4h/12h rows were stamped 3h/11h after their real entry; the short
                   boost's flag was read from BTC bars that closed after the short opened.
  funding_cost.py  the book had never been charged funding: 21% of lifetime long R.

Five orderings leave ~+-1.5%/mo of noise on a mean, which is the size of every difference
at stake here. So: 20 orderings, and each variant is compared to main on the SAME ordering
(paired), which removes the shared noise and gives a standard error for the difference.

    python -m backtest.honest_rescore
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402
from backtest.causal_t0 import boost, real_t0  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402

SEEDS = tuple(range(20))


def per_seed(rows, bear, cut, half):
    out = []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
        s = evaluate(o, bear, t_to=cut) if half == "tune" else evaluate(o, bear, t_from=cut)
        out.append((s["hpm"], s["dd"], s["worst_mo"]))
    return np.array(out)


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    main_r = charged(real_t0(short_funding(long_funding(rows_for(BASE_RULES)))))
    tight_r = charged(real_t0(short_funding(long_funding(rows_for(BASE_RULES, tight=True)))))
    books = {"main": main_r,
             "tight": tight_r,
             "short boost x5": boost(main_r, 5, True),
             "tight + short boost x5": boost(tight_r, 5, True)}
    print(f"tune < {cut:%Y-%m-%d} <= holdout | causal t0, funding charged, {len(SEEDS)} orderings\n")
    print(f"  {'book':<26}{'TUNE/mo':>9}{'DD':>5}{'HOLD/mo':>9}{'DD':>5}{'worst':>8}"
          f"   {'vs main TUNE':>14}{'vs main HOLD':>15}")
    res = {k: (per_seed(v, bear, cut, "tune"), per_seed(v, bear, cut, "hold"))
           for k, v in books.items()}
    for k, (a, b) in res.items():
        dt = a[:, 0] - res["main"][0][:, 0]; dh = b[:, 0] - res["main"][1][:, 0]
        se_t = dt.std(ddof=1) / np.sqrt(len(dt)); se_h = dh.std(ddof=1) / np.sqrt(len(dh))
        extra = "" if k == "main" else (f"   {dt.mean():>+6.2f}+-{se_t:.2f}"
                                         f"   {dh.mean():>+6.2f}+-{se_h:.2f}")
        print(f"  {k:<26}{a[:,0].mean():>+8.2f}%{a[:,1].mean():>4.0f}%{b[:,0].mean():>+8.2f}%"
              f"{b[:,1].mean():>4.0f}%{b[:,2].mean():>+7.1f}%{extra}")
    a, b = res["main"]
    print(f"\n  main book, spread across orderings: tune {a[:,0].min():+.2f}..{a[:,0].max():+.2f}"
          f"  holdout {b[:,0].min():+.2f}..{b[:,0].max():+.2f} %/mo")


if __name__ == "__main__":
    main()
