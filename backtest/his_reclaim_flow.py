"""WERE THE STOPS ABSORBED? - the CME order flow inside each fake break, in his 31 sittings (2026-11-22)

THE USER (2026-11-22): "check" - the one untested thing inside the fake-break pattern (his_reclaim.py: he trades back through broken
levels, 7 of 7 won; the setup is 50-52% on every day; his_reclaim_detail.py: no visible feature of the break picks his winners). The
order-flow reading of a fake break: heavy aggressive selling into a breakdown that barely moves the price (passive buyers ABSORB the
stops), then an aggressive snap-back.
DATA   the CME NQ tape with the aggressor side (his_tape.py's cache: 31 windows, 22 min before to 20 min after each statement entry,
       801,045 trades); the Exness tick days for the levels and the race (his_level_memory / his_reclaim_detail's construction).
MOMENTS every 1-minute close + 14 s inside the 31 windows (and his own clicks), where the nearest swing level is BROKEN and the price is
       back on the broken side (the reclaim setup), and the break's first bar is inside the tape window.
FLOW (signed so that 'for the reclaim' is positive)
  absorption   aggressive volume IN the break's direction from the first breach to the extreme, per point of the break's depth (high =
               much aggression for little progress: absorbed)
  snapback     aggressive volume in the RECLAIM direction from the extreme to the moment
  last30 / 60  aggressive volume in the reclaim direction over the last 30 / 60 s
TESTS  the reclaim race (+-7 on the Exness mid, 10 minutes) by tercile of each flow measure; where his 7 reclaims sit (tercile).
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  G1  The top-minus-bottom tercile difference in the reclaim race is within 10 points for absorption, and no tercile of any measure
      reaches 61%. (70%)
  G2  His 7 reclaims are not concentrated in absorption's top tercile (at most 4 of 7). (60%)
  G3  Reclaim-direction flow over the last 30 / 60 s does not lift its top tercile above 56%. (70%)
  The sample is a few hundred moments: a tercile's standard error is ~5 points - this can see a big effect, not a small one.

RESULT (2026-11-22, logs/his_reclaim_flow.txt): THE ORDER FLOW INSIDE THE FAKE BREAK DOES NOT PICK THE WINNERS (on this sample). 175 reclaim
  moments inside his 31 windows with the break on tape (race won 50.3%); 3 of his 7 reclaims had their break inside the tape window (won
  3). Absorption by tercile 44% / 59% / 48% (top - bottom +4 points, no order); snap-back flow 45 / 56 / 50; aggressive flow toward the
  reclaim over the last 30 s 42 / 55 / 53, over the last 60 s 44 / 50 / 57 (+13 points, ~56 moments a tercile, t ~1.4: a lean, not a
  finding). His 3 sit in the MIDDLE of absorption. G1, G2 right; G3 wrong by a hair (57%). Settling the last-60-s lean needs the CME
  tape for every tick day, not just his sittings.

    python -m backtest.his_reclaim_flow
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

LOG = ROOT / "logs" / "his_reclaim_flow.txt"


def legs(ts, mid, hi, lo, sh, sl, t: float):
    """The reclaim setup at t with the minute indices of the first breach and the extreme (None if no setup)."""
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
    seg_lo, seg_hi = lo[j + 1:M + 1], hi[j + 1:M + 1]
    if not len(seg_lo):
        return None
    if kind == "lo":
        brk = np.flatnonzero(seg_lo < v - BREAK)
        if not len(brk) or p >= v:
            return None
        e = int(np.nanargmin(seg_lo))
        return dict(side=1, b0=j + 1 + int(brk[0]), ex=j + 1 + e, depth=float(v - seg_lo[e]))
    brk = np.flatnonzero(seg_hi > v + BREAK)
    if not len(brk) or p <= v:
        return None
    e = int(np.nanargmax(seg_hi))
    return dict(side=-1, b0=j + 1 + int(brk[0]), ex=j + 1 + e, depth=float(seg_hi[e] - v))


def main():
    import backtest.his_tape as TP
    from backtest.his_race_curve import race2
    tape = pd.concat(pickle.loads(TP.CACHE.read_bytes()).values()).drop_duplicates().sort_values("ns", kind="stable")
    tns = tape.ns.to_numpy()
    cf = np.r_[0.0, np.cumsum(tape["size"].to_numpy() * tape.aggr.to_numpy())]

    def flow(a_ns, b_ns):
        return cf[np.searchsorted(tns, b_ns, "right")] - cf[np.searchsorted(tns, a_ns, "right")]

    cache = pickle.loads(TICKS.read_bytes())
    x = TP.entries()
    wins = TP.windows(x)
    rows = []

    def score(day, t, who, side_his=None):
        dd = cache.get(day)
        if dd is None:
            return None
        ts, mid = dd[0], dd[1]
        key = (day, "prep")
        if key not in prep:
            hi, lo = minute_bars(ts, mid)
            sh, sl = swings(hi, lo)
            prep[key] = (hi, lo, sh, sl)
        hi, lo, sh, sl = prep[key]
        g = legs(ts, mid, hi, lo, sh, sl, t)
        if g is None:
            return None
        base = (day + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).value
        b0_ns, ex_ns, t_ns = base + g["b0"] * 60 * 10**9, base + (g["ex"] + 1) * 60 * 10**9, base + int(t * 1e9)
        win = next(((a, b) for a, b in wins if a.value <= b0_ns and t_ns <= b.value), None)
        if win is None:
            return None                                              # the break is not covered by the tape window
        s = g["side"]
        brk_dir = -s                                                 # a broken LOW broke downward: selling is 'in the break's direction'
        absorption = brk_dir * flow(b0_ns, ex_ns) / max(g["depth"], 1.0)
        snapback = s * flow(ex_ns, t_ns)
        trade_side = s if side_his is None else side_his
        return dict(who=who, day=day, side=s, took_reclaim=(side_his == s) if side_his is not None else True,
                    absorption=absorption, snapback=snapback, last30=s * flow(t_ns - 30 * 10**9, t_ns),
                    last60=s * flow(t_ns - 60 * 10**9, t_ns), win=race2(ts, mid, t, trade_side, 600, 7, 7))

    prep = {}
    for a, b in wins:
        day = a.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None).normalize()
        base = (day + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        t0 = max(15 * 60, (a - base).total_seconds())
        t1 = min(375 * 60, (b - base).total_seconds())
        for t in np.arange(np.ceil((t0 - 14) / 60) * 60 + 14, t1, 60.0):
            r = score(day, float(t), "grid")
            if r is not None and r["win"] is not None:
                rows.append(r)
    for r in x.itertuples():
        h = score(r.d, float(r.t), "his", r.s)
        if h is not None:
            rows.append(h)
    D = pd.DataFrame(rows)
    G = D[D.who == "grid"]
    Hh = D[(D.who == "his") & D.took_reclaim]
    out = [f"backtest/his_reclaim_flow.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; CME NQ tape {len(tape):,} trades in {len(wins)} windows; "
           f"reclaim moments inside the windows with the break on tape: {len(G)} (race won {G.win.mean():.1%}); his reclaim trades: {len(Hh)} "
           f"(won {int((Hh.win == 1).sum())})", "",
           f"  {'measure':<11}{'bottom third':>14}{'middle':>10}{'top third':>12}{'top - bottom':>14}   his reclaims by tercile (1 = bottom)"]
    res = {}
    for f in ("absorption", "snapback", "last30", "last60"):
        q1, q2 = G[f].quantile([1 / 3, 2 / 3])
        terc = lambda v: 1 if v <= q1 else (2 if v <= q2 else 3)  # noqa: E731
        gt = G[f].map(terc)
        wr = [G[gt == k].win.mean() for k in (1, 2, 3)]
        n = [int((gt == k).sum()) for k in (1, 2, 3)]
        res[f] = wr
        his_t = sorted(int(terc(v)) for v in Hh[f])
        out.append(f"  {f:<11}{wr[0]:>9.0%} ({n[0]}){wr[1]:>6.0%} ({n[1]}){wr[2]:>7.0%} ({n[2]}){(wr[2] - wr[0]) * 100:>+11.0f} pts   {his_t}")
    out += ["", "  his reclaim trades: absorption, snap-back, last 30 s / 60 s flow (contracts, + = for the reclaim), race"]
    for r in Hh.itertuples():
        out.append(f"    {r.day:%Y-%m-%d} {'BUY ' if r.side > 0 else 'SELL'} absorption {r.absorption:+8.1f}/pt  snap-back {r.snapback:+7.0f}  "
                   f"last 30 s {r.last30:+6.0f}  last 60 s {r.last60:+6.0f}  {'won' if r.win == 1 else 'lost' if r.win == 0 else '-'}")
    q1, q2 = G.absorption.quantile([1 / 3, 2 / 3])
    top_abs = int(sum(v > q2 for v in Hh.absorption))
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  G1 absorption top - bottom within 10 points and no tercile >= 61% -> "
            f"{ok(abs(res['absorption'][2] - res['absorption'][0]) <= 0.10 and max(max(v) for v in res.values()) < 0.61)}",
            f"  G2 his reclaims not concentrated in absorption's top third (<= 4 of {len(Hh)}) -> {ok(top_abs <= 4)} ({top_abs})",
            f"  G3 last 30 / 60 s top third <= 56% -> {ok(res['last30'][2] <= 0.56 and res['last60'][2] <= 0.56)}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
