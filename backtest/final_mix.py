"""THE FINAL MIX: how big should the trend book be once the two independent books run beside it?

dd_fix_more.py (logs/dd_fix_more.txt) found that adding the market-neutral momentum book (doc 10)
and the bear breadth sleeve (doc 13) beats the uniform-bet-size frontier on both halves in 10/10
orderings (+3.38 / +4.92 %/mo for sleeve + 0.5 x MN), but only takes the worst drawdown from 53%
to 47%: the new books add return, they do not cancel a trend-book fall. The halving is the trend
book's own size. So the question becomes a menu: trend book at g = 0.5 .. 1.0 of its risk, plus
nothing / the sleeve / the sleeve + MN at 0.25 or 0.5, and what $221 does a year in each.

CHECKS
  * the excess over the trend-only frontier for the mixes, on all FOUR bar phases (the trend
    rows re-walked on shifted 4h/12h grids), 10 orderings each, both halves;
  * the $221 menu on the deployed grid, full history: typical / bad / good year (upside
    haircut on the WHOLE book, which understates the point-in-time books), share of years
    ending below $221, worst year, drawdown, worst month, months up - downside RAW.
The MN book is booked on its weekly rebalance day, so its intra-week swings are invisible here;
its own worst week at 1x is -24% (logs/carry_check.txt). Gross exposure: the trend book's 10x
guard does not see the MN book (0.25-0.5x gross), so the live cap would need to be ~0.5x lower.

REGISTERED PREDICTION (2026-09-24, before running): the sleeve + 0.5 MN excess is positive on
both halves on all four phases. On the menu, trend g 0.7 + sleeve + 0.5 MN gives about today's
triple-alone typical year ($584) at a drawdown near 35%.

    python -m backtest.final_mix
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.compounding import summarize  # noqa: E402
from backtest.dd_fixes import CAP, CUT, SEEDS, decompose, sim  # noqa: E402
from backtest.expectations import haircut, month_ends, windows  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

GS = (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
MIXES = (("nothing", 0.0, 0.0), ("+ sleeve", 0.0, 1.0), ("+ sleeve + 0.25 MN", 0.25, 1.0),
         ("+ sleeve + 0.5 MN", 0.5, 1.0))
ROOT = Path(__file__).resolve().parents[1]


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")      # written by dd_fix_more.py
    halves = {"tune": dict(t_to=CUT), "hold": dict(t_from=CUT)}

    def mix(c, kmn, ksl, h):
        r = c.pct_change().fillna(0.0)
        add = kmn * mn_d.reindex(r.index).fillna(0.0)
        if ksl:
            add = add + ksl * sleeve["hold" if h == "hold" else "full"].reindex(r.index).fillna(0.0)
        return (1 + r + add).cumprod()

    def st(c):
        return summarize(c)[0], float((1 - c / c.cummax()).max() * 100)

    print("1. EXCESS over the trend-only uniform-bet-size frontier, %/mo, mean +- se (wins/10), per bar phase")
    print(f"   {'mix (trend at g 1.0)':<22}" + "".join(f"{'ph' + str(p) + ' TUNE':>19}{'HOLD':>17}" for p in range(4)))
    menu_curves = None
    table = {name: "" for name, _, _ in MIXES[1:]}
    passes = {name: True for name, _, _ in MIXES[1:]}
    for p in range(4):
        rows = decompose(rows_for_phase(p, tight=True, time_stop=(100, 2.0), max_units=7))
        cur = {h: {sd: {g: sim(rows, bn, bv, sd, g=g, **kw) for g in GS} for sd in SEEDS} for h, kw in halves.items()}
        for name, kmn, ksl in MIXES[1:]:
            for h in halves:
                ex = []
                for sd in SEEDS:
                    fr = [st(cur[h][sd][g]) for g in GS]
                    dds = np.array([x[1] for x in fr]); rets = np.array([x[0] for x in fr]); o = np.argsort(dds)
                    r, d = st(mix(cur[h][sd][1.0], kmn, ksl, h))
                    ex.append(r - np.interp(d, dds[o], rets[o], left=np.nan, right=np.nan))
                v = np.array(ex); v = v[np.isfinite(v)]
                if len(v) >= 5:
                    table[name] += f"{v.mean():>+9.2f}+-{v.std(ddof=1)/np.sqrt(len(v)):.2f}({(v > 0).sum():>2})"
                    passes[name] &= v.mean() > 0
                else:
                    table[name] += f"{'outside':>17}"; passes[name] = False
        if p == 0:
            menu_curves = {sd: {g: sim(rows, bn, bv, sd, g=g) for g in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)} for sd in SEEDS}
        print(f"   phase {p} done", flush=True)
    for name, _, _ in MIXES[1:]:
        print(f"   {name:<22}{table[name]}   {'PASS: all 4 phases, both halves' if passes[name] else 'fails somewhere'}")

    print("\n2. THE MENU: what $221 does in 12 months, full history, deployed grid, 10 orderings")
    print("   (upside haircut on the whole book; bad year = 1 in 4; downside RAW)")
    print(f"   {'trend size':<11}{'plus':<22}{'typical':>9}{'bad yr':>8}{'good yr':>9}{'yrs<$221':>9}{'worst yr':>9}"
          f"{'DD':>6}{'worst mo':>9}{'mo up':>7}")
    for g in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
        for name, kmn, ksl in MIXES:
            W, DD, WM, UP = [], [], [], []
            for sd in SEEDS:
                c = mix(menu_curves[sd][g], kmn, ksl, "full")
                me = month_ends(c)
                W.append(windows(me, 12)); DD.append(float((1 - c / c.cummax()).max() * 100))
                mo = me.pct_change().dropna(); WM.append(mo.min() * 100); UP.append((mo > 0).mean() * 100)
            w = np.concatenate(W); hc = np.array([haircut(x, 12) for x in w])
            print(f"   {g:<11.1f}{name:<22}${CAP*np.median(hc):>8,.0f}${CAP*np.percentile(hc, 25):>7,.0f}"
                  f"${CAP*np.percentile(hc, 75):>8,.0f}{(w < 1).mean()*100:>8.0f}%${CAP*w.min():>8,.0f}"
                  f"{np.mean(DD):>5.0f}%{np.mean(WM):>+8.1f}%{np.mean(UP):>6.0f}%")
        print()


if __name__ == "__main__":
    main()
