"""IF A HUMAN SUPERVISES AND THE BOT ONLY SIGNALS - WHAT CHANGES?

    python -m backtest.human_loop

THE QUESTION
    The bot finds the trade; a person decides and places it. That changes three
    things about how the SAME signals get traded, and each can be simulated on the
    deployed blend (1h+4h+12h sleeves, 12 shared slots) with nothing else changed:

    A. REACTION DELAY. The alert fires; the person acts 1, 3 or 8 hours later. The
       entry is taken at the open of the bar that many hours on (rounded to the
       sleeve's own bar: an 8h delay is 8 bars on 1h, 2 on 4h, 1 on 12h).

    B. SLEEP. The person is in Pakistan (UTC+5) and asleep 00:00-08:00 PKT, i.e.
       19:00-03:00 UTC. No entries are taken in that window. A breakout that is
       still firing at wake-up is taken then; one that has faded is missed. This is
       the realistic version of A.

    C. SKIPPING. The person passes on some signals - doubt, distraction, a bad week.
       Modelled as a random 10% and 25% of signals never taken, 30 random draws each.
       Random is the KIND version: a real person skips non-randomly, and the signals
       that feel worst to take (a breakout after a big run, the fifth long in a row
       in correlated alts) are disproportionately the big winners.

    In every case EXITS are assumed to be resting stop orders on the exchange, so
    they fire on time. Adds to the pyramid are assumed to be done on time too. Both
    assumptions favour the human; the real result is worse than what prints.

    Skipped or delayed signals free their slot for others, exactly as in the live
    bot - the skip is applied BEFORE allocation, not by deleting finished trades.

    What is NOT simulated, because it has already been measured: a human taking
    profit early. Capping winners at +6R turns +14,323R into -4,398R
    (backtest/pyramid_exits.py, docs/02-what-failed.md).

REGISTERED PREDICTION (2026-09-20, before running)
    Delay costs little at 1h and a lot at 8h, because breakouts do most of their
    work early. Sleep costs less than an 8h delay, since a persisting breakout is
    still there in the morning. Random skipping scales the mean down roughly in
    proportion but widens the spread badly, because 1% of trades carry 114% of the
    profit and a skip that lands on one of them costs a year. Net: supervision can
    only subtract from this strategy - its edge has no step a human does better.
"""
from __future__ import annotations

import functools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

RULES, SLOTS = ["1h", "4h", "12h"], 12
SLEEP_UTC = (19, 3)                 # 00:00-08:00 PKT
_ORIG_SIGNALS = blend.signals
_ORIG_SLEEVE = blend.sleeve


def bar_hours(df):
    t = pd.to_datetime(df["time"])
    return float(t.diff().median().total_seconds() / 3600.0)


def delayed(df, side, regime="all", *, hours=0):
    s = _ORIG_SIGNALS(df, side, regime)
    k = int(np.floor(hours / bar_hours(df) + 0.5))
    return s if k == 0 else s.shift(k).fillna(Action.HOLD).astype(s.dtype)


def awake_only(df, side, regime="all"):
    s = _ORIG_SIGNALS(df, side, regime).copy()
    h = pd.to_datetime(df["time"]).dt.hour.to_numpy()
    a, b = SLEEP_UTC
    asleep = (h >= a) | (h < b)
    s[asleep] = Action.HOLD
    return s


def patch_signals(fn):
    blend.signals = fn
    blend._S.clear()
    assert blend.signals is fn, "signal injection did not take"


def restore():
    blend.signals = _ORIG_SIGNALS
    blend.sleeve = _ORIG_SLEEVE
    blend._S.clear()


def skipping_sleeve(rate, rng):
    def sl(rule):
        tr, stops = _ORIG_SLEEVE(rule)
        keep = rng.random(len(tr)) >= rate
        return [x for x, k in zip(tr, keep) if k], stops
    return sl


def row(lab, full, hold):
    print(f"  {lab:<30}{full['hpm']:>+9.2f}%{full['dd']:>7.1f}%{full['floor']:>7.0f}"
          f"{full['R'].sum():>+9.0f} |{hold['hpm']:>+9.2f}%{hold['dd']:>7.1f}%"
          f"{hold['floor']:>7.0f}")


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: delay cheap at 1h, costly at 8h; sleep cheaper than an 8h")
    print("delay; random skips cut the mean ~proportionally and widen the spread badly.")
    print("Supervision can only subtract from this strategy.\n")

    restore()
    base_full = blend.run(RULES, SLOTS)
    ts_all = pd.DatetimeIndex(sorted(x[0] for x in blend.sleeve("1h")[0]))
    cut = ts_all[int(len(ts_all) * 0.6)]
    base_hold = blend.run(RULES, SLOTS, t_from=cut)

    patch_signals(functools.partial(delayed, hours=0))
    z = blend.run(RULES, SLOTS)
    assert z["n"] == base_full["n"] and abs(z["hpm"] - base_full["hpm"]) < 1e-9, \
        "a zero-hour delay does not reproduce the deployed blend"
    print(f"  guard OK: zero delay reproduces the deployed blend "
          f"({base_full['n']} trades)   holdout from {cut.date()}\n")

    hdr = (f"  {'':<30}{'FULL /mo':>10}{'DD':>8}{'floor':>7}{'total R':>9} |"
           f"{'HOLD /mo':>10}{'DD':>8}{'floor':>7}")

    print("=" * 100)
    print("A. REACTION DELAY — the person acts N hours after the alert")
    print("=" * 100)
    print(hdr)
    row("bot, no delay (deployed)", base_full, base_hold)
    for h in (1, 3, 8):
        patch_signals(functools.partial(delayed, hours=h))
        row(f"human, {h}h late", blend.run(RULES, SLOTS),
            blend.run(RULES, SLOTS, t_from=cut))

    print("\n" + "=" * 100)
    print("B. SLEEP — no entries 00:00-08:00 Pakistan time")
    print("=" * 100)
    print(hdr)
    row("bot, 24/7 (deployed)", base_full, base_hold)
    patch_signals(awake_only)
    row("human, asleep 8h a night", blend.run(RULES, SLOTS),
        blend.run(RULES, SLOTS, t_from=cut))

    print("\n" + "=" * 100)
    print("C. SKIPPING — a random share of signals never taken, 30 draws each")
    print("=" * 100)
    restore()
    _ORIG_SLEEVE(RULES[0])                  # warm the cache the wrapper reads from
    for r in RULES[1:]:
        _ORIG_SLEEVE(r)
    print(f"  {'':<14}{'median /mo':>12}{'5th pct':>10}{'95th pct':>10}"
          f"{'worst':>9}{'draws below bot/2':>20}")
    print(f"  {'bot, takes all':<14}{base_full['hpm']:>+11.2f}%")
    for rate in (0.10, 0.25):
        rng = np.random.default_rng(int(rate * 1000))
        out = []
        for _ in range(30):
            blend.sleeve = skipping_sleeve(rate, rng)
            out.append(blend.run(RULES, SLOTS)["hpm"])
        blend.sleeve = _ORIG_SLEEVE
        o = np.array(out)
        print(f"  skip {int(rate*100):>2}%{'':<6}{np.median(o):>+11.2f}%"
              f"{np.percentile(o,5):>+9.2f}%{np.percentile(o,95):>+9.2f}%"
              f"{o.min():>+8.2f}%{int((o < base_full['hpm']/2).sum()):>14} of 30")
    restore()

    print("\n  All figures are the backtest's hindsight-divided honest %/month. Compare")
    print("  rows with each other; the absolute level carries the usual caveats.")


if __name__ == "__main__":
    main()
