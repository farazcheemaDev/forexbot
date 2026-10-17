"""CONNECTING THE DOTS: every book we have, how they move together, and the one machine they make (2026-10-17)

The user: "see if there is any correlation between them all ... one end product combining everything ... tell me what
we are left with". Every book that passed its own tests, as a daily return series on the same calendar:
    trend      the triple trend book, guard 6.25x, 21-day anchor, gains shrunk for hindsight (final_machine.trend_capped)
    mn_blend   market-neutral, half 30-day momentum / half RSI(14), +50% short exit
    carry      funding carry, x0.5 as deployed
    sleeve     the bear breadth sleeve
    bids       the crash bids, capped at 10 fills an hour
    daily      daily Bollinger(30, 1.5), 20-day-mean exit, x0.5 as deployed
    capit2     capitulation (coin -10% + limit -2%), 8 slots of the whole account at 2x (deployed 2026-10-16)
    news       short coin / long BTC after Binance adds-products / monitoring tags (news/combo.py --narrow: 72h,
               stop 25%), 1/10 of equity a trade - a CANDIDATE (types chosen after looking)
    ndx_dip    NASDAQ's sharp down days bought (ndx_capit.py: RSI(2) < 10 at the close, out above the 5-day average,
               1x, Exness costs) - a CANDIDATE from another market, tradable on Bitget's QQQ perp
The 7 machine books per ordering (10), news and ndx_dip are the same in every ordering. Reported:
    1. each book alone: CAGR, biggest fall, months up
    2. the monthly correlation matrix (averaged over orderings), and the correlation in the machine's WORST 20% of months
       (the months a diversifier has to help in)
    3. the machines: DEPLOYED (the 7 books) / + news (w 1) / + news + ndx_dip (x0.5) - $300 typical / bad / worst 12
       months, worst month, fall, months up; tune (before 2024-08-29) and holdout
REGISTERED BEFORE THE RUN (2026-10-17)
    A1 trend correlates with daily (> +0.3); mn_blend, carry, sleeve, news and ndx_dip each with trend within -0.2..+0.2.
    A2 in the machine's worst months, news and ndx_dip are positive on average (they help when it hurts).
    A3 + news + ndx_dip raises the share of months up by >= 3 points on both halves at no deeper worst month.

RESULT (2026-10-17, logs/all_books.txt) - every book is a diversifier; the trend book is the one that hurts.
    Monthly correlations are all low: highest trend~bids +0.38, mn~daily +0.37, mn~bids +0.36; trend~daily -0.01 (A1
    WRONG - the daily book is not the trend book's twin). In the machine's worst 20% of months: trend -9.2%, mn -2.8%,
    daily -2.2%, carry -1.0%, sleeve -0.6%; bids +0.6%, capit2 +0.4%, NEWS +1.9%, NDX_DIP +1.0% (A2 right - they pay
    when it hurts). $300 typical year tune / holdout: deployed $3,774 / $5,494 -> + news $4,170 / $8,630 -> + news +
    ndx x1 $4,435 / $9,838; worst month -21.1 -> -19.2% (tune), -30.0 -> -31.3% (holdout); fall 46 -> 42% / 51 -> 49%;
    months up 65 -> 67% / 63 -> 68% (A3 wrong by a point: +2 on the tune half). BACKTEST; news and ndx_dip are
    candidates (news types chosen after looking); the trend book's gains are shrunk for hindsight.

    python -m backtest.all_books
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "all_books.txt"
BOOKS = ["trend", "mn_blend", "carry", "sleeve", "bids", "daily", "capit2"]


def machine_books():
    from backtest import capit_combos as cc
    from backtest import daily_combos as dc
    from backtest import final_machine as fm
    from backtest import machine_combos as mc
    from backtest import mn_combos as m
    from backtest.moderate_retests import scored_run
    P = mc.parts()
    T625 = fm.trend_capped(6.25)
    D = m.data()
    C = pd.DataFrame(D["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    T20 = {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES}
    cT2 = {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER)) for off in cc.PHASES}
    out = []
    for sd in mc.SEEDS:
        b = P[sd]
        idx = b.index
        o = sd % 7
        r = lambda s: s.reindex(idx).fillna(0.0)  # noqa: E731
        off, coff = dc.PHASES[sd % 3], cc.PHASES[sd % 4]
        out.append(pd.DataFrame({
            "trend": T625[sd].reindex(idx).fillna(0.0),
            "mn_blend": 0.5 * r(scored_run(mom, start=o, stop="short_only", short_stop=0.5))
            + 0.5 * r(scored_run(rsi, start=o, stop="short_only", short_stop=0.5)),
            "carry": 0.5 * r(m.mn_run(look=1, score="funding7", fwin=7, frac=0.2, start=o, stop="short_only", short_stop=0.5)),
            "sleeve": b.sleeve, "bids": b.bids,
            "daily": 0.5 * r(dc.curve(T20[off], dc.allocate(T20[off], sd), off).pct_change()),
            "capit2": r(cc.curve(cT2[coff], dc.allocate(cT2[coff].assign(units=None), sd, 2.0)).pct_change())}))
    return out


def news_book():
    import news.combo as NC
    NC.TYPES, NC.HOLD, NC.STOP = ("adds_products", "monitoring_tag"), 72, 0.25
    return NC.daily(NC.news_trades(0.0012))


def ndx_dip():
    from backtest import ndx_capit as nc
    d, P, L, S = nc.load()
    tr = nc.run(P, L["rsi2_10"], 1, "close", "X2", False)
    dates = pd.to_datetime(P["dates"])
    s = pd.Series(0.0, index=dates)
    for i, k, g, net, _ in tr:
        s.iloc[k] += net                                   # 1x, one position at a time, booked at the exit close
    return s.resample("D").sum()


def stats1(r):
    c = (1 + r).cumprod()
    yrs = max((c.index[-1] - c.index[0]).days / 365.25, 0.25)
    me = c.resample("ME").last()
    mo = (me / me.shift(1)).dropna() - 1
    return (c.iloc[-1] ** (1 / yrs) - 1 if c.iloc[-1] > 0 else -1), float((1 - c / c.cummax()).max()), float((mo > 0).mean())


def main():
    from backtest.machine import CUT, summary
    M = machine_books()
    idx = M[0].index
    news = news_book().reindex(idx).fillna(0.0)
    ndx = ndx_dip().reindex(idx).fillna(0.0)
    lines = [f"backtest/all_books.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {idx[0]:%Y-%m-%d} .. {idx[-1]:%Y-%m-%d}, "
             f"10 orderings (machine books); trend gains shrunk, everything else raw", "", "1. EACH BOOK ALONE (its own weight in the machine)"]
    names = BOOKS + ["news", "ndx_dip"]
    for nm in names:
        if nm in BOOKS:
            v = [stats1(x[nm]) for x in M]
            cg, dd, up = (float(np.median([a[k] for a in v])) for k in range(3))
        else:
            s = news if nm == "news" else ndx
            s = s[s.index >= (s != 0).idxmax()]
            cg, dd, up = stats1(s)
        lines.append(f"   {nm:<9} CAGR {cg * 100:+6.0f}%  fall {dd * 100:4.0f}%  months up {up * 100:3.0f}%")
    mo = []
    for x in M:
        y = x.copy()
        y["news"], y["ndx_dip"] = news, ndx
        mo.append((1 + y).resample("ME").prod() - 1)
    live = mo[0].index >= news[news != 0].index[0].to_period("M").to_timestamp("M")
    Cm = sum(z[live].corr() for z in mo) / len(mo)
    lines += ["", "2. MONTHLY CORRELATION (months the news book exists; averaged over orderings)",
              "   " + " " * 9 + "".join(f"{n[:7]:>8}" for n in names)]
    for a in names:
        lines.append(f"   {a:<9}" + "".join(f"{Cm.loc[a, b]:>+8.2f}" for b in names))
    worst = []
    for z in mo:
        tot = z[BOOKS].sum(axis=1)
        w = z[tot <= tot.quantile(0.2)]
        worst.append(w[names].mean())
    W = sum(worst) / len(worst)
    lines += ["", "   average month of each book in the MACHINE'S WORST 20% OF MONTHS:",
              "   " + "  ".join(f"{n} {W[n] * 100:+.1f}%" for n in names)]
    lines += ["", "3. THE MACHINES ($300, 12 months)",
              f"   {'machine':<34}{'half':>8}{'typical':>9}{'bad':>8}{'worst':>8}{'worst mo':>9}{'fall':>6}{'months up':>10}"]
    R = {}
    for lab, f in (("DEPLOYED (7 books)", lambda x: x[BOOKS].sum(axis=1)),
                   ("+ news (w 1)", lambda x: x[BOOKS].sum(axis=1) + news),
                   ("+ news + ndx_dip x0.5", lambda x: x[BOOKS].sum(axis=1) + news + 0.5 * ndx),
                   ("+ news + ndx_dip x1", lambda x: x[BOOKS].sum(axis=1) + news + ndx)):
        xs = [f(x) for x in M]
        for half, s in (("tune", summary([x[x.index < CUT] for x in xs])), ("holdout", summary(xs, CUT))):
            R[(lab, half)] = s
            lines.append(f"   {lab:<34}{half:>8} ${s['typ']:>7,.0f} ${s['bad']:>6,.0f} ${s['worst']:>6,.0f}{s['wm']:>+8.1f}%{s['dd']:>5.0f}%{s['up']:>9.0f}%")
    a1 = Cm.loc["trend", "daily"] > 0.3 and all(-0.2 <= Cm.loc["trend", n] <= 0.2 for n in ("mn_blend", "carry", "sleeve", "news", "ndx_dip"))
    a2 = W["news"] > 0 and W["ndx_dip"] > 0
    a3 = all(R[("+ news + ndx_dip x0.5", h)]["up"] >= R[("DEPLOYED (7 books)", h)]["up"] + 3
             and R[("+ news + ndx_dip x0.5", h)]["wm"] >= R[("DEPLOYED (7 books)", h)]["wm"] for h in ("tune", "holdout"))
    lines += ["", "REGISTERED PREDICTIONS",
              f"  A1 trend~daily > +0.3 ({Cm.loc['trend', 'daily']:+.2f}); mn / carry / sleeve / news / ndx within +-0.2 of trend "
              f"({', '.join(f'{Cm.loc['trend', n]:+.2f}' for n in ('mn_blend', 'carry', 'sleeve', 'news', 'ndx_dip'))}) -> {'RIGHT' if a1 else 'WRONG'}",
              f"  A2 news and ndx_dip positive in the machine's worst months ({W['news'] * 100:+.1f}% / {W['ndx_dip'] * 100:+.1f}%) -> "
              f"{'RIGHT' if a2 else 'WRONG'}",
              f"  A3 + news + ndx x0.5: months up +3 points on both halves, worst month no deeper -> {'RIGHT' if a3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
