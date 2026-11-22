"""THE FAILED BREAK ('stop hunt') AT A RECENT LEVEL - his 7-of-7 pattern, tested on every day (2026-11-22)

THE USER (2026-11-22): "don't be pessimistic ... in one minute I moved you toward this hint of 'against it'" - after his_level_memory.py
showed him trading AGAINST the textbook level call. The case list (this session) narrowed it: at a swing level that had BROKEN (the price
went more than 3 points beyond it) with the price back near it from the broken side, he traded BACK THROUGH it - a broken low with the
price below it -> BUY, a broken high with the price above it -> SELL - 7 times, and won all 7 (02-17, 02-27, 03-02, 04-06, 06-05, 07-01,
09-14); going with the break there he won 2 of 4. That is the failed-break / stop-hunt reclaim. FOUND IN HIS TRADES (post hoc), so only
the whole market can confirm it.
DATA   Exness USTECm ticks (strategy_analysis/data/ustec_tick_days.pkl, 181 days 2026-01-02 .. 09-14), his_level_memory's levels (swing
       highs / lows of the closed 1-minute bars of the last 120 minutes, +-3 bars, the nearest within 10 points), broken = traded > 3
       points beyond since it formed.
THE RULE at every 1-minute close + 14 s (his habit), 09:45-15:45 New York: the nearest level is BROKEN and the price is back within 10
       points of it from the broken side -> trade back through it (RECLAIM side); the textbook CONTINUATION side for comparison. Subsets:
       FRESH (the break happened in the last 15 minutes), STRONG (the level was touched at least twice), and both.
OUTCOME the +-7 race on the mid (race2, 10 minutes), by half (first 60% of days / the rest). Break-even after a ~1.5-point spread at +-7:
       a 61% race.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  B1  The reclaim rule wins 50-56% of races on both halves - far from his 88% and under the 61% it needs to pay. (70%)
  B2  FRESH + STRONG lifts it to at most 58% on either half. (70%)
  B3  His own trades in the rule's set beat the rule's rate by 25+ points (his edge is not the pattern). (65%)

RESULT (2026-11-22, logs/his_reclaim.txt): A REAL PIECE OF HIS PLAYBOOK, NOT HIS EDGE. 21,211 moments on 181 days with a broken level and the
  price back on the broken side: the reclaim side won 50.1% / 52.4% of +-7 races (tune / holdout; holdout p < 0.001 - a sliver),
  continuation 49.9% / 47.6%; fresh breaks the same; strong levels 50.7% / 51.2%; fresh + strong 50.8% / 51.2%. His own clicks in this
  set: 11 - the reclaim side 7 times, won 7 of 7; the continuation side 4 times, won 2. He trades fake breaks (stop-hunt reclaims), and
  picks the ones that work: the setup is a coin flip, his choice inside it is not. B1-B3 right. Needs 61% to pay a ~1.5-point spread.

    python -m backtest.his_reclaim
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_level_memory import BREAK, K, LOOK, NEAR, TICKS, TOUCH, minute_bars, swings  # noqa: E402

LOG = ROOT / "logs" / "his_reclaim.txt"
FRESH = 15


def broken_level(ts, mid, hi, lo, sh, sl, t: float):
    """The nearest swing level within NEAR points, if it is BROKEN and the price is back on the broken side:
    returns (reclaim side, fresh, strong) or None."""
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
        side = 1                                                     # back above the broken low
        touches = int(np.sum(np.abs(lo[j + K + 1:j + 1 + brk[0]] - v) <= TOUCH))
    else:
        brk = np.flatnonzero(seg_hi > v + BREAK)
        if not len(brk) or p <= v:
            return None
        side = -1                                                    # back below the broken high
        touches = int(np.sum(np.abs(hi[j + K + 1:j + 1 + brk[0]] - v) <= TOUCH))
    fresh = (M - (j + 1 + int(brk[-1]))) <= FRESH                  # the latest bar beyond the level is recent
    return side, fresh, touches >= 1                               # touched again (at least once) before the break: 2+ tests in all


def main():
    from scipy.stats import binomtest
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
            b = broken_level(ts, mid, hi, lo, sh, sl, t)
            if b is None:
                continue
            side, fresh, strong = b
            w_re, w_co = race2(ts, mid, t, side, 600, 7, 7), race2(ts, mid, t, -side, 600, 7, 7)
            if w_re is not None:
                rows.append(dict(day=day, fresh=fresh, strong=strong, reclaim=w_re, cont=w_co))
    R = pd.DataFrame(rows)
    R["half"] = np.where(R.day < cut, "tune", "hold")
    out = [f"backtest/his_reclaim.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, split {pd.Timestamp(cut):%Y-%m-%d}; "
           f"moments with a broken level and the price back on the broken side: {len(R):,}", "",
           f"  {'subset':<16}{'half':>6}{'moments':>9}{'RECLAIM won':>13}{'p':>8}{'continuation won':>18}"]
    res = {}
    for nm, m in (("all", np.ones(len(R), bool)), ("fresh", R.fresh.to_numpy()), ("strong", R.strong.to_numpy()),
                  ("fresh + strong", (R.fresh & R.strong).to_numpy())):
        for h in ("tune", "hold"):
            x = R[m & (R.half == h)]
            if not len(x):
                continue
            wr = x.reclaim.mean()
            res[(nm, h)] = wr
            out.append(f"  {nm:<16}{h:>6}{len(x):>9,}{wr:>12.1%}{binomtest(int(x.reclaim.sum()), len(x), 0.5).pvalue:>8.3f}"
                       f"{x.cont.dropna().mean():>17.1%}")
    # his own trades that fall in the rule's set
    x = TP.entries()
    hrows = []
    for r in x.itertuples():
        pr = prep.get(r.d)
        if pr is None or r.t < 15 * 60:
            continue
        b = broken_level(*pr, r.t)
        if b is None:
            continue
        side, fresh, strong = b
        hrows.append(dict(with_rule=r.s == side, race=race2(pr[0], pr[1], r.t, r.s, 600, 7, 7), fresh=fresh, strong=strong))
    Hh = pd.DataFrame(hrows)
    hr = Hh[Hh.with_rule]
    out += ["", f"  HIS clicks in the rule's set: {len(Hh)}; he took the reclaim side on {len(hr)}, won the race on "
                f"{int((hr.race == 1).sum())} of {int(hr.race.notna().sum())}; the continuation side on {len(Hh) - len(hr)}, won "
                f"{int((Hh[~Hh.with_rule].race == 1).sum())} of {int(Hh[~Hh.with_rule].race.notna().sum())}"]
    allr = R.reclaim.mean()
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  B1 the reclaim rule 50-56% on both halves -> {ok(all(0.50 <= res[('all', h)] <= 0.56 for h in ('tune', 'hold')))} ("
            f"{res[('all', 'tune')]:.1%} / {res[('all', 'hold')]:.1%})",
            f"  B2 fresh + strong at most 58% on either half -> {ok(all(res.get(('fresh + strong', h), 0) <= 0.58 for h in ('tune', 'hold')))}",
            f"  B3 his reclaim trades beat the rule by 25+ points -> {ok((hr.race == 1).mean() - allr >= 0.25)} "
            f"({(hr.race == 1).mean():.0%} vs {allr:.0%})"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
