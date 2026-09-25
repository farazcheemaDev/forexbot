"""ALL-WEATHER: the mix that maximises the WORST market, not the typical year.

THE GOAL, IN THE USER'S WORDS (2026-09-26)
    "an end result bot basically our product ... i just need an end product that can give crazy
    gains in every time of market not just [bull]"

WHY THIS FILE EXISTS, AND WHY max_mix.py DOES NOT ANSWER IT
    max_mix.py searched the same books, but its objective was "highest typical YEAR with a fall
    no worse than today's". That objective is indifferent to WHERE the return comes from, so it
    selected a mix whose sideways months are +0.2% average, -4.5% typical, 32% up
    (logs/machine.txt). Against this goal that is a failure, however good the yearly number is.
    A different objective picks a different mix. Same books, same data, different question:

        maximise the WORST of the three regime cells, then take the most return among the
        mixes that clear it.

WHAT IS ALREADY ESTABLISHED, so this does not re-tread it
    * TREND cannot be cut ONLY in chop - dd_fixes.py measured every chop gate at -0.46 to -4.48
      %/mo with 0-2 wins of 10. It must be in the market to catch the turn into bull. But it CAN
      be made uniformly smaller, which is a different lever and is in this grid as g.
    * MN cannot be made safer by a short-leg stop (mn_stop.py: the stop fires on 0.3% of
      positions and makes the worst week WORSE, -26.3% against -24.2%).
    * MN cannot be made safer by widening the basket (mn_scale.py: at equal tail risk frac 0.10
      beats every wider basket; the signal dilutes faster than the tail shrinks).
    So MN's size is the free variable and its -24.2% worst week at 1x is the price of each unit.
    Scaling it is not free and every candidate here reports what it costs.

METHOD
    The four books as DAILY returns on one account, summed - the method of final_regimes.py and
    machine.py. Trend gains shrunk for hindsight and its losses kept whole; MN, sleeve and bids
    are point-in-time and raw. Months are labelled by the BTC regime most of their days carried.
    The trend book's gross guard is lowered by the MN size it has to share margin with.

REGISTERED PREDICTIONS (before running, 2026-09-26)
    1. NO mix makes all three regime MEDIANS positive. The sideways median is -4.5% today and
       the MN book's chop edge is a MEAN effect carried by its good weeks, so the median month
       moves far less than the average does.
    2. The min-regime objective picks a SMALLER trend book (g 0.7) and a LARGER MN, because the
       trend book is the only one of the four that loses in chop.
    3. That costs total return: the typical year falls from $1,812 toward $1,200-1,400.
    4. The binding constraint is the WORST MONTH, not the return - MN at 2x pushes it past -35%.
    5. The best all-weather mix gets all three regime MEANS positive while the sideways MEDIAN
       stays negative. If a mix clears the median too, check it for a bug before believing it.

    python -m backtest.all_weather
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
G_TREND = (0.7, 0.85, 1.0)
K_MN = (1.0, 1.5, 2.0)
K_SL = (1.0, 1.5, 2.0)
K_BID = (0.0, 1.0)


def build():
    """The four books as daily series. Only the trend book depends on the ordering seed."""
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    reg = btc_regime(C)
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(),
                     index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    bids = pd.read_pickle(ROOT / "logs" / "wick_capped.pkl")[10]
    rows = decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))

    trend = {}
    for k_mn in K_MN:
        for sd in SEEDS:
            base = sim(rows, bn, bv, sd).pct_change().fillna(0.0)
            s = M.shrink_factor(base)
            # the trend book shares margin with MN: its gross guard drops by MN's size
            rt = sim(rows, bn, bv, sd, lev=max(10.0 - k_mn, 4.0), size_fn=anchor(21))
            rt = rt.pct_change().fillna(0.0)
            trend[(k_mn, sd)] = pd.Series(np.where(rt > 0, s * rt, rt), index=rt.index)
    idx = trend[(K_MN[0], SEEDS[0])].index
    dom = reg.groupby(reg.index.to_period("M")).agg(lambda v: v.value_counts().index[0])
    return trend, mn_d.reindex(idx).fillna(0.0), sleeve.reindex(idx).fillna(0.0), \
        bids.reindex(idx).fillna(0.0), dom


def evaluate(trend, mn_d, sl, bd, dom, g, k_mn, k_sl, k_bid):
    cells, months, dds, worst = {}, [], [], []
    for sd in SEEDS:
        r = g * trend[(k_mn, sd)] + k_mn * mn_d + k_sl * sl + k_bid * bd
        eq = (1 + r).cumprod()
        dds.append(float((1 - eq / eq.cummax()).max() * 100))
        mo = eq.resample("ME").last().pct_change().dropna()
        months.append(mo)
        worst.append(float(mo.min() * 100))
    mo = pd.concat(months)
    lab = pd.Series([dom.get(p, "chop") for p in mo.index.to_period("M")], index=mo.index)
    for gk in ("bull", "chop", "bear"):
        x = mo[lab == gk]
        cells[gk] = dict(mean=float(x.mean() * 100), med=float(x.median() * 100),
                         up=float((x > 0).mean() * 100))
    yr = float(np.median([(1 + m).prod() ** (12 / max(len(m), 1)) for m in months])) * CAP
    return dict(cells=cells, yr=yr, dd=float(np.mean(dds)), worst=float(np.mean(worst)),
                minmean=min(c["mean"] for c in cells.values()),
                minmed=min(c["med"] for c in cells.values()))


def main():
    print("building the four books (this takes a few minutes)...")
    trend, mn_d, sl, bd, dom = build()
    print(f"{len(SEEDS)} orderings | ${CAP:.0f} | trend gains shrunk for hindsight, losses whole")
    print("months labelled by the BTC regime most of their days carried\n")

    res = []
    for g in G_TREND:
        for k_mn in K_MN:
            for k_sl in K_SL:
                for k_bid in K_BID:
                    e = evaluate(trend, mn_d, sl, bd, dom, g, k_mn, k_sl, k_bid)
                    e["cfg"] = (g, k_mn, k_sl, k_bid)
                    res.append(e)

    def line(e, tag=""):
        g, k_mn, k_sl, k_bid = e["cfg"]
        nm = f"trend {g:.2f} | MN {k_mn:g}x | sleeve {k_sl:g}x | bids {k_bid:g}x"
        c = e["cells"]
        return (f"  {nm:<44}{c['bull']['mean']:>+8.1f}%{c['chop']['mean']:>+8.1f}%"
                f"{c['bear']['mean']:>+8.1f}%{c['chop']['med']:>+8.1f}%{c['chop']['up']:>5.0f}%"
                f"{e['yr']:>8.0f}${e['dd']:>5.0f}%{e['worst']:>+7.0f}%{tag}")

    hdr = (f"  {'mix':<44}{'BULL':>9}{'CHOP':>8}{'BEAR':>8}{'chop med':>8}{'up':>6}"
           f"{'typ yr':>8}{'DD':>6}{'wst mo':>7}")
    print("1. TODAY'S PRODUCT, and the mixes that beat it on the WORST regime cell")
    print(hdr)
    today = [e for e in res if e["cfg"] == (1.0, 1.0, 1.0, 1.0)][0]
    print(line(today, "  <- MACHINE v2 (on the VM, without bids)"))
    print()
    res.sort(key=lambda e: -e["minmean"])
    print("2. RANKED BY THE WORST REGIME CELL (the goal's objective)")
    print(hdr)
    for e in res[:10]:
        print(line(e, "  *" if e["minmean"] > today["minmean"] else ""))

    print()
    print("3. THE COST OF ALL-WEATHER - return given up to lift the worst cell")
    print(f"  {'mix':<44}{'worst cell':>12}{'typ yr':>9}{'vs today':>10}")
    for e in sorted(res, key=lambda z: -z["minmean"])[:6]:
        g, k_mn, k_sl, k_bid = e["cfg"]
        nm = f"trend {g:.2f} | MN {k_mn:g}x | sleeve {k_sl:g}x | bids {k_bid:g}x"
        print(f"  {nm:<44}{e['minmean']:>+11.1f}%{e['yr']:>8.0f}${e['yr'] - today['yr']:>+9.0f}$")
    print(f"  {'TODAY (machine v2)':<44}{today['minmean']:>+11.1f}%{today['yr']:>8.0f}$"
          f"{0:>+9.0f}$")

    print()
    best = res[0]
    print(f"  BEST WORST-CELL: {best['cfg']} -> every market at least "
          f"{best['minmean']:+.1f}%/mo on average")
    print(f"  sideways MEDIAN month there: {best['cells']['chop']['med']:+.1f}%, "
          f"{best['cells']['chop']['up']:.0f}% of sideways months up")
    print(f"  worst month {best['worst']:+.0f}%, fall {best['dd']:.0f}%, typical year "
          f"${best['yr']:.0f} against today's ${today['yr']:.0f}")
    if best["minmed"] > 0:
        print("  NOTE: all three regime MEDIANS are positive. Prediction 5 said this would not")
        print("  happen - check it for a bug before believing it.")


if __name__ == "__main__":
    main()
