"""THE SHAPE OF THE PAUSE HE JOINS - tick microstructure, tested in two independent stages.

The user, 2026-09-26: "if we have identified the pause we can identify other things too". The Exness
USTECm feed carries NO order book: its spread is fixed (1.12 points all hour on 2026-09-14) and bid and
ask move together on 100% of ticks - one price plus a markup. What the ticks DO carry is how that
price moves: how many updates (each is a change in the underlying futures quote), how big each step
is, how straight the run-up was, how deep the dip is against it, and whether the last seconds turned.
Book pressure leaves footprints in exactly those (a thin book moves in fewer, bigger steps).

FEATURES at a moment t for a trade in direction s (sign-aligned so + = s's way), from ticks before t:
  f_move      5-min move (points)                       f_eff     5-min net move / path length
  f_dip       30-s move (points)                        f_retr    |dip| / |5-min move|
  f_last5     5-s move (points; + = already turning)    f_quiet   updates in the 30-s dip / 30 x the
                                                                  5-min average rate (<1 = a quiet dip)
  f_step      mean |step| in the dip / mean |step| over the 5 min (>1 = bigger, thinner steps)
  f_upstep    in the 5-min move, mean size of steps s's way / steps against (>1 = it moves s's way
              in bigger jumps)
  f_fresh     seconds since the 5-min extreme in s's direction (small = the move is fresh)

STAGE A (which features mark HIS pauses): each of his 26 clean entries (April on; his_strategy.md
s25) is ranked against the SAME clock second on ~20 other days, same direction. Holm across 9.
STAGE B (does the feature predict price by itself, independent of his trades): 12 random moments a
day x 118 days x both directions; for each feature, the outcome +7 before -7 within 5 min (bid/ask),
compared between the top and bottom thirds of the feature; both halves of the period.
A feature counts only if it passes A (Holm) AND B (both halves).

REGISTERED PREDICTION (2026-09-26, before running): at most one feature separates his entries in A
(f_quiet or f_fresh), and it fails B - the fixed-spread feed carries too little to reconstruct a book
reader's choice. Expected: 0 features pass both.

    python -m backtest.his_microstructure
"""
from __future__ import annotations

import pickle
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0
FEATS = ("f_move", "f_eff", "f_dip", "f_retr", "f_last5", "f_quiet", "f_step", "f_upstep", "f_fresh")


def day_ticks(mt5, day):
    """All USTECm mid ticks 09:30-19:30 ET of a New York date, as (seconds from 09:30 ET float, mid)."""
    a = pd.Timestamp(day).tz_localize("America/New_York") + pd.Timedelta(hours=9, minutes=30)
    b = a + pd.Timedelta(hours=10)
    t = mt5.copy_ticks_range("USTECm", a.tz_convert("UTC").to_pydatetime(), b.tz_convert("UTC").to_pydatetime(),
                             mt5.COPY_TICKS_ALL)
    if t is None or len(t) < 5000:
        return None
    d = pd.DataFrame(t)
    d = d[(d.bid > 0) & (d.ask > 0)]
    s = (d.time_msc.to_numpy() - a.tz_convert("UTC").value // 10**6) / 1000.0
    return s.astype(np.float64), ((d.bid + d.ask) / 2).to_numpy(np.float64), (d.ask - d.bid).to_numpy(np.float64)


def feats(ts, mid, t, s):
    """Features at time t (seconds from 09:30 ET) for direction s. None if not enough ticks."""
    i1 = np.searchsorted(ts, t, side="right")
    i0 = np.searchsorted(ts, t - 300, side="left")
    j0 = np.searchsorted(ts, t - 30, side="left")
    k0 = np.searchsorted(ts, t - 5, side="left")
    if i1 - i0 < 30 or i1 - j0 < 3 or i0 == 0:
        return None
    m5, m30 = mid[i0:i1], mid[j0:i1]
    p_now, p300, p30, p5 = mid[i1 - 1], mid[i0 - 1], mid[j0 - 1], mid[k0 - 1]
    steps5, steps30 = np.diff(m5), np.diff(m30)
    move = s * (p_now - p300)
    path = np.abs(steps5).sum()
    up = s * steps5
    ups, dns = up[up > 0], -up[up < 0]
    ext = np.argmax(s * m5)                                      # the extreme in s's direction
    rate5 = (i1 - i0) / 300.0
    return dict(f_move=move, f_eff=move / path if path > 0 else 0.0, f_dip=s * (p_now - p30),
                f_retr=abs(p_now - p30) / abs(p_now - p300) if abs(p_now - p300) > 0.5 else np.nan,
                f_last5=s * (p_now - p5), f_quiet=(i1 - j0) / (30 * rate5) if rate5 > 0 else np.nan,
                f_step=(np.abs(steps30).mean() / np.abs(steps5).mean()) if len(steps30) and np.abs(steps5).mean() > 0 else np.nan,
                f_upstep=(ups.mean() / dns.mean()) if len(ups) and len(dns) else np.nan,
                f_fresh=t - ts[i0 + ext])


def outcome(ts, mid, spr, t, s):
    """+1 if +7 is reached (exit side) before -7 within 300 s, -1 if -7 first, 0 neither; entry at the quote."""
    i = np.searchsorted(ts, t, side="right") - 1
    if i < 0:
        return None
    e = mid[i] + s * spr[i] / 2
    j1 = np.searchsorted(ts, t + 300, side="right")
    for j in range(i + 1, j1):
        pnl = s * ((mid[j] - s * spr[j] / 2) - e)
        if pnl >= 7:
            return 1
        if pnl <= -7:
            return -1
    return 0


def main():
    import MetaTrader5 as mt5
    cache = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    days = list(pd.bdate_range("2026-04-01", "2026-09-14"))
    need = [d for d in days if d not in cache]
    if need:
        assert mt5.initialize(), mt5.last_error()
        for k, d in enumerate(need):
            cache[d] = day_ticks(mt5, d)
            if k % 25 == 24:
                CACHE.write_bytes(pickle.dumps(cache)); print(f"  fetched {k + 1}/{len(need)}", flush=True)
        mt5.shutdown()
        CACHE.write_bytes(pickle.dumps(cache))
    days = [d for d in days if cache.get(d) is not None]

    # ---------------------------------------------------------------- STAGE A
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-01"]
    rng = np.random.default_rng(4)
    ranks = []
    for r in x.itertuples():
        et = pd.Timestamp(r.utc).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        day = et.normalize()
        t = (et - (day + pd.Timedelta(hours=9, minutes=30))).total_seconds()
        s = 1 if r.side == "BUY" else -1
        if day not in cache or cache[day] is None or not (300 < t < 36000):
            continue
        mine = feats(cache[day][0], cache[day][1], t, s)
        if mine is None:
            continue
        ctrl = []
        for dd in rng.permutation(days):
            if dd == day:
                continue
            f = feats(cache[dd][0], cache[dd][1], t, s)
            if f:
                ctrl.append(f)
            if len(ctrl) >= 20:
                break
        C = pd.DataFrame(ctrl)
        ranks.append({k: (C[k].dropna() < mine[k]).mean() + 0.5 * (C[k].dropna() == mine[k]).mean()
                      for k in FEATS if not np.isnan(mine[k])})
    RA = pd.DataFrame(ranks)
    pA = {}
    print(f"STAGE A - his {len(RA)} clean entries ranked vs the same clock second on 20 other days (0.50 ordinary)")
    for k in FEATS:
        v = RA[k].dropna()
        z = (v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))
        pA[k] = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    order = sorted(pA, key=pA.get)
    holmA = {k: min(1.0, max(pA[j] * (len(pA) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in pA}
    for k in FEATS:
        v = RA[k].dropna()
        print(f"  {k:<10} mean rank {v.mean():.2f}  top third {np.mean(v > 2/3)*100:3.0f}%  bottom third "
              f"{np.mean(v < 1/3)*100:3.0f}%   p {pA[k]:.3f}  Holm {holmA[k]:.3f}")

    # ---------------------------------------------------------------- STAGE B
    rows = []
    for d in days:
        ts, mid, spr = cache[d]
        for t in rng.uniform(600, 35000, 12):
            for s in (1, -1):
                f = feats(ts, mid, t, s)
                o = outcome(ts, mid, spr, t, s)
                if f and o is not None:
                    rows.append(dict(day=d, s=s, o=o, **f))
    B = pd.DataFrame(rows)
    mid_day = days[len(days) // 2]
    print(f"\nSTAGE B - {len(B)} random moment x direction pairs; share reaching +7 before -7 (of those resolved), by "
          f"feature third. Base rate {np.mean(B[B.o != 0].o > 0)*100:.1f}%.")
    print(f"  {'feature':<10}{'low third':>11}{'high third':>12}{'diff':>8}{'1st half':>10}{'2nd half':>10}")
    passB = {}
    for k in FEATS:
        v = B.dropna(subset=[k])
        v = v[v.o != 0]
        lo, hi = v[k].quantile(1 / 3), v[k].quantile(2 / 3)
        def win(g):
            return (g.o > 0).mean() * 100 if len(g) else np.nan
        a_ = win(v[v[k] <= lo]); b_ = win(v[v[k] >= hi])
        h1 = win(v[(v[k] >= hi) & (v.day < mid_day)]) - win(v[(v[k] <= lo) & (v.day < mid_day)])
        h2 = win(v[(v[k] >= hi) & (v.day >= mid_day)]) - win(v[(v[k] <= lo) & (v.day >= mid_day)])
        passB[k] = (np.sign(h1) == np.sign(h2)) and min(abs(h1), abs(h2)) >= 3
        print(f"  {k:<10}{a_:>10.1f}%{b_:>11.1f}%{b_ - a_:>+8.1f}{h1:>+10.1f}{h2:>+10.1f}")
    print("\nVERDICT (Holm-significant in A, and a same-sign >= 3-point split on both halves in B):")
    for k in FEATS:
        a_ok = holmA[k] < 0.05
        print(f"  {k:<10} A {'PASS' if a_ok else 'fail'} | B {'PASS' if passB[k] else 'fail'} -> "
              f"{'BOTH - a real marker of his pause' if a_ok and passB[k] else 'no'}")
    RA.to_csv(ROOT / "logs" / "his_microstructure_ranks.csv", index=False)


if __name__ == "__main__":
    main()
