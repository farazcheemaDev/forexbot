"""DOES THE EQUITY ANCHOR STILL ADD ON TOP OF THE MIX?

dd_fix_check.py (logs/dd_fix_check.txt): sizing the trend book from min(equity, its k-day average)
beats the uniform-bet-size frontier on both halves on all four bar phases for k = 14 / 21 / 30
(20 orderings, 19-20 wins in most cells); k = 45 / 60 fail one tune cell. final_mix.py
(logs/final_mix.txt): trend at 70% + breadth sleeve + 0.5 x market-neutral is the recommended mix.
Question: with the other two books present, does the anchor still add? The anchor acts only on
the trend book's sizing, so it should.

For every bar phase and half, 10 orderings: the excess over the trend-only frontier of the mix
at trend g 0.7 WITHOUT and WITH the 21-day anchor, and their paired difference. Then the $221
menu on the deployed grid for the anchored mix.

REGISTERED PREDICTION (2026-09-24, before running): the anchor adds +0.3 to +0.6 %/mo of excess
on both halves on all four phases, and trims the mix's biggest fall by 2-4 points.

    python -m backtest.final_anchor
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
from backtest.dd_fixes import CAP, CUT, SEEDS, anchor, decompose, sim  # noqa: E402
from backtest.expectations import haircut, month_ends, windows  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

GS = (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
ROOT = Path(__file__).resolve().parents[1]
K = 21


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")
    halves = {"tune": dict(t_to=CUT), "hold": dict(t_from=CUT)}

    def mix(c, h):
        r = c.pct_change().fillna(0.0)
        add = 0.5 * mn_d.reindex(r.index).fillna(0.0) + sleeve["hold" if h == "hold" else "full"].reindex(r.index).fillna(0.0)
        return (1 + r + add).cumprod()

    def st(c):
        return summarize(c)[0], float((1 - c / c.cummax()).max() * 100)

    print(f"mix = trend at g 0.7 + breadth sleeve (real $221) + 0.5 x market-neutral; anchor = size the trend book "
          f"from min(equity, its {K}-day average)")
    print("excess over the trend-only frontier, %/mo, mean +- se over 10 orderings; diff = anchored minus plain, paired\n")
    print(f"  {'phase':<7}{'half':<6}{'plain mix':>16}{'anchored mix':>18}{'diff':>18}{'DD plain':>10}{'DD anch':>9}")
    for p in range(4):
        rows = decompose(rows_for_phase(p, tight=True, time_stop=(100, 2.0), max_units=7))
        for h, kw in halves.items():
            e0, e1, d0, d1 = [], [], [], []
            for sd in SEEDS:
                fr = [st(sim(rows, bn, bv, sd, g=g, **kw)) for g in GS]
                dds = np.array([x[1] for x in fr]); rets = np.array([x[0] for x in fr]); o = np.argsort(dds)
                a = st(mix(sim(rows, bn, bv, sd, g=0.7, **kw), h))
                b = st(mix(sim(rows, bn, bv, sd, g=0.7, size_fn=anchor(K), **kw), h))
                e0.append(a[0] - np.interp(a[1], dds[o], rets[o], left=np.nan, right=np.nan))
                e1.append(b[0] - np.interp(b[1], dds[o], rets[o], left=np.nan, right=np.nan))
                d0.append(a[1]); d1.append(b[1])
            e0, e1 = np.array(e0), np.array(e1)
            df = e1 - e0
            ok = np.isfinite(df)
            f = lambda x: f"{np.nanmean(x):+.2f}+-{np.nanstd(x, ddof=1)/np.sqrt(np.isfinite(x).sum()):.2f}"  # noqa: E731
            print(f"  {p:<7}{h:<6}{f(e0):>16}{f(e1):>18}{f(df):>13} ({(df[ok] > 0).sum():>2}){np.mean(d0):>9.0f}%{np.mean(d1):>8.0f}%")
        print(f"  phase {p} done", flush=True)

    print("\nWHAT $221 DOES IN 12 MONTHS, full history, deployed grid (upside haircut on the whole book; downside RAW)")
    print(f"  {'book':<44}{'typical':>9}{'bad yr':>8}{'good yr':>9}{'yrs<$221':>9}{'worst yr':>9}{'DD':>6}{'worst mo':>9}{'mo up':>7}")
    rows = decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    for name, g, anc, with_mix in (("today: triple alone", 1.0, False, False),
                                   ("triple alone + anchor", 1.0, True, False),
                                   ("trend 70% + sleeve + 0.5 MN", 0.7, False, True),
                                   ("trend 70% + anchor + sleeve + 0.5 MN", 0.7, True, True),
                                   ("trend 80% + anchor + sleeve + 0.5 MN", 0.8, True, True),
                                   ("trend 100% + anchor + sleeve + 0.5 MN", 1.0, True, True)):
        W, DD, WM, UP = [], [], [], []
        for sd in SEEDS:
            c = sim(rows, bn, bv, sd, g=g, size_fn=anchor(K) if anc else None)
            if with_mix:
                c = mix(c, "full")
            me = month_ends(c)
            W.append(windows(me, 12)); DD.append(float((1 - c / c.cummax()).max() * 100))
            mo = me.pct_change().dropna(); WM.append(mo.min() * 100); UP.append((mo > 0).mean() * 100)
        w = np.concatenate(W); hc = np.array([haircut(x, 12) for x in w])
        print(f"  {name:<44}${CAP*np.median(hc):>8,.0f}${CAP*np.percentile(hc, 25):>7,.0f}${CAP*np.percentile(hc, 75):>8,.0f}"
              f"{(w < 1).mean()*100:>8.0f}%${CAP*w.min():>8,.0f}{np.mean(DD):>5.0f}%{np.mean(WM):>+8.1f}%{np.mean(UP):>6.0f}%")


if __name__ == "__main__":
    main()
