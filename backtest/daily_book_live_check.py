"""The daily breakout book live: 1 winner in 18 closed trades on the two paper accounts - broken, unlucky, or what the backtest always was? (2026-11-12)

THE USER: "daily breakout is shit in my opinion, not a single positive trade, look into that" (and why the fresh account is so far down).
Live (combo_final_trades.csv on the VM, read 2026-11-12): main 10 closed daily trades, 1 won, -$35.18; fresh 8 closed, 0 won, -$34.72. The
same 8 signals on both accounts (main also has 2 from before fresh started). Three trades lost 45-57% each (AKE, AIN, JCT).

THE BOOK (final_books.py / backtest daily_combos.gen with mean_n=20): daily Bollinger(30, 1.5) break on the PIT top-40, enter at the next open,
exit at the first daily CLOSE under the 20-day mean (cap 30 days), no stop, x0.5 of a slot. Its backtest says it lives on a few pump trades.

QUESTIONS (predictions written before running)
  D1  The backtest's win rate per trade is under 35% (a pump-catcher).                                                       (75%)
  D2  A stretch of 18 consecutive trades with at most 1 winner happens in at least 5% of the backtest's 18-trade stretches.     (55%)
  D3  Trades losing 40%+ (exit only at a daily close, no stop) are at least 2% of backtest trades, and at least half of them are
      in coins that were later delisted or fell out of the top-40.                                                           (50% - the second half is not measured here, dropped)
  D4  The book's 2025-26 trades are worse than its 2020-24 trades per trade.                                                  (70%)

RESULT (2026-11-12, logs/daily_book_live_check.txt): the losing STREAK is normal for this book, the SIZE of the live losers is not. D1, D2, D4 right; D3 wrong.
  Backtest 5,064 trades: 34% won, median trade -5.5%, the best 5% of trades carry 135% of the profit (a pump-catcher); 2025-26 +3.2% a trade at
  27-28% won, against +7.1% before. 18 trades with <= 1 winner: 9.4% of all 18-trade stretches (6.3% since 2025) - losses come in clusters, so
  1 of 18 is inside the book's own history. But trades losing 40%+ are 0.4% of the backtest and 3 of the 18 live trades (AKE -45%, AIN -57%,
  JCT -56%); AIN and JCT are not in the backtest's universe at all (the data ends 2026-09; they reached the live top-40 by volume after it).

    python -m backtest.daily_book_live_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "daily_book_live_check.txt"
LIVE_WON, LIVE_N = 1, 18


def main():
    from backtest import daily_combos as dc
    cfg = dict(dc.BASE, mean_n=20)
    T = []
    for off in dc.PHASES:
        g = dc.gen(off, cfg)
        g = pd.DataFrame(g) if not isinstance(g, pd.DataFrame) else g
        T.append(g.assign(phase=off))
    T = pd.concat(T, ignore_index=True)
    tin = pd.to_datetime(T["t_in"], unit="ms") if np.issubdtype(T["t_in"].dtype, np.number) else pd.to_datetime(T["t_in"])
    T["t"] = tin
    L = [f"backtest/daily_book_live_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; daily_combos.gen(mean_n=20), PIT top-40, "
         f"3 day boundaries, every signal (no slot limit); {len(T)} trades {T.t.min():%Y-%m-%d} .. {T.t.max():%Y-%m-%d}", ""]
    for off, g in T.groupby("phase"):
        n = g.net.to_numpy()
        L.append(f"  boundary {off:>2}h: {len(g)} trades, won {(n > 0).mean() * 100:.0f}%, mean {n.mean() * 100:+.2f}%, median {np.median(n) * 100:+.2f}%, "
                 f"losers under -40%: {(n < -0.4).mean() * 100:.1f}%, best 5% of trades carry {np.sort(n)[-max(1, len(n) // 20):].sum() / n.sum() * 100:.0f}% of the sum")
    by = T.groupby(T.t.dt.year).net.agg(["size", "mean", lambda x: (x > 0).mean()])
    L.append("  by year (n, mean, won): " + "  ".join(f"{y} {int(a)} {b * 100:+.2f}% {c * 100:.0f}%" for y, (a, b, c) in by.iterrows()))
    streak = []
    for off, g in T.groupby("phase"):
        w = (g.sort_values("t").net.to_numpy() > 0).astype(int)
        s = np.convolve(w, np.ones(LIVE_N, int), mode="valid")
        streak.append(s)
    s = np.concatenate(streak)
    recent = []
    for off, g in T[T.t >= "2025-01-01"].groupby("phase"):
        w = (g.sort_values("t").net.to_numpy() > 0).astype(int)
        if len(w) >= LIVE_N:
            recent.append(np.convolve(w, np.ones(LIVE_N, int), mode="valid"))
    r = np.concatenate(recent) if recent else np.array([])
    wr = (T.net > 0).mean()
    from math import comb
    p_binom = sum(comb(LIVE_N, k) * wr ** k * (1 - wr) ** (LIVE_N - k) for k in range(LIVE_WON + 1))
    L += ["", f"  stretches of {LIVE_N} consecutive trades with <= {LIVE_WON} winner: {(s <= LIVE_WON).mean() * 100:.1f}% of all stretches; "
          f"since 2025: {(r <= LIVE_WON).mean() * 100 if len(r) else float('nan'):.1f}%; binomial at the backtest's {wr * 100:.0f}% win rate: {p_binom * 100:.1f}%"]
    old, new = T[T.t < "2025-01-01"].net, T[T.t >= "2025-01-01"].net
    L += ["", "PREDICTIONS",
          f"  D1 win rate < 35% ({wr * 100:.0f}%) -> {'RIGHT' if wr < 0.35 else 'WRONG'}",
          f"  D2 <= {LIVE_WON} winner in {LIVE_N} in >= 5% of stretches ({(s <= LIVE_WON).mean() * 100:.1f}%) -> {'RIGHT' if (s <= LIVE_WON).mean() >= 0.05 else 'WRONG'}",
          f"  D3 losers under -40% >= 2% of trades ({(T.net < -0.4).mean() * 100:.1f}%) -> {'RIGHT' if (T.net < -0.4).mean() >= 0.02 else 'WRONG'} (second half not measured)",
          f"  D4 2025-26 worse per trade than 2020-24 ({new.mean() * 100:+.2f}% vs {old.mean() * 100:+.2f}%) -> {'RIGHT' if new.mean() < old.mean() else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
