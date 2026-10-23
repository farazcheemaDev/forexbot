"""THE WHOLE RECIPE + THE CROWD-SQUEEZE BOOK in one account - what the combination looks like (2026-10-23)

THE USER (2026-10-23): "it's valid that we will add it later to all the recipe we have created before - now tell me the
numbers with everything combined". The crowd book runs on paper on its own (news/crowd_paper.py); this measures the
account it would make INSIDE the deployed machine.
  MACHINE  the deployed final machine: trend + MN blend + carry 0.5 + sleeve + daily 0.5 + capit2 (resting limit, 2x) +
           crash bids + news + NASDAQ dip (machine_fixes.py's "F1 + F2 (deployed 2026-10-22)", 10 orderings; trend gains
           shrunk for hindsight, the rest raw)
  CROWD    positioning_hist.py's crowd book as crowd_paper runs it - Monday + Thursday sleeves, half each - marked at every
           DAILY close (its weekly product reproduces positioning_hist.book's net weeks: asserted), funding and the
           backtest's fee charged; added at k = 0.5 and 1.0 of account equity (1x gross per unit of k)
  SPANS    the crowd data starts 2022-01, so both are scored on the SAME dates: 2022-01-25 .. 2024-08-28 (the machine's
           tune half from 2022) and 2024-08-29 .. 2026-09 (its holdout); $300, every 12-month window, as machine.summary
  LINES    paired per ordering (the % change in the typical year, wins of 10); and the BET-SMALLER line: the machine alone
           scaled until its average fall equals the combination's - the crowd book is worth adding only if the
           combination's typical year beats that

REGISTERED BEFORE THE RUN (2026-10-23)
  Y1 daily correlation of the crowd book with the machine between -0.10 and +0.20.
  Y2 the crowd book at 0.5 adds +5% .. +35% to the typical year on BOTH spans, 10/10 orderings.
  Y3 at 0.5 the worst month moves by under 3 points and the average fall by under 5, on both spans.
  Y4 at 0.5 it beats the bet-smaller line on the 2024-26 span and NOT on 2022-24 (the book made +23%/yr there).

RESULT (2026-10-23, logs/crowd_combo.txt; BACKTEST) - the crowd book improves the whole machine on both spans, 10/10.
  Y1-Y3 RIGHT; Y4 WRONG the good way (it beats the bet-smaller line on 2022-24 too).
  Correlation with the machine +0.09 daily / +0.22 monthly; the book alone +24%/yr 2022-24, +69%/yr 2024-26, worst
  month -18.6%. $300 typical 12 months (bad year / worst month / fall):
    2022-01 .. 2024-08   machine $1,177 ($610 / -18.2% / 41%)   + crowd x0.5 $1,362 (+16%)   + crowd x1.0 $1,519 (+34%)
    2024-08 .. 2026-09   machine $9,838 ($4,652 / -31.3% / 49%) + crowd x0.5 $12,914 (+34%)  + crowd x1.0 $16,045 (+77%)
  x0.5 leaves the worst month and fall within 1.5 points; x1.0 costs 1-3 points. The machine scaled to the same fall
  makes $1,175 / $10,482 (x0.5's line) - the crowd book is a better use of the risk than more of the machine.
  WHY NOT TO BANK IT: the book was picked as the lead from this same 2022-26 data (t 1.8-2.0, no pass), and two-thirds
  of its edge is 2025-26; its paper record (news/crowd_paper.py, verdict 2027-04-26) decides. Inside a $300 account at
  x0.5 a leg is ~$3.75 (under Bitget's $5 minimum); x1.0 gives $6.8-7.5 legs. The account gate (14.5x paper) is not
  modelled here: the book adds k x gross.

    python -m backtest.crowd_combo
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "crowd_combo.txt"
SPANS = (("2022-01 .. 2024-08", "2022-01-25", "2024-08-29"), ("2024-08 .. 2026-09", "2024-08-29", None))
KS = (0.5, 1.0)


def crowd_daily():
    """Each sleeve as a daily return series on its own equity, and the book = half each, rebalanced daily."""
    from news import positioning_hist as ph
    anchors, el, F, C, Fd, cff, piv = ph.inputs()
    idx = C.index
    S = {}
    for wd, k in ((0, "mon"), (3, "thu")):
        D = ph.panel(wd, anchors, el, C, Fd, cff, piv)
        _, ref = ph.book(D, "crowd", ph.SIGN["crowd"])
        out, wk, prev_l, prev_s = {}, {}, set(), set()
        for a, g in D.groupby("a"):
            g = g.dropna(subset=["crowd"]).set_index("s")
            if len(g) < 16:
                continue
            ln, sn = ph.quarters(g["crowd"])                       # SIGN -1: long the low (most short) quarter
            fee = ph.turnover_fee(prev_l, prev_s, ln, sn)
            prev_l, prev_s = ln, sn
            d0, d1 = a - pd.Timedelta(days=1), a + pd.Timedelta(days=6)
            days = idx[(idx > d0) & (idx <= d1)]
            cols = sorted(ln | sn)
            w = pd.Series({s: (0.5 / len(ln) if s in ln else -0.5 / len(sn)) for s in cols})
            move = cff.loc[days, cols] / C.loc[d0, cols] - 1
            fund = Fd.loc[days, cols].cumsum()
            V = 1 - fee + ((move - fund) * w).sum(axis=1)           # value / the week's opening equity
            r = V / pd.concat([pd.Series([1.0], index=[d0]), V.iloc[:-1]]).to_numpy() - 1
            out.update(r.to_dict())
            wk[a] = V.iloc[-1] - 1
        wk = pd.Series(wk)
        err = (wk - ref.reindex(wk.index)).abs().max()
        assert err < 1e-12, f"{k}: daily marks do not reproduce positioning_hist.book ({err:.2e})"
        S[k] = pd.Series(out).sort_index()
    i = S["mon"].index.union(S["thu"].index)
    return 0.5 * S["mon"].reindex(i).fillna(0.0) + 0.5 * S["thu"].reindex(i).fillna(0.0), S


def machine():
    from backtest import machine_combos as mc
    from backtest.all_books import machine_books, ndx_dip, news_book
    from backtest.machine_fixes import CACHE
    M = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else machine_books()
    news, ndx = news_book(), ndx_dip()
    out = []
    for sd, x in zip(mc.SEEDS, M):
        r = lambda s: s.reindex(x.index).fillna(0.0)  # noqa: E731
        out.append(x.trend + x.sleeve + x.daily + r(news) + r(ndx) + x.mn_blend + x.carry + x.capit2 + x.bids)
    return out


def cut(xs, a, b):
    return [x[(x.index >= a) & ((x.index < b) if b else True)] for x in xs]


def main():
    from backtest.machine import summary
    cr, S = crowd_daily()
    M = machine()
    end = min(cr.index[-1], M[0].index[-1])
    first = pd.Timestamp(SPANS[0][1])
    M = [x[(x.index >= first) & (x.index <= end)] for x in M]
    crr = cr[(cr.index >= first) & (cr.index <= end)]                # each ordering's calendar differs by a day:
    al = lambda x: crr.reindex(x.index).fillna(0.0)  # noqa: E731    # the crowd series is aligned to each one
    corr_d = float(np.mean([np.corrcoef(x.to_numpy(), al(x).to_numpy())[0, 1] for x in M]))
    mo = lambda s: (1 + s).resample("ME").prod() - 1  # noqa: E731
    corr_m = float(np.mean([np.corrcoef(mo(x), mo(al(x)))[0, 1] for x in M]))
    yr = lambda s: ((1 + s).prod() ** (365 / max(len(s), 1)) - 1) * 100  # noqa: E731
    L = [f"backtest/crowd_combo.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the deployed machine (machine_fixes.py F1+F2, "
         f"10 orderings) + the crowd book (positioning_hist.py, daily marks reproduce its weeks); $300; BACKTEST", "",
         f"   crowd book alone: {yr(crr[crr.index < SPANS[1][1]]):+.0f}%/yr 2022-24, {yr(crr[crr.index >= SPANS[1][1]]):+.0f}%/yr "
         f"2024-26; worst month {mo(crr).min() * 100:+.1f}%; correlation with the machine: daily {corr_d:+.2f}, monthly {corr_m:+.2f}", "",
         f"   {'$300, 12 months':<30}{'span':>20}{'typical':>10}{'bad':>9}{'worst':>9}{'worst mo':>9}{'fall':>6}{'mo up':>7}"
         f"{'vs machine, paired':>24}{'machine at same fall':>22}"]
    R = {}
    for lab, a, b in SPANS:
        base = cut(M, a, b)
        s0 = summary(base)
        per0 = np.array([summary([x])["typ"] for x in base])
        R[(lab, 0)] = s0
        L.append(f"   {'MACHINE (deployed)':<30}{lab:>20} ${s0['typ']:>8,.0f} ${s0['bad']:>7,.0f} ${s0['worst']:>7,.0f}"
                 f"{s0['wm']:>+8.1f}%{s0['dd']:>5.0f}%{s0['up']:>6.0f}%")
        for k in KS:
            xs = [x + k * crr.reindex(x.index).fillna(0.0) for x in base]
            s = summary(xs)
            per = np.array([summary([x])["typ"] for x in xs])
            d = (per / per0 - 1) * 100
            lo, hi = 0.5, 3.0                                      # the machine scaled to the combination's fall
            for _ in range(40):
                m = (lo + hi) / 2
                lo, hi = (m, hi) if summary([x * m for x in base])["dd"] < s["dd"] else (lo, m)
            sm = summary([x * m for x in base])
            R[(lab, k)] = dict(s, pair=d.mean(), wins=int((d > 0).sum()), line=sm["typ"], m=m)
            L.append(f"   {f'MACHINE + CROWD x{k}':<30}{lab:>20} ${s['typ']:>8,.0f} ${s['bad']:>7,.0f} ${s['worst']:>7,.0f}"
                     f"{s['wm']:>+8.1f}%{s['dd']:>5.0f}%{s['up']:>6.0f}%{f'{d.mean():+.1f}% +- {d.std(ddof=1) / np.sqrt(len(d)):.1f}, {int((d > 0).sum())}/10':>24}"
                     f"{f'x{m:.2f}: ${sm[chr(116) + chr(121) + chr(112)]:,.0f}':>22}")
        L.append("")
    sp = [s[0] for s in SPANS]
    y1 = -0.10 <= corr_d <= 0.20
    y2 = all(5 <= R[(s, 0.5)]["pair"] <= 35 and R[(s, 0.5)]["wins"] == 10 for s in sp)
    y3 = all(abs(R[(s, 0.5)]["wm"] - R[(s, 0)]["wm"]) < 3 and abs(R[(s, 0.5)]["dd"] - R[(s, 0)]["dd"]) < 5 for s in sp)
    y4 = R[(sp[1], 0.5)]["typ"] > R[(sp[1], 0.5)]["line"] and not R[(sp[0], 0.5)]["typ"] > R[(sp[0], 0.5)]["line"]
    L += ["REGISTERED PREDICTIONS",
          f"  Y1 daily correlation -0.10..+0.20: {corr_d:+.2f} -> {'RIGHT' if y1 else 'WRONG'}",
          f"  Y2 x0.5 adds +5..+35% to the typical year on both spans, 10/10: "
          f"{[(s, round(R[(s, 0.5)]['pair'], 1), R[(s, 0.5)]['wins']) for s in sp]} -> {'RIGHT' if y2 else 'WRONG'}",
          f"  Y3 x0.5 worst month within 3 points, fall within 5: -> {'RIGHT' if y3 else 'WRONG'}",
          f"  Y4 x0.5 beats the bet-smaller line on 2024-26 only: "
          f"{[(s, R[(s, 0.5)]['typ'] > R[(s, 0.5)]['line']) for s in sp]} -> {'RIGHT' if y4 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
