"""THE MACHINE + THE CAPITULATION BOOK - does a crash-buying sleeve add to a bull-market trend machine? (2026-10-08)

The capitulation book (capitulation_exits.py / capitulation_tp5.py: top-40, 4h RSI<20 + volume > 2x, >= 5 coins in
24h, +5% or out after 24 bars if not in profit) earns in crashes; the machine (machine.py: trend triple + MN + bear
sleeve + crash bids) earns in bulls. Added here as one more overlay on the same margin, the way machine.py adds MN, the
sleeve and the bids: the capitulation book's own daily return (an 8-slot account at 1x or 2x, equity / 8 per trade)
times a weight w.
Machine as machine.py: $300, 10 orderings, trend gains shrunk for hindsight, losses whole; other books raw. The
capitulation book is raw (point-in-time universe: no haircut - and said so, rule 5). Its 4 bar phases are rotated
over the 10 orderings (ordering k uses phase k % 4).

REGISTERED BEFORE RUNNING: the capitulation book's monthly correlation with the machine is near zero or negative;
adding it at w = 1 (1x) improves the machine's worst month and typical year, by modest amounts (typical year +5..+15%).

    python -m backtest.machine_capit
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.bear_chop import fast_run  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.machine import CUT, SEEDS, summary  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402
from backtest.worst_month import TCACHE  # noqa: E402

LOG = ROOT / "logs" / "machine_capit.txt"


def capit_daily(T, lev, slots=8):
    """Daily return of a capitulation account (equity / slots per trade, skip while full), booked at each exit."""
    liq = 1 / lev - 0.005 - 0.0006
    eq, open_, pts = 1.0, [], []
    for r in T.sort_values("t_in", kind="stable").itertuples():
        for p in sorted([p for p in open_ if p[0] <= r.t_in]):
            eq += p[1]
            pts.append((p[0], eq))
        open_ = [p for p in open_ if p[0] > r.t_in]
        if len(open_) >= slots or eq <= 0:
            continue
        size = eq / slots
        open_.append((r.t_out, -size if r.worst >= liq else size * max(lev * r.net, -1.0)))
    for p in sorted(open_):
        eq += p[1]
        pts.append((p[0], eq))
    s = pd.Series([e for _, e in pts], index=pd.DatetimeIndex([t for t, _ in pts])).groupby(level=0).last()
    d = s.resample("D").last().ffill()
    d = pd.concat([pd.Series([1.0], index=[d.index[0] - pd.Timedelta(days=1)]), d])
    return d.pct_change().dropna()


def main():
    cache = pickle.loads(TCACHE.read_bytes())
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    bids = pd.read_pickle(ROOT / "logs" / "wick_capped.pkl")[10]
    A = pd.read_csv(ROOT / "logs" / "capitulation_exits_trades.csv", parse_dates=["t_in", "t_out"])
    A = A[A.exit == "tp5_nw"]
    cap = {(off, lev): capit_daily(A[A.off == off], lev) for off in (0, 60, 120, 180) for lev in (1, 2)}
    lines = [f"backtest/machine_capit.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; machine v2 (machine.py) + the capitulation "
             f"book as an overlay of weight w; $300, 10 orderings (phase = ordering % 4)", ""]
    base, corr = {}, []
    for sd in SEEDS:
        t = cache[("anchor", sd)]
        idx = t.index
        m = t + mn_d.reindex(idx).fillna(0.0) + sleeve.reindex(idx).fillna(0.0) + bids.reindex(idx).fillna(0.0)
        base[sd] = m
        c1 = cap[((0, 60, 120, 180)[sd % 4], 1)].reindex(idx).fillna(0.0)
        mm = (1 + m).groupby(idx.to_period("M")).prod() - 1
        cm = (1 + c1).groupby(idx.to_period("M")).prod() - 1
        corr.append(np.corrcoef(mm, cm)[0, 1])
    lines.append(f"monthly correlation, machine vs capitulation book (1x): mean {np.mean(corr):+.2f} "
                 f"(range {min(corr):+.2f} .. {max(corr):+.2f})")
    for span, t0 in (("all years", None), ("last 2 years", CUT)):
        lines.append(f"\n{span}: $300 after 12 months - typical / bad (1 in 4) / worst; worst month; biggest fall; months up")
        for lev in (1, 2):
            for w in (0.0, 0.5, 1.0, 2.0):
                if lev == 2 and w == 0.0:
                    continue
                xs = [base[sd] + w * cap[((0, 60, 120, 180)[sd % 4], lev)].reindex(base[sd].index).fillna(0.0) for sd in SEEDS]
                s = summary(xs, t0)
                lines.append(f"  capitulation {lev}x weight {w:.1f}: ${s['typ']:>7,.0f} / ${s['bad']:>6,.0f} / ${s['worst']:>6,.0f}"
                             f" | worst month {s['wm']:+.1f}% | fall {s['dd']:.0f}% | up {s['up']:.0f}%")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
