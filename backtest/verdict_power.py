"""HOW SOON CAN THE PAPER RECORD TELL A WORKING MACHINE FROM A DEAD ONE? (2026-10-23)

THE USER (2026-10-23): "I want the verdict soon, can't wait 3 months". The question behind it: after N days of paper
record, how often does the machine AS BACKTESTED look like a machine with NO edge? If the two look alike at 30 days, a
30-day verdict is a coin toss, whatever it says.
  WORKING  the running final machine (all_books.machine_books + news + NASDAQ dip, with the two fixes deployed
           2026-10-22: capit2 as backtested and the crash bids on; machine_fixes.py's "F1 + F2"), 10 orderings, daily
           returns; every N-day window, compounded
  DEAD     the same daily returns with their mean LOG return removed (per ordering): the same shape - fat tails, bad
           days, the trend book's lumps - and zero growth. (First run removed the plain mean: with the booked-at-close
           lumps the daily volatility is 12.6%, so a zero-mean series compounds at about -1.2% a day from volatility
           drag alone and the 'dead' machine lost 56% in 180 days - not a fair null. Changed after seeing it.)
  For each N: the best single cut between the two distributions, its accuracy, and how often each side lands on the
  wrong side of it. And the evidence so far: where the main account's -12.5% at day 14 sits in each, and the
  likelihood ratio (how many times more likely that reading is from a dead machine than a working one).
REGISTERED BEFORE THE RUN (2026-10-23)
  P1 at 30 days the best cut classifies <= 70% correctly; at 90 days 75-85%; at 180 days >= 85%.
  P2 the day-14 reading (-12.5%) is 1.5-4 times more likely under DEAD than WORKING - evidence against, not a verdict.

RESULT (2026-10-23, logs/verdict_power.txt) - the record never gets much sharper than ~74%; a day-45 check is as good as day 180.
  Best-cut accuracy WORKING vs DEAD: 7 days 63%, 14 days 65%, 30 days 69%, 45 / 60 / 90 days 74%, 120 / 180 days 73%. It
  PLATEAUS: the machine's months cluster by regime (the year is made in one or two bull months), so the noise grows about
  as fast as the edge. At 45 days the cut is -12.9%: a working machine lands under it 10% of the time, a dead one 58% -
  under it is ~6x as likely dead (a confident NO); over it only ~2x as likely working (a weak YES). P1 WRONG (it never
  reaches 75-85%). The evidence so far: -12.5% at day 14 sits at the 10th percentile of WORKING and the 34th of DEAD -
  2.3x as likely from a dead machine (P2 RIGHT): a warning, not a verdict.

    python -m backtest.verdict_power
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "verdict_power.txt"
CACHE = ROOT / "logs" / "daily_combos_cache" / "alt_bear_books.pkl"
NS = (7, 14, 30, 45, 60, 90, 120, 180)
LIVE_N, LIVE_R = 14, -0.125                 # the main account on the dashboard, 2026-10-22 18:56 UTC, day 13.8


def windows(r: np.ndarray, n: int) -> np.ndarray:
    lc = np.r_[0.0, np.cumsum(np.log1p(np.clip(r, -0.99, None)))]
    return np.expm1(lc[n:] - lc[:-n])


def main():
    from backtest.all_books import BOOKS, machine_books, ndx_dip, news_book
    M = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else machine_books()
    news, ndx = news_book(), ndx_dip()
    work, dead = [], []
    for x in M:
        r = (x[BOOKS].sum(axis=1) + news.reindex(x.index).fillna(0.0) + ndx.reindex(x.index).fillna(0.0)).to_numpy()
        work.append(r)
        lr = np.log1p(np.clip(r, -0.99, None))
        dead.append(np.expm1(lr - lr.mean()))           # zero GROWTH, same shape (see the run note above)
    L = [f"backtest/verdict_power.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the running final machine (7 books incl. "
         f"the crash bids + news + NASDAQ dip), 10 orderings, {len(work[0])} days each; DEAD = the same days, mean LOG return removed", "",
         f"   mean daily return {np.mean([w.mean() for w in work]) * 100:+.3f}%, daily volatility {np.mean([w.std() for w in work]) * 100:.2f}%", "",
         f"   {'days':>5}{'WORKING median':>16}{'DEAD median':>13}{'best cut':>10}{'accuracy':>10}{'working looks dead':>20}"
         f"{'dead looks working':>20}"]
    acc = {}
    for n in NS:
        W = np.concatenate([windows(w, n) for w in work])
        D = np.concatenate([windows(d, n) for d in dead])
        grid = np.quantile(np.r_[W, D], np.linspace(0.01, 0.99, 197))
        best = max(grid, key=lambda c: 0.5 * ((W > c).mean() + (D <= c).mean()))
        a = 0.5 * ((W > best).mean() + (D <= best).mean())
        acc[n] = a
        L.append(f"   {n:>5}{np.median(W) * 100:>+15.1f}%{np.median(D) * 100:>+12.1f}%{best * 100:>+9.1f}%{a * 100:>9.0f}%"
                 f"{(W <= best).mean() * 100:>19.0f}%{(D > best).mean() * 100:>19.0f}%")
    W = np.concatenate([windows(w, LIVE_N) for w in work])
    D = np.concatenate([windows(d, LIVE_N) for d in dead])
    band = 0.02
    pw = ((W > LIVE_R - band) & (W < LIVE_R + band)).mean()
    pd_ = ((D > LIVE_R - band) & (D < LIVE_R + band)).mean()
    lr = pd_ / pw if pw > 0 else np.inf
    L += ["", f"THE EVIDENCE SO FAR: {LIVE_R * 100:+.1f}% at day {LIVE_N} (main account)",
          f"   percentile among WORKING {LIVE_N}-day windows {(W <= LIVE_R).mean() * 100:.1f}, among DEAD {(D <= LIVE_R).mean() * 100:.1f}",
          f"   a reading within +-2 points of it: {pw * 100:.2f}% of WORKING windows, {pd_ * 100:.2f}% of DEAD -> {lr:.2f} times "
          f"as likely from a dead machine"]
    p1 = acc[30] <= 0.70 and 0.75 <= acc[90] <= 0.85 and acc[180] >= 0.85
    p2 = 1.5 <= lr <= 4.0
    L += ["", "REGISTERED PREDICTIONS",
          f"  P1 30d <= 70%, 90d 75-85%, 180d >= 85% ({acc[30] * 100:.0f} / {acc[90] * 100:.0f} / {acc[180] * 100:.0f}%) -> "
          f"{'RIGHT' if p1 else 'WRONG'}",
          f"  P2 the day-14 reading 1.5-4x as likely dead ({lr:.2f}) -> {'RIGHT' if p2 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
