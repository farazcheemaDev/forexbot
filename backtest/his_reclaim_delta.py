"""DELTA DIVERGENCE AT THE FAKE BREAK - the last practitioner reading on the list (2026-11-22)

THE USER (2026-11-22): "run delta" - after the literature search (his_strategy s97) left delta divergence as the one professional
fake-break signal not yet tested. The reading: the price makes a NEW extreme beyond the swing level, but the aggressive selling (for a
broken low) or buying (for a broken high) behind that second push is WEAKER than behind the push that made the level - the move is out of
fuel, so the break should fail.
DATA   the reclaim moments of his_reclaim.py (181 Exness tick days, every 1-minute close + 14 s, 09:45-15:45 New York; a swing level of the
       last 120 minutes broken by > 3 points, the price back on the broken side; the reclaim = back through it). Aggression from the FREE
       stand-in (the Exness quote's up-moves minus down-moves; rank +0.57 with the CME aggressor flow, his_reclaim_tickflow.py) on every
       day, checked against the real CME tape (his_tape.py's cache) inside his 31 sittings.
LEGS   push 1 = from the extreme of the 15 bars before the swing bar to the swing bar; push 2 = from the extreme between the swing and the
       break's extreme to that extreme. Aggression IN the push direction (selling for a broken low, buying for a broken high), summed.
       DIVERGENCE = push 2's aggression below push 1's (moments where push 1 had none are dropped).
TESTS  the reclaim race (+-7, race2, 10 minutes) with and without divergence, and by tercile of push 2 / push 1, by half; his 7 reclaims;
       the stand-in's divergence flag against the real tape's inside his sittings.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  D1  Reclaims with a divergence beat those without by at most 3 points on both halves, and neither group reaches 56%. (65%)
  D2  His 7 reclaims are not all divergences (at most 5 of 7). (55%)
  D3  The stand-in's divergence flag agrees with the real tape's on at least 65% of the sitting moments where both exist. (55%)

RESULT (2026-11-22, logs/his_reclaim_delta.txt): DELTA DIVERGENCE DOES NOT PICK THE FAKE BREAKS THAT REVERSE. 18,201 reclaim moments with an
  aggressive first push on 181 days (race won 51.0%), 38% with a divergence: WITH 49.9% / 52.6% (tune / holdout), without 50.3% / 52.5%
  (-0.4 / +0.1 points); by tercile of push-2 / push-1 aggression 50.0 / 50.4 / 50.0% and 52.4 / 53.5 / 51.5% - flat. The stand-in's
  divergence flag equals the real CME tape's on 61 of 71 sitting moments (86%). His 7 reclaims: 3 with a divergence, 4 without, all won.
  D1-D3 right. With this, every practitioner fake-break reading found in the search (s97) has been tested.

    python -m backtest.his_reclaim_delta
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_level_memory import BREAK, K, LOOK, NEAR, TICKS, minute_bars, swings  # noqa: E402

LOG = ROOT / "logs" / "his_reclaim_delta.txt"


def tick_flow(ts, mid, a_s, b_s):
    """Up-moves minus down-moves of the mid over (a_s, b_s] seconds since 09:30."""
    a, b = np.searchsorted(ts, a_s, side="right"), np.searchsorted(ts, b_s, side="right")
    d = np.diff(mid[max(a - 1, 0):b])
    return float(np.sum(d > 0) - np.sum(d < 0))


def pushes(ts, mid, hi, lo, sh, sl, t: float):
    """The reclaim setup at t with its two pushes as (start, end) seconds since 09:30 and the push direction (-1 down / +1 up)."""
    try:
        return _pushes(ts, mid, hi, lo, sh, sl, t)
    except ValueError:                                             # an all-gap stretch of minute bars: no reading
        return None


def _pushes(ts, mid, hi, lo, sh, sl, t: float):
    i = np.searchsorted(ts, t - 1.0, side="right") - 1
    if i < 0:
        return None
    p = float(mid[i])
    M = int(t // 60) - 1
    best = None
    for kind, idx, arr in (("hi", sh, hi), ("lo", sl, lo)):
        for j in idx[(idx <= M - K) & (idx >= M - LOOK)]:
            d = abs(arr[j] - p)
            if d <= NEAR and (best is None or d < best[0]):
                best = (d, kind, int(j), float(arr[j]))
    if best is None:
        return None
    _, kind, j, v = best
    if j < 16:
        return None
    seg_lo, seg_hi = lo[j + 1:M + 1], hi[j + 1:M + 1]
    if not len(seg_lo):
        return None
    if kind == "lo":
        if not (seg_lo < v - BREAK).any() or p >= v:
            return None
        ex = j + 1 + int(np.nanargmin(seg_lo))
        a1 = j - 15 + int(np.nanargmax(hi[j - 15:j]))
        a2 = (j + 1 + int(np.nanargmax(hi[j + 1:ex]))) if ex > j + 1 else ex
        return dict(side=1, push=-1, leg1=(60 * a1, 60 * (j + 1)), leg2=(60 * a2, 60 * (ex + 1)))
    if not (seg_hi > v + BREAK).any() or p <= v:
        return None
    ex = j + 1 + int(np.nanargmax(seg_hi))
    a1 = j - 15 + int(np.nanargmin(lo[j - 15:j]))
    a2 = (j + 1 + int(np.nanargmin(lo[j + 1:ex]))) if ex > j + 1 else ex
    return dict(side=-1, push=1, leg1=(60 * a1, 60 * (j + 1)), leg2=(60 * a2, 60 * (ex + 1)))


def main():
    import backtest.his_tape as TP
    from backtest.his_race_curve import race2
    cache = pickle.loads(TICKS.read_bytes())
    prep = {}
    for day, dd in cache.items():
        if dd is None:
            continue
        ts, mid = dd[0], dd[1]
        hi, lo = minute_bars(ts, mid)
        sh, sl = swings(hi, lo)
        prep[day] = (ts, mid, hi, lo, sh, sl)
    days = sorted(prep)
    cut = days[int(len(days) * 0.6)]
    rows = []
    for day in days:
        ts, mid, hi, lo, sh, sl = prep[day]
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            g = pushes(ts, mid, hi, lo, sh, sl, t)
            if g is None:
                continue
            a1 = g["push"] * tick_flow(ts, mid, *g["leg1"])
            a2 = g["push"] * tick_flow(ts, mid, *g["leg2"])
            if a1 <= 0:
                continue
            w = race2(ts, mid, t, g["side"], 600, 7, 7)
            if w is not None:
                rows.append(dict(day=day, t=t, win=w, div=a2 < a1, ratio=a2 / a1, **{k: g[k] for k in ("leg1", "leg2", "push")}))
    R = pd.DataFrame(rows)
    R["half"] = np.where(R.day < cut, "tune", "hold")
    out = [f"backtest/his_reclaim_delta.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, split {pd.Timestamp(cut):%Y-%m-%d}; "
           f"reclaim moments with an aggressive first push: {len(R):,} (race won {R.win.mean():.1%}); with a divergence {R['div'].mean():.0%}", "",
           f"  {'':<24}{'tune':>18}{'holdout':>18}"]
    res = {}
    for nm, m in (("WITH a divergence", R["div"]), ("without", ~R["div"])):
        cells = []
        for h in ("tune", "hold"):
            x = R[m & (R.half == h)]
            res[(nm, h)] = x.win.mean()
            cells.append(f"{x.win.mean():.1%} of {len(x):,}")
        out.append(f"  {nm:<24}{cells[0]:>18}{cells[1]:>18}")
    q1, q2 = R.ratio.quantile([1 / 3, 2 / 3])
    terc = np.where(R.ratio <= q1, 1, np.where(R.ratio <= q2, 2, 3))
    for k, nm in ((1, "push 2 weakest third"), (2, "middle third"), (3, "push 2 strongest third")):
        cells = [f"{R[(terc == k) & (R.half == h)].win.mean():.1%}" for h in ("tune", "hold")]
        out.append(f"  {nm:<24}{cells[0]:>18}{cells[1]:>18}")
    # his reclaims
    x = TP.entries()
    his = []
    for r in x.itertuples():
        pr = prep.get(r.d)
        if pr is None or r.t < 15 * 60:
            continue
        g = pushes(*pr, float(r.t))
        if g is None or g["side"] != r.s:
            continue
        a1 = g["push"] * tick_flow(pr[0], pr[1], *g["leg1"])
        a2 = g["push"] * tick_flow(pr[0], pr[1], *g["leg2"])
        his.append(dict(d=r.d, s=r.s, a1=a1, a2=a2, div=(a1 > 0 and a2 < a1), win=race2(pr[0], pr[1], r.t, r.s, 600, 7, 7)))
    Hh = pd.DataFrame(his)
    out += ["", f"  HIS RECLAIMS: {len(Hh)}; with a divergence {int(Hh['div'].sum())}; won {int((Hh.win == 1).sum())}"]
    for r in Hh.itertuples():
        out.append(f"    {r.d:%Y-%m-%d} {'BUY ' if r.s > 0 else 'SELL'} push-1 aggression {r.a1:+6.0f}  push-2 {r.a2:+6.0f}  "
                   f"{'DIVERGENCE' if r.div else 'no divergence'}  {'won' if r.win == 1 else 'lost' if r.win == 0 else '-'}")
    # the stand-in against the real CME tape inside his sittings
    tape = pd.concat(pickle.loads(TP.CACHE.read_bytes()).values()).drop_duplicates().sort_values("ns", kind="stable")
    tns = tape.ns.to_numpy()
    cf = np.r_[0.0, np.cumsum(tape["size"].to_numpy() * tape.aggr.to_numpy())]
    wins = TP.windows(x)
    agree, n_chk = 0, 0
    for r in R.itertuples():
        base = (r.day + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).value
        a_ns, b_ns = base + int(r.leg1[0] * 1e9), base + int(r.leg2[1] * 1e9)
        if not any(w0.value <= a_ns and b_ns <= w1.value for w0, w1 in wins):
            continue
        f = lambda a, b: cf[np.searchsorted(tns, base + int(b * 1e9), "right")] - cf[np.searchsorted(tns, base + int(a * 1e9), "right")]  # noqa: E731
        c1, c2 = r.push * f(*r.leg1), r.push * f(*r.leg2)
        if c1 <= 0:
            continue
        n_chk += 1
        agree += int((c2 < c1) == r.div)
    gap = [res[("WITH a divergence", h)] - res[("without", h)] for h in ("tune", "hold")]
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", f"  CHECK: the stand-in's divergence flag = the real CME tape's on {agree} of {n_chk} sitting moments "
                f"({agree / max(n_chk, 1):.0%})", "", "REGISTERED PREDICTIONS",
            f"  D1 divergence beats no-divergence by <= 3 points on both halves, neither >= 56% -> "
            f"{ok(all(g <= 0.03 for g in gap) and max(res.values()) < 0.56)} (" + " | ".join(f"{g * 100:+.1f}" for g in gap) + " points)",
            f"  D2 his reclaims at most 5 of 7 divergences -> {ok(int(Hh['div'].sum()) <= 5)} ({int(Hh['div'].sum())} of {len(Hh)})",
            f"  D3 stand-in agrees with the tape on >= 65% -> {ok(n_chk > 0 and agree / n_chk >= 0.65)}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
