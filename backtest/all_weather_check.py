"""DOES THE ALL-WEATHER MIX SURVIVE THE CONTROLS? - both halves, bar phases, matched risk.

WHAT all_weather.py FOUND
    Ranking mixes by their WORST regime cell instead of by the typical year picks
    trend 0.70 | MN 2x | sleeve 1x | bids 1x, which turns the sideways cell from +0.3%/mo to
    +7.0% and leaves the typical year unchanged ($1,474 against $1,469 on $221).

WHY THAT IS NOT YET A RESULT
    It raises the fall from 57% to 68% and the worst month from -29% to -34%, and MN 2x means a
    -48% week for that leg alone. In this repo a change that buys return by adding exposure has
    to beat the same return reached by simply BETTING MORE - that control killed 16 slots
    (slots_sweep.py) and is what made MAX_UNITS 5->7 believable. It also has to hold on both
    halves and on all four bar phases.

    THE CONTROL HERE: scale the WHOLE machine v2 up until its fall matches the all-weather mix's.
    If that reaches the same sideways number, MN 2x is just leverage wearing a costume. If it
    does not - and it should not, because scaling everything scales the trend book's chop LOSS
    too - then the mix is really re-allocating risk toward the regime that needs it.

REGISTERED PREDICTIONS (before running, 2026-09-26)
    1. The control FAILS to match: machine v2 scaled to a 68% fall still has a sideways mean
       under +2%/mo, because its trend book grows with it.
    2. The sideways gain holds on BOTH halves. It is a portfolio weight, not a fitted parameter,
       and MN earns in chop on both (mn_scale.py: +1.403%/wk full, +2.369% holdout).
    3. The sideways MEDIAN stays negative on both halves and on every bar phase. Nothing here
       fixes the typical month - only the average.
    4. Bar phase changes the trend book and therefore the bull cell, but moves the sideways cell
       by under 2 points, because 3 of the 4 books do not depend on the trend grid at all.

    python -m backtest.all_weather_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.max_mix as M  # noqa: E402
from backtest.bar_phase import PHASES, rows_for_phase  # noqa: E402
from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.dd_fixes import CAP, SEEDS, anchor, decompose, sim  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CUT = pd.Timestamp("2024-08-29")
BEST = dict(g=0.70, k_mn=2.0, k_sl=1.0, k_bid=1.0)
TODAY = dict(g=1.00, k_mn=1.0, k_sl=1.0, k_bid=1.0)


def books(phase=0):
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
    rows = decompose(rows_for_phase(phase, tight=True, time_stop=(100, 2.0), max_units=7))
    tr = {}
    for lev in (8.0, 9.0):
        for sd in SEEDS:
            base = sim(rows, bn, bv, sd).pct_change().fillna(0.0)
            s = M.shrink_factor(base)
            rt = sim(rows, bn, bv, sd, lev=lev, size_fn=anchor(21)).pct_change().fillna(0.0)
            tr[(lev, sd)] = pd.Series(np.where(rt > 0, s * rt, rt), index=rt.index)
    idx = tr[(9.0, SEEDS[0])].index
    dom = reg.groupby(reg.index.to_period("M")).agg(lambda v: v.value_counts().index[0])
    return tr, mn_d.reindex(idx).fillna(0.0), sleeve.reindex(idx).fillna(0.0), \
        bids.reindex(idx).fillna(0.0), dom


def cells(tr, mn_d, sl, bd, dom, g, k_mn, k_sl, k_bid, scale=1.0, t_from=None, t_to=None):
    lev = 8.0 if k_mn >= 2.0 else 9.0
    months, dds = [], []
    for sd in SEEDS:
        r = g * tr[(lev, sd)] + k_mn * mn_d + k_sl * sl + k_bid * bd
        r = r * scale
        if t_from is not None:
            r = r[r.index >= t_from]
        if t_to is not None:
            r = r[r.index < t_to]
        if len(r) < 200:
            return None
        eq = (1 + r).cumprod()
        dds.append(float((1 - eq / eq.cummax()).max() * 100))
        months.append(eq.resample("ME").last().pct_change().dropna())
    mo = pd.concat(months)
    lab = pd.Series([dom.get(p, "chop") for p in mo.index.to_period("M")], index=mo.index)
    out = dict(dd=float(np.mean(dds)), worst=float(np.mean([m.min() * 100 for m in months])),
               yr=float(np.median([(1 + m).prod() ** (12 / max(len(m), 1)) for m in months])) * CAP)
    for gk in ("bull", "chop", "bear"):
        x = mo[lab == gk]
        out[gk] = float(x.mean() * 100)
        out[gk + "_med"] = float(x.median() * 100)
        out[gk + "_up"] = float((x > 0).mean() * 100)
    return out


def row(lab, c, extra=""):
    return (f"  {lab:<34}{c['bull']:>+8.1f}%{c['chop']:>+8.1f}%{c['bear']:>+8.1f}%"
            f"{c['chop_med']:>+9.1f}%{c['chop_up']:>5.0f}%{c['yr']:>8.0f}${c['dd']:>5.0f}%"
            f"{c['worst']:>+7.0f}%{extra}")


HDR = (f"  {'mix':<34}{'BULL':>9}{'CHOP':>8}{'BEAR':>8}{'chop med':>9}{'up':>6}"
       f"{'typ yr':>8}{'DD':>6}{'wst mo':>7}")


def main():
    print("building the four books...")
    tr, mn_d, sl, bd, dom = books(0)
    t = cells(tr, mn_d, sl, bd, dom, **TODAY)
    b = cells(tr, mn_d, sl, bd, dom, **BEST)

    print("\n1. THE CONTROL - machine v2 scaled up until its fall matches the all-weather mix")
    print(HDR)
    print(row("machine v2 (today)", t, "  <- today"))
    print(row("all-weather (trend .7 | MN 2x)", b, "  <- candidate"))
    hit = None
    for s in (1.1, 1.2, 1.3, 1.4, 1.5, 1.6):
        c = cells(tr, mn_d, sl, bd, dom, **TODAY, scale=s)
        mark = ""
        if hit is None and c["dd"] >= b["dd"]:
            hit, mark = s, "  <- matched fall"
        print(row(f"machine v2 x{s:g} (just bet more)", c, mark))
    print("\n  If a scaled machine v2 reaches the candidate's CHOP cell at the same fall, the")
    print("  candidate is leverage in disguise. If it does not, MN 2x is buying something.")

    print(f"\n2. BOTH HALVES - tune < {CUT:%Y-%m-%d} <= holdout")
    print(HDR)
    for lab, kw in (("machine v2", TODAY), ("all-weather", BEST)):
        for wlab, w in (("tune", dict(t_to=CUT)), ("hold", dict(t_from=CUT))):
            c = cells(tr, mn_d, sl, bd, dom, **kw, **w)
            if c:
                print(row(f"{lab} - {wlab}", c))

    print("\n3. ALL FOUR BAR PHASES - does the sideways gain depend on the trend grid?")
    print(f"  {'phase':<8}{'v2 CHOP':>10}{'AW CHOP':>10}{'gain':>8}{'AW chop med':>13}"
          f"{'AW up':>7}{'AW DD':>7}")
    for ph in PHASES:
        trp, mnp, slp, bdp, domp = books(ph) if ph else (tr, mn_d, sl, bd, dom)
        a = cells(trp, mnp, slp, bdp, domp, **TODAY)
        c = cells(trp, mnp, slp, bdp, domp, **BEST)
        print(f"  {ph:<8}{a['chop']:>+9.1f}%{c['chop']:>+9.1f}%{c['chop'] - a['chop']:>+7.1f}%"
              f"{c['chop_med']:>+12.1f}%{c['chop_up']:>6.0f}%{c['dd']:>6.0f}%"
              + ("  <- deployed grid" if ph == 0 else ""))


if __name__ == "__main__":
    main()
