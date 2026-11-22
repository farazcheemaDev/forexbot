"""LEVEL MEMORY: DOES HIS SIDE FOLLOW WHAT THE PRICE DID LAST TIME AT THE LEVEL HE PULLS BACK TO? (2026-11-22)

THE USER (2026-11-22): "waiting for the price to pull back a little toward a recent level before entering, then seeing what the price did
before on that level - maybe there is a relation". his_retest.py (s55) found he enters a little nearer a recent level, and
his_flip_pairs.py's all-trades check that he goes either way from it - but neither asked what the price DID at that level before. The
textbook reading ('level memory'): a level that HELD before holds again (bounce off support, rejection at resistance); a level that
BROKE flips its role (old support becomes resistance, old resistance support) when the price comes back to it from the other side.
DATA   Exness USTECm ticks (strategy_analysis/data/ustec_tick_days.pkl: 182 days 2026-01-02 .. 09-14, seconds since 09:30 New York, mid),
       one-minute high / low / close built from them; his NASDAQ entries (his_tape.entries, the corrected clock).
LEVELS at a moment t: swing highs / lows of the closed 1-minute bars of the last 120 minutes (a bar whose high / low is the extreme of the
       3 bars either side, so confirmed 3 bars later); the NEAREST to the price (mid one second before t) within 10 points.
MEMORY since the swing formed: BROKEN if the price traded more than 3 points beyond it, else HELD. The call: a HELD low -> buy, a HELD high
       -> sell; a BROKEN low with the price now below it -> sell (old support = resistance); a BROKEN high with the price now above it ->
       buy; otherwise no call. 'Strong' = touched again (a bar within 1.5 points of it) at least twice since it formed.
TESTS  A his side vs the call at his clicks (binomial); B the call as a RULE at every 1-minute close + 14 s, 09:45-15:45 New York, on every
       tick day: the +-7 race on the mid (race2, 10 minutes), by half (first 60% of days / the rest), all calls and strong levels.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  R1  His side agrees with the call on 35-65% of the clicks that have one, p > 0.05. (70%)
  R2  As a rule the call wins the race 46-54% on both halves. (80%)
  R3  Strong levels do no better than 56% as a rule on either half. (80%)

RESULT (2026-11-22, logs/his_level_memory.txt): THE LEVEL'S HISTORY DOES NOT SET HIS SIDE. 42 of his clicks scored, 19 with a recent swing
  level within 10 points: his side = the textbook level-memory call on 8 of 19 (42%, p 0.65); on strong levels (touched twice since)
  2 of 10 - he went AGAINST the call 8 times in 10 - and he won the race 90% when against it, 62% when with it (tiny samples). As a
  rule on 181 days the call wins 49.4% / 48.4% of +-7 races (tune / holdout; holdout p 0.001 - slightly WORSE than a coin), strong
  levels 49.9% / 47.4%; the opposite call would win ~51-52%, nowhere near his 88%. R1-R3 right.

    python -m backtest.his_level_memory
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "his_level_memory.txt"
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
K, LOOK, NEAR, BREAK, TOUCH = 3, 120, 10.0, 3.0, 1.5


def minute_bars(ts: np.ndarray, mid: np.ndarray):
    k = (ts // 60).astype(int)
    n = int(k.max()) + 1
    hi = np.full(n, np.nan)
    lo = np.full(n, np.nan)
    np.fmax.at(hi, k, mid)
    np.fmin.at(lo, k, mid)
    return hi, lo


def swings(hi: np.ndarray, lo: np.ndarray):
    """Indices of swing highs / lows (the extreme of the K bars either side)."""
    n = len(hi)
    sh, sl = [], []
    for j in range(K, n - K):
        wh, wl = hi[j - K:j + K + 1], lo[j - K:j + K + 1]
        if np.isfinite(hi[j]) and hi[j] >= np.nanmax(wh):
            sh.append(j)
        if np.isfinite(lo[j]) and lo[j] <= np.nanmin(wl):
            sl.append(j)
    return np.array(sh, int), np.array(sl, int)


def call_at(ts, mid, hi, lo, sh, sl, t: float):
    """(call, strong) at moment t: +1 buy, -1 sell, 0 none."""
    i = np.searchsorted(ts, t - 1.0, side="right") - 1
    if i < 0:
        return 0, False
    p = float(mid[i])
    M = int(t // 60) - 1                                         # the last closed minute
    best = None
    for kind, idx, arr in (("hi", sh, hi), ("lo", sl, lo)):
        ok = idx[(idx <= M - K) & (idx >= M - LOOK)]
        for j in ok:
            d = abs(arr[j] - p)
            if d <= NEAR and (best is None or d < best[0]):
                best = (d, kind, j, float(arr[j]))
    if best is None:
        return 0, False
    _, kind, j, v = best
    after_hi, after_lo = hi[j + 1:M + 1], lo[j + 1:M + 1]
    if kind == "lo":
        broken = bool(np.nanmin(after_lo) < v - BREAK) if len(after_lo) else False
        touches = int(np.sum(np.abs(lo[j + K + 1:M + 1] - v) <= TOUCH))
        c = 1 if not broken else (-1 if p < v else 0)
    else:
        broken = bool(np.nanmax(after_hi) > v + BREAK) if len(after_hi) else False
        touches = int(np.sum(np.abs(hi[j + K + 1:M + 1] - v) <= TOUCH))
        c = -1 if not broken else (1 if p > v else 0)
    return c, touches >= 2


def main():
    from scipy.stats import binomtest
    import backtest.his_tape as TP
    from backtest.his_race_curve import race2
    cache = pickle.loads(TICKS.read_bytes())
    prep = {}
    for day, dd in cache.items():
        if dd is None:                                           # a day the cache holds no ticks for
            continue
        ts, mid = dd[0], dd[1]
        hi, lo = minute_bars(ts, mid)
        sh, sl = swings(hi, lo)
        prep[day] = (ts, mid, hi, lo, sh, sl)
    x = TP.entries()
    his = []
    for r in x.itertuples():
        pr = prep.get(r.d)
        if pr is None or r.t < 15 * 60:
            continue
        c, strong = call_at(*pr, r.t)
        his.append(dict(s=r.s, call=c, strong=strong, race=race2(pr[0], pr[1], r.t, r.s, 600, 7, 7)))
    H = pd.DataFrame(his)
    hc = H[H.call != 0]
    k = int((hc.s == hc.call).sum())
    pA = binomtest(k, len(hc), 0.5).pvalue if len(hc) else np.nan
    days = sorted(prep)
    cut = days[int(len(days) * 0.6)]
    rows = []
    for day in days:
        ts, mid, hi, lo, sh, sl = prep[day]
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            c, strong = call_at(ts, mid, hi, lo, sh, sl, t)
            if c != 0:
                w = race2(ts, mid, t, c, 600, 7, 7)
                if w is not None:
                    rows.append(dict(day=day, strong=strong, win=w))
    R = pd.DataFrame(rows)
    R["half"] = np.where(R.day < cut, "tune", "hold")
    out = [f"backtest/his_level_memory.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, split {pd.Timestamp(cut):%Y-%m-%d}; "
           f"swing levels of the last {LOOK} min (+-{K} bars), nearest within {NEAR:.0f} points, broken = traded > {BREAK:.0f} points beyond", "",
           f"  A HIS CLICKS: {len(H)} scored, {len(hc)} with a level-memory call; his side = the call on {k} ({k / max(len(hc), 1):.0%}), "
           f"binomial p {pA:.3f}; strong levels: {int((hc[hc.strong].s == hc[hc.strong].call).sum())} of {int(hc.strong.sum())}",
           f"    his race when he agreed with the call {hc[hc.s == hc.call].race.mean():.0%}, when he went against it {hc[hc.s != hc.call].race.mean():.0%}",
           "", "  B THE CALL AS A RULE (every 1-minute close + 14 s, 09:45-15:45 New York; +-7 race on the mid):"]
    res = {}
    for nm, m in (("all calls", np.ones(len(R), bool)), ("strong levels", R.strong.to_numpy())):
        for h in ("tune", "hold"):
            x_ = R[m & (R.half == h)]
            res[(nm, h)] = x_.win.mean()
            out.append(f"    {nm:<14} {h}: won {x_.win.mean():.1%} of {len(x_):,} races (p vs 50%: "
                       f"{binomtest(int(x_.win.sum()), len(x_), 0.5).pvalue:.3f})")
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  R1 his side agrees with the call 35-65%, p > 0.05 -> {ok(0.35 <= k / max(len(hc), 1) <= 0.65 and pA > 0.05)} ({k} of {len(hc)})",
            f"  R2 the rule wins 46-54% on both halves -> {ok(all(0.46 <= res[('all calls', h)] <= 0.54 for h in ('tune', 'hold')))}",
            f"  R3 strong levels <= 56% on both halves -> {ok(all(res[('strong levels', h)] <= 0.56 for h in ('tune', 'hold')))}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
