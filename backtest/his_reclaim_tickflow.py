"""THE LAST-MINUTE FLOW LEAN, ON EVERY DAY, FROM A FREE STAND-IN (2026-11-22)

THE USER (2026-11-22): "buy, I don't care - today we have a new lead" - the lean his_reclaim_flow.py found inside the fake-break setup
(aggressive CME flow toward the reclaim over the last 60 s: 44% / 50% / 57% by tercile on 175 moments in his 31 sittings, t ~1.4).
Settling it needs the flow on every day; the CME tape for all 181 tick days is quoted at $61.85 (not bought until the user confirms the
total). This first tries a FREE stand-in on every day: the Exness mid's tick direction - up-moves minus down-moves of the quote over the
last 30 / 60 s, signed toward the reclaim.
STEP 1 (validation)  on the 175 sitting moments, the stand-in against the real CME aggressor flow (rank correlation).
STEP 2 (the test)    on all 181 tick days, every 1-minute close + 14 s, 09:45-15:45 New York, the reclaim setup (his_reclaim_flow.legs):
                     the reclaim race (+-7, race2, 10 minutes) by tercile of the stand-in, by half (first 60% of days / the rest).
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  T1  The stand-in tracks the CME flow over 60 s with a rank correlation of at least +0.4 on the sitting moments. (60%)
  T2  On all days the top tercile of the last-60-s stand-in wins the reclaim race at most 56% on either half - the lean does not hold
      at scale. (65%)
  T3  If T1 holds and T2 fails (the lean holds at scale), buying the real tape is worth it; otherwise not.

RESULT (2026-11-22, logs/his_reclaim_tickflow.txt): THE LEAN DOES NOT HOLD AT SCALE; THE $61.85 TAPE IS NOT WORTH BUYING FOR IT. The stand-in
  tracks the real CME aggressor flow at rank +0.57 on 313 sitting moments (T1 right). On all 181 days (21,211 reclaim moments, race won
  51.0%) the reclaim race by tercile of the last-60-s stand-in is 49.3 / 51.0 / 50.1% (tune) and 52.9 / 52.4 / 51.7% (holdout); the last
  30 s the same - no lift at the top (T2 right). His_reclaim_flow.py's 44 / 50 / 57% on 175 moments was the small sample. T3: NO.

    python -m backtest.his_reclaim_tickflow
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_level_memory import TICKS, minute_bars, swings  # noqa: E402
from backtest.his_reclaim_flow import legs  # noqa: E402

LOG = ROOT / "logs" / "his_reclaim_tickflow.txt"


def tick_flow(ts, mid, t, w):
    """Up-moves minus down-moves of the mid over (t - w, t]."""
    a, b = np.searchsorted(ts, t - w, side="right"), np.searchsorted(ts, t, side="right")
    d = np.diff(mid[max(a - 1, 0):b])
    return float(np.sum(d > 0) - np.sum(d < 0))


def main():
    from scipy.stats import spearmanr
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
    # STEP 1: validation against the real CME aggressor flow inside his 31 windows
    tape = pd.concat(pickle.loads(TP.CACHE.read_bytes()).values()).drop_duplicates().sort_values("ns", kind="stable")
    tns = tape.ns.to_numpy()
    cf = np.r_[0.0, np.cumsum(tape["size"].to_numpy() * tape.aggr.to_numpy())]
    wins = TP.windows(TP.entries())
    val = []
    for a, b in wins:
        day = a.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None).normalize()
        pr = prep.get(day)
        if pr is None:
            continue
        base = (day + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        for t in np.arange(max(15 * 60, (a - base).total_seconds()), min(375 * 60, (b - base).total_seconds()), 60.0) + 14:
            t_ns = base.value + int(t * 1e9)
            if t_ns > b.value:
                continue
            g = legs(*pr, float(t))
            if g is None:
                continue
            cme = g["side"] * (cf[np.searchsorted(tns, t_ns, "right")] - cf[np.searchsorted(tns, t_ns - 60 * 10**9, "right")])
            val.append((g["side"] * tick_flow(pr[0], pr[1], t, 60), cme))
    V = np.array(val)
    rho = spearmanr(V[:, 0], V[:, 1]).correlation if len(V) > 10 else np.nan
    # STEP 2: every day
    days = sorted(prep)
    cut = days[int(len(days) * 0.6)]
    rows = []
    for day in days:
        ts, mid, hi, lo, sh, sl = prep[day]
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            g = legs(ts, mid, hi, lo, sh, sl, t)
            if g is None:
                continue
            w = race2(ts, mid, t, g["side"], 600, 7, 7)
            if w is not None:
                rows.append(dict(day=day, win=w, f30=g["side"] * tick_flow(ts, mid, t, 30), f60=g["side"] * tick_flow(ts, mid, t, 60)))
    R = pd.DataFrame(rows)
    R["half"] = np.where(R.day < cut, "tune", "hold")
    out = [f"backtest/his_reclaim_tickflow.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, split {pd.Timestamp(cut):%Y-%m-%d}; "
           f"reclaim moments {len(R):,} (race won {R.win.mean():.1%})", "",
           f"  STEP 1 the stand-in (quote up-moves minus down-moves, 60 s) vs the CME aggressor flow on {len(V)} sitting moments: rank correlation "
           f"{rho:+.2f}", "", f"  STEP 2 the reclaim race by tercile of the stand-in (bottom / middle / top), tune | holdout:"]
    res = {}
    for f in ("f30", "f60"):
        q1, q2 = R[f].quantile([1 / 3, 2 / 3])
        terc = np.where(R[f] <= q1, 1, np.where(R[f] <= q2, 2, 3))
        line = f"    last {f[1:]} s:"
        for h in ("tune", "hold"):
            m = R.half == h
            wr = [R[m & (terc == k)].win.mean() for k in (1, 2, 3)]
            res[(f, h)] = wr
            line += f"  {h} " + " / ".join(f"{v:.1%}" for v in wr) + f" (n {int((m & (terc == 3)).sum()):,} in the top)"
        out.append(line)
    t1 = rho >= 0.4
    t2 = all(res[("f60", h)][2] <= 0.56 for h in ("tune", "hold"))
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  T1 the stand-in tracks the CME flow at rank >= +0.4 -> {ok(t1)} ({rho:+.2f})",
            f"  T2 the top tercile of the last-60-s stand-in <= 56% on both halves -> {ok(t2)} ("
            + " | ".join(f"{h} {res[('f60', h)][2]:.1%}" for h in ("tune", "hold")) + ")",
            f"  T3 buying the real tape is worth it (T1 holds and the lean holds at scale): {'YES' if t1 and not t2 else 'NO'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
