"""THE EXIT LAB — capturing profit that the trail currently gives back.

THE OBSERVATION THIS COMES FROM, and it is a LIVE one, not a backtest
    Bitget demo, 2026-09-13. Three shorts open, all in profit:

        BTC  entry 77,122  peak +1.78R  ->  later -0.05R
        ETH  entry 2,485   peak +0.70R  ->  later -0.32R
        XRP  entry 1.3609  peak +2.13R  ->  later +1.84R

    BTC gave back 1.83R of open profit and captured none of it. A 5xATR trail on a
    2xATR stop gives back 2.5R before it triggers, so a short has to reach +2.5R
    before one cent is protected. The current breakeven is set at 3R, so on BTC it
    never armed at all.

WHAT IS ALREADY RULED OUT
    A FIXED PROFIT TARGET. Closing the whole position at 1R/2R/3R makes mean R
    NEGATIVE (-0.048 / -0.029 / -0.021 against the trail's +0.305). It deletes the
    rare enormous winners that carry everything - the top 25 of 6,054 trades made
    102% of the profit. That is settled and this file does not retest it.

WHAT HAS NEVER BEEN TESTED - the gap
    Everything so far has been ALL-OR-NOTHING: either the whole position closes at a
    target, or the whole position rides a fixed trail. The middle ground is untouched.

    1. PARTIAL SCALE-OUT. Close HALF at +2R, let the other half run on the trail.
       Fundamentally different from a target: it banks something AND keeps the tail.
       The reason a full target fails - losing the 1000R trade - does not apply to
       the half that is still running.
    2. EARLY BREAKEVEN, SHORT-SPECIFIC. The 1R-6R breakeven sweep applied one
       threshold to BOTH sleeves. Shorts give back 2.5R on their trail, so they need
       it earlier than longs do. Never isolated.
    3. RATCHETING TRAIL. Start wide, tighten as profit grows (5x -> 3x after +2R).
       The trail sweep tested FIXED widths only.
    4. GIVE-BACK CAP. Exit when open profit retreats a PERCENTAGE of its peak rather
       than a fixed ATR distance. Scale-free in profit terms instead of in volatility
       terms.

METHOD
    All variants run SINGLE-UNIT on both sleeves so the exit rule is the only thing
    changing. The live config pyramids the long side, so the absolute numbers here are
    not the live book's - the RANKING between exit rules is what transfers.

    Within a bar the stop is checked FIRST and wins ties, the pessimistic assumption
    used everywhere in this project. A scale-out level triggers on the bar's extreme,
    which is correct for a resting limit order - it would have filled - and is not the
    same as using the extreme to make a market decision.

REGISTERED PREDICTION (2026-09-13, before running)
    Partial scale-out improves the SHORT sleeve clearly (its trail gives back 2.5R and
    crashes reverse fast) and roughly breaks even on longs (whose 20x trail exists
    precisely to hold the monsters). Early breakeven helps shorts. The ratcheting
    trail and the give-back cap I expect to be reparameterisations of the trail with
    no independent benefit.

    If a 50% scale-out at 2R raises mean R on BOTH sleeves I will suspect that the
    limit-fill assumption is doing the work and re-check it.

    python -m backtest.exitlab
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import fetch  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
SL_MULT = 2.0
HINDSIGHT = 3.0
RISK, SLOTS = 0.30, 8
BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT"]
_D: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def run_exits(df, sig, *, trail, sl_mult=SL_MULT, fee_bp=FEE_BP,
              be_at=0.0, scale=(), ratchet=(), giveback=0.0,
              atr_period=14, max_bars=100000):
    """One engine, every exit rule under test. Returns (R per position, exit idx,
    entry idx, direction).

    scale:    ((level_R, fraction), ...) partial exits at resting limit prices
    ratchet:  ((level_R, new_trail), ...) tighten the trail once profit reaches level
    giveback: exit the remainder if open profit falls below this FRACTION of its peak

    R is expressed in units of the INITIAL risk on the FULL position, so a variant
    that closes half at +2R and stops the rest at breakeven scores +1.0R, and every
    row in the output table stays comparable.
    """
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, atr_period).to_numpy(float)
    n = len(df); fee = fee_bp / 1e4
    Rs, xi, ei, ds = [], [], [], []
    pos = None
    for i in range(1, n):
        if pos is None and s[i] != Action.HOLD and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            d = 1 if s[i] == Action.BUY else -1
            e = o[i]; risk = sl_mult * a[i - 1]
            pos = dict(d=d, e=e, risk=risk, stop=e - d * risk, best=e, bar=i,
                       size=1.0, banked=0.0, done=set(), tr=trail, peak=0.0)
        if pos is None:
            continue
        d, e, risk = pos["d"], pos["e"], pos["risk"]
        # ---- stop first, pessimistic, and it closes whatever size is left
        hit = (lo[i] <= pos["stop"]) if d == 1 else (h[i] >= pos["stop"])
        if hit or i - pos["bar"] >= max_bars:
            px = pos["stop"] if hit else c[i]
            r = pos["banked"] + pos["size"] * ((px - e) * d / risk
                                               - fee * abs(px) / risk)
            Rs.append(r); xi.append(i); ei.append(pos["bar"]); ds.append(d)
            pos = None
            continue
        # ---- partial exits, as resting limit orders at fixed R levels
        for lvl, frac in scale:
            if lvl in pos["done"] or pos["size"] <= 1e-9:
                continue
            tgt = e + d * lvl * risk
            reached = (h[i] >= tgt) if d == 1 else (lo[i] <= tgt)
            if reached:
                take = min(frac, pos["size"])
                pos["banked"] += take * (lvl - fee * abs(tgt) / risk)
                pos["size"] -= take
                pos["done"].add(lvl)
        if pos["size"] <= 1e-9:              # fully scaled out
            Rs.append(pos["banked"]); xi.append(i); ei.append(pos["bar"])
            ds.append(d); pos = None
            continue
        # ---- water mark, then the trail
        ref = h[i] if d == 1 else lo[i]
        pos["best"] = max(pos["best"], ref) if d == 1 else min(pos["best"], ref)
        gain = (pos["best"] - e) * d / risk
        pos["peak"] = max(pos["peak"], gain)
        for lvl, newtr in ratchet:
            if gain >= lvl:
                pos["tr"] = min(pos["tr"], newtr)
        cand = pos["best"] - d * pos["tr"] * a[i - 1]
        if be_at > 0 and gain >= be_at:
            cand = max(cand, e) if d == 1 else min(cand, e)
        if giveback > 0 and pos["peak"] > 0:
            # stop placed so the remainder keeps `giveback` of the peak gain
            keep = pos["peak"] * giveback
            gb = e + d * keep * risk
            cand = max(cand, gb) if d == 1 else min(cand, gb)
        pos["stop"] = max(pos["stop"], cand) if d == 1 else min(pos["stop"], cand)
        # SAME-BAR RE-CHECK. The stop was just moved using THIS bar's extreme, and a
        # bar's high and low happen in unknown order - so if the new stop sits inside
        # this bar's range it would already have filled. Checking it only next bar is
        # the "mildly optimistic" assumption convex.py documents, and it is mild for a
        # 5xATR trail sitting far from price.
        #
        # It is NOT mild for a give-back stop. Keeping 50% of a +0.1R peak puts the
        # stop 0.05R from price, where ordinary intrabar noise breaches it constantly.
        # Without this re-check the give-back variants reported +12.69%/month at a
        # 4.0% drawdown - a return/drawdown ratio of 75, against this project's rule
        # that anything above 2.5 is presumed broken. It was: 6x the trade count of
        # every other variant, a 76% win rate, and maxR collapsed from 43 to 26.
        breach = (lo[i] <= pos["stop"]) if d == 1 else (h[i] >= pos["stop"])
        if breach:
            px = pos["stop"]
            r = pos["banked"] + pos["size"] * ((px - e) * d / risk
                                               - fee * abs(px) / risk)
            Rs.append(r); xi.append(i); ei.append(pos["bar"]); ds.append(d)
            pos = None
    return (np.asarray(Rs), np.asarray(xi, dtype=int),
            np.asarray(ei, dtype=int), np.asarray(ds, dtype=int))


def sleeve(side, **kw):
    """One sleeve, whole book, as (entry_time, exit_time, R)."""
    tr = []
    for cn in BOOK:
        df = load(cn)
        if df is None or len(df) < 3000:
            continue
        sig = signals(df, side, "all")
        if int((sig != Action.HOLD).sum()) == 0:
            continue
        R, xi, ei, _d = run_exits(df, sig, **kw)
        t = df["time"].to_numpy()
        tr += [(t[int(b)], t[int(x)], float(r)) for r, x, b in zip(R, xi, ei)]
    tr.sort(key=lambda z: z[0])
    return tr


def stats(tr, risk=RISK, slots=SLOTS):
    if len(tr) < 30:
        return None
    f = risk / 100.0
    eq, curve, times, opens, Rs = 1.0, [], [], [], []
    ruined = False
    for a_, b_, r in tr:
        opens = [u for u in opens if u > a_]
        if len(opens) >= slots:
            continue
        opens.append(b_)
        Rs.append(r)
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 0.01:
                eq, ruined = 0.0, True
        curve.append(eq); times.append(b_)
    if len(Rs) < 30:
        return None
    R = np.asarray(Rs); cur = np.asarray(curve)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    hc = cagr / HINDSIGHT if cagr > -100 else -100.0
    return dict(n=len(R), mean=float(R.mean()), win=float((R > 0).mean() * 100),
                mx=float(R.max()), dd=dd, ruined=ruined,
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0)


HDR = (f"{'exit rule':<34} {'n':>6} {'meanR':>8} {'win%':>6} {'maxR':>9} "
       f"{'HONEST /mo':>11} {'DD':>7}")


def row(tag, d):
    if not d:
        return f"{tag:<34} (no result)"
    return (f"{tag:<34} {d['n']:>6} {d['mean']:>+8.3f} {d['win']:>6.1f} "
            f"{d['mx']:>9.1f} {d['hpm']:>+10.2f}% {d['dd']:>6.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: scale-out helps SHORTS clearly, longs roughly")
    print("break even. Early breakeven helps shorts. Ratchet and give-back are")
    print("reparameterisations with no independent benefit.\n")

    for side, base_trail, label in (("short", 5.0, "SHORT sleeve (trail 5xATR)"),
                                    ("long", 20.0, "LONG sleeve (trail 20xATR)")):
        print("=" * 112)
        print(f"{label} — single unit, so the exit rule is the only variable")
        print("=" * 112)
        print(HDR)
        variants = [
            ("baseline: trail only", dict(trail=base_trail)),
            ("+ breakeven @3R (current)", dict(trail=base_trail, be_at=3.0)),
            ("+ breakeven @1.0R", dict(trail=base_trail, be_at=1.0)),
            ("+ breakeven @1.5R", dict(trail=base_trail, be_at=1.5)),
            ("+ breakeven @2.0R", dict(trail=base_trail, be_at=2.0)),
            ("scale 50% @1R, rest trails", dict(trail=base_trail,
                                                scale=((1.0, 0.5),))),
            ("scale 50% @2R, rest trails", dict(trail=base_trail,
                                                scale=((2.0, 0.5),))),
            ("scale 50% @3R, rest trails", dict(trail=base_trail,
                                                scale=((3.0, 0.5),))),
            ("scale 33% @1R +33% @2R", dict(trail=base_trail,
                                            scale=((1.0, 1 / 3), (2.0, 1 / 3)))),
            ("scale 50% @2R + BE@2R", dict(trail=base_trail, be_at=2.0,
                                           scale=((2.0, 0.5),))),
            ("scale 50% @1.5R + BE@1.5R", dict(trail=base_trail, be_at=1.5,
                                               scale=((1.5, 0.5),))),
            ("ratchet: tighten x0.6 @2R", dict(trail=base_trail,
                                               ratchet=((2.0, base_trail * 0.6),))),
            ("ratchet: tighten x0.4 @3R", dict(trail=base_trail,
                                               ratchet=((3.0, base_trail * 0.4),))),
            # GIVE-BACK CAP: REMOVED AS UNMEASURABLE ON OHLC BARS.
            #
            # It reported +21.60%/month at a 4.2% drawdown - a return/drawdown ratio
            # of 5.1 on a strategy whose honest figure is under 1. The tell was that
            # keep-50% and keep-33% produced the IDENTICAL trade count (79,738,
            # against the baseline's 7,026): both were closing on the entry bar, so
            # the count had become the number of signals.
            #
            # The mechanism cannot work on bar data. The stop is placed at a fraction
            # of the peak, the peak comes from the current bar's own high/low, and the
            # profit banked is therefore derived from an extreme that was not knowable
            # when the order was placed. Adding a same-bar stop check does not fix it,
            # because the LOOK-AHEAD IS IN THE PROFIT ITSELF, not in the exit timing.
            #
            # Testing this honestly needs tick or 1-minute data to resolve the
            # intrabar path. Until then it is neither a pass nor a fail - it is
            # unmeasurable, and reporting the number would have been the most
            # flattering artifact produced in this project.
        ]
        res = {}
        for tag, kw in variants:
            d = stats(sleeve(side, **kw))
            res[tag] = d
            print(row(tag, d), flush=True)
        base = res.get("baseline: trail only")
        cur = res.get("+ breakeven @3R (current)")
        if base and cur:
            better = [(t, d) for t, d in res.items()
                      if d and d["mean"] > cur["mean"] and d["dd"] <= cur["dd"]]
            print(f"\n  current rule (BE@3R): mean R {cur['mean']:+.3f}, "
                  f"DD {cur['dd']:.1f}%, {cur['hpm']:+.2f}%/mo")
            if better:
                better.sort(key=lambda x: -x[1]["mean"])
                print("  BEATS IT on mean R and drawdown:")
                for t, d in better:
                    print(f"    {t:<32} mean R {d['mean']:+.3f} "
                          f"({d['mean']-cur['mean']:+.3f})  DD {d['dd']:.1f}%  "
                          f"{d['hpm']:+.2f}%/mo")
            else:
                print("  nothing beat it on both mean R and drawdown.")
        print()

    print("=" * 112)
    print("HOW TO READ THIS")
    print("=" * 112)
    print("The question is NOT whether a rule banks more often - a fixed target banks")
    print("constantly and loses money. It is whether mean R rises while the maxR")
    print("column stays large. A variant that lifts win% and collapses maxR has")
    print("recreated the profit cap under a new name.")
    print("\nJudge the SHORT table first: that is where the live give-back happened,")
    print("and a 5xATR trail on a 2xATR stop structurally gives back 2.5R.")


if __name__ == "__main__":
    main()
