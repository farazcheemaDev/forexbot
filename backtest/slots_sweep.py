"""IS 12 SLOTS TOO FEW? - the cap the live book hits hardest, on the corrected engine.

WHY THIS ONE, AND WHY NOW
    `MAX_UNITS = 5` turned out to be an arbitrary cap set too low: 7 beat it on both halves, on
    all four bar grids, and beat a matched-risk control (doc 11 part 8). `SLOTS = 12` is the same
    kind of number, and the live paper book says it binds harder than anything else in the
    config - its status line reads **563 signals declined for want of a slot** against 47 taken.
    The book is turning away more than ten times the trades it accepts.

    12 coins x 3 sleeves = 36 possible positions, so 12 slots rejects two thirds of the book by
    construction. `graveyard_rescore.py` swept DOWNWARD (8 slots: less return, less drawdown) and
    never swept up.

WHAT MAKES THIS DIFFERENT FROM "BETTING MORE"
    More slots is more positions at the SAME risk per unit, so it is diversification rather than
    leverage - up to a point. That point is gross leverage: every open position adds notional, and
    `lev_test.py` put the liquidation line at 10x. At 12 slots the tight book runs 5.3x at p99, so
    doubling the slots should approach or breach it. The sweep therefore reports leverage per cell
    and the matched-risk control, exactly as the MAX_UNITS test did - because a slot increase that
    only works by adding exposure is the same mistake in different clothing.

THE BAR
    Baseline is the TRIPLE book (tight + time stop + 7 units) - the best configuration measured,
    now paper book #7, so an improvement has to improve on the best.
    Stage 1: beat it on BOTH halves, paired within ordering, |t| > 2, and stay under 10x p99.
    Stage 2: survivors face the four bar grids.

REGISTERED PREDICTIONS (before running, 2026-09-24)
    1. 16 slots beats 12 on return on both halves - the declined signals are not systematically
       worse than the taken ones, and slot_priority.py already established that no entry feature
       ranks simultaneous signals, which means the ones turned away are a random sample.
    2. The gain is SMALLER than the MAX_UNITS gain, because a 13th position is an average trade
       while a 6th unit is attached to a proven runner.
    3. Gross leverage at 20 slots breaches 10x at p99, capping the usable answer near 16.
    4. Drawdown rises with slots, but sub-linearly, because the extra positions are imperfectly
       correlated.

    python -m backtest.slots_sweep
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.kelly_corrected import LEV_CAP, score, simulate  # noqa: E402

SEEDS = tuple(range(10))
SLOTS = (8, 12, 16, 20, 24, 36)
TRIPLE = dict(tight=True, time_stop=(100, 2.0), max_units=7)


def cell(rows, bear, cut, slots, risk=None):
    risk = blend.RISK if risk is None else risk
    out = {}
    for win, kw in (("tune", dict(t_to=cut)), ("hold", dict(t_from=cut))):
        res = [simulate(rows, bear, s, risk, slots=slots, **kw) for s in SEEDS]
        out[win] = dict(per=[r for r in res if r], sc=score(res))
    full = [simulate(rows, bear, s, risk, slots=slots) for s in SEEDS]
    out["lev99"] = float(np.median([x["lev99"] for x in full if x]))
    out["levmax"] = float(np.median([x["levmax"] for x in full if x]))
    return out


def hpms(res, win):
    """Per-ordering %/month, so differences can be paired."""
    vals = []
    for r in res[win]["per"]:
        c = r["curve"]
        yrs = max((c.index[-1] - c.index[0]).days / 365.25, 0.1)
        cagr = max(float(c.iloc[-1]), 1e-12) ** (1 / yrs) - 1
        hc = cagr / blend.HINDSIGHT
        vals.append(((1 + hc) ** (1 / 12) - 1) * 100 if hc > -1 else -100.0)
    return np.array(vals)


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    rows = rows_for_phase(0, **TRIPLE)
    print(f"baseline = TRIPLE book (tight + time stop + 7 units), {len(rows)} trades")
    print(f"{len(SEEDS)} orderings | 0.30%/unit | 3x haircut | tune < {cut:%Y-%m-%d} <= holdout")
    print("bar: both halves paired |t| > 2 AND gross leverage p99 under 10x\n")

    base = cell(rows, bear, cut, 12)
    b_t, b_h = hpms(base, "tune"), hpms(base, "hold")
    print(f"  {'slots':>7}{'TUNE/mo':>10}{'diff':>8}{'t':>7}{'w':>6}{'HOLD/mo':>10}{'diff':>8}"
          f"{'t':>7}{'w':>6}{'DD':>6}{'lev99':>8}{'levmax':>8}")
    survivors, store = [], {}
    for n in SLOTS:
        c = cell(rows, bear, cut, n) if n != 12 else base
        store[n] = c
        cells, clears = "", True
        for win, b in (("tune", b_t), ("hold", b_h)):
            a = hpms(c, win)
            if n == 12:
                cells += f"{a.mean():>+9.2f}%{'-':>8}{'-':>7}{'-':>6}"
                continue
            d = a - b
            se = d.std(ddof=1) / len(d) ** 0.5
            t = d.mean() / se if se else np.nan
            cells += f"{a.mean():>+9.2f}%{d.mean():>+7.2f}%{t:>+7.2f}{(d > 0).sum():>4}/{len(d)}"
            clears &= (d.mean() > 0 and abs(t) > 2)
        over = c["lev99"] > LEV_CAP
        flag = "  OVER 10x" if over else ("  <- DEPLOYED" if n == 12 else "")
        if n != 12 and clears and not over:
            survivors.append(n)
            flag = "  CLEARS STAGE 1"
        print(f"  {n:>7}{cells}{c['hold']['sc']['dd']:>5.0f}%{c['lev99']:>7.1f}x"
              f"{c['levmax']:>7.1f}x{flag}")

    print()
    print("  THE CONTROL - does raising RISK at 12 slots reach the same place?")
    print("  if it does, more slots is just exposure and not diversification")
    print(f"  {'setting':<28}{'HOLD/mo':>10}{'DD':>6}{'lev99':>8}")
    for lab, n, rk in (("12 slots @ 0.30% (deployed)", 12, 0.30),
                       ("16 slots @ 0.30%", 16, 0.30),
                       ("12 slots @ 0.40%", 12, 0.40),
                       ("20 slots @ 0.30%", 20, 0.30),
                       ("12 slots @ 0.50%", 12, 0.50)):
        c = cell(rows, bear, cut, n, rk)
        print(f"  {lab:<28}{c['hold']['sc']['hpm']:>+9.2f}%{c['hold']['sc']['dd']:>5.0f}%"
              f"{c['lev99']:>7.1f}x" + ("  OVER 10x" if c["lev99"] > LEV_CAP else ""))

    print()
    if not survivors:
        print("  Nothing clears stage 1. 12 slots is not costing the book anything measurable,")
        print("  and the 563 declined signals are declined for a reason.")
        return
    print(f"  slots clearing stage 1: {survivors} -> the phase test")
    # bar_phase.variant_across_phases compares two ROW SETS; slots is a SIMULATION parameter, so
    # it cannot express this comparison. Done directly here instead: same rows per phase, two
    # slot caps, paired within ordering.
    from backtest.bar_phase import PHASES
    for n in survivors[:2]:
        print()
        print(f"TRIPLE at {n} slots vs 12, paired within ordering, on every bar phase")
        print(f"  {'phase':<7}{'TUNE d':>9}{'t':>7}{'w':>6}{'HOLD d':>9}{'t':>7}{'w':>6}"
              f"{'lev99':>8}")
        ok = 0
        for ph in PHASES:
            pr = rows_for_phase(ph, **TRIPLE)
            a12, an = cell(pr, bear, cut, 12), cell(pr, bear, cut, n)
            line, both = "", True
            for win in ("tune", "hold"):
                d = hpms(an, win) - hpms(a12, win)
                se = d.std(ddof=1) / len(d) ** 0.5
                line += f"{d.mean():>+8.2f}%{d.mean()/se:>+7.2f}{(d > 0).sum():>4}/{len(d)}"
                both &= d.mean() > 0
            ok += both
            print(f"  {ph:<7}{line}{an['lev99']:>7.1f}x"
                  + ("  <- DEPLOYED grid" if ph == 0 else ""))
        print(f"  wins both halves on {ok} of {len(PHASES)} phases")


if __name__ == "__main__":
    main()
