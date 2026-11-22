"""IF YOU FOLLOW THE ANALYST TAB'S SIGNALS: HOW THEY PERFORMED AND HOW OFTEN THEY CAME (2026-11-15)

THE USER (2026-11-15), after the Analyst tab was rebuilt around one graded signal: "if I follow these signals how will it perform and how often
should I get strong signals". The tab grades each idea (dashboard/lib/sizepanel.mjs gradeCall): BEST SETUP = a stop of 0.8% or more and AGAINST
the market's mood (analyst.lean_of); WEAKER SETUP = a stop of 0.8% or more WITH the mood; SKIP = a tighter stop. (The tab also skips an idea the
price has already run through; at the moment a call is made it is live, so that part does not apply here.)

DATA     the desk's replay (strategy_analysis/data/analyst_replay/calls.json: its three rules on 1h bars 2022-02 .. 2026-09, a bar touching both stop
         and target = loss, 12bp a round trip) for the five crypto coins, with the works map's market state of the day each call was made
         (analyst_states.load). Halves split 2024-12-07 (the replay's own). A bet = the calls made the same UTC day in the same direction.
ACCOUNT  $100, every call of a grade followed at 1% (and 2%) of the equity BOOKED at its entry (entry-sized, compounded by close date - CLAUDE.md
         rules 3 and 12), all open at once if they overlap; and the same with 1% per BET split across that bet's calls (the way to follow five
         coins that fire together as one idea). No leverage limit, no minimum order, no slippage beyond the 12bp in the replay.

EXPECTED BEFORE THE RUN (2026-11-15)
  E1  BEST SETUP loses per call on both halves (about -0.05 to -0.15R) - the sweet spot lost on the replay (analyst_replay_cuts.py) and the mood
      only lifts the hit rate a few points.
  E2  It comes about once or twice a week on average, in clumps (several coins the same day), with many weeks of none.
  E3  $100 followed at 1% a call ends below $100 on both halves.

RESULT (2026-11-15, logs/analyst_grades.txt): FOLLOWING THE SIGNALS LOST MONEY AT EVERY GRADE. BEST SETUP (3,333 calls in 239 weeks): hit 15.9%
against 15.4% for a random entry with the same stop / target / hours, -0.141R a call (-0.122 / -0.175 by half), -0.027R a bet (t -0.8). The mood
lifts the hit rate over random (Best +0.5 points, Weaker -3.3) but Best setups have lower odds to begin with (longs in falling markets, far
targets), so per call they lose about as much as Weaker ones (-0.117R); SKIP is clearly worst (-0.311R, t -5.6), so the grade sorts bad from
less bad, not losing from winning. Every year 2022-26 negative (-0.11..-0.21R). $100 following every Best setup at 1% of the booked equity: $4.87
(2022-02 .. 2024-12) and $10.45 (2024-12 .. 2026-09), falls 96% / 91%; at 2%: ~$0; at 1% a BET split across the coins that fire together: $100.32 /
$64.69, falls 32% / 44%. HOW OFTEN: 13.9 Best setups a week on average (median 13, busiest 37), in clumps of 2.8 coins on the days they fire
(~5 independent bets a week), almost every week (1% of weeks have none); 44% longs. E1, E3 right; E2 wrong (13.9 a week, not 1-2: the replay fires
on five coins every hour). Live (the dashboard feed, 2026-11-15): ideas with a stop of 0.8%+ since the 2026-11-06 registration: 13 bets, -0.16R a
bet; the whole desk 134 ideas, 22% hit vs 30% needed, -0.21R each (its paper book is +3% only because its 3x gross cap skipped the tight-stop calls).

    python -m backtest.analyst_grades        (logs/analyst_grades.txt)
"""
from __future__ import annotations

import heapq
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "analyst_grades.txt"
SPLIT = pd.Timestamp("2024-12-07")
SWEET = 0.008


def grade_rows(d: pd.DataFrame) -> pd.Series:
    """The tab's grade at the moment each replay call was made."""
    import analyst as an
    lean = [an.lean_of(s, sd, dict(btc=b, fuel=f, alt30=a)) for s, sd, b, f, a in zip(d.symbol, d.side, d.btc, d.fuel, d.alt30)]
    wide = d.stop_pct >= SWEET
    return pd.Series(np.where(~wide, "skip", np.where(np.array(lean) == "against", "best", "ok")), index=d.index)


def account(d: pd.DataFrame, risk: float, per_bet: bool = False, start: float = 100.0) -> dict:
    """Entry-sized, compounded by close date: each call risks `risk` x the equity booked by its entry (split across the calls of its bet when
    per_bet). Returns the final equity, the biggest fall of the booked equity, the month-end series."""
    d = d.sort_values("made_ms", kind="stable")
    n_in_bet = d.groupby(["day", "side"]).made_ms.transform("size") if per_bet else pd.Series(1, index=d.index)
    eq, peak, fall, open_, pts = start, start, 0.0, [], []
    for r, k in zip(d.itertuples(), n_in_bet):
        while open_ and open_[0][0] <= r.made_ms:
            t, pnl = heapq.heappop(open_)
            eq += pnl
            peak = max(peak, eq)
            fall = max(fall, 1 - eq / peak)
            pts.append((t, eq))
        heapq.heappush(open_, (int(r.exit_ms), risk / k * eq * float(r.r_net)))
    while open_:
        t, pnl = heapq.heappop(open_)
        eq += pnl
        peak = max(peak, eq)
        fall = max(fall, 1 - eq / peak)
        pts.append((t, eq))
    s = pd.Series([e for _, e in pts], index=pd.to_datetime([t for t, _ in pts], unit="ms")) if pts else pd.Series(dtype=float)
    me = s.resample("ME").last().ffill() if len(s) else s
    mo = (me / me.shift(1).fillna(start) - 1) if len(me) else me
    return dict(end=eq, fall=fall, months=len(mo), up=float((mo > 0).mean()) if len(mo) else np.nan, worst=float(mo.min()) if len(mo) else np.nan)


def bet_t(x: pd.DataFrame) -> tuple:
    b = x.groupby(["day", "side"]).r_net.mean()
    t = b.mean() / (b.std(ddof=1) / np.sqrt(len(b))) if len(b) > 2 else np.nan
    return float(b.mean()), float(t), len(b)


def main():
    from backtest import analyst_states as A
    t0 = time.time()
    d = A.load()
    d["grade"] = grade_rows(d)
    d["half"] = np.where(d.t < SPLIT, "tune", "hold")
    weeks = (d.t.max() - d.t.min()).days / 7
    L = [f"backtest/analyst_grades.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the desk's replay, crypto, {len(d)} calls {d.t.min():%Y-%m-%d} .. "
         f"{d.t.max():%Y-%m-%d} ({weeks:.0f} weeks), graded as the Analyst tab grades them; 12bp; halves split {SPLIT.date()}; BACKTEST", ""]
    L.append("1. HOW EACH GRADE PERFORMED (hit = target first; random = the same stop / target / hours from a random moment)")
    L.append(f"   {'grade':<8}{'half':>6}{'calls':>7}{'bets':>6}{'a week':>8}{'hit':>7}{'random':>8}{'R/call':>8}{'R/bet':>8}{'t':>6}")
    for g, nm in (("best", "BEST"), ("ok", "WEAKER"), ("skip", "SKIP")):
        for h in ("tune", "hold", "all"):
            x = d[d.grade == g] if h == "all" else d[(d.grade == g) & (d.half == h)]
            wk = (x.t.max() - x.t.min()).days / 7 if len(x) > 1 else np.nan
            span = weeks if h == "all" else ((SPLIT - d.t.min()).days / 7 if h == "tune" else (d.t.max() - SPLIT).days / 7)
            rb, t, nb = bet_t(x)
            L.append(f"   {nm:<8}{h:>6}{len(x):>7}{nb:>6}{len(x) / span:>8.1f}{x.win.mean() * 100:>6.1f}%{x.base_p.mean() * 100:>7.1f}%{x.r_net.mean():>+8.3f}{rb:>+8.3f}{t:>+6.1f}")
    b = d[d.grade == "best"]
    L += ["", "2. BEST SETUP BY YEAR", "   " + "   ".join(f"{y}: {len(x)} calls, hit {x.win.mean() * 100:.0f}% vs {x.base_p.mean() * 100:.0f}% random, {x.r_net.mean():+.2f}R"
                                                     for y, x in b.groupby(b.t.dt.year))]
    L += ["", "3. HOW OFTEN BEST SETUPS COME"]
    wk = b.set_index("t").resample("W").size()
    days = b.groupby("day").size()
    L.append(f"   per week: mean {wk.mean():.1f}, median {wk.median():.0f}; weeks with none {np.mean(wk == 0) * 100:.0f}%; weeks with 5+ {np.mean(wk >= 5) * 100:.0f}%; "
             f"busiest week {wk.max()}")
    L.append(f"   on days that have one: {days.mean():.1f} calls a day (several coins together: one bet); longs {np.mean(b.side == 'long') * 100:.0f}% / shorts "
             f"{np.mean(b.side == 'short') * 100:.0f}%; by rule {', '.join(f'{k} {v}' for k, v in b.method.value_counts().items())}")
    mo = b.set_index("t").resample("ME").size()
    L.append(f"   per month: median {mo.median():.0f}, quietest {mo.min()}, busiest {mo.max()}; months with none {np.mean(mo == 0) * 100:.0f}%")
    L += ["", "4. $100 FOLLOWING EVERY CALL OF A GRADE (entry-sized, compounded by close date)"]
    L.append(f"   {'grade':<8}{'sizing':<22}{'half':>6}{'$100 ->':>10}{'fall':>7}{'months up':>11}{'worst month':>13}")
    res = {}
    for g, nm in (("best", "BEST"), ("ok", "WEAKER"), ("skip", "SKIP")):
        for lab, risk, pb in (("1% a call", 0.01, False), ("2% a call", 0.02, False), ("1% a bet (split)", 0.01, True)):
            for h in ("tune", "hold"):
                x = d[(d.grade == g) & (d.half == h)]
                a = account(x, risk, pb)
                res[(g, lab, h)] = a
                L.append(f"   {nm:<8}{lab:<22}{h:>6}{a['end']:>10.2f}{a['fall'] * 100:>6.0f}%{a['up'] * 100:>10.0f}%{a['worst'] * 100:>+12.1f}%")
    e1 = all(d[(d.grade == "best") & (d.half == h)].r_net.mean() < 0 for h in ("tune", "hold"))
    e2 = 0.8 <= wk.mean() <= 3.0 and np.mean(wk == 0) >= 0.2
    e3 = all(res[("best", "1% a call", h)]["end"] < 100 for h in ("tune", "hold"))
    ok = lambda v: "RIGHT" if v else "WRONG"  # noqa: E731
    L += ["", "EXPECTED BEFORE THE RUN",
          f"  E1 Best setup loses per call on both halves -> {ok(e1)}",
          f"  E2 about 1-2 a week, 20%+ of weeks with none -> {ok(e2)} (mean {wk.mean():.1f}, none {np.mean(wk == 0) * 100:.0f}%)",
          f"  E3 $100 at 1% a call ends below $100 on both halves -> {ok(e3)}",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
