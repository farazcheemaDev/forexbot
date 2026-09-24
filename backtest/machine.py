"""THE MACHINE, v2: the final version + the capped crash bids, measured every way that matters.

Asked 2026-09-25: "the perfect money making machine... every risk taken into account... crazy gains...
solid evidence". The pieces, each validated separately:
  TREND   the triple (tight + time stop + 7 units) at 100%, 21-day anchor, 9x guard (docs 11, 14)
  MN      market-neutral momentum 1x (doc 10)
  SLEEVE  bear breadth sleeve 1x (doc 13, replicated on the 2018 bear)
  BIDS    crash bids: top-40, 10% under, no bids on BEAR days, first 10 fills an hour, sold at the
          hour's close (doc 16; on Bitget's own 1-minute bars it earns the same per fill as on
          Binance, wick_bitget.py)
Method as worst_month.py: $300, 10 orderings, trend gains shrunk for hindsight and losses whole, the
other books raw; the bids are logs/wick_capped.pkl (5-minute fills, cap 10, Binance, 2020-2026).

A. BY MARKET TYPE: months labelled by the BTC regime most of their days carried (final_regimes.py).
B. THE SIZE DIAL: every book x g, g = 0.7 / 0.85 / 1.0 / 1.2 / 1.4 - what more size buys and costs,
   with the account's worst hour estimated from joint_worst_hour.py (ordering 0: the trend book lost
   38% of the account and the cap-10 bids 15.8% in the 2025-10-10 21:00 hour; both scaled by g, which
   overstates the trend part a little above g = 1 because the 9x guard then binds).
C. MONTHLY INCOME: fixed withdrawals from $300, paused while the balance is under $300 (worst_month.py
   showed that taking money out through a loss is what stops recovery).

REGISTERED PREDICTION (2026-09-25, before running): A - the bids leave rising months about unchanged,
lift sideways months by ~1 point on average and leave falling months unchanged (no bids on BEAR
days). B - x1.2 raises the typical year ~25% and deepens the worst month to about -35% and the fall
to ~65%; its worst hour leaves ~36%, x1.4 ~26%: x1.0 stays the recommendation. C - $20 a month paused
under water leaves a typical ~$1,300 after a year.

    python -m backtest.machine
"""
from __future__ import annotations

import pickle
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
from backtest.expectations import month_ends, windows  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402
from backtest.worst_month import TCACHE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAP = 300.0
CUT = pd.Timestamp("2024-08-29")
SEEDS = tuple(range(10))
TREND_WORST, BIDS_WORST = 0.38, 0.158          # joint_worst_hour.py, ordering 0, 2025-10-10 21:00


def summary(lst, t0=None):
    W12, WM, UP, DD = [], [], [], []
    for x in lst:
        y = x if t0 is None else x[x.index >= t0]
        c = (1 + y).cumprod()
        me = month_ends(c)
        mo = (me / me.shift(1)).dropna().to_numpy() - 1
        W12.append(windows(me, 12)); WM.append(mo.min()); UP.append((mo > 0).mean())
        DD.append(float((1 - c / c.cummax()).max()))
    w = np.concatenate(W12)
    return dict(typ=CAP * np.median(w), bad=CAP * np.percentile(w, 25), worst=CAP * w.min(),
                below=(w < 1).mean() * 100, half=(w < 0.5).mean() * 100, wm=np.mean(WM) * 100,
                up=np.mean(UP) * 100, dd=np.mean(DD) * 100)


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    bids = pd.read_pickle(ROOT / "logs" / "wick_capped.pkl")[10]
    trows = D.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    cache = pickle.loads(TCACHE.read_bytes()) if TCACHE.exists() else {}

    def trend(key, sd, g=1.0):
        if ("shrink", sd) not in cache:
            cache[("shrink", sd)] = M.shrink_factor(D.sim(trows, bn, bv, sd).pct_change().fillna(0.0))
        if (key, sd) not in cache:
            r = D.sim(trows, bn, bv, sd, lev=9.0, size_fn=D.anchor(21), g=g).pct_change().fillna(0.0)
            s = cache[("shrink", sd)]
            cache[(key, sd)] = pd.Series(np.where(r > 0, s * r, r), index=r.index)
            TCACHE.write_bytes(pickle.dumps(cache))
        return cache[(key, sd)]

    def parts(sd, g=1.0, with_bids=True):
        t = trend("anchor" if g == 1.0 else f"g{g}", sd, g)
        idx = t.index
        return pd.DataFrame({"trend": t, "mn": g * mn_d.reindex(idx).fillna(0.0),
                             "sleeve": g * sleeve.reindex(idx).fillna(0.0),
                             "bids": (g if with_bids else 0.0) * bids.reindex(idx).fillna(0.0)})

    base = {sd: parts(sd) for sd in SEEDS}
    # ------------------------------------------------------------ A
    reg = btc_regime(C).reindex(base[0].index).ffill()
    lab = reg.groupby(reg.index.to_period("M")).agg(lambda s: s.value_counts().idxmax())
    print("A. BY MARKET TYPE ($300 account; monthly return, average / typical, months up; mean of 10 orderings)")
    print(f"  {'':<10}{'months':>7}{'final, no bids':>22}{'MACHINE v2':>22}{'  what the bids added (avg)':>28}")
    for rg, nm in (("bull", "RISING"), ("chop", "SIDEWAYS"), ("bear", "FALLING")):
        per = lab[lab == rg].index
        a, b, add = [], [], []
        for sd in SEEDS:
            p = base[sd]
            mo = (1 + p).groupby(p.index.to_period("M")).prod() - 1
            fin = (1 + p.drop(columns="bids").sum(axis=1)).groupby(p.index.to_period("M")).prod() - 1
            mac = (1 + p.sum(axis=1)).groupby(p.index.to_period("M")).prod() - 1
            a.append(fin.reindex(per)); b.append(mac.reindex(per)); add.append(mo.bids.reindex(per))
        a, b, add = pd.concat(a), pd.concat(b), pd.concat(add)
        print(f"  {nm:<10}{len(per):>7}{a.mean()*100:>+10.1f}% / {a.median()*100:+5.1f}% {(a > 0).mean()*100:3.0f}%"
              f"{b.mean()*100:>+10.1f}% / {b.median()*100:+5.1f}% {(b > 0).mean()*100:3.0f}%{add.mean()*100:>+20.2f}%")

    # ------------------------------------------------------------ B
    print("\nB. THE SIZE DIAL: every book x g ($300, 12 months: typical / bad (1 in 4) / worst; share of years ending")
    print("   below $300 and below $150; worst month; biggest fall; months up; the account left in its worst hour)")
    for span, t0 in (("all 6 years", None), ("last 2 years", CUT)):
        print(f"\n  {span}")
        print(f"  {'':<22}{'typical':>9}{'bad':>8}{'worst':>8}{'<$300':>7}{'<$150':>7}{'worst mo':>10}{'fall':>6}"
              f"{'up':>5}{'worst hour left':>17}")
        fin = summary([base[sd].drop(columns="bids").sum(axis=1) for sd in SEEDS], t0)
        print(f"  {'final (no bids) x1.0':<22}${fin['typ']:>7,.0f}${fin['bad']:>6,.0f}${fin['worst']:>6,.0f}"
              f"{fin['below']:>6.0f}%{fin['half']:>6.0f}%{fin['wm']:>+9.1f}%{fin['dd']:>5.0f}%{fin['up']:>4.0f}%"
              f"{(1 - TREND_WORST) * 100:>15.0f}%")
        for g in (0.7, 0.85, 1.0, 1.2, 1.4):
            s = summary([parts(sd, g).sum(axis=1) for sd in SEEDS], t0)
            left = 1 - g * (TREND_WORST + BIDS_WORST)
            print(f"  {'MACHINE v2 x' + str(g):<22}${s['typ']:>7,.0f}${s['bad']:>6,.0f}${s['worst']:>6,.0f}"
                  f"{s['below']:>6.0f}%{s['half']:>6.0f}%{s['wm']:>+9.1f}%{s['dd']:>5.0f}%{s['up']:>4.0f}%"
                  f"{left * 100:>15.0f}%")

    # ------------------------------------------------------------ C
    print("\nC. MONTHLY INCOME from $300 (MACHINE v2 x1.0, every 12-month window, 6 years, 10 orderings):")
    print("   a fixed amount at each month end, PAUSED while the balance is under $300")
    print(f"  {'per month':>10}{'taken out in a year: typical':>30}{'balance after 12 months: typical':>34}{'bad (1 in 4)':>14}{'< $300':>8}")
    for amt in (0, 20, 30, 50, 75):
        outs, bals = [], []
        for sd in SEEDS:
            r = base[sd].sum(axis=1)
            me_idx = np.r_[r.index[1:].month != r.index[:-1].month, True]
            v = r.to_numpy()
            starts = np.flatnonzero(np.r_[True, me_idx[:-1]])
            for i0 in starts:
                i1 = i0 + 365
                if i1 > len(v):
                    break
                bal, took = CAP, 0.0
                for i in range(i0, i1):
                    bal *= 1 + v[i]
                    if me_idx[i] and bal >= CAP + amt:
                        bal -= amt; took += amt
                outs.append(took); bals.append(bal)
        outs, bals = np.array(outs), np.array(bals)
        print(f"  ${amt:>9}{'$':>21}{np.median(outs):>8,.0f}{'$':>25}{np.median(bals):>8,.0f}"
              f"${np.percentile(bals, 25):>12,.0f}{(bals < CAP).mean()*100:>7.0f}%")


if __name__ == "__main__":
    main()
