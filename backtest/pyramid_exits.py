"""THREE WAYS TO PROTECT A PYRAMID WITHOUT CAPPING IT.

    python -m backtest.pyramid_exits

WHY THIS TEST, FROM THE LIVE BOOK
    2026-09-20, the VM's 12 open positions priced at market: +161.7R open, and
    -139.0R if every one of them fell back to its printed stop. Ten of the twelve
    show stop == entry, which reads as "cannot lose". They can: the breakeven floor
    sits at the FIRST unit's entry, and each added unit was bought 2R higher, so a
    position stopped there loses 0+2+4+6+8 = -20R at 5 units. The live bot's worst
    closed trade (-6.22R) is a 3-unit position stopped exactly there.

    The obvious fix - take profit - is ruled out by measurement: on the same 5,503
    backtest trades, capping every winner at +6R turns +14,323R into -4,398R. The top
    1% of trades carry 114% of all profit. So any fix must PROTECT gains without
    CAPPING them. Three candidates, each declared before running:

THE VARIANTS (all parameters fixed here, none swept)
    current    breakeven at the FIRST entry once +3R, one shared stop, 20xATR trail.
               What the live bot runs. Must reproduce backtest/pyramid.run_pyramid
               exactly - asserted, not assumed.

    scale_out  the first unit keeps the 20xATR trail. Each ADDED unit also gets its
               own 5xATR trail (the short sleeve's trail, reused rather than tuned),
               so a pullback closes the added units and leaves the core running.
               A unit that is stopped is not re-bought: at most 5 units ever.

    avg_be     breakeven floor at the AVERAGE entry of all units instead of the
               first, so the whole position is protected, not just unit 1. At 5
               units that floor sits at +4R.

    ratchet    trail 20xATR until the position is +10R, then tightening linearly to
               10xATR at +30R and staying there. A +40R winner gives back ~5R
               instead of ~10R. Nothing changes below +10R.

    Shorts are untouched in every variant (one unit, run_uncapped), and so is the
    allocator: each variant is injected into blend.sleeve and run through the same
    blend.run with the deployed 1h+4h+12h sleeves and 12 shared slots.

THE DECISION RULE, DECLARED BEFORE RUNNING
    Same 60/40 split as backtest/blend.py. A variant is adopted only if, on the
    HOLDOUT, it beats `current` on return per unit of drawdown AND lowers the capital
    floor, AND the tune window agrees in direction. Anything else is recorded and
    left alone - the live bot does not change on a single-window result.

REGISTERED PREDICTION (2026-09-20, before running)
    ratchet is the likeliest to pass, because it only acts on positions already past
    +10R and gives up the least. scale_out will cut drawdown the most and cost the
    most return: in a full pyramid the ADDED units carry most of the R (live AVAX,
    5 units at +46.8R, gets 33.4R of it from units 2-5), and a 5xATR trail will close
    them on ordinary pullbacks mid-trend. avg_be will fail - a +4R floor on a
    volatile alt gets hit during the run, not at its end.
"""
from __future__ import annotations

import functools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest import pyramid as pyr  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

MODES = ("current", "scale_out", "avg_be", "ratchet")
SCALE_TRAIL = 5.0                  # ATR, for added units - the short sleeve's trail
RATCHET_FROM, RATCHET_TO = 10.0, 30.0     # R of open gain
RATCHET_MIN = 10.0                 # ATR, the tightest the ratchet goes
RULES = ["1h", "4h", "12h"]        # the deployed sleeves
SLOTS = 12                         # the deployed slot cap
DIAG: dict = {}


def trail_mult(mode, trail, gain_r):
    if mode != "ratchet" or gain_r <= RATCHET_FROM:
        return trail
    f = min(1.0, (gain_r - RATCHET_FROM) / (RATCHET_TO - RATCHET_FROM))
    return trail - (trail - RATCHET_MIN) * f


def pyramid_x(df, sig, *, sl_mult=2.0, trail=20.0, max_units=1, add_every=2.0,
              fee_bp=pyr.FEE_BP, atr_period=14, breakeven_at=0.0,
              strict_fill=False, mode="current"):
    """run_pyramid with per-unit stops. Same causality: entry at open[i] sized from
    atr[i-1]; every stop is checked against the bar's extreme BEFORE anything is
    advanced on that bar."""
    assert not strict_fill, "strict_fill is not implemented here; blend never uses it"
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    a = atr_ind(df, atr_period).to_numpy(float)
    n = len(df)
    fee = fee_bp / 1e4
    diag = DIAG.setdefault(mode, [])

    Rs, idx, units_used, held = [], [], [], []
    pos = None

    def close(i, px_rest):
        """Close every still-open unit at px_rest and book the whole position."""
        for u in pos["units"]:
            if u["exit"] is None:
                u["exit"] = px_rest
        risk = pos["risk"]
        gross = sum(u["exit"] - u["e"] for u in pos["units"]) / risk
        cost = sum(fee * u["e"] for u in pos["units"]) / risk
        Rs.append(gross - cost)
        idx.append(i)
        units_used.append(len(pos["units"]))
        held.append(i - pos["bar"])
        diag.append((len(pos["units"]), gross - cost))

    for i in range(1, n):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            risk = sl_mult * a[i - 1]
            pos = dict(risk=risk, stop=o[i] - risk, best=o[i], bar=i, next_add=1,
                       units=[dict(e=o[i], stop=None, exit=None)])
        if pos is None:
            continue
        risk = pos["risk"]
        e0 = pos["units"][0]["e"]

        # 1. added units' own stops (scale_out only), then the shared stop
        if mode == "scale_out":
            for u in pos["units"][1:]:
                if u["exit"] is None and u["stop"] is not None and lo[i] <= u["stop"]:
                    u["exit"] = u["stop"]
        if lo[i] <= pos["stop"]:
            close(i, pos["stop"])
            pos = None
            continue

        # 2. adds - fill at the trigger level, never the bar high
        if len(pos["units"]) < max_units:
            gain_r = (h[i] - e0) / risk
            if gain_r >= pos["next_add"] * add_every:
                pos["units"].append(dict(e=e0 + pos["next_add"] * add_every * risk,
                                         stop=pos["stop"], exit=None))
                pos["next_add"] += 1

        # 3. advance: best, shared trail, breakeven floor
        pos["best"] = max(pos["best"], h[i])
        gain_best = (pos["best"] - e0) / risk
        cand = pos["best"] - trail_mult(mode, trail, gain_best) * a[i - 1]
        if breakeven_at > 0 and gain_best >= breakeven_at:
            if mode == "avg_be":
                floor = float(np.mean([u["e"] for u in pos["units"]]))
            else:
                floor = e0
            cand = max(cand, floor)
        if cand > pos["stop"]:
            pos["stop"] = cand

        # 4. added units' tight trail, never below the shared stop
        if mode == "scale_out":
            ucand = pos["best"] - SCALE_TRAIL * a[i - 1]
            for u in pos["units"][1:]:
                if u["exit"] is None:
                    u["stop"] = max(u["stop"], ucand, pos["stop"])

    if pos is not None:
        close(n - 1, c[n - 1])
    return (np.asarray(Rs), np.asarray(idx, dtype=int),
            np.asarray(units_used, dtype=int), np.asarray(held, dtype=int))


def guard_equivalence():
    """mode='current' must reproduce the deployed run_pyramid bit for bit."""
    from backtest.shortside import signals
    from backtest.timeframes import resample
    checked = 0
    for coin in blend.BOOK[:4]:
        d = blend.load(coin)
        if d is None:
            continue
        for rule in RULES:
            df = resample(d, rule)
            if len(df) < 300:
                continue
            sig = signals(df, "long", "all")
            kw = dict(sl_mult=blend.SL_MULT, trail=blend.LONG_TRAIL,
                      max_units=blend.MAX_UNITS, add_every=blend.ADD_EVERY,
                      fee_bp=blend.FEE_BP, breakeven_at=blend.BE_AT)
            ref = pyr.run_pyramid(df, sig, **kw)
            new = pyramid_x(df, sig, mode="current", **kw)
            assert len(ref[0]) == len(new[0]) and np.allclose(ref[0], new[0]) \
                and (ref[1] == new[1]).all() and (ref[3] == new[3]).all(), (
                    f"pyramid_x(mode='current') diverges from run_pyramid on "
                    f"{coin} {rule}: {len(ref[0])} vs {len(new[0])} positions")
            checked += 1
    DIAG.clear()
    return checked


def use(mode):
    blend.run_pyramid = functools.partial(pyramid_x, mode=mode)
    blend._S.clear()
    DIAG.pop(mode, None)           # sleeves rebuild now; don't double-count them
    assert isinstance(blend.run_pyramid, functools.partial) and \
        blend.run_pyramid.keywords["mode"] == mode, "injection did not take"


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: ratchet likeliest to pass; scale_out cuts drawdown most and")
    print("costs most return (added units carry most of a pyramid's R); avg_be fails.\n")

    k = guard_equivalence()
    print(f"  guard OK: mode='current' reproduces run_pyramid on {k} coin/sleeve pairs\n")

    use("current")
    ts_all = pd.DatetimeIndex(sorted(x[0] for x in blend.sleeve("1h")[0]))
    cut = ts_all[int(len(ts_all) * 0.6)]
    print(f"  sleeves {'+'.join(RULES)}, {SLOTS} shared slots, split at {cut.date()}\n")

    res = {}
    for m in MODES:
        use(m)
        res[m] = (blend.run(RULES, SLOTS, t_to=cut), blend.run(RULES, SLOTS, t_from=cut),
                  blend.run(RULES, SLOTS))

    print("=" * 104)
    print("1. TUNE / HOLDOUT — honest %/month, max drawdown, capital floor (MEXC)")
    print("=" * 104)
    print(f"  {'variant':<11}| {'TUNE /mo':>9}{'DD':>7}{'floor':>7}{'MAR':>7} | "
          f"{'HOLD /mo':>9}{'DD':>7}{'floor':>7}{'MAR':>7}{'n':>6}")
    for m in MODES:
        a, b, _ = res[m]
        print(f"  {m:<11}| {a['hpm']:>+8.2f}%{a['dd']:>6.1f}%{a['floor']:>7.0f}"
              f"{a['hpm']/a['dd']*100:>7.2f} | {b['hpm']:>+8.2f}%{b['dd']:>6.1f}%"
              f"{b['floor']:>7.0f}{b['hpm']/b['dd']*100:>7.2f}{b['n']:>6}")
    print("\n  MAR here = %/month per 100 points of drawdown. Above ~60% drawdown it is")
    print("  a weak guide (docs/03-mistakes.md) - read DD and floor directly as well.")

    print("\n" + "=" * 104)
    print("2. THE TAIL — did protecting gains cost the winners that pay for everything?")
    print("=" * 104)
    print(f"  {'variant':<11}{'mean R':>9}{'win%':>7}{'best R':>9}"
          f"{'top 1% share':>14}{'total R':>10}")
    for m in MODES:
        R = np.sort(res[m][2]["R"])[::-1]
        k1 = max(1, int(len(R) * 0.01))
        print(f"  {m:<11}{R.mean():>+9.3f}{100*(R>0).mean():>6.0f}%{R[0]:>+9.1f}"
              f"{100*R[:k1].sum()/R.sum():>13.0f}%{R.sum():>+10.0f}")

    print("\n" + "=" * 104)
    print("3. THE PROBLEM BEING FIXED — pyramids of 3+ units that still closed at a loss")
    print("=" * 104)
    print(f"  {'variant':<11}{'3+ unit pos':>13}{'closed < 0':>12}{'mean R':>9}"
          f"{'worst R':>9}")
    for m in MODES:
        d = [r for u, r in DIAG.get(m, []) if u >= 3]
        if not d:
            continue
        d = np.array(d)
        print(f"  {m:<11}{len(d):>13}{100*(d<0).mean():>11.0f}%{d.mean():>+9.2f}"
              f"{d.min():>+9.1f}")
    print("  (all three sleeves, full sample, long side only)")

    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)
    base_t, base_h, _ = res["current"]
    passed = []
    for m in MODES[1:]:
        t, h, _ = res[m]
        mar_h = h["hpm"] / h["dd"] > base_h["hpm"] / base_h["dd"]
        mar_t = t["hpm"] / t["dd"] > base_t["hpm"] / base_t["dd"]
        floor_h = h["floor"] < base_h["floor"]
        ok = mar_h and mar_t and floor_h
        print(f"  {m:<11} holdout MAR {'better' if mar_h else 'worse '}  "
              f"tune MAR {'better' if mar_t else 'worse '}  "
              f"floor {'lower ' if floor_h else 'higher'}   -> "
              f"{'PASSES' if ok else 'fails'}")
        if ok:
            passed.append(m)
    if passed:
        print(f"\n  {', '.join(passed)} passed all three conditions. Do not ship on this")
        print("  alone - re-run on the point-in-time universe (pit_blend) first.")
    else:
        print("\n  NONE PASS. The current exit stays. The -20R-at-breakeven exposure is")
        print("  the price of the pyramid's right tail, and every way of protecting it")
        print("  tested here costs more than it saves.")


if __name__ == "__main__":
    main()
