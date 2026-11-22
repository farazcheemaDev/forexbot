"""Where inside the minute does the NASDAQ trader click? The timing branch of the 'observe him' plan (2026-11-13)

THE USER (after a side session's plan: record his sittings, his broker's ticks, his click timing, a group signal): "can't you measure his
click timing or something". The plan's step 3: if his entries sit TIGHTLY a few seconds after a 1-minute candle closes, he reacts to something
that updates on the close (an indicator alert, a message, a bot); if they are spread over 5-25 s it is a person reading the chart. That can be
measured on the trades we have now, as a description (no new hypothesis about the market is tested on the old 46 - the plan's own warning).

KNOWN BEFORE THIS FILE (his_candles.py / his_strategy.md s30-s31): 24 of 46 NASDAQ entries fall 5-24 s into the minute (p 0.011); his exits and
his gold entries are uniform.

DATA  strategy_analysis/statement_trades.csv (his statement: 91 trades, open and close to the second, his broker's clock - exact against CME and
      Exness, his_clock_exits.py; the one-hour winter error does not touch seconds) + logs/his_new_trades.csv (4 NASDAQ trades of 2026-10-08 / 13
      scored by his_score_new.py).

QUESTIONS AND PREDICTIONS (written before the numbers below)
  K1  NASDAQ entries are not uniform over the minute (chi-square on six 10-s bins, p < 0.05).                              (80%)
  K2  The cluster is BROAD: the middle half of the in-cluster entries (5-24 s) spans 8 s or more - a person, not an alert.  (70%)
  K3  His exits and his gold entries are uniform (p > 0.2) - the controls.                                                  (75%)
  K4  The clustered entries do not bank more points than the others (difference within 1 se).                             (65%)
  K5  The first trade of a sitting clusters as much as the follow-ups (within 15 points of share).                         (55%)

RESULT (2026-11-13, logs/his_click_timing.txt) - NASDAQ entries cluster TIGHTLY ~10-16 s after a 1-minute close; nothing else does.
  K1, K3 right; K2, K4 (by 0.03 se), K5 wrong.
  NASDAQ entries: 24 of 46 in 5-24 s (p 0.006), median 14 s, middle half 10-16 s (6 s wide); 13 of 46 (28%) in one 6-s span against ~10%
  uniform. Exits (NASDAQ and gold) and gold entries: uniform (chi-square p 0.37-0.69). Follow-up trades of a sitting cluster more (10 of 15)
  than first trades (14 of 31); sells 65%, buys 39%. Clustered entries banked +10.8 pts (24 of 24 won) vs +7.4 (20 of 22): not significant
  (Mann-Whitney p 0.88). The 4 new trades (Oct 08 / 13): 1 of 4 in the window (seconds 06, 30, 48, 55) - too few to read.
  READING: a fixed ~10-16 s reaction to the candle close on NASDAQ only. Consistent with BOTH a disciplined chart reader and an alert / message
  that fires at the close; the timing alone cannot separate them. A screen recording of the next sittings (what is on his screen at second 0-15)
  can.

    python -m backtest.his_click_timing
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "his_click_timing.txt"
LO, HI = 5, 24                                   # the known window, seconds into the minute


def secs(t: pd.Series) -> np.ndarray:
    return pd.to_datetime(t).dt.second.to_numpy()


def hist(s: np.ndarray) -> str:
    c = np.bincount(s // 5, minlength=12)
    return " ".join(f"{k * 5:02d}-{k * 5 + 4:02d}:{n}" for k, n in enumerate(c))


def chi(s: np.ndarray) -> float:
    return float(stats.chisquare(np.bincount(s // 10, minlength=6)).pvalue)


def window_p(s: np.ndarray) -> tuple:
    k = int(((s >= LO) & (s <= HI)).sum())
    return k, float(stats.binomtest(k, len(s), (HI - LO + 1) / 60, alternative="greater").pvalue)


def main():
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv")
    x["o"], x["c"] = pd.to_datetime(x.open_time), pd.to_datetime(x.close_time)
    x = x.sort_values("o", kind="stable").reset_index(drop=True)
    x["s_open"], x["s_close"] = x.o.dt.second, x.c.dt.second
    nq = x[x.symbol.str.startswith("NASDAQ")].copy()
    au = x[x.symbol == "GOLD"]
    new = pd.read_csv(ROOT / "logs" / "his_new_trades.csv")
    s_new = pd.to_datetime(new.open, format="%H:%M:%S").dt.second.to_numpy()
    L = [f"backtest/his_click_timing.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; statement {len(x)} trades (NASDAQ {len(nq)}, gold {len(au)}), "
         f"new NASDAQ trades {len(new)}; window {LO}-{HI} s = {(HI - LO + 1) / 60 * 100:.0f}% of the minute", "",
         "1. SECONDS INTO THE MINUTE (5-s bins)"]
    rows = (("NASDAQ entries", nq.s_open.to_numpy()), ("NASDAQ exits", nq.s_close.to_numpy()), ("gold entries", au.s_open.to_numpy()),
            ("gold exits", au.s_close.to_numpy()), ("new NASDAQ entries", s_new))
    P = {}
    for lab, s in rows:
        k, p = window_p(s)
        P[lab] = (chi(s) if len(s) >= 12 else np.nan, k, len(s), p)
        L.append(f"  {lab:<20} n {len(s):>2}  in {LO}-{HI} s: {k:>2} ({k / len(s) * 100:3.0f}%, binomial p {p:.3f})  chi-square p {P[lab][0]:.3f}")
        L.append(f"    {hist(s)}")
    s = nq.s_open.to_numpy()
    w = np.sort(s[(s >= LO) & (s <= HI)])
    q1, med, q3 = np.percentile(w, [25, 50, 75])
    L += ["", "2. HOW TIGHT IS THE CLUSTER",
          f"  in-window NASDAQ entries: median {med:.0f} s, middle half {q1:.0f}-{q3:.0f} s (width {q3 - q1:.0f} s), all: {', '.join(map(str, w))}",
          f"  share in the tightest 6-s span of the minute: {max(((s >= a) & (s < a + 6)).sum() for a in range(60)) / len(s) * 100:.0f}% (uniform ~10%)"]
    # outcome by timing: points he banked (his own record, clock-free)
    pts = np.where(nq.side.str.upper() == "BUY", nq.close_price - nq.open_price, nq.open_price - nq.close_price)
    inw = (s >= LO) & (s <= HI)
    a, b = pts[inw], pts[~inw]
    d = a.mean() - b.mean()
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    L += ["", "3. DOES THE TIMING PAY (points banked, his own record)",
          f"  in {LO}-{HI} s: n {len(a)}, mean {a.mean():+.2f} pts, median {np.median(a):+.2f}, won {(a > 0).mean() * 100:.0f}%",
          f"  elsewhere:   n {len(b)}, mean {b.mean():+.2f} pts, median {np.median(b):+.2f}, won {(b > 0).mean() * 100:.0f}%",
          f"  difference {d:+.2f} pts (se {se:.2f}); Mann-Whitney p {stats.mannwhitneyu(a, b).pvalue:.2f}"]
    # first trade of a sitting (> 30 min since his previous trade of any symbol) vs follow-ups
    gap = x.o.diff().dt.total_seconds().fillna(1e9)
    x["first"] = gap > 1800
    f = x.loc[nq.index, "first"].to_numpy()
    fs, ls_ = s[f], s[~f]
    sh = lambda z: ((z >= LO) & (z <= HI)).mean()
    by_half = nq.o < pd.Timestamp("2026-03-29")
    L += ["", "4. WHO CLICKS IN THE WINDOW",
          f"  first trade of a sitting: {((fs >= LO) & (fs <= HI)).sum()} of {len(fs)} ({sh(fs) * 100:.0f}%);  follow-ups: {((ls_ >= LO) & (ls_ <= HI)).sum()} of "
          f"{len(ls_)} ({sh(ls_) * 100:.0f}%)",
          f"  before the 2026-03-29 clock change: {sh(s[by_half.to_numpy()]) * 100:.0f}% of {int(by_half.sum())};  after: {sh(s[~by_half.to_numpy()]) * 100:.0f}% "
          f"of {int((~by_half).sum())}",
          f"  BUY {sh(s[(nq.side.str.upper() == 'BUY').to_numpy()]) * 100:.0f}% / SELL {sh(s[(nq.side.str.upper() == 'SELL').to_numpy()]) * 100:.0f}%"]
    L += ["", "PREDICTIONS",
          f"  K1 NASDAQ entries not uniform (chi-square p {P['NASDAQ entries'][0]:.3f}) -> {'RIGHT' if P['NASDAQ entries'][0] < 0.05 else 'WRONG'}",
          f"  K2 cluster broad, middle half >= 8 s ({q3 - q1:.0f} s) -> {'RIGHT' if q3 - q1 >= 8 else 'WRONG'}",
          f"  K3 exits and gold entries uniform (p {P['NASDAQ exits'][0]:.2f} / {P['gold entries'][0]:.2f}) -> "
          f"{'RIGHT' if min(P['NASDAQ exits'][0], P['gold entries'][0]) > 0.2 else 'WRONG'}",
          f"  K4 clustered entries bank no more (diff {d:+.2f}, se {se:.2f}) -> {'RIGHT' if abs(d) <= se else 'WRONG'}",
          f"  K5 first trades cluster like follow-ups ({sh(fs) * 100:.0f}% vs {sh(ls_) * 100:.0f}%) -> {'RIGHT' if abs(sh(fs) - sh(ls_)) <= 0.15 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
