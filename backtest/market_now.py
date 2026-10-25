"""THIS KIND OF MARKET, IN THE BACKTEST - how often it comes, what the machine did in it, and what came after (2026-10-25)

THE USER (2026-10-25): "it's going good right in this kind of market - in the backtest this kind of market comes how often".
The market since the main account started (2026-10-09 .. 10-25, 17 days; Binance daily closes):
    BTC's label (market_neutral.btc_regime: price vs its 50-day average and that average's 20-day slope) BULL on 14 of
    17 days, yet BTC itself -2.5%; the PIT top-40 altcoins' median coin -9.8%, i.e. 7.3% BEHIND BTC (30 days: -15.6%).
    A stalling bull with an altcoin sell-off under it.
THE SAME KIND OF STRETCH in 2020-01 .. 2026-09: every 17-day window whose days are mostly BTC-BULL and whose top-40 alts
(PIT, dead coins in, median coin) fell 5% or more behind BTC. For those windows: how often they occur, the deployed
machine's return in them (machine_fixes.py F1+F2, 10 orderings, $300; trend gains shrunk, the rest raw), where the main
account's live -13.7% sits among them, and the machine's next 30 / 90 days from the window's end.

REGISTERED BEFORE THE RUN (2026-10-25)
  M1 such windows are 8-20% of all 17-day windows.
  M2 the machine's median return in them is negative, and the live -13.7% sits above their 10th percentile.
  M3 over the 90 days after them the machine is up in at least 60% of cases.

RESULT (2026-10-25, logs/market_now.txt; BACKTEST) - a COMMON market, usually survived, usually followed by gains. M1 M3
RIGHT; M2 WRONG (the machine's median in such stretches is POSITIVE, +7.1%).
  Such stretches are 16.0% of all 17-day windows, in 34 different months of 2020-26 (roughly one every two months).
  The machine in them: median +7.1%, 39% down, 10th / 25th percentile -17.8% / -8.1% (all windows: +5.5%, 38% down).
  The main account's live -13.7% = the 16th percentile of windows like now (10th of all) - bad, inside the normal range.
  After them: next 30 days up 78%, next 90 up 88% (any window: 69% / 83%). By period, next 90 days up: 2020-21 100%,
  2022-23 86%, 2024 73%, 2025-26 94%. The SIZE of those 90-day medians (+23% .. +355%) is the bull runs these stretches
  sat in, on a backtest the live record is so far running below (10th-16th percentile) - read the direction, not the size.

    python -m backtest.market_now
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "market_now.txt"
N_DAYS, ALT_GAP, LIVE = 17, -0.05, -0.137


def main():
    from backtest.crowd_combo import machine
    from backtest.market_neutral import NON_CRYPTO, btc_regime, load_panel
    from backtest.wide_book import eligibility
    C, _, _ = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    lab = btc_regime(C)
    el = eligibility(40)
    months = C.index.strftime("%Y-%m")
    M = machine()
    cal = M[0].index
    rows = []
    for i in range(0, len(cal) - N_DAYS):
        a, z = cal[i], cal[i + N_DAYS]
        if a not in C.index or z not in C.index:
            continue
        m = a.strftime("%Y-%m")
        alts = [s for s, ms in el.items() if m in ms and s != "BTCUSDT" and s[:-4] not in NON_CRYPTO and s in C.columns]
        r = (C.loc[z, alts] / C.loc[a, alts] - 1).dropna()
        if len(r) < 20:
            continue
        rb = C.at[z, "BTCUSDT"] / C.at[a, "BTCUSDT"] - 1
        bull = (lab.loc[a:z].iloc[1:] == "bull").mean()
        mach = [float(np.prod(1 + x.loc[a:z].iloc[1:].to_numpy()) - 1) for x in M]
        nxt = {}
        for h in (30, 90):
            if i + N_DAYS + h < len(cal):
                b2 = cal[i + N_DAYS + h]
                nxt[h] = float(np.median([np.prod(1 + x.loc[z:b2].iloc[1:].to_numpy()) - 1 for x in M]))
        rows.append(dict(a=a, z=z, btc=rb, alt=r.median(), gap=r.median() - rb, bull=bull, mach=float(np.median(mach)),
                         mach_all=mach, n30=nxt.get(30), n90=nxt.get(90)))
    D = pd.DataFrame(rows)
    like = D[(D.bull > 0.5) & (D.gap <= ALT_GAP)]
    allm = np.concatenate(D.mach_all.to_numpy())
    likem = np.concatenate(like.mach_all.to_numpy())
    pct = lambda v, x: float((x < v).mean() * 100)  # noqa: E731
    eps = like.a.dt.to_period("M").nunique()
    L = [f"backtest/market_now.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {N_DAYS}-day windows {D.a.min():%Y-%m} .. "
         f"{D.z.max():%Y-%m}; the deployed machine (10 orderings, $300); BACKTEST", "",
         f"   all {N_DAYS}-day windows: {len(D):,}; BTC-BULL most days: {(D.bull > 0.5).mean() * 100:.0f}%",
         f"   LIKE NOW (BTC-BULL most days AND top-40 alts >= {-ALT_GAP:.0%} behind BTC): {len(like):,} windows = "
         f"{len(like) / len(D) * 100:.1f}% of all, in {eps} distinct months",
         "",
         f"   the machine over {N_DAYS} days            all windows        like now",
         f"      median                         {np.median(allm) * 100:>+7.1f}%          {np.median(likem) * 100:>+7.1f}%",
         f"      10th / 25th percentile    {np.percentile(allm, 10) * 100:>+7.1f}% / {np.percentile(allm, 25) * 100:>+6.1f}%   "
         f"{np.percentile(likem, 10) * 100:>+7.1f}% / {np.percentile(likem, 25) * 100:>+6.1f}%",
         f"      share of windows down          {(allm < 0).mean() * 100:>6.0f}%           {(likem < 0).mean() * 100:>6.0f}%",
         f"   the main account's live {LIVE:+.1%}: the {pct(LIVE, allm):.0f}th percentile of all windows, the "
         f"{pct(LIVE, likem):.0f}th of windows like now",
         "",
         f"   AFTER a window like now (machine, median of the orderings): next 30 days up in "
         f"{(like.n30.dropna() > 0).mean() * 100:.0f}% (median {like.n30.median() * 100:+.1f}%), next 90 days up in "
         f"{(like.n90.dropna() > 0).mean() * 100:.0f}% (median {like.n90.median() * 100:+.1f}%)",
         f"   after ANY window: next 30 days up {(D.n30.dropna() > 0).mean() * 100:.0f}% (median {D.n30.median() * 100:+.1f}%), "
         f"90 days up {(D.n90.dropna() > 0).mean() * 100:.0f}% (median {D.n90.median() * 100:+.1f}%)",
         "",
         "   AFTER a window like now, by period (is the recovery only the big bulls?):"]
    for lab_, a_, z_ in (("2020-21", "2020", "2022"), ("2022-23", "2022", "2024"), ("2024", "2024", "2025"),
                         ("2025-26", "2025", "2027")):
        g = like[(like.a >= a_) & (like.a < z_)]
        if len(g):
            L.append(f"      {lab_}: {len(g):>3} windows | machine in them {g.mach.median() * 100:+.1f}% | next 30 days up "
                     f"{(g.n30.dropna() > 0).mean() * 100:.0f}% (median {g.n30.median() * 100:+.1f}%) | next 90 up "
                     f"{(g.n90.dropna() > 0).mean() * 100:.0f}% (median {g.n90.median() * 100:+.1f}%)")
    L += ["",
         "   when it happened (start months, windows): " + ", ".join(f"{p} {n}" for p, n in like.a.dt.to_period("M").value_counts().sort_index().items())]
    m1 = 8 <= len(like) / len(D) * 100 <= 20
    m2 = np.median(likem) < 0 and LIVE > np.percentile(likem, 10)
    m3 = (like.n90.dropna() > 0).mean() >= 0.6
    L += ["", "REGISTERED PREDICTIONS",
          f"  M1 8-20% of windows: {len(like) / len(D) * 100:.1f}% -> {'RIGHT' if m1 else 'WRONG'}",
          f"  M2 median negative and the live -13.7% above their 10th percentile -> {'RIGHT' if m2 else 'WRONG'}",
          f"  M3 up over the next 90 days in >= 60% -> {'RIGHT' if m3 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
