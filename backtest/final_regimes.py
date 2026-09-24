"""THE FINAL VERSION, BY MARKET TYPE: rising (bull), sideways (chop), falling (bear).

The final version (doc 14 section 8, combo_paper.py): the triple trend book at 100% with the
21-day equity anchor + the bear breadth sleeve at 1x + the market-neutral book at 1x, one account.
Same method as backtest/max_mix.py: the trend book's gains shrunk for hindsight (s ~0.733, losses
whole), the two point-in-time books raw, 10 orderings, 2020-2026, deployed bar grid. Months are
labelled by the BTC regime (market_neutral.btc_regime) that most of their days carried.

For each regime: the average and typical (median) month, share of months up, worst month, and
what each component contributed on average.

REGISTERED PREDICTION (2026-09-24, before running): the trend book does all the earning in bull
months and is ~flat in chop and slightly negative in bear; in chop the MN book lifts the typical
month from ~0 to positive; in bear the sleeve + MN turn the average month from negative to
positive. Bull months are almost unchanged by the other two books.

    python -m backtest.final_regimes
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.max_mix as M  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.dd_fixes import CAP, SEEDS, anchor, decompose, sim  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    reg = btc_regime(C)
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    rows = decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    dom = reg.groupby(reg.index.to_period("M")).agg(lambda v: v.value_counts().index[0])

    rec = {"TODAY: triple alone": [], "FINAL: trend 100% + anchor + sleeve 1x + MN 1x": []}
    parts = []
    for sd in SEEDS:
        base = sim(rows, bn, bv, sd).pct_change().fillna(0.0)
        s = M.shrink_factor(base)
        t0 = pd.Series(np.where(base > 0, s * base, base), index=base.index)
        rt = sim(rows, bn, bv, sd, lev=9.0, size_fn=anchor(21)).pct_change().fillna(0.0)
        t1 = pd.Series(np.where(rt > 0, s * rt, rt), index=rt.index)
        m_mn = mn_d.reindex(t1.index).fillna(0.0)
        m_sl = sleeve.reindex(t1.index).fillna(0.0)
        for name, r in (("TODAY: triple alone", t0), ("FINAL: trend 100% + anchor + sleeve 1x + MN 1x", t1 + m_mn + m_sl)):
            eq = (1 + r).cumprod()
            mo = eq.resample("ME").last().pct_change().dropna()
            rec[name].append(mo)
        # each component's own monthly return on the account (not compounded together)
        comp = pd.DataFrame({"trend": t1, "MN": m_mn, "sleeve": m_sl})
        parts.append(comp.resample("ME").sum())

    print("month by month, by the BTC regime most of the month's days carried (2020-2026, 10 orderings)")
    print("trend gains shrunk for hindsight, losses whole; the two point-in-time books raw\n")
    for name, lst in rec.items():
        mo = pd.concat(lst)
        lab = pd.Series([dom.get(p, "chop") for p in mo.index.to_period("M")], index=mo.index)
        print(f"  {name}")
        print(f"    {'market':<22}{'months':>7}{'average':>9}{'typical':>9}{'up':>6}{'worst':>8}{'best':>9}{'typical $221 month':>20}")
        for g, glab in (("bull", "RISING (bull)"), ("chop", "SIDEWAYS (chop)"), ("bear", "FALLING (bear)")):
            x = mo[lab == g]
            print(f"    {glab:<22}{len(x) // len(SEEDS):>7}{x.mean()*100:>+8.1f}%{x.median()*100:>+8.1f}%"
                  f"{(x > 0).mean()*100:>5.0f}%{x.min()*100:>+7.0f}%{x.max()*100:>+8.0f}%{CAP*x.median():>+19.0f}$")
        print()
    P = pd.concat(parts)
    lab = pd.Series([dom.get(p, "chop") for p in P.index.to_period("M")], index=P.index)
    print("  what each part of the FINAL version adds in an average month, % of the account (simple sum):")
    for g, glab in (("bull", "RISING"), ("chop", "SIDEWAYS"), ("bear", "FALLING")):
        x = P[lab == g]
        print(f"    {glab:<10} trend {x.trend.mean()*100:+6.1f}%   market-neutral {x.MN.mean()*100:+5.1f}%   "
              f"bear sleeve {x.sleeve.mean()*100:+5.1f}%")


if __name__ == "__main__":
    main()
