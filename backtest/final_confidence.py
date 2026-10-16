"""HOW LIKELY IS THE FINAL BOT'S BACKTEST TO HOLD WITH REAL MONEY? - the deployed configuration, stress-tested (2026-10-16)

The user: "list what our final bot is expected to give, then evaluate extensively and give a confident score how likely
it will give it if pushed on real money". The configuration is the one running since 2026-10-16 01:05 UTC
(combo_bot.py --final, final_books.py: trend triple guard 6.25x, MN blend, carry 0.5x, sleeve, crash bids, daily 0.5x,
capit2 1.0 x 2x; final_capit2_lev.py cell W 1.0 / L 2). Each line below removes one known flattering assumption:
    AS BACKTESTED      trend gains shrunk for hindsight, everything else raw (final_capit2_lev.py)
    LIVE-MODEL GAP     -1.5%/month: the live bots' position model (one per key, retry, a one-bar pause) runs 1-2 %/mo under
                       the engine (engine_vs_live.py / slot_retry.py, s10 2026-10-06)
    + MINED HOLDOUT    the MN blend, carry and the daily book's 20-day exit were found in the ~10th sweep of a mined
                       holdout and the daily book was chosen after looking: their gains halved
    + WEAK MARKET      only the days BTC sat under its 1000h average (the bear gate), strung together - what a year of
                       weak market alone does to the book (it is a bull amplifier)
Reported on $300: typical / bad (25th pct) / worst 12 months, P(12 months end below the start), P(below half), the worst
month, the biggest fall; and where the live paper records sit in the backtest's own distribution of same-length starts.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. AS BACKTESTED ends a 12-month window below the start in <= 5% of windows; after the live-model gap and the mined
       halving, 15-30%.
    2. The final machine's live -10.6% over its first 7 days sits at or below the 15th percentile of 7-day windows.

RESULT (2026-10-16, logs/final_confidence.txt) - prediction 1 WRONG (the backtest is sturdier to these discounts than
    registered), 2 right. $300, 12 months, typical / 25th pct / 10th pct / worst, P(below start), worst month, fall:
    AS BACKTESTED $4,098 / $1,337 / $504 / $238, 1%, -30%, 57% | - live gap $3,432, 3% | - mined halved $2,149 / $842 /
    $420 / $223, 4%, -25%, 52% | weak-market days only $1,370, 7%. The discounts shrink the typical year 2-3x; they barely
    move P(loss), because the backtest's 12-month windows almost never lose.
    BUT the live paper records sit in the backtest's bottom tail: the final machine's first 7 days (-10.6%) at the 7.3rd
    percentile, the combo paper's 21 days (-20.5%) at the 3.8th of the final machine's 21-day windows. Same weeks of the
    same market, so not two independent draws - one weak stretch, read twice. Not a verdict; the reason a backtest's 1%
    P(loss) is not a planning number.
    First run failed on the s3 trap ('~' on an object-dtype column) - .astype(bool) added.

    python -m backtest.final_confidence
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402
from backtest import final_machine as fm  # noqa: E402
from backtest import machine_combos as mc  # noqa: E402
from backtest import mn_combos as m  # noqa: E402
from backtest.moderate_retests import scored_run  # noqa: E402

LOG = ROOT / "logs" / "final_confidence.txt"
CAP = 300.0


def parts():
    """Per ordering: the deployed final machine's daily return split into (solid, mined) parts."""
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
        mn_blend = 0.5 * r(scored_run(mom, start=o, stop="short_only", short_stop=0.5)) \
            + 0.5 * r(scored_run(rsi, start=o, stop="short_only", short_stop=0.5))
        carry = r(m.mn_run(look=1, score="funding7", fwin=7, frac=0.2, start=o, stop="short_only", short_stop=0.5))
        off = dc.PHASES[sd % 3]
        daily20 = 0.5 * r(dc.curve(T20[off], dc.allocate(T20[off], sd), off).pct_change())
        coff = cc.PHASES[sd % 4]
        cap2 = r(cc.curve(cT2[coff], dc.allocate(cT2[coff].assign(units=None), sd, 2.0)).pct_change())
        solid = T625[sd].reindex(idx).fillna(0.0) + b.sleeve + b.bids + cap2
        mined = mn_blend + 0.5 * carry + daily20
        out.append((solid, mined))
    return out


def windows12(x):
    c = (1 + x).cumprod()
    me = c.resample("ME").last()
    return (me.shift(-12) / me).dropna().to_numpy(), (me / me.shift(1)).dropna().to_numpy() - 1, float((1 - c / c.cummax()).max())


def report(name, xs):
    W, WM, DD = [], [], []
    for x in xs:
        w, mo, dd = windows12(x)
        W.append(w)
        WM.append(mo.min())
        DD.append(dd)
    w = np.concatenate(W)
    return dict(name=name, typ=CAP * np.median(w), bad=CAP * np.percentile(w, 25), p10=CAP * np.percentile(w, 10),
                worst=CAP * w.min(), below=(w < 1).mean(), half=(w < 0.5).mean(), wm=np.mean(WM), dd=np.mean(DD), n=len(w))


def pct_of(xs, days, live):
    v = []
    for x in xs:
        c = (1 + x).cumprod()
        v.append((c.shift(-days) / c).dropna().to_numpy() - 1)
    v = np.concatenate(v)
    return (v <= live).mean(), np.median(v)


def main():
    from backtest.bull_boost import regimes
    S = parts()

    lines = [f"backtest/final_confidence.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the deployed final machine "
             f"(capit2 1.0 x 2x), $300, 10 orderings; BACKTEST, progressively discounted", ""]
    base = [s + mi for s, mi in S]
    per_day = 0.015 / 30.44
    live = [x - per_day for x in base]
    mined = [s + 0.5 * mi - per_day for s, mi in S]
    reg = regimes()[1000]
    rg = pd.Series(reg.to_numpy(bool), index=pd.DatetimeIndex(reg.index)).resample("D").last().ffill()
    notbull = [x[~rg.reindex(x.index).ffill().fillna(False).astype(bool).to_numpy()] for x in mined]   # .astype(bool): s3 trap
    R = [report("AS BACKTESTED", base), report("- live-model gap (-1.5%/mo)", live),
         report("- and mined parts halved", mined), report("- and only BTC-under-1000h days", notbull)]
    lines.append(f"  {'line':<32}{'typical':>9}{'bad 25%':>9}{'10%':>8}{'worst':>8}{'P(<$300)':>10}{'P(<$150)':>10}{'worst mo':>10}{'fall':>7}")
    for r in R:
        lines.append(f"  {r['name']:<32}${r['typ']:>7,.0f} ${r['bad']:>7,.0f} ${r['p10']:>6,.0f} ${r['worst']:>6,.0f}"
                     f"{r['below'] * 100:>9.0f}%{r['half'] * 100:>9.0f}%{r['wm'] * 100:>+9.1f}%{r['dd'] * 100:>6.0f}%")
    p7, m7 = pct_of(base, 7, -0.106)
    p21, m21 = pct_of(base, 21, -0.2048)
    lines += ["", "WHERE THE LIVE PAPER RECORDS SIT in the backtest's own same-length windows",
              f"  final machine dry, 7 days -10.6%: percentile {p7 * 100:.1f} (median 7-day window {m7 * 100:+.1f}%)",
              f"  combo paper (machine v2, a close relative), 21 days -20.5%: percentile {p21 * 100:.1f} of the FINAL machine's "
              f"21-day windows (median {m21 * 100:+.1f}%)"]
    p1 = R[0]["below"] <= 0.05 and 0.15 <= R[2]["below"] <= 0.30
    lines += ["", "REGISTERED PREDICTIONS",
              f"  1 below-start: as backtested {R[0]['below'] * 100:.0f}% (<= 5), discounted {R[2]['below'] * 100:.0f}% (15-30) -> "
              f"{'RIGHT' if p1 else 'WRONG'}",
              f"  2 live 7-day at or below the 15th percentile: {p7 * 100:.1f} -> {'RIGHT' if p7 <= 0.15 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
