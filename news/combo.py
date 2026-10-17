"""CONNECTING THE DOTS: the news book inside the final machine (2026-10-17, docs/26 step 3)

news/news_book.py: shorting a coin against BTC after bad-for-the-coin news (TUNE_CHOSEN types: Binance adds a token to
products, monitoring tags, exchange spot listings, new pairs) earns +240..+544bp a trade over the same trade at ordinary
times, on both halves. Here it meets the machine:
    NEWS BOOK   TUNE_CHOSEN events, short coin / long BTC at the next hour's open, held 72h, stop +50% (with 3% stop
                slippage) - the setting with the best TUNE-half edge (+437bp) among those with a stop; 1/10 of equity a
                trade, at most 10 open; booked at exit -> a daily return series. "w" scales it (w 2 = 1/5 a trade).
    COSTS       12bp a leg (Bitget taker) and, as a stress, 50bp a leg - new listings and tagged coins trade thin.
    MACHINE     the deployed final machine (final_confidence.parts: trend guard 6.25x, MN blend, carry, sleeve, bids,
                daily, capit2 1.0 x 2x), 10 orderings; "k" scales it.
    MIX         k x machine + w x news, k in 0.5 / 0.65 / 0.8 / 1.0, w in 0..4. $300, typical / worst 12 months, worst
                month and biggest fall (machine.summary), TUNE = before 2024-08-29 (machine.CUT), HOLDOUT = after.
    FRONTIER    for a worst-fall limit F = 30 / 50 / 70%: the (k, w) with the best TUNE typical year whose TUNE fall
                is within F; its HOLDOUT numbers are the honest ones.

REGISTERED BEFORE THE RUN (2026-10-17)
    C1 the news book's monthly returns correlate with the machine's between -0.2 and +0.2.
    C2 news at w 2 raises the machine's typical year on BOTH tune and holdout by > 5% and deepens the worst month by
       under 2 points.
    C3 at 50bp a leg the news book alone still makes money (CAGR > 0).

RESULT (2026-10-17, logs/news_combo.txt, logs/news_combo_narrow.txt; machine $300 typical 12 months)
    AS REGISTERED (all four TUNE_CHOSEN types, 72h, stop 50%): the news book alone +7%/yr, fall 58%; -9%/yr at 50bp a
    leg (C3 wrong). Correlation with the machine +0.04 (C1 right). Added at w 2 it deepens the worst month -21 -> -34%
    (C2 wrong). The frontier picks NO news at every fall limit. Found here: news_book.py's filter bug (see its RESULT).
    --narrow (adds_products + monitoring_tag, 72h, stop 25% - chosen after looking): +19%/yr, fall 27%; +14% at 50bp;
    correlation -0.05. Machine x1 + news w 1: typical $3,774 -> $4,170 tune, $5,494 -> $8,630 holdout, worst month
    -21.1 -> -20.3 / -30.0 -> -31.6%, fall 46 -> 44% / 51 -> 51%. w 2: holdout $10,479 but worst month -33.5% (C2 wrong
    by 1.5 points). w 3-4: holdout falls 57-71%. The tune-chosen frontier (w 3-4) fails on the holdout: if added, w 1.

    python -m news.combo
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import news.news_book as NB  # noqa: E402

LOG = ROOT / "logs" / "news_combo.txt"
KS = (0.5, 0.65, 0.8, 1.0)
WS = (0, 1, 2, 3, 4)


TYPES = NB.TUNE_CHOSEN
HOLD, STOP = 72, 0.5


def news_trades(fee, hold=None, stop=None):
    hold, stop = hold or HOLD, stop or STOP
    NB.FEE = fee
    E = pd.read_parquet(NB.EV)
    E = E[E.etype.isin(TYPES) & (E.coins != "")]
    out = []
    for r in E.itertuples():
        entry = (pd.Timestamp(r.t).floor("h") + pd.Timedelta(hours=1)).value
        for coin in r.coins.split(",")[:3]:
            if not coin or coin == "BTCUSDT":
                continue
            x = NB.trade(coin, entry, hold, stop)
            if x is not None:
                out.append((entry, x[2], x[0]))
    NB.FEE = 0.0012
    return out


def daily(trades, slots=10, frac=0.10):
    """Equity booked at each exit (NB.book's rule) -> daily returns on a calendar grid."""
    trades = sorted(trades, key=lambda x: x[0])
    eq, open_, pts = 1.0, [], []
    for t_in, t_out, net in trades:
        for p in sorted([p for p in open_ if p[0] <= t_in]):
            eq += p[1]
            pts.append((p[0], eq))
        open_ = [p for p in open_ if p[0] > t_in]
        if len(open_) >= slots or eq <= 0:
            continue
        open_.append((t_out, eq * frac * net))
    for p in sorted(open_):
        eq += p[1]
        pts.append((p[0], eq))
    s = pd.Series([e for _, e in pts], index=pd.to_datetime([t for t, _ in pts])).groupby(level=0).last()
    s = s.resample("D").last().ffill()
    return s.pct_change().fillna(0.0)


def stats1(r):
    c = (1 + r).cumprod()
    yrs = (c.index[-1] - c.index[0]).days / 365.25
    return (c.iloc[-1] ** (1 / yrs) - 1 if c.iloc[-1] > 0 else -1.0), float((1 - c / c.cummax()).max())


def main():
    from backtest.final_confidence import parts
    from backtest.machine import CUT, summary
    lines = [f"news/combo.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; news book = {', '.join(TYPES)}, {HOLD}h, stop {STOP:.0%}; machine = "
             f"the deployed final machine, 10 orderings; $300; tune < {CUT:%Y-%m-%d} <= holdout", ""]
    N = {}
    for fee in (0.0012, 0.0050):
        tr = news_trades(fee)
        N[fee] = daily(tr)
        cg, dd = stats1(N[fee])
        lines.append(f"  news book alone at {fee * 1e4:.0f}bp a leg: {len(tr)} trades, CAGR {cg * 100:+.0f}%, fall {dd * 100:.0f}%")
    news = N[0.0012]
    M = [s + mi for s, mi in parts()]
    idx = M[0].index
    nz = news.reindex(idx).fillna(0.0)
    mo_m = (1 + M[0]).resample("ME").prod() - 1
    mo_n = (1 + nz).resample("ME").prod() - 1
    live = mo_n.index >= news.index[0]
    corr = float(np.corrcoef(mo_m[live], mo_n[live])[0, 1])
    lines += [f"  monthly correlation news vs machine (ordering 0, months the news book exists): {corr:+.2f}", "",
              f"  {'k':>5}{'w':>3} | {'TUNE typ':>9}{'worst mo':>9}{'fall':>6} | {'HOLD typ':>9}{'worst mo':>9}{'fall':>6} | {'6y typ':>8}"]
    R = {}
    for k in KS:
        for w in WS:
            xs = [k * m + w * nz for m in M]
            tu = summary([x[x.index < CUT] for x in xs])
            ho = summary(xs, CUT)
            al = summary(xs)
            R[(k, w)] = (tu, ho, al)
            lines.append(f"  {k:>5.2f}{w:>3} | ${tu['typ']:>7,.0f}{tu['wm']:>+8.1f}%{tu['dd']:>5.0f}% | ${ho['typ']:>7,.0f}{ho['wm']:>+8.1f}%"
                         f"{ho['dd']:>5.0f}% | ${al['typ']:>6,.0f}")
    lines += ["", "  FRONTIER - chosen on the TUNE half, judged on the HOLDOUT:"]
    for F in (30, 50, 70):
        ok = [(v[0]["typ"], kw) for kw, v in R.items() if v[0]["dd"] <= F]
        if not ok:
            lines.append(f"    fall <= {F}%: nothing qualifies on the tune half")
            continue
        _, (k, w) = max(ok)
        tu, ho, al = R[(k, w)]
        lines.append(f"    fall <= {F}%: machine x{k}, news x{w} -> tune ${tu['typ']:,.0f} (fall {tu['dd']:.0f}%, worst month "
                     f"{tu['wm']:+.0f}%) | HOLDOUT ${ho['typ']:,.0f} (fall {ho['dd']:.0f}%, worst month {ho['wm']:+.0f}%)")
    b, n2 = R[(1.0, 0)], R[(1.0, 2)]
    c2 = (n2[0]["typ"] > 1.05 * b[0]["typ"] and n2[1]["typ"] > 1.05 * b[1]["typ"]
          and n2[0]["wm"] > b[0]["wm"] - 2 and n2[1]["wm"] > b[1]["wm"] - 2)
    lines += ["", "REGISTERED PREDICTIONS",
              f"  C1 correlation within -0.2..+0.2: {corr:+.2f} -> {'RIGHT' if abs(corr) <= 0.2 else 'WRONG'}",
              f"  C2 w 2 lifts the typical year > 5% on both halves, worst month < 2 points deeper: tune ${b[0]['typ']:,.0f} -> "
              f"${n2[0]['typ']:,.0f}, holdout ${b[1]['typ']:,.0f} -> ${n2[1]['typ']:,.0f}; worst month {b[0]['wm']:+.1f} -> {n2[0]['wm']:+.1f} / "
              f"{b[1]['wm']:+.1f} -> {n2[1]['wm']:+.1f} -> {'RIGHT' if c2 else 'WRONG'}",
              f"  C3 at 50bp a leg the news book makes money: CAGR {stats1(N[0.005])[0] * 100:+.0f}% -> "
              f"{'RIGHT' if stats1(N[0.005])[0] > 0 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    # --narrow: only the two types with a strong edge per type (news_book.py, 2026-10-17) - chosen AFTER seeing the
    # per-type results, so a candidate for forward paper, not a pass
    if "--narrow" in sys.argv:
        TYPES, HOLD, STOP = ("adds_products", "monitoring_tag"), 72, 0.25
        LOG = ROOT / "logs" / "news_combo_narrow.txt"
    main()
