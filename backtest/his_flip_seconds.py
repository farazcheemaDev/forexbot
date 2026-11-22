"""HIS FLIP PAIRS, SECOND BY SECOND (2026-11-21)

THE USER (2026-11-21): "test what we can" - after his_flip_pairs.py showed that no 1-minute reading flips with him inside his six
buy/sell pairs and two of them flipped within 27 / 39 seconds, inside one candle. This repeats the pair test on Exness ticks, one-second
resolution, with readings a minute-chart cannot see.
DATA   his NASDAQ trades (his_noise.his_trades) and the Exness USTECm tick days (strategy_analysis/data/ustec_tick_days.pkl: per day,
       seconds since 09:30 New York and the mid; 2026-01-02 .. 09-14, so the 10-08 pair is not covered).
READINGS at a click t (seconds since 09:30), from the mid one second BEFORE it (buy-ish reading in brackets):
  move over the last 1 / 3 / 6 / 10 / 20 / 30 / 60 s (it fell: a FADE reading); position in the high-low of the last 30 / 60 / 120 s
  (low half); the 1-minute candle in progress (red so far); the last closed 1-minute candle (red).
PAIRS  consecutive trades on one day, opposite sides, <= 10 minutes apart (his_flip_pairs.py's definition). A pair is consistent with a
       reading as FADE when it is buy-ish at his buy and sell-ish at his sell, as FOLLOW when the reverse.
THEN   readings consistent in all pairs or all but one: (a) his side vs the reading on his OTHER trades; (b) the reading as a RULE at
       every 1-minute close + 14 s, 09:45-15:45 New York, on all 182 tick days: does its side win the +7-before--7 race (race2, 10
       minutes)? his own race is 88%; nearby moments 55%.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-21)
  S1  The last 1-6 seconds' move flips with him as a FADE in at least 4 of the 5 covered pairs - his known habit of entering on a small
      pullback against himself (s34), which is his ENTRY TIMING. (60%)
  S2  Every reading consistent in all pairs or all but one matches his side on 40-65% of his other trades. (70%)
  S3  As a rule on all days, each such reading wins the race 46-54% of the time. (85%)

RESULT (2026-11-21, logs/his_flip_seconds.txt): 42 of his trades on the tick days (race won 36 of 41 - his known 88%, the data lines up); 5
  of the 6 flip pairs covered (10-08 is past the tick cache). No reading flips with him in more than 2 of 5 pairs, in either
  orientation; none qualifies. In most pairs the last 20-120 seconds read the SAME at his buy and his sell (the price had risen at both);
  in the two fast pairs (27 s, 39 s) he bought into a rise, took a quick profit and sold the top of the same rise. S1 WRONG (the last
  1-6 s move fits 0-2 of 5 as a fade), S2 and S3 right (none qualified). His side is not in the recent price path at 1 second either.

    python -m backtest.his_flip_seconds
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "his_flip_seconds.txt"
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
MOVES = (1, 3, 6, 10, 20, 30, 60)
RANGES = (30, 60, 120)


def at_sec(ts: np.ndarray, mid: np.ndarray, t: float) -> float:
    i = np.searchsorted(ts, t, side="right") - 1
    return float(mid[i]) if i >= 0 else np.nan


def readings(ts: np.ndarray, mid: np.ndarray, t: float) -> dict | None:
    """+1 buy-ish / -1 sell-ish / 0 neutral, from the mid one second before the click."""
    t0 = t - 1.0
    p = at_sec(ts, mid, t0)
    if not np.isfinite(p) or t0 < 125:
        return None
    sg = lambda x: 1 if x < 0 else (-1 if x > 0 else 0)  # noqa: E731  (a fall = buy-ish: the FADE reading)
    f = {f"move_{n}s": sg(p - at_sec(ts, mid, t0 - n)) for n in MOVES}
    for n in RANGES:
        a, b = np.searchsorted(ts, t0 - n), np.searchsorted(ts, t0, side="right")
        w = mid[a:b]
        if len(w) < 3:
            return None
        lo, hi = w.min(), w.max()
        pos = (p - lo) / (hi - lo) if hi > lo else 0.5
        f[f"range_{n}s"] = 1 if pos < 0.5 else (-1 if pos > 0.5 else 0)
    m0 = np.floor(t / 60.0) * 60.0                                # this minute's start (seconds since 09:30)
    f["candle_now"] = sg(p - at_sec(ts, mid, m0))
    f["candle_prev"] = sg(at_sec(ts, mid, m0 - 0.001) - at_sec(ts, mid, m0 - 60.0))
    return f


def main():
    from backtest.his_noise import his_trades
    from backtest.his_race_curve import race2
    from scipy.stats import binomtest
    cache = pickle.loads(TICKS.read_bytes())
    T = his_trades()
    rows = []
    for r in T.itertuples():
        day = r.et.normalize()
        t = (r.et - day - pd.Timedelta(hours=9, minutes=30)).total_seconds()
        dd = cache.get(day)
        if dd is None or t < 0:
            continue
        ts, mid = dd[0], dd[1]
        f = readings(ts, mid, t)
        if f is not None:
            rows.append(dict(et=r.et, day=day, t=t, side=r.side, pts=r.pts, race=race2(ts, mid, t, r.side, 600, 7, 7), **f))
    X = pd.DataFrame(rows).sort_values("et").reset_index(drop=True)
    feats = [c for c in X.columns if c.startswith(("move_", "range_", "candle_"))]
    pairs = []
    for i in range(len(X) - 1):
        a, b = X.iloc[i], X.iloc[i + 1]
        if a.day == b.day and a.side != b.side and (b.et - a.et) <= pd.Timedelta(minutes=10):
            pairs.append((a, b) if a.side > 0 else (b, a))
    in_pair = {p[0].et for p in pairs} | {p[1].et for p in pairs}
    out = [f"backtest/his_flip_seconds.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; his NASDAQ trades with tick data: {len(X)} "
           f"(race won {int((X.race == 1).sum())} of {int(X.race.notna().sum())}); flip pairs covered: {len(pairs)}", ""]
    for b, s in pairs:
        out.append(f"  pair {min(b.et, s.et):%Y-%m-%d %H:%M:%S} -> {max(b.et, s.et):%H:%M:%S} ({abs((s.et - b.et).total_seconds()):.0f} s)")
    out += ["", f"  {'reading':<13}{'FADE pairs':>12}{'FOLLOW pairs':>14}   at the BUY / at the SELL"]
    best = {}
    for f in feats:
        fade = sum(1 for b, s in pairs if b[f] > 0 and s[f] < 0)
        follow = sum(1 for b, s in pairs if b[f] < 0 and s[f] > 0)
        best[f] = (fade, follow)
        out.append(f"  {f:<13}{fade:>7} of {len(pairs)}{follow:>9} of {len(pairs)}   " + "  ".join(f"{int(b[f]):+d}/{int(s[f]):+d}" for b, s in pairs))
    qual = [(f, o) for f, (fa, fo) in best.items() for o, k in (("fade", fa), ("follow", fo)) if pairs and k >= len(pairs) - 1]
    others = X[~X.et.isin(in_pair)]
    out += ["", f"  READINGS CONSISTENT IN ALL PAIRS OR ALL BUT ONE: {', '.join(f'{f} ({o})' for f, o in qual) or 'none'}"]
    carry, rule = {}, {}
    if qual:
        # the rule at every 1-minute close + 14 s, 09:45-15:45 New York, on every tick day
        moments = []
        for day, (ts, mid, *_rest) in cache.items():
            for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
                f = readings(ts, mid, t)
                if f is not None:
                    moments.append((ts, mid, t, f))
        for f, o in qual:
            sgn = 1 if o == "fade" else -1
            x = others[others[f] != 0]
            k = int((x.side == sgn * x[f]).sum())
            carry[(f, o)] = (k, len(x), binomtest(k, len(x), 0.5).pvalue if len(x) else np.nan)
            res = [race2(ts, mid, t, sgn * ff[f], 600, 7, 7) for ts, mid, t, ff in moments if ff[f] != 0]
            res = [v for v in res if v is not None]
            rule[(f, o)] = (float(np.mean(res)) if res else np.nan, len(res))
            out.append(f"    {f} as {o.upper()}: his other trades {k} of {len(x)} ({k / max(len(x), 1):.0%}, p {carry[(f, o)][2]:.3f}); "
                       f"as a RULE on {len(cache)} days: race won {rule[(f, o)][0]:.1%} of {rule[(f, o)][1]} moments")
    s1 = max(best.get(f"move_{n}s", (0, 0))[0] for n in (1, 3, 6)) >= min(4, len(pairs))
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  S1 the last 1-6 s move flips with him as a FADE in >= 4 of the pairs -> {ok(s1)} ("
            + ", ".join(f"{n}s {best[f'move_{n}s'][0]} of {len(pairs)}" for n in (1, 3, 6)) + ")",
            f"  S2 qualifying readings match 40-65% on his other trades -> {ok(all(0.40 <= k / max(n, 1) <= 0.65 for k, n, _ in carry.values()))}"
            + (" (none qualified)" if not carry else ""),
            f"  S3 as rules they win the race 46-54% -> {ok(all(0.46 <= w <= 0.54 for w, _ in rule.values()))}" + (" (none qualified)" if not rule else "")]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
