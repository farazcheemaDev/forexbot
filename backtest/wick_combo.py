"""THE FINAL VERSION + THE WICK-BID BOOK: what does catching crash wicks add, on $300?

crash_buy_check.py (logs/crash_buy_check.txt): resting buys 10% below the previous hour's close on the
PIT top-20 perps, each 1/20 of equity, every fill taken, sold at the fill hour's close, made +37.5%/yr
(tune +48.4, holdout +15.8), worst day -17.3%, max DD 22%; it survived +100bp of exit slippage at
k 15-20%, the removal of the top days and of all of 2021, and Bitget's own candles (k 10%: +5.4% per
fill on 34 fills vs Binance's +4.8% on the same dates; k 15%: no Bitget fills in 11 months).

This adds it, as a fourth book on the same account, to the final version (trend 100% + 21-day anchor +
sleeve 1x + MN 1x, max_mix.py's fair method), with 30bp of extra exit slippage charged on every fill.
Reported on $300: the year, the months, the falls, correlation, both halves.

REGISTERED PREDICTION (2026-09-24, before running): correlation with the final version near zero
(it earns in crash hours, the trend book loses in them); the typical year on $300 rises by 10-25%;
the worst month improves a little; the biggest fall is about unchanged.

    python -m backtest.wick_combo
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.dd_fixes as D  # noqa: E402
import backtest.max_mix as M  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.crash_buy import fills_for, load_1h  # noqa: E402
from backtest.crash_buy_check import honest  # noqa: E402
from backtest.expectations import month_ends, windows  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAP = 300.0
CUT = pd.Timestamp("2024-08-29")
SEEDS = tuple(range(10))


def main():
    el = drop_non_crypto(eligibility(20))
    rows = []
    for s in sorted(x for x, ms in el.items() if ms):
        d = load_1h(s)
        if d is not None:
            rows += fills_for(s, d, el[s], d.time.iloc[0], "buy")
    W = pd.DataFrame(rows)
    wick = honest(W, 0.10, 1 / 20, extra=0.003).pct_change().fillna(0.0)

    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    trows = D.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))

    res = {"FINAL version": [], "FINAL + wick bids": []}
    corr = []
    for sd in SEEDS:
        base = D.sim(trows, bn, bv, sd).pct_change().fillna(0.0)
        s = M.shrink_factor(base)
        r = D.sim(trows, bn, bv, sd, lev=9.0, size_fn=D.anchor(21)).pct_change().fillna(0.0)
        t1 = pd.Series(np.where(r > 0, s * r, r), index=r.index)
        fin = t1 + mn_d.reindex(t1.index).fillna(0.0) + sleeve.reindex(t1.index).fillna(0.0)
        wk = wick.reindex(fin.index).fillna(0.0)
        corr.append(fin.corr(wk))
        res["FINAL version"].append(fin)
        res["FINAL + wick bids"].append(fin + wk)

    print(f"wick book alone (top-20, 10% below, 1/20 each, +30bp exit slippage): "
          f"{((1 + wick).prod() ** (365.25 / len(wick)) - 1) * 100:+.1f}%/yr; daily correlation with the final version "
          f"{np.mean(corr):+.2f}\n")
    print(f"${CAP:.0f} over 12 months (10 orderings; trend gains shrunk for hindsight, the other books raw)")
    for span, t0 in (("all 6 years", None), ("last 2 years", CUT)):
        print(f"\n  {span}")
        print(f"  {'book':<22}{'typical yr':>11}{'bad yr':>9}{'<$300':>7}{'worst yr':>10}{'fall':>6}{'typ month':>11}"
              f"{'worst month':>13}{'months up':>11}")
        for name, lst in res.items():
            W12, DD, TM, WM, UP = [], [], [], [], []
            for x in lst:
                c = (1 + (x if t0 is None else x[x.index >= t0])).cumprod()
                me = month_ends(c)
                m = (me / me.shift(1)).dropna().to_numpy() - 1
                W12.append(windows(me, 12)); DD.append(float((1 - c / c.cummax()).max() * 100))
                TM.append(np.median(m)); WM.append(m.min()); UP.append((m > 0).mean() * 100)
            w = np.concatenate(W12)
            print(f"  {name:<22}${CAP*np.median(w):>9,.0f}${CAP*np.percentile(w, 25):>7,.0f}{(w < 1).mean()*100:>6.0f}%"
                  f"${CAP*w.min():>8,.0f}{np.mean(DD):>5.0f}%{CAP*np.mean(TM):>+9.0f}$ {np.mean(WM)*100:>+9.0f}%  "
                  f"{np.mean(UP):>8.0f}%")


if __name__ == "__main__":
    main()
