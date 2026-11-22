"""WHERE DO HIS EXITS LAND ON THE CHART? (2026-11-22)

THE USER (2026-11-22), on "on 10-08 he took profit at the previous low": "how did you not study this further - it is the most important
clue - the strategy is somewhere in the charts". his_retest.py (s55, 2026-10-12) was built on that same 10-08 picture and tested his
ENTRIES against the highs and lows of the last 15 minutes (a style lean, no side, the rule = random). His EXITS against the chart were
never measured: his median exit is +7.00 but only 11% are exactly +7.00 and 30% are +10 or more - do the rest land ON chart levels?
DATA   his NASDAQ statement trades (open / close times and CapitalFX prices; clock per his_tape.entries) and the Exness USTECm mid
       (strategy_analysis/data/ustec_tick_days.pkl; CapitalFX = Exness + a steady futures premium, minute moves corr 0.992, so a
       distance on one is a distance on the other).
AT EACH TRADE  the swing levels known at ENTRY: the high / low of the last 5 / 15 / 30 / 60 minutes (up to 30 s before the click);
       the level AHEAD in his direction (the previous high for a buy, the previous low for a sell) and its distance ('room').
       His exit is AT a level when his Exness move entry -> exit is within 1.5 points of a room > 2 points (any of the four lookbacks);
       at the +7 target when he banked 6.5 .. 7.5; at a ROUND level when the CapitalFX exit price is within 1 point of a multiple of 25.
CONTROL the same exit distance (his own banked points) applied at the other moments of his sitting (+-1 .. 20 minutes, his direction):
       how often would an exit that far away land on a prior swing level by chance. Round levels: chance from the price grid.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  E1  His exits land at a prior swing level no more often than the control (within 10 points of it). (55%)
  E2  Under 15% of his exits sit within 1 point of a round 25-level (chance ~8%). (70%)
  E3  The exits that are NOT +7 targets land at a prior swing level more often than the +7 exits do (he hand-exits at levels). (50%)

RESULT (2026-11-22, logs/his_exit_levels.txt): HIS EXITS ARE NOT ON CHART LEVELS. 35 trades (the tick days, with a 60-minute look-back).
  Exits within 1.5 points of the previous high / low of the last 5 / 15 / 30 / 60 minutes: 2 of 35 (6%), against 12% for the same exit
  distance at his sittings' other moments (p 0.31) - fewer than chance. Within 1 point of a round 25-level: 3 of 35 (9%), chance ~9%.
  At entry the swing level ahead sat a median 12.8 / 25.5 / 32.3 / 44.7 points away (5 / 15 / 30 / 60 min); he exits after 2-25
  points, long before it. 10-08's exit at the previous low (his_chart_capfx.py) is one instance, not his habit. E1-E3 right.

    python -m backtest.his_exit_levels
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "his_exit_levels.txt"
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
LOOKS = (5, 15, 30, 60)
TOL = 1.5


def mid_at(ts, mid, t):
    i = np.searchsorted(ts, t, side="right") - 1
    return float(mid[i]) if i >= 0 else np.nan


def rooms(ts, mid, t, s):
    """Distance from the mid at t to the swing level ahead (previous high for a buy, low for a sell), per lookback."""
    p = mid_at(ts, mid, t)
    out = {}
    for L in LOOKS:
        a, b = np.searchsorted(ts, t - L * 60), np.searchsorted(ts, t - 30, side="right")
        w = mid[a:b]
        if len(w) < 5:
            out[L] = np.nan
            continue
        lvl = w.max() if s > 0 else w.min()
        out[L] = s * (lvl - p)
    return p, out


def at_level(move, rm):
    return any(np.isfinite(r) and r > 2 and abs(move - r) <= TOL for r in rm.values())


def main():
    from scipy.stats import binomtest
    import backtest.his_tape as TP
    x = TP.entries()                                         # the statement's NASDAQ rows, with the corrected clock
    from backtest.his_clock_check import to_utc
    cu = to_utc(pd.to_datetime(x.close_time), 4.0, 5.0).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x["tx"] = (cu - x.d).dt.total_seconds() - 9.5 * 3600
    x["banked"] = x.s * (x.close_price - x.open_price)
    x["close_px"] = x.close_price
    cache = pickle.loads(TICKS.read_bytes())
    rows, ctrl = [], []
    for r in x.itertuples():
        dd = cache.get(r.d)
        if dd is None or r.t < 3700:
            continue
        ts, mid = dd[0], dd[1]
        p, rm = rooms(ts, mid, r.t, r.s)
        move = r.s * (mid_at(ts, mid, r.tx) - p)
        rows.append(dict(d=r.d, t=r.t, s=r.s, banked=r.banked, move=move, target=6.5 <= r.banked <= 7.5,
                         lvl=at_level(move, rm), rnd=abs(r.close_px - 25 * round(r.close_px / 25)) <= 1.0,
                         **{f"room{L}": v for L, v in rm.items()}))
        others = x[x.d == r.d].t.to_numpy()
        for mnt in list(range(-20, 0)) + list(range(1, 21)):
            t2 = r.t + 60 * mnt
            if t2 < 3700 or np.min(np.abs(others - t2)) < 60:
                continue
            _, rm2 = rooms(ts, mid, t2, r.s)
            ctrl.append(dict(lvl=at_level(r.banked, rm2), target=6.5 <= r.banked <= 7.5))
    X, Cc = pd.DataFrame(rows), pd.DataFrame(ctrl)
    out = [f"backtest/his_exit_levels.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(X)} of his NASDAQ trades on the tick days "
           f"(after the first hour of the tick day, so a 60-minute look-back exists); {len(Cc)} control moments", ""]
    p_lvl, c_lvl = X.lvl.mean(), Cc.lvl.mean()
    k = int(X.lvl.sum())
    pb = binomtest(k, len(X), c_lvl).pvalue
    out += [f"  exits AT a prior swing level (within {TOL} points of the previous high / low of the last 5 / 15 / 30 / 60 min): {k} of {len(X)} "
            f"({p_lvl:.0%}); control, the same distance at his sittings' other moments: {c_lvl:.0%}; binomial p {pb:.3f}",
            f"  exits at the +7 target (6.5-7.5 banked): {int(X.target.sum())} of {len(X)}; at a level among them {X[X.target].lvl.mean():.0%}, "
            f"among the other exits {X[~X.target].lvl.mean():.0%} (control for those distances {Cc[~Cc.target].lvl.mean():.0%})",
            f"  exits within 1 point of a round 25-level (CapitalFX price): {int(X.rnd.sum())} of {len(X)} ({X.rnd.mean():.0%}; chance on a "
            f"quarter-point grid ~{9 / 100:.0%})",
            f"  room to the level ahead at his entries (median points): " + ", ".join(f"{L} min {X[f'room{L}'].median():.1f}" for L in LOOKS),
            "", "  each trade: banked, his move on the Exness mid, room to the level ahead (5 / 15 / 30 / 60 min), at a level?"]
    for r in X.itertuples():
        out.append(f"    {r.d:%Y-%m-%d} {'BUY ' if r.s > 0 else 'SELL'} banked {r.banked:+6.2f}  move {r.move:+6.2f}  room "
                   + " / ".join(f"{getattr(r, f'room{L}'):5.1f}" for L in LOOKS) + f"  {'AT LEVEL' if r.lvl else ''}{'  round' if r.rnd else ''}")
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  E1 at a level no more than 10 points over the control -> {ok(p_lvl - c_lvl <= 0.10)} ({p_lvl:.0%} vs {c_lvl:.0%})",
            f"  E2 round-level exits under 15% -> {ok(X.rnd.mean() < 0.15)} ({X.rnd.mean():.0%})",
            f"  E3 non-+7 exits at a level more often than +7 exits -> {ok(X[~X.target].lvl.mean() > X[X.target].lvl.mean())}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
