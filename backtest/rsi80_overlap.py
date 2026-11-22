"""DOES THE RSI-80 MOMENTUM RULE ADD ANYTHING TO THE MACHINE, OR IS IT THE TREND BOOK AGAIN? (2026-11-08)

THE USER (2026-11-08): "yes, check overlap" - after rsi80_more.py found the 4h RSI-above-80 momentum long positive on unseen data (+0.14R a trade, t 1.80, a
narrow no-pass) with its profit carried by ~20 burst days, the trend book's own shape.

THE BOOKS (daily return series on the machine's calendar, all_books.machine_books: 10 orderings; the trend book's gains shrunk for hindsight as everywhere):
  trend     the deployed triple trend book (final_machine.trend_capped(6.25))
  MACHINE   the 7 deployed books summed (trend, mn_blend, carry, sleeve, bids, daily, capit2) - all_books' DEPLOYED line
  RSI-100   the RSI rule on every top-100 perp 2020-26 (rsi80_more's OLD + NEW-PERP trades), every signal, 1% of the account at risk a trade, booked on the
            exit day (risk x R) - includes the top-40 it was found on
  RSI-NEW   the same on the coins ranked 41-100 only (never used to find it) - the honest addition
OVERLAP MEASURES: (1) daily and monthly correlation with trend and with the MACHINE (mean over orderings); (2) the RSI book's 20 best days: what trend made
  on them and how many sit in trend's best 10% of days; (3) the RSI book's mean in the machine's worst 20% of months; (4) the share of RSI trades in the
  12 coins the trend book trades (blend.BOOK).
ADDED VALUE (the repo's standard): MACHINE + RSI-NEW (and RSI-100) at 1% risk against the MACHINE x k (k = 0.30 .. 2.50) - the "just bet bigger / smaller" line.
  The combination's typical 12 months on $300 is compared with the line's typical year AT THE SAME BIGGEST FALL (interpolated), on each half (split
  2024-08-29, machine.CUT). PASS = above the line on both halves.

REGISTERED BEFORE THE FIRST RUN (2026-11-08)
  O1  RSI-NEW's daily correlation with trend is +0.25 .. +0.60 (the same alt bursts, different coins and timing).                    55%
  O2  At least 10 of RSI-NEW's 20 best days are in trend's best 10% of days.                                                       55%
  O3  RSI-NEW loses on average in the machine's worst 20% of months (it is long-only momentum: no help when the machine hurts).    70%
  O4  Adding RSI-NEW does NOT beat the bet-bigger line on both halves.                                                            65%
  O5  Under 20% of RSI-100's trades are in the trend book's 12 coins.                                                             75%

RESULT (2026-11-08, logs/rsi80_overlap.txt) - NOT the trend book again, but NOT a proven addition either.
  (1) Correlation: RSI-NEW daily -0.04 with trend, -0.02 with the machine; monthly +0.07 / +0.13 (RSI-100 the same). (2) On RSI-NEW's 20 best days trend made
  -0.36% a day against its average +0.59%, and 0 of 20 were in trend's best 10% of days. (3) In the machine's worst 20% of months RSI-NEW made +2.02% a month
  (all months +2.15%): it held up when the machine hurt. (4) 10.7% of RSI-100's trades are in the trend book's 12 coins.
  (5) Against the bet-bigger line ($300, typical year, same biggest fall): machine + RSI-NEW tune $4,108 vs the line's $4,899 (-$791), holdout $8,430 vs $5,028
  (+$3,401) -> does NOT pass both halves. Machine + RSI-100 passes both (+$618 / +$6,229), but RSI-100 contains the top-40 the rule was chosen on, over the
  same split dates - in-sample, not evidence. Machine alone: $3,774 / $5,494.
  CAVEAT: every series here is booked at the exit; the trend book exits weeks after a move, the RSI rule within 4 days, so daily / monthly correlation of booked
  P&L understates exposure to the same market episodes. The best-day and worst-month readings do not depend on that and say the same: different days.
  PREDICTIONS: O1 WRONG (-0.04, not +0.25..+0.60). O2 WRONG (0 of 20, not >= 10). O3 WRONG (it made money in the machine's worst months). O4 right (RSI-NEW does not
    pass both halves). O5 right (10.7%).
  READING: a genuinely different stream - small alt momentum bursts on coins the trend book never holds - that pays on the 2024-26 half and not on 2020-24 as an
    add-on. Standalone (rsi80_more.py): +19%/yr at 1% risk on ~$100+ on unseen coins, a narrow no-pass. Only a forward record can say more.

    python backtest/rsi80_overlap.py         tests: python tests/test_rsi80_overlap.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "rsi80_overlap.txt"
TRADES = ROOT / "logs" / "rsi80_more_trades.pkl"
RISK = 0.01
KS = np.round(np.arange(0.30, 2.51, 0.05), 2)
BOOKS = ["trend", "mn_blend", "carry", "sleeve", "bids", "daily", "capit2"]


def daily_book(T: pd.DataFrame, idx: pd.DatetimeIndex, risk: float = RISK) -> pd.Series:
    """Every trade booked on its exit day as risk x R (a fraction of the account), on the calendar idx; days with no exit are 0."""
    d = pd.to_datetime(T.t_out).dt.floor("D")
    s = (risk * T.net.astype(float)).groupby(d.to_numpy()).sum()
    return s.reindex(idx).fillna(0.0)


def best_day_overlap(rsi: pd.Series, trend: pd.Series, n: int = 20, top: float = 0.10) -> tuple:
    """(trend's mean return on RSI's n best days, how many of those days are in trend's best `top` share of days)."""
    best = rsi.nlargest(n).index
    thr = trend.quantile(1 - top)
    return float(trend.loc[best].mean()), int((trend.loc[best] >= thr).sum())


def line_gap(base: list, combo: list, half, ks=KS) -> dict:
    """The combination's typical $300 year minus the bet-bigger line's (base x k) at the same biggest fall, on one half. `half` = (t0, t1) or None."""
    from backtest.machine import summary

    def cut(xs):
        if half is None:
            return xs
        a, b = half
        return [x[(x.index >= a) & (x.index < b)] for x in xs]
    line = [(k, summary(cut([k * x for x in base]))) for k in ks]
    dd = np.array([s["dd"] for _, s in line])
    typ = np.array([s["typ"] for _, s in line])
    c = summary(cut(combo))
    order = np.argsort(dd)
    at = float(np.interp(c["dd"], dd[order], typ[order]))
    inside = bool(dd.min() <= c["dd"] <= dd.max())
    return dict(combo=c, line_typ=at, gap=c["typ"] - at, inside=inside)


def main():
    from backtest import all_books as ab
    from backtest import blend
    from backtest.machine import CUT
    X = pd.read_pickle(TRADES)
    M = ab.machine_books()
    idx = M[0].index
    rsi100 = daily_book(X[X.src.isin(["OLD", "NEW-PERP"])], idx)
    rsinew = daily_book(X[X.src == "NEW-PERP"], idx)
    L = [f"backtest/rsi80_overlap.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; machine calendar {idx[0]:%Y-%m-%d} .. {idx[-1]:%Y-%m-%d}, 10 orderings; "
         f"RSI books at {RISK * 100:.0f}% risk a trade, booked on the exit day"]
    L.append("\n1. CORRELATION (mean over orderings)")
    for nm, r in (("RSI-NEW", rsinew), ("RSI-100", rsi100)):
        cd_t = np.mean([r.corr(x.trend) for x in M])
        cd_m = np.mean([r.corr(x[BOOKS].sum(axis=1)) for x in M])
        rm = (1 + r).resample("ME").prod() - 1
        cm_t = np.mean([rm.corr((1 + x.trend).resample("ME").prod() - 1) for x in M])
        cm_m = np.mean([rm.corr((1 + x[BOOKS].sum(axis=1)).resample("ME").prod() - 1) for x in M])
        L.append(f"   {nm}: daily with trend {cd_t:+.2f}, with the machine {cd_m:+.2f} | monthly with trend {cm_t:+.2f}, with the machine {cm_m:+.2f}")
    L.append("\n2. THE RSI BOOK'S 20 BEST DAYS vs the trend book (mean over orderings)")
    for nm, r in (("RSI-NEW", rsinew), ("RSI-100", rsi100)):
        o = [best_day_overlap(r, x.trend) for x in M]
        L.append(f"   {nm}: those days make {np.mean([a for a, _ in o]) * 100:+.2f}% for trend (its average day {np.mean([x.trend.mean() for x in M]) * 100:+.2f}%); "
                 f"{np.mean([b for _, b in o]):.1f} of 20 are in trend's best 10% of days")
    L.append("\n3. IN THE MACHINE'S WORST 20% OF MONTHS (mean over orderings)")
    for nm, r in (("RSI-NEW", rsinew), ("RSI-100", rsi100)):
        rm = (1 + r).resample("ME").prod() - 1
        w = []
        for x in M:
            tot = (1 + x[BOOKS].sum(axis=1)).resample("ME").prod() - 1
            w.append(rm[tot <= tot.quantile(0.2)].mean())
        L.append(f"   {nm}: {np.mean(w) * 100:+.2f}% a month (all months {rm.mean() * 100:+.2f}%)")
    book = set(blend.BOOK)
    p100 = X[X.src.isin(["OLD", "NEW-PERP"])]
    L.append(f"\n4. COINS: {p100.coin.isin(book).mean() * 100:.1f}% of RSI-100's trades are in the trend book's 12 coins ({sorted(book)})")
    L.append("\n5. ADDED VALUE: the machine + the RSI book vs the machine x k at the same biggest fall ($300, typical 12 months)")
    res = {}
    base = [x[BOOKS].sum(axis=1) for x in M]
    for nm, r in (("RSI-NEW", rsinew), ("RSI-100", rsi100)):
        combo = [b + r for b in base]
        for hn, half in (("tune", (idx[0], CUT)), ("holdout", (CUT, idx[-1] + pd.Timedelta(days=1)))):
            g = line_gap(base, combo, half)
            res[(nm, hn)] = g
            c = g["combo"]
            L.append(f"   machine + {nm:<8} {hn:<8} typical ${c['typ']:>8,.0f} (line at the same fall ${g['line_typ']:>8,.0f}: {g['gap']:+,.0f})  fall {c['dd']:.0f}%  "
                     f"worst month {c['wm']:+.1f}%  months up {c['up']:.0f}%{'' if g['inside'] else '  (fall outside the line: extrapolated)'}")
    for hn, half in (("tune", (idx[0], CUT)), ("holdout", (CUT, idx[-1] + pd.Timedelta(days=1)))):
        from backtest.machine import summary
        s = summary([x[(x.index >= half[0]) & (x.index < half[1])] for x in base])
        L.append(f"   machine alone           {hn:<8} typical ${s['typ']:>8,.0f}  fall {s['dd']:.0f}%  worst month {s['wm']:+.1f}%  months up {s['up']:.0f}%")
    for nm in ("RSI-NEW", "RSI-100"):
        ok = all(res[(nm, h)]["gap"] > 0 for h in ("tune", "holdout"))
        L.append(f"   {nm}: {'PASSES' if ok else 'does not pass'} the bet-bigger line on both halves")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
