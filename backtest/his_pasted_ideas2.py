"""THREE MORE IDEAS FROM AN OUTSIDE WRITE-UP THE USER PASTED (2026-10-13)

TEST 1   "self-fulfilling flow: he broadcasts, copiers pile in". CME NQ trades (nq_trades_windows.pkl) in [t+1, t+20 s]
         after his click vs [t-15, t]: trades a second, median trade size, share of 1-2 lot trades, aggressor volume his
         way - his clicks against his sittings' other moments (same side), and against the sittings' moments whose next
         60 s moved >= 7 points his way (an ordinary move of the same size).
TEST 2   "a CME iceberg at his entry price". NOT testable as written: the cached trades and book carry no prices. The
         nearest measure is his_absorb.py (s53: ruled out).
TEST 3   "0DTE strike magnet": does his side point toward the nearest 25 / 50 / 100 level? On his own (futures-priced)
         fills AND on the cash index at his second (Exness USTECm ~ NDX, the options' underlying); and is he unusually often
         5-12 points from one?

REGISTERED BEFORE THE RUN (2026-10-13)
    1. Test 1: after-click intensity / small-lot share at his clicks within +-25% of ordinary 7-point moves.
    3. Test 3: agreement with the nearest level 35-65% for all six cells; the 5-12-point zone at a rate within +-15
       points of the sittings' moments.

RESULT (2026-10-13, logs/his_pasted_ideas2.txt) - ALL RULED OUT.
    Test 1 RIGHT: after his click the tape looks like any 7-point move - 9.6 trades a second (same-size moves 10.8), median
      1 lot, 91% small trades (92%), net aggressor share his way 0.10 (0.10); intensity after / before 0.86x (0.98x). No
      crowd piling in.
    Test 3 WRONG on one cell only: toward the nearest 25 / 50 / 100 level 48 / 57 / 50% on his fills, 52 / 45 / 31% on the
      cash index; the 31% (p 0.02, Holm over six 0.12) points AWAY from the level, the opposite of a magnet. 5-12 points
      from a 50: 33% vs 25% (inside the registered +-15).

    python -m backtest.his_pasted_ideas2
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402

LOG = ROOT / "logs" / "his_pasted_ideas2.txt"


def main():
    from scipy.stats import binomtest
    T = pd.concat(pickle.loads((ROOT / "strategy_analysis" / "data" / "nq_trades_windows.pkl").read_bytes()).values())
    T = T.drop_duplicates().sort_values("ns", kind="stable")
    ns, sz, ag = T.ns.to_numpy(), T["size"].to_numpy(), T.aggr.to_numpy()

    def win(a, b):
        i, j = np.searchsorted(ns, a, "left"), np.searchsorted(ns, b, "left")
        return sz[i:j], ag[i:j]

    x = TP.entries()
    ticks = pickle.loads(TP.TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None or r.t < 960:
            continue
        ts, mid, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).value
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if r.t + 60 * m > 960 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            at = base + int(t * 1e9)
            sa, aa = win(at - 15 * 10**9, at)
            sb, ab = win(at + 10**9, at + 20 * 10**9)
            if len(sb) == 0 or len(sa) == 0:
                continue
            i0 = np.searchsorted(ts, t, "right") - 1
            i1 = np.searchsorted(ts, t + 60, "right") - 1
            mv = r.s * (mid[i1] - mid[i0])
            p = mid[i0]
            rows.append(dict(who=who, s=r.s, mv=mv, rate_b=len(sb) / 19, rate_a=len(sa) / 15, med_b=np.median(sb),
                             small_b=np.mean(sb <= 2), his_way_b=(sb * ag[0:0].sum() if False else (sb * ab).sum() * r.s) / sb.sum(),
                             cash=p))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    M = N[N.mv >= 7]
    out = [f"backtest/his_pasted_ideas2.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", "",
           f"TEST 1 - CME tape in the 20 s after the click ({len(H)} his, {len(N)} sitting moments, {len(M)} of them followed by a "
           f">= 7-point move his side)"]
    for col, name in (("rate_b", "trades a second, t+1..t+20"), ("med_b", "median trade size (lots)"),
                      ("small_b", "share of 1-2 lot trades"), ("his_way_b", "aggressor volume his way (net share)")):
        out.append(f"   {name:<40} his {H[col].median():6.3f} | sittings {N[col].median():6.3f} | same-size moves {M[col].median():6.3f}")
    ratio = H.rate_b.median() / M.rate_b.median()
    small_ratio = H.small_b.median() / M.small_b.median()
    out.append(f"   intensity after / before the click: his {np.median(H.rate_b / H.rate_a):.2f}x, same-size moves {np.median(M.rate_b / M.rate_a):.2f}x")
    out.append("")

    # TEST 3
    s = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    n = s[s.symbol.str.startswith("NASDAQ")]
    fill_side = np.where(n.side.str.upper() == "BUY", 1, -1)
    out.append("TEST 3 - does his side point toward the nearest round level?")
    cells = []
    for scale, prices, sides in (("his fills (futures scale)", n.open_price.to_numpy(), fill_side),
                                 ("cash index at his second", H.cash.to_numpy(), H.s.to_numpy())):
        for k in (25, 50, 100):
            lvl = np.round(prices / k) * k
            d = lvl - prices
            ok = d != 0
            agree = (np.sign(d[ok]) == sides[ok])
            p = binomtest(int(agree.sum()), int(ok.sum()), 0.5).pvalue
            cells.append(agree.mean())
            out.append(f"   {scale:<28} nearest {k:>3}: toward it {agree.mean() * 100:4.0f}% of {ok.sum()} (p {p:.2f}); "
                       f"median distance {np.median(np.abs(d)):.1f}")
    zh = np.mean((np.abs(np.round(H.cash / 50) * 50 - H.cash) >= 5) & (np.abs(np.round(H.cash / 50) * 50 - H.cash) <= 12))
    zn = np.mean((np.abs(np.round(N.cash / 50) * 50 - N.cash) >= 5) & (np.abs(np.round(N.cash / 50) * 50 - N.cash) <= 12))
    out.append(f"   5-12 points from the nearest 50 (cash): his {zh * 100:.0f}% vs sittings {zn * 100:.0f}%")
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 his after-click intensity {ratio:.2f}x and small-lot share {small_ratio:.2f}x of same-size moves, within 0.75-1.25 -> "
            f"{'RIGHT' if 0.75 <= ratio <= 1.25 and 0.75 <= small_ratio <= 1.25 else 'WRONG'}",
            f"  3 agreement " + ", ".join(f"{c * 100:.0f}%" for c in cells) + f" within 35-65%, zone {zh * 100:.0f} vs {zn * 100:.0f} within 15 -> "
            f"{'RIGHT' if all(0.35 <= c <= 0.65 for c in cells) and abs(zh - zn) <= 0.15 else 'WRONG'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
