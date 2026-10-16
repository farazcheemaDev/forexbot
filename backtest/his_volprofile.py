"""VOLUME PROFILE - the point of control and the value area, at his clicks and as rules (2026-10-13)

WHY      The last common screen tool never tested on him (his_strategy s58). NASDAQ scalpers read the volume profile:
         where most trading happened (the point of control, POC) and the price band holding 70% of it (the value area,
         VAL..VAH) - yesterday's, and today's as it develops. Classic reads: price returns to the POC; the value-area
         edge is faded back into value; price accepted outside value runs away from it.

DATA     Exness USTECm ticks (strategy_analysis/data/ustec_tick_days.pkl, 181 days 2026-01-02 .. 09-14, 09:30-19:30
         New York). Tick COUNT per 5-point price bin stands in for traded volume (Exness has no exchange volume; quote
         activity tracks trading closely, but this is a proxy and the test says so).
LEVELS   yesterday's cash session (09:30-16:00): pPOC, pVAH / pVAL (the 85th / 15th tick-weighted price percentiles - the
         central 70%, to the 5-point bin); today's DEVELOPING profile from 09:30 to the last completed minute: dPOC, dVAH / dVAL.
RULES    (side at a moment; no signal otherwise)
    R1 back to yesterday's POC (|p - pPOC| >= 10)      R2 back to today's developing POC (|p - dPOC| >= 10)
    R3 fade yesterday's value edge (within 8 points)   R4 fade today's value edge (within 8 points)
    R5 outside yesterday's value: go with it (> 8 out) R6 outside today's value: go with it (> 8 out)
TESTS    A his side vs each rule's side at his entries (binomial, Holm over 6);
         B his distance to the nearest of the six levels, ranked among his sittings' other moments (low = nearer);
         C each rule at every minute 10:00-19:00 on all days, +-7 at the real ask / bid (30-min cap), against a random side
           at the same minutes; tune (first 60% of days) and holdout halves.

REGISTERED BEFORE THE RUN (2026-10-13)
    1. A: every rule agrees with his side 35-65%; nothing survives Holm.
    2. B: rank 0.40-0.60.
    3. C: every rule within +-3 points of the random side's win rate on both halves, and loses the spread.
    LEAD LINE: a rule agreeing >= 75% with his side (Holm p < 0.05) AND beating random by >= 5 points on both halves.

RESULT (2026-10-13, logs/his_volprofile.txt) - RULED OUT; lead line not hit.
    A (39 entries after 10:00): the six rules agree with his side 41 / 52 / 0 (fired once) / 50 / 55 / 50%; Holm p 1.00
      for all. B: his distance to the nearest profile level 14.8 vs 18.8 points, rank 0.45 (p 0.39).
    C (every minute, 181 days): win rates within -2.6..+3.9 points of a random side (the two outside +-3 are R3, which
      flips sign between halves on 1,384-1,927 calls), every rule -1.2..-2.1 points a trade.
    Predictions 1 and 3 read WRONG only on those edges (R3 firing once at his entries; R3's +3.9 holdout / -2.6 tune).

    python -m backtest.his_volprofile
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

LOG = ROOT / "logs" / "his_volprofile.txt"
BIN, NEAR, AWAY, X = 5.0, 8.0, 10.0, 7.0
RULES = ("R1 back to yesterday's POC", "R2 back to today's POC", "R3 fade yesterday's value edge",
         "R4 fade today's value edge", "R5 outside yesterday's value: with it", "R6 outside today's value: with it")


def from_counts(cnt, bmin):
    """POC, VAH, VAL from tick counts per bin (value area = the bins holding the central 70% of ticks)."""
    tot = cnt.sum()
    if tot < 50:
        return np.nan, np.nan, np.nan
    cum = np.cumsum(cnt)
    poc = (np.argmax(cnt) + bmin + 0.5) * BIN
    val = (np.searchsorted(cum, 0.15 * tot) + bmin + 0.5) * BIN
    vah = (np.searchsorted(cum, 0.85 * tot) + bmin + 0.5) * BIN
    return poc, vah, val


def profile(m):
    """POC, VAH, VAL of a tick-price array (tick count per 5-point bin)."""
    if len(m) < 50:
        return np.nan, np.nan, np.nan
    b = np.floor(m / BIN).astype(np.int64)
    return from_counts(np.bincount(b - b.min()), b.min())


def dev_profiles(ts, mid, times):
    """today's developing profile at each of the sorted `times`, from running counts (ticks from 09:30 up to each time)."""
    keep = ts >= 0
    ts, mid = ts[keep], mid[keep]
    b = np.floor(mid / BIN).astype(np.int64)
    bmin = b.min()
    b = b - bmin
    cnt = np.zeros(b.max() + 1, dtype=np.int64)
    ks = np.searchsorted(ts, times, "left")
    out, last = [], 0
    for k in ks:
        if k > last:
            cnt += np.bincount(b[last:k], minlength=len(cnt))
            last = k
        out.append(from_counts(cnt, bmin))
    return out


def sides(p, L):
    """each rule's side (+1 / -1 / 0) at price p given levels L = (pPOC, pVAH, pVAL, dPOC, dVAH, dVAL)."""
    pP, pH, pL, dP, dH, dL = L
    out = []
    for poc in (pP, dP):
        out.append(0 if not np.isfinite(poc) or abs(p - poc) < AWAY else int(np.sign(poc - p)))
    for H, Lo in ((pH, pL), (dH, dL)):
        if not np.isfinite(H):
            out.append(0)
        elif abs(p - H) <= NEAR:
            out.append(-1)
        elif abs(p - Lo) <= NEAR:
            out.append(1)
        else:
            out.append(0)
    for H, Lo in ((pH, pL), (dH, dL)):
        out.append(0 if not np.isfinite(H) else (1 if p > H + NEAR else (-1 if p < Lo - NEAR else 0)))
    return out


def levels_at(day, prev, t):
    ts, mid, _ = day
    pP, pH, pL = (np.nan,) * 3
    if prev is not None:
        pts, pm, _ = prev
        pP, pH, pL = profile(pm[(pts >= 0) & (pts < 23400)])
    dP, dH, dL = dev_profiles(ts, mid, np.array([np.floor(t / 60) * 60]))[0]   # to the last completed minute
    return (pP, pH, pL, dP, dH, dL)


def grid(day):
    ts, mid, spr = day
    g = np.arange(np.ceil(ts[0]), ts[-1], 1.0)
    gi = np.searchsorted(ts, g, "right") - 1
    return g, mid[gi], spr[gi]


def race(gm, gsp, i, side, cap=1800):
    e = gm[i] + side * gsp[i] / 2
    p = side * ((gm[i + 1:i + cap] - side * gsp[i + 1:i + cap] / 2) - e)
    up, dn = np.flatnonzero(p >= X), np.flatnonzero(p <= -X)
    if len(up) and (not len(dn) or up[0] < dn[0]):
        return X
    if len(dn):
        return -X
    return float(p[-1]) if len(p) else 0.0


def main():
    from scipy.stats import binomtest, wilcoxon
    cache = pickle.loads(TP.TICKS.read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    prev_of = {d: (cache[days[i - 1]] if i > 0 else None) for i, d in enumerate(days)}
    x = TP.entries()
    rows = []
    for r in x.itertuples():
        if r.d not in cache or cache[r.d] is None or r.t < 1800:
            continue
        day = cache[r.d]
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if r.t + 60 * m > 1800 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        ts, mid, _ = day
        for who, t in starts:
            i = np.searchsorted(ts, t, "right") - 1
            if i < 0:
                continue
            p = mid[i]
            L = levels_at(day, prev_of[r.d], t)
            sd = sides(p, L)
            dist = np.nanmin([abs(p - v) for v in L]) if np.isfinite(L).any() else np.nan
            rows.append(dict(entry=r.Index, who=who, s=r.s, dist=dist, **{f"R{j + 1}": sd[j] for j in range(6)}))
    D = pd.DataFrame(rows)
    H = D[D.who == "his"]
    out = [f"backtest/his_volprofile.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Exness USTECm ticks, {len(days)} days; "
           f"tick count per {BIN:g}-point bin as volume; {len(H)} of his entries after 10:00 New York, "
           f"{(D.who == 'near').sum()} same-sitting moments", "",
           "A. Does each rule's side agree with HIS side where it fires?"]
    pa = []
    for j, name in enumerate(RULES):
        v = H[H[f"R{j + 1}"] != 0]
        ag = (v[f"R{j + 1}"] == v.s)
        p = binomtest(int(ag.sum()), len(v), 0.5).pvalue if len(v) else np.nan
        pa.append(p)
        out.append(f"   {name:<40} fires at {len(v):2d} of his entries, agrees {ag.mean() * 100 if len(v) else np.nan:5.1f}% (p {p:.3f})")
    m = len(pa)
    holm = sorted(range(m), key=lambda k: pa[k])
    hp = [np.nan] * m
    run = 0.0
    for rank, k in enumerate(holm):
        run = max(run, min(1.0, (m - rank) * pa[k]))
        hp[k] = run
    out.append(f"   Holm-adjusted p: " + ", ".join(f"R{k + 1} {hp[k]:.2f}" for k in range(m)))
    rk = []
    for _, g in D.groupby("entry"):
        h, n = g[g.who == "his"], g[g.who == "near"]
        if len(h) and len(n) >= 10 and np.isfinite(h.dist.iat[0]):
            hv, nv = h.dist.iat[0], n.dist.dropna().to_numpy()
            rk.append((nv < hv).mean() + 0.5 * (nv == hv).mean())
    rk = np.array(rk)
    out.append("")
    out.append(f"B. his distance to the nearest profile level: median {H.dist.median():.1f} pts vs {D[D.who == 'near'].dist.median():.1f}; "
               f"rank {rk.mean():.2f} (p {wilcoxon(rk - 0.5).pvalue:.3f}, {len(rk)} entries; low = nearer)")
    out.append("")
    # C. the rules on every day
    cut = days[int(len(days) * 0.6)]
    rng = np.random.default_rng(3)
    res = {(j, h): ([], []) for j in range(6) for h in ("tune", "HOLDOUT")}
    for di, d in enumerate(days):
        day = cache[d]
        ts, mid, _ = day
        g, gm, gsp = grid(day)
        half = "tune" if d < cut else "HOLDOUT"
        prev = prev_of[d]
        pL = profile(prev[1][(prev[0] >= 0) & (prev[0] < 23400)]) if prev is not None else (np.nan,) * 3
        times = np.arange(1800, min(34200, g[-1] - 1801), 60.0)
        devs = dev_profiles(ts, mid, times)
        for t, dL in zip(times, devs):
            i = int(np.searchsorted(g, t, "right") - 1)
            if i < 0 or i + 1801 >= len(g):
                continue
            sd = sides(gm[i], (*pL, *dL))
            if not any(sd):
                continue
            rs = int(rng.choice([-1, 1]))
            rnd = race(gm, gsp, i, rs)
            for j in range(6):
                if sd[j]:
                    res[(j, half)][0].append(race(gm, gsp, i, sd[j]))
                    res[(j, half)][1].append(rnd)
    out.append("C. Each rule at every minute 10:00-19:00 (overlapping trades), +-7 at real prices vs a random side at the same minutes")
    out.append(f"   {'rule':<40}{'half':>9}{'calls':>8}{'won':>8}{'random':>9}{'diff':>8}{'net pts':>9}")
    cdiff = []
    for j, name in enumerate(RULES):
        for half in ("tune", "HOLDOUT"):
            a, b = np.array(res[(j, half)][0]), np.array(res[(j, half)][1])
            if not len(a):
                continue
            wa, wb = np.mean(a >= X) * 100, np.mean(b >= X) * 100
            cdiff.append((j, half, wa - wb, a.mean()))
            out.append(f"   {name:<40}{half:>9}{len(a):>8,}{wa:>7.1f}%{wb:>8.1f}%{wa - wb:>+8.1f}{a.mean():>+9.2f}")
    out.append("")
    ags = [((H[H[f'R{j + 1}'] != 0][f'R{j + 1}'] == H[H[f'R{j + 1}'] != 0].s).mean()) for j in range(6)]
    out.append("REGISTERED PREDICTIONS")
    out.append(f"  1 A within 35-65% and nothing survives Holm: " + ", ".join(f"{a * 100:.0f}%" for a in ags) + f" (min Holm p "
               f"{np.nanmin(hp):.2f}) -> {'RIGHT' if all(0.35 <= a <= 0.65 for a in ags if np.isfinite(a)) and np.nanmin(hp) >= 0.05 else 'WRONG'}")
    out.append(f"  2 B rank {rk.mean():.2f} within 0.40-0.60 -> {'RIGHT' if 0.4 <= rk.mean() <= 0.6 else 'WRONG'}")
    out.append(f"  3 C within +-3 of random on both halves and net < 0: diffs " + ", ".join(f"{dd:+.1f}" for *_, dd, _ in cdiff) +
               f" -> {'RIGHT' if all(abs(dd) <= 3 and net < 0 for *_, dd, net in cdiff) else 'WRONG'}")
    lead = [RULES[j] for j in range(6) if np.isfinite(ags[j]) and ags[j] >= 0.75 and hp[j] < 0.05
            and all(dd >= 5 for jj, _, dd, _ in cdiff if jj == j)]
    out.append(f"  LEAD LINE: {', '.join(lead) if lead else 'not hit'}")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
