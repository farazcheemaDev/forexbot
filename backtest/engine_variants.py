"""TURNING THE ENGINE'S OWN STONES - add structure, sleeve set, alignment filter.

Everything outside the engine has been tested (49 categories). These are the untested
choices INSIDE the deployed engine, which is where the remaining edge would have to live.

  1. PYRAMID ADDS ON PULLBACKS. Today units 2-5 are filled at fixed +2R breakout levels -
     bought HIGH. That is exactly where the -20R breakeven loss comes from (giveback.py:
     a 5-unit position stopped at its first entry loses 0+2+4+6+8 R). Filling those adds on
     a PULLBACK of P x ATR from the running high instead lowers every added unit's entry.
     Cost: in a fast trend the pullback never comes and the add is missed.
  2. NEW SLEEVES. The blend is 1h+4h+12h. 12h is the strongest of the three, and nobody has
     tried 1d, 2h, 6h or 8h. Slots stay at 12, so more sleeves means more declines - the
     test has to be run through the real allocator, not pooled.
  3. MULTI-TIMEFRAME ALIGNMENT. Take a 1h entry only when the coin's 12h sleeve is also
     above its band. Low prior (filters keep dying here) but cheap next to the same walk.

METHOD
    One position at a time per coin x sleeve (the deployed rule), the deployed pyramid,
    trail, breakeven and fees. Shorts unchanged from the deployed short sleeve. Every row
    goes through the 12-slot allocator with the 1000h regime gate, compounded by close
    date, %/mo after the 3x hindsight haircut, tune/holdout split as bear_date.py.

    EVERY figure is averaged over 5 random orderings of simultaneous entries, because that
    ordering alone swings a single run by 3-5%/mo (btc_exit.py). Single-run differences
    below ~2%/mo mean nothing.

    python -m backtest.engine_variants
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.shortside import bands, signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

BASE_RULES = ["1h", "4h", "12h"]
SEEDS = (0, 1, 2, 3, 4)
_CACHE: dict = {}


def long_walk(df, rule, coin, add_mode="breakout", pull_atr=1.0, align=None, tb=None):
    """Deployed long pyramid, one position at a time.

    add_mode 'breakout' fills unit k at entry + k*2R the moment price trades there (today).
    add_mode 'pullback' arms the add at the same +2R eligibility but fills it only after a
    P x ATR pullback from the running high, at that lower price; if the pullback never comes
    the add is simply missed.
    align, if given, is a bool array on this df's bars: an entry is only taken when True."""
    s = signals(df, "long", "all").to_numpy()
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    t = df["time"].to_numpy()
    fee = FEE_BP / 1e4
    out, pos = [], None
    for i in range(1, len(df)):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            if align is None or align[i]:
                r = blend.SL_MULT * a[i - 1]
                pos = dict(risk=r, stop=o[i] - r, best=o[i], bar=i, ents=[o[i]], nxt=1,
                           armed=False, tight=False, addt=[t[i]],
                           barmed=(tb is None or not tb[i]))
        if pos is None:
            continue
        r = pos["risk"]; e0 = pos["ents"][0]
        if tb is not None and i > pos["bar"]:           # BTC-break tighten (btc_exit.py)
            if not tb[i]:
                pos["barmed"] = True
            elif pos["barmed"]:
                pos["tight"] = True
        if lo[i] <= pos["stop"]:
            px = pos["stop"]
            R = (sum(px - e for e in pos["ents"]) - sum(fee * e for e in pos["ents"])) / r
            out.append(dict(t0=t[pos["bar"]], t1=t[i], R=float(R), side="long",
                            sf=r / e0, adds=list(pos["addt"]), coin=coin, rule=rule))
            pos = None
            continue
        # --- pyramid ---
        if len(pos["ents"]) < blend.MAX_UNITS:
            gain = (h[i] - e0) / r
            level = e0 + pos["nxt"] * blend.ADD_EVERY * r
            if add_mode == "breakout":
                if gain >= pos["nxt"] * blend.ADD_EVERY:
                    pos["ents"].append(level); pos["nxt"] += 1; pos["addt"].append(t[i])
            else:
                if gain >= pos["nxt"] * blend.ADD_EVERY and not pos["armed"]:
                    pos["armed"] = True
                    pos["armed_bar"] = i          # armed by THIS bar's high...
                if pos["armed"] and i > pos["armed_bar"]:   # ...fill no earlier than the
                    #  NEXT bar, so we never assume this bar's high came before its low
                    # pos["best"] here is still the high through bar i-1: the trail/water
                    # mark is updated AFTER this block, so this level was knowable before
                    # bar i opened. Using this bar's own high would assume the high came
                    # before the low - intrabar look-ahead (doc 03, the entry-bar stop bug).
                    want = pos["best"] - pull_atr * a[i - 1]
                    # fill only on a real pullback, and never above the breakout level
                    if lo[i] <= want and want < level:
                        pos["ents"].append(want); pos["nxt"] += 1; pos["armed"] = False
                        pos["addt"].append(t[i])
        pos["best"] = max(pos["best"], h[i])
        cand = pos["best"] - (5.0 if pos["tight"] else blend.LONG_TRAIL) * a[i - 1]
        if (pos["best"] - e0) / r >= blend.BE_AT:
            cand = max(cand, e0)
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None:
        px = c[-1]
        R = (sum(px - e for e in pos["ents"]) - sum(fee * e for e in pos["ents"])) / pos["risk"]
        out.append(dict(t0=t[pos["bar"]], t1=t[-1], R=float(R), side="long",
                        sf=pos["risk"] / pos["ents"][0], adds=list(pos["addt"]),
                        coin=coin, rule=rule))
    return out


def shorts_for(rule):
    if ("sh", rule) not in _CACHE:
        tr, stops = sleeve_sided(rule)
        _CACHE[("sh", rule)] = [dict(t0=a_, t1=b_, R=r, sf=stops.get(c_, 0.05), adds=[a_],
                                     side="short", coin=c_, rule=rule)
                                for a_, b_, r, _ru, c_, side in tr if side == "short"]
    return _CACHE[("sh", rule)]


def align_map(d, df, rule):
    """For each bar of df, is the coin's 12h close above its 12h upper band (shifted)?"""
    h12 = resample(d, "12h")
    lo_b, up_b = bands(h12)
    ok = (h12["close"] > up_b).shift(1).fillna(False)
    s = pd.Series(ok.to_numpy(bool), index=pd.DatetimeIndex(h12["time"]))
    idx = pd.DatetimeIndex(df["time"])
    return s.reindex(s.index.union(idx)).ffill().reindex(idx).fillna(False).to_numpy(bool)


def break_map(df, rule):
    """BTC 4h trail-break flag aligned to each bar's START time (btc_exit.py)."""
    from backtest.btc_exit import btc_trail
    br = _CACHE.setdefault("btcbreaks", btc_trail(5))
    idx = pd.DatetimeIndex(df["time"])
    starts = idx if rule == "1h" else idx - pd.Timedelta(rule)
    return br.reindex(br.index.union(starts)).ffill().reindex(starts)        .fillna(False).to_numpy(bool)


def rows_for(rules, add_mode="breakout", pull_atr=1.0, aligned=False, tight=False):
    key = (tuple(rules), add_mode, pull_atr, aligned, tight)
    if key in _CACHE:
        return _CACHE[key]
    rows = []
    for rule in rules:
        rows += shorts_for(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            al = align_map(d, df, rule) if (aligned and rule != "12h") else None
            tb = break_map(df, rule) if tight else None
            rows += long_walk(df, rule, coin, add_mode, pull_atr, al, tb)
    _CACHE[key] = rows
    return rows


def run(rows, bear, cut, half):
    hpm, dd, wm, n = [], [], [], []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
        s = evaluate(o, bear, t_to=cut) if half == "tune" else evaluate(o, bear, t_from=cut)
        hpm.append(s["hpm"]); dd.append(s["dd"]); wm.append(s["worst_mo"])
    return np.mean(hpm), np.mean(dd), np.mean(wm)


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print(f"tune < {cut:%Y-%m-%d} <= holdout | {len(SEEDS)} orderings averaged\n")
    print(f"  {'variant':<40}{'longs':>7}{'TUNE/mo':>9}{'DD':>6}{'HOLD/mo':>9}{'DD':>6}{'worst':>8}")

    def show(lab, rows):
        a = run(rows, bear, cut, "tune"); b = run(rows, bear, cut, "hold")
        nl = sum(1 for r in rows if r["side"] == "long")
        print(f"  {lab:<40}{nl:>7}{a[0]:>+8.2f}%{a[1]:>5.0f}%{b[0]:>+8.2f}%{b[1]:>5.0f}%"
              f"{b[2]:>+7.1f}%")
        return a, b

    base = show("BASE 1h+4h+12h, breakout adds", rows_for(BASE_RULES))

    print("\n  1. PYRAMID ADDS ON PULLBACKS (same eligibility, lower fill)")
    for p in (0.5, 1.0, 2.0):
        show(f"pullback adds {p:g}xATR", rows_for(BASE_RULES, "pullback", p))

    print("\n  2. SLEEVE SETS (slots still 12)")
    for rules in (["1h", "4h", "12h", "1d"], ["4h", "12h", "1d"], ["1h", "4h", "12h", "8h"],
                  ["1h", "2h", "4h", "12h"], ["12h", "1d"], ["1h", "4h", "12h", "2h", "1d"]):
        show("+".join(rules), rows_for(rules))

    print("\n  3. MULTI-TIMEFRAME ALIGNMENT (1h/4h entries need 12h above its band)")
    show("aligned to 12h", rows_for(BASE_RULES, aligned=True))

    print(f"\n  base holdout {base[1][0]:+.2f}%/mo at {base[1][1]:.0f}% DD - a variant only")
    print("  counts if it beats that on BOTH halves by more than ~2%/mo.")


if __name__ == "__main__":
    main()
