"""THE BEST BOOK ASSEMBLABLE FROM WHAT SURVIVED - do the three live candidates stack?

Three changes are on paper right now, each measured alone:
    tight exit    longs switch to a 5xATR trail once BTC's 4h trail breaks  (btc_exit.py)
    short boost   a short's risk x M while that same break is on           (vol_target.py)
    runner sizing each long's risk x its runner-probability rank, mean 1    (entry_runner.py)

They touch different parts of the book - long exits, short sizing, long sizing - so they
should be close to independent. This measures the assembled book against the deployed one,
seed-averaged over 5 orderings, and then LEVERED to the deployed drawdown, because two of
the three pay in drawdown rather than return.

The runner model is fit on the TUNE half only and scored on everything, so the holdout
column never sees a model that saw it.

    python -m backtest.composite
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.btc_exit import btc_trail  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402
from backtest.entry_runner import FEATS, fit_predict  # noqa: E402
from backtest.runner_leverage import build  # noqa: E402

SEEDS = (0, 1, 2, 3, 4)
POS_FEATS = [f for f in FEATS if f not in ("btc_bear", "btc_30")]
RS_SPREAD = 0.9


def stat(rows, bear, cut, half, mult=1.0):
    hpm, dd, wm = [], [], []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        o = [dict(rows[i], R=rows[i]["R"] * mult)
             for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
        s = evaluate(o, bear, t_to=cut) if half == "tune" else evaluate(o, bear, t_from=cut)
        hpm.append(s["hpm"]); dd.append(s["dd"]); wm.append(s["worst_mo"])
    return float(np.mean(hpm)), float(np.mean(dd)), float(np.mean(wm))


def lever(rows, bear, cut, target_t, target_h):
    best = 1.0
    for m in np.linspace(1.0, 3.0, 41):
        t = stat(rows, bear, cut, "tune", m); h = stat(rows, bear, cut, "hold", m)
        if t[1] <= target_t and h[1] <= target_h:
            best = m
        else:
            break
    return best


def main():
    Ddep, Dtight, shorts = build()
    cut = Ddep["t0"].quantile(0.6)
    bear = regimes()[1000]
    tr = Ddep[Ddep.t0 < cut]

    # runner scores: model fit on the TUNE half of the deployed book, applied to both books
    p_dep, _ = fit_predict(tr, Ddep, POS_FEATS)
    p_tig, _ = fit_predict(tr, Dtight, POS_FEATS)
    med = float(np.median(p_dep))

    def rowset(D, p, sized, boost_mult):
        rank = pd.Series(p).rank(pct=True).to_numpy()
        rows = []
        for (r, pv, rk) in zip(D.itertuples(), p, rank):
            f = 1.0 + RS_SPREAD * (rk - 0.5) * 2 if sized else 1.0
            rows.append(dict(t0=r.t0, t1=r.t1, R=r.R * f, side="long", sf=0.05, adds=[r.t0]))
        br = btc_trail(5)
        for s in shorts:
            f = 1.0
            if boost_mult > 1:
                t = pd.Timestamp(s["t0"])
                if t >= br.index[0] and bool(br.asof(t)):
                    f = boost_mult
            rows.append(dict(s, R=s["R"] * f))
        rows.sort(key=lambda r: r["t0"])
        return rows

    dep = rowset(Ddep, p_dep, False, 1)
    bt = stat(dep, bear, cut, "tune"); bh = stat(dep, bear, cut, "hold")
    print(f"deployed: tune {bt[0]:+.2f}%/mo @{bt[1]:.0f}%DD | holdout {bh[0]:+.2f}%/mo "
          f"@{bh[1]:.0f}%DD, worst {bh[2]:+.1f}%\n")
    print(f"  {'book':<40}{'TUNE':>8}{'DD':>5}{'HOLD':>8}{'DD':>5}{'worst':>8} |"
          f"{'x':>6}{'TUNE':>8}{'HOLD':>8}")

    def show(lab, rows):
        t = stat(rows, bear, cut, "tune"); h = stat(rows, bear, cut, "hold")
        m = lever(rows, bear, cut, bt[1], bh[1])
        tm = stat(rows, bear, cut, "tune", m); hm = stat(rows, bear, cut, "hold", m)
        print(f"  {lab:<40}{t[0]:>+7.2f}%{t[1]:>4.0f}%{h[0]:>+7.2f}%{h[1]:>4.0f}%"
              f"{h[2]:>+7.1f}% |{m:>6.2f}{tm[0]:>+7.2f}%{hm[0]:>+7.2f}%")

    show("deployed", dep)
    show("tight exit", rowset(Dtight, p_tig, False, 1))
    show("short boost x8", rowset(Ddep, p_dep, False, 8))
    show("runner sizing", rowset(Ddep, p_dep, True, 1))
    print()
    show("tight + short boost x8", rowset(Dtight, p_tig, False, 8))
    show("tight + runner sizing", rowset(Dtight, p_tig, True, 1))
    show("short boost x8 + runner sizing", rowset(Ddep, p_dep, True, 8))
    show("ALL THREE", rowset(Dtight, p_tig, True, 8))
    print("\n  'x' is the largest risk multiple keeping BOTH halves at or under the deployed")
    print("  book's drawdown. Stacking works only if ALL THREE beats each single change.")


if __name__ == "__main__":
    main()
