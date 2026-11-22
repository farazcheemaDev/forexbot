"""TICK CHARTS AND RENKO AT HIS CLICKS - does another chart type fit his timing or his side better than the 1-minute chart? (2026-11-22)

THE USER (2026-11-22): "run tick and renko charts" - item 5 of the study list. A TICK chart closes a candle every N price updates; a RENKO
chart draws a brick each time the price moves B points (one brick to continue, two to reverse), so it ignores time. Either can show a
signal a 1-minute chart hides. What we know: his NASDAQ entries cluster 5-24 s after a 1-MINUTE candle closes (his_click_timing.py, 24 of
46, p 0.006) - a person reacting to a closed bar. If he really reacts to a tick candle or a Renko brick instead, his clicks should sit
just after THOSE closes even more tightly.
DATA   Exness USTECm ticks (ustec_tick_days.pkl, 181 days, mid); his NASDAQ clicks (his_tape.entries, the corrected clock) and his 31 sitting
       windows (his_tape.windows). RENKO is price-only, so his broker's Renko (CapitalFX = Exness + ~207 points, his_chart_capfx.py) is this
       one on a shifted grid: every brick size is run on 10 grid offsets (steps of B/10), Renko started at the day's first tick (09:30). A
       TICK chart counts HIS broker's quotes, which we do not have: Exness's quote count is only a stand-in (10 phases per size).
A  TIMING  the share of his clicks 5-24 s after the last bar close (the 1-minute window), per chart setting; the statistic is the BEST of
           its 10 offsets, judged against 2,000 sets of pseudo-clicks (each click moved to a random second of its own sitting window) run
           through the same best-of-10 - so the offset search is paid for. Renko B = 5 / 7 / 10 / 15 / 20 points; tick N = 100 / 250 /
           500 / 1,000 / 2,000 quotes; the 1-minute chart as the reference.
B  DIRECTION at his clicks: his side vs the last Renko brick (B 5 / 10 / 20, offset 0) and vs the last tick candle's body (N 250 / 500 /
           1,000, phase 0). As RULES on every day (09:45-15:45, 14 s after each close, the +-7 race, 10 minutes, by half): Renko
           continuation (the last brick's way) and the first counter brick after a run of 3+ (the new way; the 'buy the dip' trade is its
           mirror); tick-candle body continuation and reversal wicks (a lower wick of half the range closing in the upper half -> buy;
           the mirror -> sell).
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  K1  No tick or Renko setting fits his click timing better than chance after the offset search (every p > 0.05, Holm over 10). (70%)
  K2  The 1-minute chart's timing fit is stronger (a smaller p) than every tick and Renko setting's. (60%)
  K3  Renko rules win 47-53% of races on both halves at every brick size. (70%)
  K4  Tick-candle rules win 47-53% on both halves at every size. (75%)
  K5  His side matches the last Renko brick and the last tick candle's body on 35-65% of his clicks at every size. (65%)
  Bar for a LEAD: a rule at 56%+ on both halves; for a trade, 61% (the +-7 race after a ~1.5-point spread).

RESULT (2026-11-22, logs/his_alt_charts.txt): HE READS A 1-MINUTE TIME CHART, NOT TICK CANDLES OR RENKO. 42 clicks with ticks on 27 days.
  Timing: 55% of his clicks come 5-24 s after a 1-MINUTE close against 31% of random seconds in his sittings (p 0.002 - the earlier finding
  replicated); no tick or Renko setting beats chance once the offset search is paid for (best: tick 250 at 64% vs 49%, raw p 0.19; Renko
  5 at 40% vs 33%, p 0.51; Holm 1.00 for all ten). Direction: his side matches the last Renko brick 57% / 45% / 62% (5 / 10 / 20 points)
  and the last tick candle's body 49% / 54% / 52% - ordinary. As rules on 181 days: Renko continuation 48.4-50.7%, the first counter
  brick 48.7-53.0%, tick-candle continuation 49.2-49.8%, reversal wicks 48.7-50.2%. K1-K5 right; no LEAD.

    python -m backtest.his_alt_charts
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_level_memory import TICKS  # noqa: E402

LOG = ROOT / "logs" / "his_alt_charts.txt"
RENKO = (5.0, 7.0, 10.0, 15.0, 20.0)
TICKN = (100, 250, 500, 1000, 2000)
NOFF, NULL, LO, HI = 10, 2000, 5.0, 24.0


def renko_events(ts: np.ndarray, mid: np.ndarray, B: float, off: float):
    """Classic Renko (one brick to continue, two to reverse) on the grid off + k*B from the day's first tick: one event per tick that
    completes bricks -> (time, direction, bricks)."""
    n = len(mid)
    times, dirs, cnts = [], [], []
    if n == 0:
        return np.array(times), np.array(dirs, int), np.array(cnts, int)
    base = off + np.round((mid[0] - off) / B) * B
    up, dn = base + B, base - B
    i, CH = 0, 4096
    while i < n:
        w = mid[i:i + CH]
        hit = np.flatnonzero((w >= up) | (w <= dn))
        if not len(hit):
            i += CH
            continue
        j = i + int(hit[0])
        p = mid[j]
        if p >= up:
            k = int(np.floor((p - up) / B)) + 1
            top = up + (k - 1) * B
            up, dn = top + B, top - 2 * B
            times.append(ts[j]); dirs.append(1); cnts.append(k)
        else:
            k = int(np.floor((dn - p) / B)) + 1
            bot = dn - (k - 1) * B
            dn, up = bot - B, bot + 2 * B
            times.append(ts[j]); dirs.append(-1); cnts.append(k)
        i = j + 1
    return np.array(times), np.array(dirs, int), np.array(cnts, int)


def prior_run(dirs: np.ndarray, cnts: np.ndarray) -> np.ndarray:
    """For each event, the bricks of the run it ENDS if it reverses (0 if it continues)."""
    out = np.zeros(len(dirs), int)
    run = 0
    for e in range(len(dirs)):
        if e and dirs[e] != dirs[e - 1]:
            out[e] = run
            run = cnts[e]
        else:
            run += cnts[e]
    return out


def tick_bars(ts: np.ndarray, mid: np.ndarray, N: int, phase: int):
    """Candles of N quotes (the day's first `phase` quotes form a partial first candle); the last, unfinished candle is dropped:
    (close time, open, high, low, close)."""
    idx = (np.arange(len(mid)) + phase) // N
    ends = np.flatnonzero(np.r_[idx[1:] != idx[:-1], True])
    starts = np.r_[0, ends[:-1] + 1]
    o, c = mid[starts], mid[ends]
    h, l = np.maximum.reduceat(mid, starts), np.minimum.reduceat(mid, starts)
    return ts[ends][:-1], o[:-1], h[:-1], l[:-1], c[:-1]


def since_last(E: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Seconds since the last event at or before each t (NaN before the first)."""
    k = np.searchsorted(E, t, side="right") - 1
    out = np.full(t.shape, np.nan)
    ok = k >= 0
    out[ok] = t[ok] - E[k[ok]]
    return out


def main():
    from scipy.stats import binomtest
    import backtest.his_tape as TP
    from backtest.his_race_curve import race2
    cache = pickle.loads(TICKS.read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]

    # his clicks and their sitting windows, in seconds since 09:30 New York of the day
    x = TP.entries()
    wins = TP.windows(x)
    clicks = []
    for r in x.itertuples():
        if r.d not in cache or cache[r.d] is None or not (0 <= r.t <= 36_000):
            continue
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        cu = base + pd.Timedelta(seconds=float(r.t))
        w = next(((a, b) for a, b in wins if a <= cu <= b), (cu - pd.Timedelta(minutes=22), cu + pd.Timedelta(minutes=20)))
        a_s, b_s = (w[0] - base).total_seconds(), (w[1] - base).total_seconds()
        clicks.append(dict(d=r.d, t=float(r.t), s=int(r.s), a=max(a_s, 0.0), b=min(b_s, 36_000.0)))
    C = pd.DataFrame(clicks)
    rng = np.random.default_rng(20261122)
    P = np.stack([rng.uniform(r.a, r.b, NULL) for r in C.itertuples()])           # pseudo-clicks: clicks x NULL

    # A. timing
    def in_win(sv):
        return (sv >= LO) & (sv <= HI)

    rowsA = []
    f_min = float(in_win(C.t.to_numpy() % 60).mean())
    f_min_null = in_win(P % 60).mean(axis=0)
    p_min = float((f_min_null >= f_min).mean())
    rowsA.append(("1-minute candles (reference)", f_min, float(f_min_null.mean()), p_min, "-"))
    for kind, sizes in (("Renko", RENKO), ("tick", TICKN)):
        for z in sizes:
            his_f, null_f = [], []
            for k in range(NOFF):
                sv_h, sv_n = np.full(len(C), np.nan), np.full(P.shape, np.nan)
                for d in C.d.unique():
                    ts, mid = cache[d][0], cache[d][1]
                    if kind == "Renko":
                        E = renko_events(ts, mid, z, k * z / NOFF)[0]
                    else:
                        E = tick_bars(ts, mid, int(z), int(k * z // NOFF))[0]
                    m = (C.d == d).to_numpy()
                    sv_h[m] = since_last(E, C.t.to_numpy()[m])
                    sv_n[m] = since_last(E, P[m])
                his_f.append(float(in_win(sv_h).mean()))
                null_f.append(in_win(sv_n).mean(axis=0))
            best_k = int(np.argmax(his_f))
            best = his_f[best_k]
            null_best = np.max(np.stack(null_f), axis=0)
            rowsA.append((f"{kind} {z:g}", best, float(np.mean([v.mean() for v in null_f])), float((null_best >= best).mean()), best_k))
    pv = np.array([r[3] for r in rowsA[1:]])
    order = np.argsort(pv)
    holm = np.empty_like(pv)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, pv[i] * (len(pv) - rank)))
        holm[i] = run

    # B. direction at his clicks, and the rules on every day
    agree = {}
    for B in (5.0, 10.0, 20.0):
        k = n = 0
        for r in C.itertuples():
            ts, mid = cache[r.d][0], cache[r.d][1]
            E, D, _ = renko_events(ts, mid, B, 0.0)
            j = np.searchsorted(E, r.t - 1.0, side="right") - 1
            if j >= 0:
                n += 1
                k += int(D[j] == r.s)
        agree[f"Renko {B:g}"] = (k, n)
    for N in (250, 500, 1000):
        k = n = 0
        for r in C.itertuples():
            ts, mid = cache[r.d][0], cache[r.d][1]
            tc, o, h, l, c = tick_bars(ts, mid, N, 0)
            j = np.searchsorted(tc, r.t - 1.0, side="right") - 1
            if j >= 0 and c[j] != o[j]:
                n += 1
                k += int(np.sign(c[j] - o[j]) == r.s)
        agree[f"tick {N}"] = (k, n)

    rules = []
    for d in days:
        ts, mid = cache[d][0], cache[d][1]
        half = "tune" if d < cut else "hold"
        for B in (5.0, 10.0, 20.0):
            E, D, K = renko_events(ts, mid, B, 0.0)
            pr = prior_run(D, K)
            for e in range(len(E)):
                t = E[e] + 14.0
                if not (15 * 60 <= E[e] <= 375 * 60):
                    continue
                w = race2(ts, mid, t, int(D[e]), 600, 7, 7)
                if w is None:
                    continue
                rules.append(dict(half=half, rule=f"Renko {B:g}: continuation", win=w))
                if pr[e] >= 3:
                    rules.append(dict(half=half, rule=f"Renko {B:g}: first counter brick after 3+", win=w))
        for N in (250, 500, 1000):
            tc, o, h, l, c = tick_bars(ts, mid, N, 0)
            rg = h - l
            for i in np.flatnonzero((tc >= 15 * 60) & (tc <= 375 * 60) & (rg > 0)):
                t = tc[i] + 14.0
                body = c[i] - o[i]
                lw, uw = (min(o[i], c[i]) - l[i]) / rg[i], (h[i] - max(o[i], c[i])) / rg[i]
                cl = (c[i] - l[i]) / rg[i]
                if body != 0:
                    w = race2(ts, mid, t, int(np.sign(body)), 600, 7, 7)
                    if w is not None:
                        rules.append(dict(half=half, rule=f"tick {N}: body continuation", win=w))
                sd = 1 if (lw >= 0.5 and cl >= 0.5) else (-1 if (uw >= 0.5 and cl <= 0.5) else 0)
                if sd:
                    w = race2(ts, mid, t, sd, 600, 7, 7)
                    if w is not None:
                        rules.append(dict(half=half, rule=f"tick {N}: reversal wick", win=w))
    RU = pd.DataFrame(rules)
    tab = RU.groupby(["rule", "half"]).win.agg(["mean", "size"]).unstack("half")

    out = [f"backtest/his_alt_charts.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, split {pd.Timestamp(cut):%Y-%m-%d}; "
           f"his clicks with ticks {len(C)} on {C.d.nunique()} days; pseudo-click sets {NULL}", "",
           f"  A. TIMING - share of clicks {LO:g}-{HI:g} s after the last close (best of {NOFF} offsets for tick / Renko; the null pays for it)",
           f"    {'chart':<30}{'his clicks':>12}{'random':>10}{'p':>8}{'Holm':>8}{'best offset':>13}"]
    for i, (nm, f, f0, p, bk) in enumerate(rowsA):
        hm = "-" if i == 0 else f"{holm[i - 1]:.2f}"
        out.append(f"    {nm:<30}{f:>11.0%}{f0:>10.0%}{p:>8.3f}{hm:>8}{str(bk):>13}")
    out += ["", "  B. DIRECTION - his side vs the last Renko brick / the last tick candle's body"]
    for nm, (k, n) in agree.items():
        out.append(f"    {nm:<12} his side = it on {k} of {n} ({k / max(n, 1):.0%}; binomial p {binomtest(k, n, 0.5).pvalue:.2f})")
    out += ["", "  B. RULES on every day (14 s after each close, the +-7 race)", f"    {'rule':<46}{'tune':>18}{'holdout':>18}"]
    res = {}
    for rule in tab.index:
        cells = []
        for h_ in ("tune", "hold"):
            m_, n_ = tab.loc[rule, ("mean", h_)], tab.loc[rule, ("size", h_)]
            res[(rule, h_)] = m_
            cells.append(f"{m_:.1%} of {int(n_):,}")
        out.append(f"    {rule:<46}{cells[0]:>18}{cells[1]:>18}")
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    alt_p = [r[3] for r in rowsA[1:]]
    renko_rules = [v for (rl, _), v in res.items() if rl.startswith("Renko")]
    tick_rules = [v for (rl, _), v in res.items() if rl.startswith("tick")]
    lead = sorted({rl for (rl, _), v in res.items() if all(res[(rl, h_)] >= 0.56 for h_ in ("tune", "hold"))})
    out += ["", "REGISTERED PREDICTIONS",
            f"  K1 no tick / Renko setting fits his timing after the offset search (Holm p > 0.05) -> {ok(all(h > 0.05 for h in holm))} "
            f"(smallest raw p {min(alt_p):.3f}, Holm {holm.min():.2f})",
            f"  K2 the 1-minute fit is stronger than every tick / Renko setting's -> {ok(p_min < min(alt_p))} (1-minute p {p_min:.3f})",
            f"  K3 Renko rules 47-53% on both halves -> {ok(all(0.47 <= v <= 0.53 for v in renko_rules))} "
            f"({min(renko_rules):.1%} .. {max(renko_rules):.1%})",
            f"  K4 tick-candle rules 47-53% on both halves -> {ok(all(0.47 <= v <= 0.53 for v in tick_rules))} "
            f"({min(tick_rules):.1%} .. {max(tick_rules):.1%})",
            f"  K5 his side = the last brick / candle on 35-65% -> {ok(all(0.35 <= k / max(n, 1) <= 0.65 for k, n in agree.values()))}",
            f"  LEAD (56%+ on both halves): {', '.join(lead) if lead else 'none'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
