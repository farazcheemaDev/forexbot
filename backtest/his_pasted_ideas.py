"""TWO IDEAS FROM AN OUTSIDE WRITE-UP THE USER PASTED (2026-10-13)

IDEA 1   "bots fire at seconds 00-04 of each minute; he waits to see how that flow is absorbed, then clicks 5-24 s in".
         Real CME NQ aggressor flow (strategy_analysis/data/nq_trades_windows.pkl, Databento, his windows) in seconds
         00-04 of the minute he clicks in (signed buy - sell lots), against his side - followed and faded - and ranked
         among his sittings' other moments taken at the SAME second of their minute. Plus the rule at those moments
         (+-7 race on Exness mid, both directions).
IDEA 2   "at 11:00 New York European funds execute; a European index telegraphs NASDAQ by seconds". Exness DE30m (DAX)
         and STOXX50m ticks from MT5: their move over the 3 / 10 / 30 / 60 s before his NASDAQ clicks, all and the
         top-of-hour ones (minutes :00-:04), against his side.

REGISTERED BEFORE THE RUN (2026-10-13)
    1. Idea 1: agreement (follow or fade) 35-65%; rank 0.40-0.60; the rule's race 45-58% either way.
    2. Idea 2: agreement 35-65% at every window for both indices; at the top-of-hour clicks too (few, so wide).
    LEAD LINE: any agreement >= 75% with binomial p < 0.01.

RESULT (2026-10-13, logs/his_pasted_ideas.txt) - BOTH RULED OUT; predictions right; lead line not hit.
    Idea 1: his side follows the 00-04 s flow 51% / fades it 49% (39 entries); rank 0.48; as a rule 51% / 49%.
    Idea 2: DAX 49-53%, STOXX 50 36-50% at 3-60 s (21-41 clicks, every p >= 0.16); top-of-hour subsets 22-67% on 9-12.

    python -m backtest.his_pasted_ideas      (needs MT5 running)
"""
from __future__ import annotations

import pickle
import sys
from datetime import timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

LOG = ROOT / "logs" / "his_pasted_ideas.txt"


def main():
    from scipy.stats import binomtest, wilcoxon
    out = ["backtest/his_pasted_ideas.py, " + f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", ""]
    T = pd.concat(pickle.loads((ROOT / "strategy_analysis" / "data" / "nq_trades_windows.pkl").read_bytes()).values())
    T = T.drop_duplicates().sort_values("ns", kind="stable")
    ns, sz, ag = T.ns.to_numpy(), T["size"].to_numpy(), T.aggr.to_numpy()
    cs = np.r_[0, np.cumsum(sz * ag)]
    ct = np.r_[0, np.cumsum(sz)]

    def open5(at_ns):
        m0 = at_ns - at_ns % (60 * 10**9)                               # start of the minute
        if at_ns - m0 < 5 * 10**9:                                    # clicked inside 00-04: use the previous minute's
            m0 -= 60 * 10**9
        i, j = np.searchsorted(ns, m0, "left"), np.searchsorted(ns, m0 + 5 * 10**9, "left")
        return (cs[j] - cs[i], ct[j] - ct[i])

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
            f, tot = open5(base + int(t * 1e9))
            if tot == 0:
                continue
            rows.append(dict(entry=r.Index, who=who, s=r.s, f=f, up=race2(ts, mid, t, 1, 600, 7, 7)))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    v = H[H.f != 0]
    fol = (np.sign(v.f) == v.s)
    p1 = binomtest(int(fol.sum()), len(v), 0.5).pvalue
    rk = []
    for _, g in D.groupby("entry"):
        h, n = g[g.who == "his"], g[g.who == "near"]
        if len(h) and len(n) >= 10:
            hv, nv = h.f.iat[0] * h.s.iat[0], (n.f * n.s).to_numpy()
            rk.append((nv < hv).mean() + 0.5 * (nv == hv).mean())
    u = N.dropna(subset=["up"])
    u = u[u.f != 0]
    top = u[u.f.abs() >= u.f.abs().quantile(0.8)]
    follow_win = np.where(top.f > 0, top.up, 1 - top.up).mean()
    out += ["IDEA 1 - CME aggressor flow in seconds 00-04 of the minute he clicks in",
            f"   {len(v)} of his entries with flow there: his side FOLLOWS it {fol.mean() * 100:.0f}%, FADES it {(1 - fol.mean()) * 100:.0f}% (p {p1:.3f})",
            f"   rank of his-side flow among his sittings' moments (same second of the minute): {np.mean(rk):.2f} (p {wilcoxon(np.array(rk) - 0.5).pvalue:.3f}, {len(rk)} entries)",
            f"   rule at the sittings' moments, top 20% |flow| ({len(top)}): follow wins {follow_win * 100:.0f}% of +-7 races, fade {100 - follow_win * 100:.0f}%", ""]
    a1 = max(fol.mean(), 1 - fol.mean())

    # IDEA 2
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    out.append("IDEA 2 - DAX / STOXX 50 (Exness ticks) moving his way in the seconds before his NASDAQ click")
    a2 = []
    for sym in ("DE30m", "STOXX50m"):
        rec = {w: [] for w in (3, 10, 30, 60)}
        top_rec = {w: [] for w in (3, 10, 30, 60)}
        for r in x.itertuples():
            t0 = pd.Timestamp(r.utc).tz_localize("UTC")
            tk = mt5.copy_ticks_range(sym, (t0 - pd.Timedelta(seconds=90)).to_pydatetime(),
                                      (t0 + pd.Timedelta(seconds=1)).to_pydatetime(), mt5.COPY_TICKS_ALL)
            if tk is None or len(tk) < 5:
                continue
            tt = tk["time_msc"].astype(np.int64)
            mid = (tk["bid"] + tk["ask"]) / 2
            now_ms = t0.value // 10**6

            def at(ms):
                i = np.searchsorted(tt, ms, "right") - 1
                return mid[i] if i >= 0 else np.nan
            et = t0.tz_convert("America/New_York")
            for w in rec:
                mv = at(now_ms) - at(now_ms - w * 1000)
                if np.isfinite(mv) and mv != 0:
                    rec[w].append(np.sign(mv) == r.s)
                    if et.minute <= 4:
                        top_rec[w].append(np.sign(mv) == r.s)
        cells = []
        for w in rec:
            a = np.array(rec[w])
            pa = binomtest(int(a.sum()), len(a), 0.5).pvalue if len(a) else np.nan
            b = np.array(top_rec[w])
            cells.append(f"{w} s: {a.mean() * 100 if len(a) else np.nan:.0f}% of {len(a)} (p {pa:.2f}); top of hour {b.mean() * 100 if len(b) else np.nan:.0f}% of {len(b)}")
            if len(a):
                a2.append((a.mean(), pa))
        out.append(f"   {sym}: " + " | ".join(cells))
    mt5.shutdown()
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 idea 1: agreement {a1 * 100:.0f}% within 35-65%, rank {np.mean(rk):.2f} within 0.40-0.60, rule {follow_win * 100:.0f}% within 45-58% -> "
            f"{'RIGHT' if 0.35 <= a1 <= 0.65 and 0.4 <= np.mean(rk) <= 0.6 and 0.42 <= follow_win <= 0.58 else 'WRONG'}",
            f"  2 idea 2: every cell 35-65%: " + ", ".join(f"{m * 100:.0f}" for m, _ in a2) +
            f" -> {'RIGHT' if all(0.35 <= m <= 0.65 for m, _ in a2) else 'WRONG'}"]
    lead = (a1 >= 0.75 and p1 < 0.01) or any(m >= 0.75 and p < 0.01 for m, p in a2)
    out.append(f"  LEAD LINE: {'HIT' if lead else 'not hit'}")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
