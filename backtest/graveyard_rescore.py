"""THE GRAVEYARD, RE-SCORED ON THE CORRECTED ENGINE - rule 9's one legitimate exception.

WHY THIS IS ALLOWED
    CLAUDE.md rule 9: kills are permanent unless the MEASUREMENT was broken. On 2026-09-23
    three measurement errors were found in the engine every engine-level test used:
      #12 4h/12h rows stamped at the bar label, 3h/11h after the real entry (causal_t0.py)
      #13 funding never charged - 21% of lifetime long R, 46% on the 12h sleeve (funding_cost.py)
      #14 daily-sum / sequential compounding, ~2x the achievable return (compounding.py)
    #13 is not neutral between variants: every rule that SHORTENS long holds was denied the
    funding it saves, and every rule that lengthens them was spared the funding it costs. #14
    is not neutral either: it inflates overlapping runners, so variants that hold fewer, longer
    runners were flattered. So the engine-level kills and near-misses are re-scored here.

THE CORRECTED ENGINE
    Real entry times; funding charged per unit per settlement; ENTRY-SIZED compounding (a
    position's dollars fixed from closed equity at entry - what the bot does); 12 slots, 1000h
    gate, CAGR/3 haircut for %/mo; 10 random orderings, each variant PAIRED with main on the
    same ordering so the difference carries its own standard error.

WHAT IS RE-SCORED (original file and verdict in brackets)
    A. exits that shorten holds
       tight exit                         [btc_exit.py: promising; now on paper]
       time stop: below +2R after 100 bars [final_variants.py: near-miss, holdout-only]
       time stop: below 0R after 100 bars  [final_variants.py: near-miss]
       tighten to 0.5x trail above +80R    [giveback.py: dead, -4,181R]
       tight + time stop 2R/100            [never run]
    B. sleeve sets (the 12h sleeve pays 46% of its R in funding)
       1h+4h | 1h+4h+8h | 1h+2h+4h | 1h+4h+8h+12h   [engine_variants.py: no winner]
    C. per-sleeve trails (1h/4h/12h)
       20/20/12 (shorter 12h hold)         [never run]
       10/20/40                            [book_structure.py: near-miss, holdout-only]
    D. allocation / size
       8 slots                             [corr_alloc.py byproduct: better risk-adjusted]
       risk x0.67, x1.33                   [ruin.py: 0.30% near growth-optimal - sequential]
    E. entry band bb(30, 1.25)             [book_structure.py: near-miss, holdout-only]
    F. shorts x3 in bears ("lean short")   [bear_side.py: WORKS, never shipped]

REGISTERED PREDICTIONS (before running)
    1. Hold-shortening exits gain relative to their original verdicts: time stop 2R/100 beats
       main on BOTH halves; tighten-above-80R stays dead (it clips the runners that earn most).
    2. Dropping the 12h sleeve (1h+4h) helps the tune half (2021 funding) and hurts the holdout.
    3. 20/20/12 beats main; 10/20/40 gets WORSE than its original near-miss (more funding).
    4. 8 slots: lower return, lower drawdown, no both-halves win.
    5. bb(30,1.25): still holdout-only.
    6. Lean short loses most of its old edge (its bear flag was read at the label t0).
    ADOPTION BAR: beat main on BOTH halves by more than 2 paired standard errors. Anything that
    clears it is a paper-book candidate, NOT a change: this is still the mined split, and the
    forward books decide.

    python -m backtest.graveyard_rescore
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.compounding import curve, summarize  # noqa: E402
from backtest.engine_variants import break_map, shorts_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

SEEDS = tuple(range(10))
_C: dict = {}


def walk(df, rule, coin, trail=None, tb=None, time_stop=None, hi_thresh=None, hi_mult=1.0):
    """engine_variants.long_walk (deployed pyramid; records every unit's add time) plus
    optional time stop (bars, min R at the close) and high-threshold trail tightening
    (once the best gain reaches hi_thresh R, the trail multiplier x hi_mult)."""
    s = signals(df, "long", "all").to_numpy()
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    t = df["time"].to_numpy()
    fee = FEE_BP / 1e4
    wide = blend.LONG_TRAIL if trail is None else trail
    out, pos = [], None

    def close(px, i):
        R = (sum(px - e for e in pos["ents"]) - sum(fee * e for e in pos["ents"])) / pos["risk"]
        out.append(dict(t0=t[pos["bar"]], t1=t[i], R=float(R), side="long",
                        sf=pos["risk"] / pos["ents"][0], adds=list(pos["addt"]),
                        coin=coin, rule=rule))

    for i in range(1, len(df)):
        if pos is None and s[i] == 1 and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            r = blend.SL_MULT * a[i - 1]
            pos = dict(risk=r, stop=o[i] - r, best=o[i], bar=i, ents=[o[i]], nxt=1,
                       tight=False, addt=[t[i]], barmed=(tb is None or not tb[i]))
        if pos is None:
            continue
        r = pos["risk"]; e0 = pos["ents"][0]
        if tb is not None and i > pos["bar"]:
            if not tb[i]:
                pos["barmed"] = True
            elif pos["barmed"]:
                pos["tight"] = True
        if lo[i] <= pos["stop"]:
            close(pos["stop"], i); pos = None; continue
        if time_stop and i - pos["bar"] >= time_stop[0] and (c[i] - e0) / r < time_stop[1]:
            close(c[i], i); pos = None; continue
        if len(pos["ents"]) < blend.MAX_UNITS and (h[i] - e0) / r >= pos["nxt"] * blend.ADD_EVERY:
            pos["ents"].append(e0 + pos["nxt"] * blend.ADD_EVERY * r); pos["nxt"] += 1
            pos["addt"].append(t[i])
        pos["best"] = max(pos["best"], h[i])
        m = 5.0 if pos["tight"] else wide
        if hi_thresh is not None and (pos["best"] - e0) / r >= hi_thresh:
            m = m * hi_mult
        cand = pos["best"] - m * a[i - 1]
        if (pos["best"] - e0) / r >= blend.BE_AT:
            cand = max(cand, e0)
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None:
        close(c[-1], len(df) - 1)
    return out


def rows(rules=("1h", "4h", "12h"), trails=None, tight=False, **kw):
    key = (tuple(rules), tuple(sorted((trails or {}).items())), tight, tuple(sorted(kw.items())))
    if key in _C:
        return _C[key]
    out = []
    for rule in rules:
        out += shorts_for(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            tb = break_map(df, rule) if tight else None
            out += walk(df, rule, coin, trail=(trails or {}).get(rule), tb=tb, **kw)
    out = charged(real_t0(short_funding(long_funding(out))))
    _C[key] = out
    return out


def taken(rs, bear, seed, t_from=None, t_to=None, slots=12):
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rs))
    o = [rs[i] for i in sorted(range(len(rs)), key=lambda i: (rs[i]["t0"], tie[i]))]
    opens, out = [], []
    for r in o:
        if (t_from is not None and r["t0"] < t_from) or (t_to is not None and r["t0"] >= t_to):
            continue
        opens = [u for u in opens if u > r["t0"]]
        if len(opens) >= slots:
            continue
        opens.append(r["t1"])
        f = blend.RISK / 100.0 * (blend.REGIME_MULT if bool(bear.asof(r["t0"])) else 1.0)
        out.append((pd.Timestamp(r["t0"]), pd.Timestamp(r["t1"]), r["R"] * f))
    return out


def score(rs, bear, cut, slots=12):
    """Per ordering and half: (hpm, DD, worst month raw)."""
    res = {}
    for half, kw in (("tune", dict(t_to=cut)), ("hold", dict(t_from=cut))):
        v = []
        for sd in SEEDS:
            c = curve(taken(rs, bear, sd, slots=slots, **kw), "entry_sized")
            hpm, _raw, dd, _fin = summarize(c)
            wm = float(c.resample("ME").last().pct_change().min() * 100)
            v.append((hpm, dd, wm))
        res[half] = np.array(v)
    return res


def lean_short(rs, bear, mult=3.0):
    """Shorts x (mult / REGIME_MULT) while the gate says bear at the REAL entry time, so a
    bear short carries mult x risk instead of x0.25 (bear_side.py's lean_short at 3x)."""
    k = mult / blend.REGIME_MULT
    return [dict(r, R=r["R"] * k) if (r["side"] == "short" and bool(bear.asof(r["t0"]))) else r
            for r in rs]


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    base = rows()
    B = score(base, bear, cut)
    print(f"corrected engine: real t0, funding, ENTRY-SIZED compounding, {len(SEEDS)} paired orderings")
    print(f"tune < {cut:%Y-%m-%d} <= holdout; %/mo is CAGR/3; DD and worst month are raw\n")
    print(f"  {'variant':<36}{'TUNE':>7}{'DD':>5}{'HOLD':>7}{'DD':>5}{'worst':>7}"
          f"{'d TUNE':>13}{'d HOLD':>13}  verdict")

    def show(lab, rs=None, slots=12, res=None):
        R = res if res is not None else score(rs, bear, cut, slots)
        dt = R["tune"][:, 0] - B["tune"][:, 0]; dh = R["hold"][:, 0] - B["hold"][:, 0]
        st = dt.std(ddof=1) / np.sqrt(len(dt)); sh = dh.std(ddof=1) / np.sqrt(len(dh))
        both = dt.mean() > 2 * st and dh.mean() > 2 * sh
        verdict = "" if lab.startswith("MAIN") else (
            "BEATS MAIN, BOTH HALVES" if both else
            ("holdout only" if dh.mean() > 2 * sh else ("tune only" if dt.mean() > 2 * st else "-")))
        print(f"  {lab:<36}{R['tune'][:,0].mean():>+6.2f}%{R['tune'][:,1].mean():>4.0f}%"
              f"{R['hold'][:,0].mean():>+6.2f}%{R['hold'][:,1].mean():>4.0f}%"
              f"{R['hold'][:,2].mean():>+6.1f}%"
              f"{dt.mean():>+7.2f}+-{st:.2f}{dh.mean():>+7.2f}+-{sh:.2f}  {verdict}")
        return R

    show("MAIN (deployed rules)", res=B)
    print("\n  A. exits that shorten holds")
    show("tight exit", rows(tight=True))
    show("time stop: < +2R after 100 bars", rows(time_stop=(100, 2.0)))
    show("time stop: < 0R after 100 bars", rows(time_stop=(100, 0.0)))
    show("tighten x0.5 above +80R", rows(hi_thresh=80.0, hi_mult=0.5))
    show("tight + time stop 2R/100", rows(tight=True, time_stop=(100, 2.0)))
    print("\n  B. sleeve sets")
    for rs_ in (("1h", "4h"), ("1h", "4h", "8h"), ("1h", "2h", "4h"), ("1h", "4h", "8h", "12h")):
        show("+".join(rs_), rows(rules=rs_))
    print("\n  C. per-sleeve trails (1h/4h/12h)")
    show("trail 20 / 20 / 12", rows(trails={"12h": 12.0}))
    show("trail 10 / 20 / 40", rows(trails={"1h": 10.0, "12h": 40.0}))
    print("\n  D. allocation / size")
    show("8 slots", base, slots=8)
    for m in (0.67, 1.33):
        show(f"risk x{m}", [dict(r, R=r["R"] * m) for r in base])
    print("\n  E. entry band")
    import backtest.bear_side as BS
    import backtest.engine_variants as EV
    import backtest.funding_cost as FC
    import backtest.shortside as SS
    SS.BB_P, SS.BB_STD = 30, 1.25
    EV._CACHE.clear(); BS._S.clear(); FC._SH.clear(); _C.clear()
    show("bb(30, 1.25)", rows())
    SS.BB_P, SS.BB_STD = 30, 1.5
    EV._CACHE.clear(); BS._S.clear(); FC._SH.clear(); _C.clear()
    print("\n  F. shorts")
    show("lean short: shorts x3 in bears", lean_short(rows(), bear))
    print("\n  'd' = paired difference vs MAIN on the same orderings, +- one standard error "
          "(ordering noise only).")

    # Declared after the first (crashed) run showed tight + time stop clearing the MAIN bar:
    # the real question is whether the time stop adds anything ON TOP of the tight book that
    # is already on paper. Same bar: both halves, > 2 paired SE, against TIGHT this time.
    T = score(rows(tight=True), bear, cut)
    TT = score(rows(tight=True, time_stop=(100, 2.0)), bear, cut)
    print("\n  TIGHT + TIME STOP vs TIGHT alone (paired):")
    for half in ("tune", "hold"):
        d = TT[half][:, 0] - T[half][:, 0]
        wm = TT[half][:, 2].mean() - T[half][:, 2].mean()
        dd = TT[half][:, 1].mean() - T[half][:, 1].mean()
        print(f"    {half}: {d.mean():+.2f} +- {d.std(ddof=1) / np.sqrt(len(d)):.2f} %/mo, "
              f"DD {dd:+.0f} pts, worst month {wm:+.1f} pts")


if __name__ == "__main__":
    main()
