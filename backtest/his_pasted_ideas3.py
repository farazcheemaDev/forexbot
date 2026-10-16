"""THREE MORE IDEAS FROM A THIRD OUTSIDE WRITE-UP (2026-10-13)

TEST 1   "block trades step in his way on the pullback while 1-2 lot retail sells into it": CME NQ trades in [t-15 s, t]
         (nq_trades_windows.pkl) - net aggressor sign of 1-2 lot trades, of >= 5 and >= 10 lot trades, and the block share
         of volume, at his clicks vs his sittings' other moments. (s37 had the >= 5-lot sign at 5-120 s: 45-63%.)
TEST 2   "his +7 zone was empty in the last 15 minutes, the adverse zone crowded": 1-minute mid bars from Exness ticks;
         occupancy = how many of the last 15 candle BODIES overlap the 7-point zone ahead vs the 7-point zone behind.
         Does his side point to the emptier zone? And as a rule at the sittings' moments (+-7 race on the mid).
TEST 3   "an audio squawk ahead of the text wires": headlines (his_headlines.py cache: FinancialJuice, Walter Bloomberg,
         Breaking Market News + 1) arriving 1-25 s AFTER his clicks vs his sittings' other moments.

REGISTERED BEFORE THE RUN (2026-10-13)
    1. Test 1: block-sign agreement with his side 35-65%, retail-sign 35-65%; block share rank 0.40-0.60.
    2. Test 2: his side toward the emptier zone 35-65%; the rule wins 45-58%.
    3. Test 3: after-click headline share within 0.5x-2x of the sittings' (the earlier before-click test: 0.48-0.88x).
    LEAD LINE: any agreement >= 75% with p < 0.01, or a headline excess >= 3x with p < 0.01.

RESULT (2026-10-13, logs/his_pasted_ideas3.txt) - all three predictions right; nothing usable.
    Test 1: 1-2 lot sign his way 48%; >= 5 lots 61% of 31 (p 0.28); >= 10 lots 65% of 17 (p 0.33); block share a little
      higher before his clicks (median 0.098 vs 0.067, rank 0.60, p 0.03 - one of several cells, nothing near Holm). As a
      rule the block sign is worthless: trading with it wins 48% (5+) / 49% (10+) of +-7 races on 1,089 / 352 moments.
    Test 2: his side points to the emptier 7-point zone 52% (p 1.00); the rule wins 52%.
    Test 3: a headline 1-25 s AFTER his click 26% vs 30% of other moments (0.87x) - no audio-squawk footprint.

    python -m backtest.his_pasted_ideas3
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
from backtest.his_race_curve import race2  # noqa: E402

LOG = ROOT / "logs" / "his_pasted_ideas3.txt"


def main():
    from scipy.stats import binomtest, wilcoxon
    T = pd.concat(pickle.loads((ROOT / "strategy_analysis" / "data" / "nq_trades_windows.pkl").read_bytes()).values())
    T = T.drop_duplicates().sort_values("ns", kind="stable")
    ns, sz, ag = T.ns.to_numpy(), T["size"].to_numpy(), T.aggr.to_numpy()
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
            i, j = np.searchsorted(ns, at - 15 * 10**9, "left"), np.searchsorted(ns, at, "left")
            s_, a_ = sz[i:j], ag[i:j]
            small, b5, b10 = s_ <= 2, s_ >= 5, s_ >= 10
            f = dict(sm=(s_ * a_)[small].sum(), b5=(s_ * a_)[b5].sum(), b10=(s_ * a_)[b10].sum(),
                     bshare=s_[b5].sum() / max(s_.sum(), 1))
            # Test 2: last 15 one-minute mid candles
            m0 = np.floor(t / 60) * 60
            edges = m0 - 60 * np.arange(15, -1, -1)
            k = np.searchsorted(ts, edges, "left")
            occ_up = occ_dn = 0
            p = mid[np.searchsorted(ts, t, "right") - 1]
            for a, b in zip(k[:-1], k[1:]):
                if b - a < 2:
                    continue
                o, c = mid[a], mid[b - 1]
                lo, hi = min(o, c), max(o, c)
                occ_up += (hi >= p) and (lo <= p + 7)
                occ_dn += (lo <= p) and (hi >= p - 7)
            rows.append(dict(entry=r.Index, who=who, s=r.s, occ_up=occ_up, occ_dn=occ_dn,
                             up=race2(ts, mid, t, 1, 600, 7, 7), utc=pd.Timestamp(at), **f))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    out = [f"backtest/his_pasted_ideas3.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(H)} of his NASDAQ entries, "
           f"{len(N)} sitting moments", "", "TEST 1 - CME trades in the 15 s before his click, signed his way"]
    ags = []
    for col, name in (("sm", "1-2 lot trades"), ("b5", ">= 5 lot trades"), ("b10", ">= 10 lot trades")):
        v = H[H[col] != 0]
        a = (np.sign(v[col]) == v.s)
        p = binomtest(int(a.sum()), len(v), 0.5).pvalue if len(v) else np.nan
        ags.append(a.mean())
        out.append(f"   {name:<18} net sign his way {a.mean() * 100:4.0f}% of {len(v)} (p {p:.2f})")
    rk = []
    for _, g in D.groupby("entry"):
        h, n = g[g.who == "his"], g[g.who == "near"]
        if len(h) and len(n) >= 10:
            rk.append((n.bshare < h.bshare.iat[0]).mean() + 0.5 * (n.bshare == h.bshare.iat[0]).mean())
    out.append(f"   block share of volume: his median {H.bshare.median():.3f} vs {N.bshare.median():.3f}; rank {np.mean(rk):.2f} "
               f"(p {wilcoxon(np.array(rk) - 0.5).pvalue:.2f})")
    both = H[(H.sm != 0) & (H.b5 != 0)]
    pat = ((np.sign(both.b5) == both.s) & (np.sign(both.sm) == -both.s)).mean()
    patn = ((np.sign(N.b5) == N.s) & (np.sign(N.sm) == -N.s))[(N.sm != 0) & (N.b5 != 0)].mean()
    out.append(f"   the exact pattern (blocks his way AND small lots against him): his {pat * 100:.0f}% vs sittings {patn * 100:.0f}%")
    for col in ("b5", "b10"):
        u = N[(N[col] != 0)].dropna(subset=["up"])
        w = np.where(u[col] > 0, u.up, 1 - u.up).mean()
        out.append(f"   rule at the sittings' moments: trade WITH the {col[1:]}+ lot net sign of the last 15 s ({len(u)}): wins {w * 100:.0f}% of +-7 races")
    out.append("")
    # TEST 2
    h2 = H[H.occ_up != H.occ_dn]
    toward = np.where(h2.occ_up < h2.occ_dn, 1, -1) == h2.s
    p2 = binomtest(int(toward.sum()), len(h2), 0.5).pvalue
    n2 = N[(N.occ_up != N.occ_dn)].dropna(subset=["up"])
    side = np.where(n2.occ_up < n2.occ_dn, 1, 0)
    rule = (side == n2.up).mean()
    out += ["TEST 2 - the 7-point zone ahead vs behind: candle bodies from the last 15 minutes in each",
            f"   his side points to the emptier zone {toward.mean() * 100:.0f}% of {len(h2)} (p {p2:.2f}); median occupancy ahead "
            f"{np.median(np.where(H.s > 0, H.occ_up, H.occ_dn)):.0f} vs behind {np.median(np.where(H.s > 0, H.occ_dn, H.occ_up)):.0f}",
            f"   rule at the sittings' moments ({len(n2)}): toward the emptier zone wins {rule * 100:.0f}% of +-7 races", ""]
    # TEST 3
    Hh = pd.read_json(ROOT / "strategy_analysis" / "data" / "headlines" / "headlines.jsonl", lines=True)
    hts = np.sort(Hh.ts.to_numpy())
    ck = (H.utc.astype("int64") // 10**9).to_numpy()
    co = (N.utc.astype("int64") // 10**9).to_numpy()

    def share(xs, a, b):
        return (np.searchsorted(hts, xs + b, "right") - np.searchsorted(hts, xs + a, "left")) > 0
    sc, so = share(ck, 1, 25), share(co, 1, 25)
    p3 = binomtest(int(sc.sum()), len(sc), max(so.mean(), 1e-6)).pvalue
    out += ["TEST 3 - a headline on the text wires 1-25 s AFTER the click",
            f"   his {sc.mean() * 100:.1f}% ({int(sc.sum())} of {len(sc)}) vs sittings {so.mean() * 100:.1f}% -> {sc.mean() / max(so.mean(), 1e-9):.2f}x (p {p3:.2f}); "
            f"{len(Hh)} headlines in the cache", ""]
    ratio3 = sc.mean() / max(so.mean(), 1e-9)
    out += ["REGISTERED PREDICTIONS",
            f"  1 sign agreement " + ", ".join(f"{a * 100:.0f}%" for a in ags) + f" within 35-65%, block rank {np.mean(rk):.2f} within 0.40-0.60 -> "
            f"{'RIGHT' if all(0.35 <= a <= 0.65 for a in ags) and 0.4 <= np.mean(rk) <= 0.6 else 'WRONG'}",
            f"  2 toward the emptier zone {toward.mean() * 100:.0f}% within 35-65%, rule {rule * 100:.0f}% within 45-58% -> "
            f"{'RIGHT' if 0.35 <= toward.mean() <= 0.65 and 0.45 <= rule <= 0.58 else 'WRONG'}",
            f"  3 after-click headlines {ratio3:.2f}x within 0.5-2x -> {'RIGHT' if 0.5 <= ratio3 <= 2 else 'WRONG'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
