"""HIS EXIT SHAPE AND HIS LOSSES: what a +7 target with no stop really is, from RANDOM entries, and every combination of target and stop (2026-11-03)

The user, 2026-11-03: "the fact that we have achieved his win rate is enough now - what I want you to do is pattern recognition: how does he account for losses; also try every sort of combinations".
The claim to settle first: is his win rate (44 of 46 NASDAQ trades) reproducible by an exit rule alone, and is a win rate by itself money? his_strategy s25: "a 7-point target with no stop wins ~83% even at random". This puts
numbers on it, on the 181 days of Exness NASDAQ ticks (strategy_analysis/data/ustec_tick_days.pkl).

THE TEST. 20 random seconds a day (10:00-15:55 New York) x both sides, entered at the QUOTE (ask for a long, bid for a short), exited at the other side's quote, so the spread is charged exactly. For every combination of
target T in {3, 5, 7, 10, 15, 25} points and stop S in {none, 10, 20, 30, 50} points: the trade ends at the first target or stop touched; with no stop (his way) it is held to the 16:00 print if the target never comes.
Reported: win rate, mean win, mean loss, expected points a trade net of the spread, its day-clustered t, tune (first 60% of days) and holdout halves. Then the break-even win rate his exit shape needs, from the average loser of the
random entries, set against his 95.7%; and the +7 / no-stop trade by entry hour (the 'pattern in the losses' - do the losers cluster in time?).

REGISTERED BEFORE THE FIRST RUN (2026-11-03)
    H1  No (T, S) combination has a positive net expectancy with t >= 2 on BOTH halves (an exit rule cannot manufacture an edge from a random entry; it only reshapes the payoff). Every cell is negative or within noise,
        and the best is about minus the spread (-2.2 points).
    H2  The +7 / no-stop trade from random entries wins 78-88% (s25 said ~83%).
    H3  Its average loser is large (at least 25 points), so the break-even win rate is 88-94% - above any win rate a rule has reached at his moments (57%) and just below his own 95.7%.
    H4  By entry hour no cell is positive on both halves with t >= 2 after Holm over the hours x sides; losers are NOT concentrated in a time of day (win rate within 8 points across hours 10-15).

RESULT (2026-11-03; logs/his_exit_shape.txt; 7,192 random entries on 181 tick days)
    H1 RIGHT: 0 of 30 target x stop combinations is positive (expectancy -1.82 to -2.85 points a trade; the spread alone is ~2.2); the best is HIS shape, +7 with no stop, -1.82 (t -2.6; tune -2.29 / holdout -1.11).
    H2 WRONG: from random entries the +7 / no-stop trade held to the 16:00 print wins 93.7%, not ~83% (that figure was a short window). His 44 of 46 = 95.7% is INDISTINGUISHABLE from it (at a 6.3% loser rate he
    would be expected to have ~2.9 losers in 46 and had 2): HIS WIN RATE IS NOT EVIDENCE OF SKILL; it is what the exit shape does. H3 HALF RIGHT: the average random loser is -132 points (hours-long, to the close), so
    the break-even win rate is 95.0% (I predicted 88-94%), just below his 95.7%. His own record: average win +10.48, average loser -19.62 (n = 2), +9.17 a trade; break-even at his loser size 65.2%.
    H4 RIGHT: by entry hour nothing is significant (t >= 2.64 needed); win rate falls from 96.1% (10:00) to 90.1% (15:00) while the average loser shrinks from -202 to -82 points (less time before the close); the only hour
    positive on both halves is 11:00 New York (+0.50, t +0.4) - his famous cluster, not significant.
    Reading: an exit rule cannot make money from a random entry (the price has no drift; a high win rate only means tiny wins and rare, huge losers). What separates him is (a) his entries avoid the early adverse move
    (+7 before -7 in 88% vs 55%, his_strategy s37) and (b) his few losers were small (-19.6 average on two; -31.75 the worst). The earlier line 'bots built from his habits win about as often as he does' was loose: the
    stop versions won ~70%, the no-stop version wins ~94% like him - and loses 1.8 points a trade.

    python -m backtest.his_exit_shape        writes logs/his_exit_shape.txt          tests: python tests/test_his_exit_shape.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_ta import TICKS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (3, 5, 7, 10, 15, 25)
STOPS = (None, 10, 20, 30, 50)
PER_DAY = 20
BIG = 10**9


def path_points(ts, mid, spr, t, s):
    """Net points after an entry at second t on side s: the exit-side quote minus the entry quote, at every later tick (so an instant round trip reads -spread)."""
    i = int(np.searchsorted(ts, t, side="right")) - 1
    if i < 0 or i + 2 >= len(ts):
        return None
    e = mid[i] + s * spr[i] / 2
    return s * ((mid[i + 1:] - s * spr[i + 1:] / 2) - e)


def first_hits(p):
    """First tick index at which each target / stop is touched (BIG = never), and the final value."""
    up = {T: (int(np.argmax(p >= T)) if (p >= T).any() else BIG) for T in TARGETS}
    dn = {S: (int(np.argmax(p <= -S)) if (p <= -S).any() else BIG) for S in STOPS if S is not None}
    return up, dn, float(p[-1])


def outcome(up, dn, end, T, S):
    """Realised net points for target T and stop S (None = no stop): whichever is touched first; a stop and a target in the same tick count as the stop; else the last tick."""
    jt = up[T]
    js = dn[S] if S is not None else BIG
    if jt == BIG and js == BIG:
        return end
    return T if jt < js else -float(S)


def hour_of(t):
    """New York hour of an entry t seconds after the 09:30 open."""
    return int(9.5 + t / 3600.0)


def clustered_t(x, day):
    x, day = np.asarray(x, float), np.asarray(day)
    m = x.mean()
    codes = np.unique(day, return_inverse=True)[1]
    s, c = np.bincount(codes, weights=x), np.bincount(codes)
    g = len(s)
    se = np.sqrt(g / max(g - 1, 1) * np.sum((s - m * c) ** 2)) / len(x)
    return m, (m / se if se > 0 else 0.0)


def collect(cache, days, seed=41):
    rng = np.random.default_rng(seed)
    rows = []
    for d in days:
        ts, mid, spr = cache[d]
        for t in rng.uniform(1800, 23400 - 300, PER_DAY):
            for s in (1, -1):
                p = path_points(ts, mid, spr, t, s)
                if p is None:
                    continue
                up, dn, end = first_hits(p)
                rows.append(dict(day=d, side=s, hour=hour_of(t), up=up, dn=dn, end=end))
    return rows


def main():
    cache = pickle.loads(TICKS.read_bytes())
    days = [d for d in sorted(cache) if cache[d] is not None]
    cut = days[int(len(days) * 0.6)]
    rows = collect(cache, days)
    day = np.array([r["day"] for r in rows])
    tune = day < cut
    out = [f"backtest/his_exit_shape.py - {len(rows)} random entries on {len(days)} tick days (tune before {cut:%Y-%m-%d}), entered at the quote, net of the spread"]
    grid = {}
    for T in TARGETS:
        for S in STOPS:
            x = np.array([outcome(r["up"], r["dn"], r["end"], T, S) for r in rows])
            m, t = clustered_t(x, day)
            grid[(T, S)] = (m, t, x[tune].mean(), x[~tune].mean(), (x > 0).mean() * 100, x[x > 0].mean() if (x > 0).any() else 0.0, x[x <= 0].mean() if (x <= 0).any() else 0.0)
    out.append("\nEXPECTED NET POINTS A TRADE (win % in brackets), every combination; t is day-clustered:")
    out.append("   target \\ stop " + "".join(f"{('none' if S is None else S):>16}" for S in STOPS))
    for T in TARGETS:
        out.append(f"   +{T:<12}" + "".join(f"{grid[(T, S)][0]:>+8.2f} ({grid[(T, S)][4]:3.0f}%)  " for S in STOPS))
    pos = [(k, v) for k, v in grid.items() if v[0] > 0 and v[1] >= 2 and v[2] > 0 and v[3] > 0]
    best = max(grid.items(), key=lambda kv: kv[1][0])
    out.append(f"   combinations positive with t >= 2 on both halves: {len(pos)} of {len(grid)}; best {best[0]} {best[1][0]:+.2f} points (t {best[1][1]:+.1f}; tune {best[1][2]:+.2f}, holdout {best[1][3]:+.2f})")
    m, t, a, b, win, W, L = grid[(7, None)]
    pstar = -L / (7 + -L)
    out.append(f"\nHIS EXIT SHAPE from random entries (+7, no stop, held to 16:00): wins {win:.1f}%, average loser {L:+.1f} points, expectancy {m:+.2f} (t {t:+.1f}); "
               f"break-even win rate = {pstar * 100:.1f}%")
    his = pd.read_csv(ROOT / "logs" / "his_vs_market.csv")
    w, l = his.pts[his.pts > 0], his.pts[his.pts <= 0]
    out.append(f"HIS RECORD: {len(w)} wins of {len(his)} ({len(w) / len(his) * 100:.1f}%), average win {w.mean():+.2f}, average loser {l.mean() if len(l) else float('nan'):+.2f} points, "
               f"mean {his.pts.mean():+.2f} a trade; his break-even win rate at his own loser size = {(-l.mean() / (w.mean() - l.mean())) * 100 if len(l) else float('nan'):.1f}%")
    out.append("\nTHE +7 / NO-STOP TRADE BY ENTRY HOUR (New York), random entries - do the losers cluster in time?")
    out.append(f"   {'hour':>5}{'n':>7}{'win %':>7}{'avg loser':>10}{'net pts':>9}{'t':>6}{'tune':>8}{'holdout':>9}")
    hrs, ps = [], []
    for h in range(10, 16):
        mk = np.array([r["hour"] == h for r in rows])
        if mk.sum() < 50:
            continue
        x = np.array([outcome(r["up"], r["dn"], r["end"], 7, None) for r in rows])[mk]
        mm, tt = clustered_t(x, day[mk])
        out.append(f"   {h:>5}{mk.sum():>7}{(x > 0).mean() * 100:>7.1f}{x[x <= 0].mean() if (x <= 0).any() else 0:>+10.1f}{mm:>+9.2f}{tt:>+6.1f}{x[tune[mk]].mean():>+8.2f}{x[~tune[mk]].mean():>+9.2f}")
        hrs.append(h)
        ps.append(tt)
    out.append(f"   hours positive with t >= 2 on both halves: see the table (a positive cell needs t >= {2.64:.2f} after Holm over {len(hrs)} hours x 2 halves)")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_exit_shape.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
