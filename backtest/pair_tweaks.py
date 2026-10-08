"""THE LAST TWO PAIN POINTS OF MACHINE V3: chop months (+3.2%) and the 40% fall (2026-10-08).

    chop dial   the market-neutral overlay at x1 in CHOP days (BTC 50-day trend, knowable), x0.5 otherwise
    anchor      the daily book sized from min(equity, its 21-day average) - doc 14's one drawdown fix that survived
Base = pair_full.py's system (daily + capitulation halves, 8 slots each, 1x, capped MN x0.5, bear sleeve x1, no gate).
3 daily x 2 capitulation phases x 10 orders.

REGISTERED BEFORE RUNNING: the chop dial lifts chop months by +1..+2 points with about the same fall; the anchor cuts the
fall by 3-8 points for under 10 points of CAGR.

RESULT (2026-10-08, logs/pair_tweaks.txt): base reproduces pair_full's +133%. CHOP DIAL: chop months +3.2 -> +5.0 (right),
    CAGR +150%, holdout +88, but the fall 40% -> 48% (predicted "about the same": WRONG) - a risk dial, not a free fix.
    ANCHOR 21d on the daily book: no effect (fall 40%, CAGR +131%) - predicted -3..-8 points of fall: WRONG. Default stays
    the base; the chop dial is the "aggressive" setting.

    python -m backtest.pair_tweaks
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest.mn_capped import mn_series  # noqa: E402

LOG = ROOT / "logs" / "pair_tweaks.txt"


def account_anchor(books, seed, extra, anchor_days=None, anchor_book="daily"):
    """pair_lab.account with the anchor: `anchor_book`'s trades sized from min(equity, mean equity of the last
    anchor_days days)."""
    liq = 1 / 1.0 - 0.005 - 0.0006
    rng = np.random.default_rng(seed)
    ev = sorted(((r.t_in, rng.random(), nm, r.t_out, r.net, r.worst) for nm, (T, sh, sl) in books.items()
                 for r in T.itertuples()), key=lambda x: (x[0], x[1]))
    eq, open_, pts, hist = 1.0, [], [], []
    for t_in, _, nm, t_out, net, worst in ev:
        for p in sorted([p for p in open_ if p[0] <= t_in], key=lambda p: p[0]):
            eq += p[1]
            pts.append((p[0], eq))
        open_ = [p for p in open_ if p[0] > t_in]
        hist.append((t_in, eq))
        _, share, slots = books[nm]
        if sum(1 for p in open_ if p[2] == nm) >= slots:
            continue
        base = eq
        if anchor_days and nm == anchor_book:
            lo = t_in - pd.Timedelta(days=anchor_days)
            past = [e for t, e in hist if t >= lo]
            base = min(eq, float(np.mean(past))) if past else eq
        size = base * share / slots
        open_.append((t_out, -size if worst >= liq else size * max(net, -1.0), nm))
    for p in sorted(open_, key=lambda p: p[0]):
        eq += p[1]
        pts.append((p[0], eq))
    s = pd.Series([e for _, e in pts], index=pd.DatetimeIndex([t for t, _ in pts])).groupby(level=0).last()
    d = s.resample("D").last().ffill()
    d = pd.concat([pd.Series([1.0], index=[min(x[0] for x in ev).normalize()]), d]).groupby(level=0).last().resample("D").last().ffill()
    r = d.pct_change().fillna(0.0) + extra.reindex(d.index).fillna(0.0)
    return (1 + r).cumprod()


def main():
    reg = pl.btc_regime_daily()
    mn = mn_series(1.0)
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    days = pd.date_range("2020-01-01", "2026-09-30", freq="D")
    r_ = reg.reindex(days).ffill()
    w_flat = pd.Series(0.5, index=days)
    w_chop = pd.Series(np.where(r_ == "chop", 1.0, 0.5), index=days)
    lines = [f"backtest/pair_tweaks.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; 6 phase combinations x 10 orders, medians", ""]
    for nm, w, anc in (("base (machine v3)", w_flat, None), ("chop dial (MN x1 in chop)", w_chop, None),
                       ("anchor 21d on the daily book", w_flat, 21), ("chop dial + anchor", w_chop, 21)):
        extra = w * mn.reindex(days).fillna(0.0) + sleeve.reindex(days).fillna(0.0)
        per = []
        for off_h in (0, 8, 16):
            D = pl.daily_trades(off_h=off_h)
            for coff in (0, 120):
                C = pl.capit_trades(coff)
                for sd in range(10):
                    per.append(pl.metrics(account_anchor({"daily": (D, 0.5, 8), "capit": (C, 0.5, 8)}, sd, extra, anc), reg))
        P = pd.DataFrame(per)
        lines.append(f"{nm:32} CAGR {P.cagr.median() * 100:+4.0f}% (5..95 {P.cagr.quantile(.05) * 100:+.0f}..{P.cagr.quantile(.95) * 100:+.0f}) "
                     f"tune {P.tune.median() * 100:+.0f} / holdout {P.hold.median() * 100:+.0f} | fall {P.dd.median():.0%} | up {P.up.median():.0%} | "
                     f"median month {P.med.median() * 100:+.1f}% | bull {P.bull.median() * 100:+.1f} chop {P.chop.median() * 100:+.1f} "
                     f"bear {P.bear.median() * 100:+.1f}")
        print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
