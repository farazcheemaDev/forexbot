"""THE ANALYST DESK'S "SWEET SPOT" - registered before any call that will judge it, scored only on calls made after the registration (2026-11-06)

The user, 2026-11-06: "I have been analysing the Analyst desk and there is a lot of potential for short-term scalping or quality trades when there is a sweet spot". The desk's own record (86 resolved calls, 2026-10-27 .. 11-06, analyst.py's calls.csv)
says, read after looking: calls with a stop under 0.4% (scalp-sized) won 1 of 19 and lost -20.5R, almost the whole desk's loss; calls with a stop of 0.8% or more won 13 of 28 (46% against random-entry odds of 13%), mean +0.71R after fees,
+0.71R in both halves of time - but those 28 calls are only 14 independent bets (one market move settles every same-direction call of a day), mean +0.42R a bet, t +1.2, and the cut was found by slicing 19 ways, so it is a HYPOTHESIS, not a result.
(Inside it SMC sweeps went 10 of 14, +1.53R, SR 1 of 9, -0.69R; also post hoc.) The desk's own verdict is NO EDGE PROVEN (p 0.137 over 19 bets) and its registered review (100 resolved calls or 2027-01-31) reads ALL calls.

THIS FILE REGISTERS THE CLAIM so it can be tested fairly. NOTHING ELSE IS TOUCHED: the desk keeps logging every call exactly as before; this only scores a subset of the calls made from REGISTERED_UTC on.
    SWEET SPOT (primary, one definition): a desk call whose stop is at least 0.8% from its entry (stop_pct >= 0.008), any method, market and side. Exploratory only, never the verdict: SMC calls inside it.
    UNIT: a bet = all sweet-spot calls made the same UTC day on the same side (one market move settles them together); a bet's value = the mean r_net of its calls (after the 12bp fee).
    BAR (all of it): at least 30 independent bets from calls made after REGISTERED_UTC, mean R per bet >= +0.15, day-clustered t >= 2.0, a hit rate above the calls' random-entry odds (the desk's base_p), and the SAME SIGN in both halves of the
    forward sample (first 15 / last 15 bets by date). Only then does a small real size become a question (the desk's 0.5% risk a call, its 3x cap), and size follows the doc 22 rule, not this file.
    ALSO REGISTERED: scalp-sized calls (stop < 0.4%) are expected to keep losing; the bar is judged on the primary only.

REGISTERED BEFORE THE FIRST FORWARD CALL (2026-11-06)
    W1  After 30 bets the mean R per bet is positive but smaller than the +0.42R seen so far (prior 60%); it clears the whole bar (prior 20%).
    W2  The hit rate stays at least 10 points above the random-entry odds (prior 55%).
    W3  SMC stays the best method inside the sweet spot (prior 40%).
    W4  The scalp-sized calls (stop < 0.4%) stay negative (prior 80%).
Pace: about 1.3 independent bets a day so far -> 30 bets in roughly 3-4 weeks (about early December).

    python -m backtest.analyst_sweetspot [calls.csv]     default: logs/analyst/calls.csv (on the VM: /opt/forexbot/logs/analyst/calls.csv)       tests: python tests/test_analyst_sweetspot.py
"""
from __future__ import annotations

import csv
import math
import statistics as st
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTERED_UTC = "2026-11-06 15:00"
REGISTERED_MS = int(datetime.strptime(REGISTERED_UTC, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp() * 1000)
SWEET_STOP = 0.008
SCALP_STOP = 0.004
MIN_BETS, MIN_MEAN_R, MIN_T = 30, 0.15, 2.0


def fnum(x, default=None):
    try:
        v = float(x)
        return v if v == v else default
    except (TypeError, ValueError):
        return default


def load(path):
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        out.append(dict(id=int(r["id"]), made_ms=int(float(r["made_ms"])), day=r["made_utc"][:10], side=r["side"], method=r["method"], status=r["status"],
                        stop_pct=fnum(r["stop_pct"]), r=fnum(r["r_net"]), base=fnum(r["base_p"])))
    return out


def resolved(rows):
    """Calls with an outcome: WIN, LOSS or EXPIRED (an open call has none)."""
    return [r for r in rows if r["status"] in ("WIN", "LOSS", "EXPIRED") and r["r"] is not None]


def forward(rows, since_ms=REGISTERED_MS):
    return [r for r in rows if r["made_ms"] >= since_ms]


def sweet(rows):
    return [r for r in rows if r["stop_pct"] is not None and r["stop_pct"] >= SWEET_STOP]


def bets(rows):
    """(day, side) -> the mean r_net of that day's same-side calls: one independent bet each, in date order."""
    g = {}
    for r in rows:
        g.setdefault((r["day"], r["side"]), []).append(r["r"])
    return [(k, st.mean(v)) for k, v in sorted(g.items())]


def tstat(x):
    x = list(x)
    if len(x) < 3 or st.stdev(x) == 0:
        return None
    return st.mean(x) / (st.stdev(x) / math.sqrt(len(x)))


def verdict(n_bets, mean_r, t, hit, base, h1, h2):
    """PASS only when every part of the registered bar holds; otherwise NOT YET (too few bets) or NO PASS (enough bets, bar missed)."""
    if n_bets < MIN_BETS:
        return f"NOT YET - {n_bets} of {MIN_BETS} independent bets"
    ok = (mean_r >= MIN_MEAN_R and t is not None and t >= MIN_T and hit > base and h1 > 0 and h2 > 0)
    return "PASS - the registered bar is met" if ok else "NO PASS - enough bets, the registered bar is not met"


def score(rows, since_ms=REGISTERED_MS):
    fw = sweet(resolved(forward(rows, since_ms)))
    bt = bets(fw)
    vals = [v for _, v in bt]
    half = len(vals) // 2
    h1 = st.mean(vals[:half]) if half else 0.0
    h2 = st.mean(vals[half:]) if len(vals) - half else 0.0
    hit = sum(1 for r in fw if r["status"] == "WIN") / len(fw) if fw else 0.0
    base = st.mean(r["base"] for r in fw if r["base"] is not None) if fw else 0.0
    mean_r = st.mean(vals) if vals else 0.0
    t = tstat(vals)
    return dict(calls=len(fw), bets=len(bt), mean_r=mean_r, t=t, hit=hit, base=base, h1=h1, h2=h2, verdict=verdict(len(bt), mean_r, t, hit, base, h1, h2))


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "logs" / "analyst" / "calls.csv"
    rows = load(path)
    fwd = resolved(forward(rows))
    s = score(rows)
    lines = [f"backtest/analyst_sweetspot.py - registered {REGISTERED_UTC} UTC; {len(rows)} calls in the log, {len(fwd)} resolved from the registration on",
             f"SWEET SPOT (stop >= {SWEET_STOP:.1%}): {s['calls']} calls = {s['bets']} independent bets | mean R per bet {s['mean_r']:+.3f}"
             f" | t {('%+.2f' % s['t']) if s['t'] is not None else 'n/a'} | hit {s['hit']:.0%} vs random-entry odds {s['base']:.0%} | halves {s['h1']:+.2f} / {s['h2']:+.2f}",
             f"VERDICT: {s['verdict']}"]
    sm = sweet(fwd)
    for m in sorted({r["method"] for r in sm}):
        L = [r for r in sm if r["method"] == m]
        lines.append(f"   exploratory: {m} inside the sweet spot: {len(L)} calls, {sum(1 for r in L if r['status'] == 'WIN')} wins, mean R {st.mean(r['r'] for r in L):+.2f}")
    sc = [r for r in fwd if r["stop_pct"] is not None and r["stop_pct"] < SCALP_STOP]
    if sc:
        lines.append(f"   scalp-sized calls (stop < {SCALP_STOP:.1%}): {len(sc)} calls, {sum(1 for r in sc if r['status'] == 'WIN')} wins, mean R {st.mean(r['r'] for r in sc):+.2f}   (W4: expected to stay negative)")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
