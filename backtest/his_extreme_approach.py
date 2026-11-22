"""AT THE EDGE: FADE A CLIMAX, FOLLOW A STAIRCASE? - the one new idea from LOOKING at his 42 trades (2026-11-22)

THE USER (2026-11-22): "you will notice yourself, not me" - after the picture book (his_picture_book.py, logs/his_picture_book/). What the
pages showed: no single picture repeats; about 16 trades FADE a sharp push at the edge of the session / recent range, about 20 follow the
15-30-minute move after a candle or two against it (his_setup_sweep.py already tested that: 49-50%), 4 BUY a fresh session high; and he
takes OPPOSITE sides on the same chart within seconds (#10/#11, #26-#28). The new idea: at the edge, his fades seem to come after a FAST,
climax-like push (#1, #7, #13, #26) and his breakout buys after a SLOW staircase climb (#5, #6, #31) - so the SPEED of the approach would
tell fade from follow. FOUND BY LOOKING AT HIS TRADES, so his trades fitting it proves nothing; only the market can confirm it.
DATA   Exness USTECm ticks (ustec_tick_days.pkl, 181 days, mid), 1-minute bars from them; his NASDAQ clicks (his_tape.entries).
AT THE EDGE  every 1-minute close + 14 s, 09:45-15:45 New York: the last closed bar made (or came within 2 points of) the high (low) of the
       last 60 bars, and the price is still within 5 points of it.
APPROACH  the 5-bar move into the edge (close of the last bar minus the close 5 bars before, signed toward the edge) against the median
       absolute 5-bar move of the 55 bars before: CLIMAX = 2x or more; STAIRCASE = more than 0 and at most 1x.
THE RULE  climax at a high -> sell, at a low -> buy (fade); staircase at a high -> buy, at a low -> sell (follow). The +-7 race on the
       mid (race2, 10 minutes), by half (first 60% of days / the rest).
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  X1  Climax fades win 47-53% of races on both halves. (65%)
  X2  Staircase follows win 47-53% on both halves. (65%)
  X3  The rule's side (both kinds together) wins under 56% on both halves. (80%)
  X4  (post hoc, not evidence) his classified clicks match the rule's side on 55-90%.
  Bar for a LEAD: 56%+ on both halves; for a trade, 61% (the +-7 race after a ~1.5-point spread).
  FRESH CHECK (added 2026-11-22 after the first run read CLIMAX -> fade at 53.8% / 55.1%, before any fresh number): the same rule on the
  44 fresh tick days 2026-09-17 .. 11-20 (weak_break.py's MT5 fetch, strategy_analysis/data/fresh/, never used by this file before).
  X5  Fresh climax fades win 52%+ with a day-bootstrap 90% interval above 50%. (35%)

RESULT (2026-11-22, logs/his_extreme_approach.txt, logs/his_extreme_approach_fresh.txt): FOUND IN THE SEEN DAYS, GONE ON FRESH ONES. On the
  181 seen days (10:36-15:45; the 60-bar look-back), 3,204 classified edge moments: CLIMAX -> fade 53.8% / 55.1% (tune / holdout; X1
  wrong - stronger than predicted), STAIRCASE -> follow 47.2% / 49.9%, both kinds 51.0% / 53.1%. On 44 fresh days (2026-09-17 .. 11-20):
  CLIMAX -> fade 50.1% of 491 moments (day-bootstrap 90% interval 44.9% .. 55.1%), STAIRCASE -> follow 49.8% of 219 - X5 wrong. His
  clicks cannot confirm it either way: the 60-bar look-back starts at 10:36 and only 1 of his 46 clicks sat at a 60-bar edge by this
  definition (the early fades, 09:51-10:33, fall before it). X2, X3 right; X1, X4, X5 wrong. No LEAD.

    python -m backtest.his_extreme_approach --fresh

    python -m backtest.his_extreme_approach
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_brooks import ohlc  # noqa: E402
from backtest.his_level_memory import TICKS  # noqa: E402

LOG = ROOT / "logs" / "his_extreme_approach.txt"
LOOK, NEAR_EDGE, NEAR_PRICE, CLIMAX, STAIR = 60, 2.0, 5.0, 2.0, 1.0


def classify(ts, mid, h, l, c, t: float):
    """(edge 'high' / 'low', approach 'climax' / 'staircase' / None, the rule's side) at moment t, or None off the edge."""
    M = int(t // 60) - 1
    if M < LOOK + 5 or M >= len(h):
        return None
    hh, ll = np.nanmax(h[M - LOOK + 1:M + 1]), np.nanmin(l[M - LOOK + 1:M + 1])
    i = np.searchsorted(ts, t - 1.0, side="right") - 1
    if i < 0 or not (np.isfinite(h[M]) and np.isfinite(l[M]) and np.isfinite(c[M]) and np.isfinite(c[M - 5])):
        return None
    p = float(mid[i])
    at_hi = h[M] >= hh - NEAR_EDGE and hh - p <= NEAR_PRICE
    at_lo = l[M] <= ll + NEAR_EDGE and p - ll <= NEAR_PRICE
    if at_hi == at_lo:
        return None
    edge = "high" if at_hi else "low"
    toward = 1 if at_hi else -1
    cc = c[M - LOOK + 1:M - 4]
    d5 = np.abs(cc[5:] - cc[:-5])
    d5 = d5[np.isfinite(d5)]
    if len(d5) < 20 or np.median(d5) <= 0:
        return None
    ratio = toward * (c[M] - c[M - 5]) / float(np.median(d5))
    kind = "climax" if ratio >= CLIMAX else ("staircase" if 0 < ratio <= STAIR else None)
    if kind is None:
        return edge, None, 0
    side = -toward if kind == "climax" else toward
    return edge, kind, side


def fresh():
    from backtest.his_race_curve import race2
    path = ROOT / "strategy_analysis" / "data" / "fresh" / "ustec_tick_days_fresh.pkl"
    cache = pickle.loads(path.read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    rows = []
    for d in days:
        ts, mid = cache[d][0], cache[d][1]
        o, h, l, c = ohlc(ts, mid)
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            r = classify(ts, mid, h, l, c, t)
            if r is None or r[1] is None:
                continue
            w = race2(ts, mid, t, r[2], 600, 7, 7)
            if w is not None:
                rows.append(dict(day=d, kind=r[1], win=w))
    R = pd.DataFrame(rows)
    rng = np.random.default_rng(5)
    out = [f"backtest/his_extreme_approach.py --fresh, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} fresh tick days "
           f"{days[0]:%Y-%m-%d} .. {days[-1]:%Y-%m-%d}; classified edge moments {len(R):,}"]
    res = {}
    for kind, lab in (("climax", "CLIMAX -> fade"), ("staircase", "STAIRCASE -> follow")):
        x = R[R.kind == kind]
        codes, uniq = pd.factorize(x.day)
        win = x.win.to_numpy(float)
        bs = []
        for _ in range(2000):
            w = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))[codes].astype(float)
            bs.append((w * win).sum() / w.sum())
        lo, hi = np.percentile(bs, [5, 95])
        res[kind] = (win.mean(), lo, hi)
        out.append(f"    {lab:<24} {win.mean():.1%} of {len(x):,} moments on {len(uniq)} days (day-bootstrap 90% interval {lo:.1%} .. {hi:.1%})")
    m, lo, hi = res["climax"]
    out += ["", f"  X5 fresh climax fades 52%+ with the interval above 50% -> {'RIGHT' if m >= 0.52 and lo > 0.50 else 'WRONG'}"]
    txt = chr(10).join(out)
    (ROOT / "logs" / "his_extreme_approach_fresh.txt").write_text(txt + chr(10), encoding="utf-8")
    print(txt)


def main():
    from scipy.stats import binomtest
    import backtest.his_tape as TP
    from backtest.his_race_curve import race2
    cache = pickle.loads(TICKS.read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    rows = []
    bars = {}
    for d in days:
        ts, mid = cache[d][0], cache[d][1]
        o, h, l, c = ohlc(ts, mid)
        bars[d] = (h, l, c)
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            r = classify(ts, mid, h, l, c, t)
            if r is None or r[1] is None:
                continue
            w = race2(ts, mid, t, r[2], 600, 7, 7)
            if w is not None:
                rows.append(dict(day=d, edge=r[0], kind=r[1], win=w))
    R = pd.DataFrame(rows)
    R["half"] = np.where(R.day < cut, "tune", "hold")
    his = []
    for x in TP.entries().itertuples():
        if x.d not in bars:
            continue
        ts, mid = cache[x.d][0], cache[x.d][1]
        h, l, c = bars[x.d]
        r = classify(ts, mid, h, l, c, float(x.t))
        if r is None:
            continue
        his.append(dict(d=x.d, s=x.s, edge=r[0], kind=r[1], side=r[2], won=race2(ts, mid, x.t, x.s, 600, 7, 7)))
    Hh = pd.DataFrame(his)
    out = [f"backtest/his_extreme_approach.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, split {pd.Timestamp(cut):%Y-%m-%d}; "
           f"moments at a 60-bar edge with a classified approach: {len(R):,}", "",
           f"    {'':<40}{'tune':>18}{'holdout':>18}"]
    res = {}
    for nm, m in (("CLIMAX -> fade", R.kind == "climax"), ("STAIRCASE -> follow", R.kind == "staircase"),
                  ("climax at a high -> sell", (R.kind == "climax") & (R.edge == "high")),
                  ("climax at a low -> buy", (R.kind == "climax") & (R.edge == "low")),
                  ("staircase at a high -> buy", (R.kind == "staircase") & (R.edge == "high")),
                  ("staircase at a low -> sell", (R.kind == "staircase") & (R.edge == "low")),
                  ("the rule, both kinds", pd.Series(True, index=R.index))):
        cells = []
        for h_ in ("tune", "hold"):
            y = R[m & (R.half == h_)]
            res[(nm, h_)] = y.win.mean() if len(y) else np.nan
            cells.append(f"{y.win.mean():.1%} of {len(y):,}" if len(y) else "-")
        out.append(f"    {nm:<40}{cells[0]:>18}{cells[1]:>18}")
    at_edge = Hh[Hh.kind.notna()] if len(Hh) else Hh
    k = int((at_edge.s == at_edge.side).sum()) if len(at_edge) else 0
    out += ["", f"  HIS CLICKS: {len(Hh)} at a 60-bar edge of {len(TP.entries())}; with a classified approach {len(at_edge)}; his side = the rule's on "
                f"{k} ({k / max(len(at_edge), 1):.0%}; binomial p {binomtest(k, len(at_edge), 0.5).pvalue if len(at_edge) else float('nan'):.2f})"]
    for r in Hh.itertuples():
        out.append(f"    {r.d:%Y-%m-%d} {'BUY ' if r.s > 0 else 'SELL'} at the {r.edge:<4}  approach {r.kind or 'in between':<10}  "
                   f"rule {'-' if not r.side else ('buy' if r.side > 0 else 'sell'):<5} {'MATCH' if r.side and r.side == r.s else '':<6} "
                   f"{'won' if r.won == 1 else 'lost' if r.won == 0 else '-'}")
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    x1 = all(0.47 <= res[("CLIMAX -> fade", h_)] <= 0.53 for h_ in ("tune", "hold"))
    x2 = all(0.47 <= res[("STAIRCASE -> follow", h_)] <= 0.53 for h_ in ("tune", "hold"))
    x3 = all(res[("the rule, both kinds", h_)] < 0.56 for h_ in ("tune", "hold"))
    lead = [nm for nm in ("CLIMAX -> fade", "STAIRCASE -> follow", "the rule, both kinds") if all(res[(nm, h_)] >= 0.56 for h_ in ("tune", "hold"))]
    out += ["", "REGISTERED PREDICTIONS",
            f"  X1 climax fades 47-53% on both halves -> {ok(x1)}", f"  X2 staircase follows 47-53% on both halves -> {ok(x2)}",
            f"  X3 the rule under 56% on both halves -> {ok(x3)}",
            f"  X4 (post hoc) his classified clicks match 55-90% -> {ok(0.55 <= k / max(len(at_edge), 1) <= 0.90)}",
            f"  LEAD (56%+ on both halves): {', '.join(lead) if lead else 'none'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    fresh() if "--fresh" in sys.argv else main()
