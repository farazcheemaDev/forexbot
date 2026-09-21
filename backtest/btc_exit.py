"""EXIT THE ALTS WHEN BTC SIGNALS A REVERSAL - a market-level exit for the whole book.

THE IDEA (2026-09-22)
    The book is 12 correlated alts; when BTC turns, they turn with it. So instead of each
    position waiting for its own 20xATR trail (we keep 21% of peak - giveback.py), watch
    BTC for a reversal and protect every position at once.

WHY IT IS NOT ALREADY ANSWERED
    Eleven exit rules died, but every one keyed on the POSITION's own R. runner_id.py used
    BTC state (btc_bear, btc_30) only as a static feature at one moment. A dynamic
    "BTC turned -> act on all longs" rule has never been run.

WHY IT MAY STILL FAIL
    The same two forces that killed every exit rule: most BTC dips that look like tops are
    not, and exiting a runner does not bank it - it re-queues you for a 77%-loser entry
    (re-entry drag). Error asymmetry measured at 2.3:1 against exits.

THE SIGNALS, DECLARED BEFORE LOOKING (all on BTC, all known before the bar that acts)
    regime_flip    BTC 1h close below its 1000h average (the deployed gate) - trend lost
    dd5/dd8/dd12   BTC close >= 5/8/12% below its 7-day high
    trail3/trail5  BTC 4h close below (highest 4h close since the last reset - k x ATR)
                   i.e. BTC's own fast trend-following stop
    divergence     BTC 4h makes a 20-bar closing high while RSI(14) is BELOW its reading
                   at the previous 20-bar high: the classic bearish divergence, 5 days on
    ema_cross      BTC 4h EMA20 below EMA50

THE ACTIONS
    close        exit every open long at the next bar's open; new longs allowed as normal
    close+block  exit, and take no new longs while the signal is on
    tighten      open longs switch from the 20xATR trail to 5xATR once the signal fires

    Shorts unchanged. Same 12-slot allocator, deployed 1000h gate on new entries,
    compounded by close date, 3x hindsight haircut on %/mo. Tune/holdout as bear_date.py.

PRIMARY, REGISTERED: regime_flip + close. Prediction: every variant loses total long R
    against the deployed book; "close" variants worst (most re-entries); if anything
    holds it will be a slow signal (regime_flip, dd12), never divergence.

    python -m backtest.btc_exit
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import evaluate, pyramid_detail, regimes  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

RULES, U = ["1h", "4h", "12h"], blend.MAX_UNITS
STEP = {"1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4), "12h": pd.Timedelta(hours=12)}


def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def btc_trail(k, rule="4h"):
    d = blend.load("BTCUSDT")
    b = resample(d, rule)
    c = pd.Series(b["close"].to_numpy(), index=pd.DatetimeIndex(b["time"]))
    a = atr_ind(b, 14).to_numpy()
    best, flag = -np.inf, []
    for px, at in zip(c.to_numpy(), a):
        best = max(best, px)
        broke = np.isfinite(at) and px < best - k * at
        flag.append(bool(broke))
        if broke:
            best = px
    return pd.Series(flag, index=c.index)


def btc_ema(f, sl, rule="4h"):
    d = blend.load("BTCUSDT")
    b = resample(d, rule)
    c = pd.Series(b["close"].to_numpy(), index=pd.DatetimeIndex(b["time"]))
    return (c.ewm(span=f, adjust=False).mean() < c.ewm(span=sl, adjust=False).mean())


def btc_signals():
    """Each signal as a boolean Series indexed by the time it becomes KNOWN (bar close)."""
    d = blend.load("BTCUSDT")
    h1 = pd.Series(d["close"].to_numpy(), index=pd.DatetimeIndex(d["time"]) + pd.Timedelta(hours=1))
    out = {"regime_flip": h1 < h1.rolling(1000).mean()}
    hi7 = h1.rolling(24 * 7).max()
    for x in (5, 8, 12):
        out[f"dd{x}"] = h1 <= hi7 * (1 - x / 100)
    b4 = resample(d, "4h")                      # right-labelled: time = bar close
    c4 = pd.Series(b4["close"].to_numpy(), index=pd.DatetimeIndex(b4["time"]))
    a4 = pd.Series(atr_ind(b4, 14).to_numpy(), index=c4.index)
    for k in (3, 5):
        # BTC's own trailing stop: track the highest close since the stop last broke
        best, flag = -np.inf, []
        for px, a in zip(c4.to_numpy(), a4.to_numpy()):
            best = max(best, px)
            broke = np.isfinite(a) and px < best - k * a
            flag.append(bool(broke))
            if broke:
                best = px                        # reset: a new trend must build
        out[f"trail{k}"] = pd.Series(flag, index=c4.index)
    r = rsi(c4)
    hi20 = c4.rolling(20).max()
    is_hi = c4 >= hi20
    last_hi_rsi = r.where(is_hi).shift(1).ffill()
    div = is_hi & (r < last_hi_rsi)
    # a divergence is an EVENT; hold the warning for 5 days (30 4h bars)
    out["divergence"] = div.astype(int).rolling(30, min_periods=1).max().astype(bool)
    e20, e50 = c4.ewm(span=20, adjust=False).mean(), c4.ewm(span=50, adjust=False).mean()
    out["ema_cross"] = e20 < e50
    return {k: v.fillna(False).astype(bool) for k, v in out.items()}


def sim(df, rule, trig, action, tight_mult=5.0):
    """Deployed long pyramid with a BTC trigger. trig[i] = signal known at the START of
    bar i. Returns rows in bull_boost's format."""
    sig = signals(df, "long", "all").to_numpy()
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    t = df["time"].to_numpy()
    a = atr_ind(df, 14).to_numpy(float)
    fee = blend.FEE_BP / 1e4
    out, pos = [], None

    def close(px, i):
        R = sum((px - e) / pos["risk"] - fee * e / pos["risk"] for e in pos["entries"])
        out.append(dict(t0=t[pos["bar"]], t1=t[i], R=R, sf=pos["risk"] / pos["entries"][0],
                        adds=list(pos["add_t"]), side="long"))

    for i in range(1, len(df)):
        if pos is None and sig[i] == 1 and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            if not (action == "close+block" and trig[i]):
                r = blend.SL_MULT * a[i - 1]
                pos = dict(risk=r, stop=o[i] - r, best=o[i], bar=i, entries=[o[i]], nxt=1,
                           add_t=[t[i]], tight=False, armed=not trig[i])
        if pos is None:
            continue
        # a trigger that was ALREADY on at entry does not exit the trade it let in;
        # it must switch off and on again - otherwise "close" would exit on bar one
        if not trig[i]:
            pos["armed"] = True
        if trig[i] and pos["armed"] and i > pos["bar"]:
            if action in ("close", "close+block"):
                close(o[i], i); pos = None; continue
            pos["tight"] = True
        r = pos["risk"]
        if lo[i] <= pos["stop"]:
            close(pos["stop"], i); pos = None; continue
        if len(pos["entries"]) < U and (h[i] - pos["entries"][0]) / r >= pos["nxt"] * blend.ADD_EVERY:
            pos["entries"].append(pos["entries"][0] + pos["nxt"] * blend.ADD_EVERY * r)
            pos["add_t"].append(t[i]); pos["nxt"] += 1
        pos["best"] = max(pos["best"], h[i])
        trail = tight_mult if pos["tight"] else blend.LONG_TRAIL
        cand = pos["best"] - trail * a[i - 1]
        if (pos["best"] - pos["entries"][0]) / r >= blend.BE_AT:
            cand = max(cand, pos["entries"][0])
        pos["stop"] = max(pos["stop"], cand)
    if pos is not None:
        close(c[-1], len(df) - 1)
    return out


def build(trigs, name, action, frames, shorts, tight_mult=5.0, seed=None):
    rows = list(shorts)
    for (rule, coin), df in frames.items():
        start = pd.DatetimeIndex(df["time"]) if rule == "1h" else \
            pd.DatetimeIndex(df["time"]) - STEP[rule]
        if name is None:
            tr = np.zeros(len(df), dtype=bool)
        else:
            s = trigs[name]
            tr = s.reindex(s.index.union(start)).ffill().reindex(start).fillna(False).to_numpy(bool)
        rows += sim(df, rule, tr, action, tight_mult)
    if seed is None:
        rows.sort(key=lambda x: x["t0"])
    else:
        # ties at the same entry time are broken RANDOMLY: with 12 slots binding, which of
        # two simultaneous signals gets the last slot is arbitrary, and the result moved
        # ~1.5%/mo between two files that differed only in that order
        rng = np.random.default_rng(seed)
        keys = rng.random(len(rows))
        order = sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], keys[i]))
        rows = [rows[i] for i in order]
    return rows


def main():
    trigs = btc_signals()
    bear = regimes()[1000]
    frames, shorts = {}, []
    for rule in RULES:
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) >= 300:
                frames[(rule, coin)] = df
        _tr, stops = sleeve_sided(rule)
        shorts += [dict(t0=a_, t1=b_, R=r, sf=stops.get(c_, 0.05), adds=[a_], side="short")
                   for a_, b_, r, _ru, c_, side in _tr if side == "short"]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]

    # guard: no trigger == the deployed long sleeve, exactly
    base = build(trigs, None, "close", frames, shorts)
    ref = []
    for (rule, coin), df in frames.items():
        ref += pyramid_detail(df)
    assert np.isclose(sum(x["R"] for x in base if x["side"] == "long"),
                      sum(x["R"] for x in ref)), "no-trigger run must equal deployed"
    print("guard: no-trigger run reproduces the deployed long sleeve exactly\n")

    print("HOW OFTEN EACH BTC SIGNAL IS ON, and whether BTC actually falls after it switches on")
    d = blend.load("BTCUSDT")
    px = pd.Series(d["close"].to_numpy(), index=pd.DatetimeIndex(d["time"]) + pd.Timedelta(hours=1))
    fwd = px.shift(-24 * 7) / px - 1                   # BTC over the next 7 days
    base_fwd = fwd.dropna()
    print(f"  {'signal':<13}{'% of time on':>13}{'switch-ons':>11}{'BTC next 7d after':>19}"
          f"{'(all hours)':>13}")
    for k, s in trigs.items():
        on = s.reindex(px.index, method="ffill").fillna(False)
        starts = on & ~on.shift(1, fill_value=False)
        f = fwd[starts].dropna()
        print(f"  {k:<13}{on.mean()*100:>12.0f}%{int(starts.sum()):>11}"
              f"{f.mean()*100:>+18.2f}%{base_fwd.mean()*100:>+12.2f}%")

    def row(lab, rows):
        a = evaluate(rows, bear, t_to=cut)
        b = evaluate(rows, bear, t_from=cut)
        L = [x for x in rows if x["side"] == "long"]
        print(f"  {lab:<30}{len(L):>7}{sum(x['R'] for x in L):>+10.0f} | {a['hpm']:>+7.2f}%"
              f"{a['dd']:>5.0f}% | {b['hpm']:>+7.2f}%{b['dd']:>5.0f}%{b['worst_mo']:>+8.1f}%")
        return a, b

    print(f"\n  {'':<30}{'longs':>7}{'long R':>10} | {'TUNE/mo':>8}{'DD':>6} | "
          f"{'HOLD/mo':>8}{'DD':>6}{'worst mo':>9}")
    d0 = row("DEPLOYED (no BTC exit)", base)
    wins = []
    for k in trigs:
        for act in ("close", "close+block", "tighten"):
            a, b = row(f"{k} + {act}", build(trigs, k, act, frames, shorts))
            if a["hpm"] > d0[0]["hpm"] and b["hpm"] > d0[1]["hpm"]:
                wins.append((k, act))
        print()
    print("variants that beat the deployed book on BOTH halves: "
          + (", ".join(f"{k}+{a}" for k, a in wins) if wins else "none"))


def robust():
    """The checks the first pass demands before any 'tighten' row is believed."""
    bear = regimes()[1000]
    frames, shorts = {}, []
    for rule in RULES:
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is not None:
                df = resample(d, rule)
                if len(df) >= 300:
                    frames[(rule, coin)] = df
        _tr, stops = sleeve_sided(rule)
        shorts += [dict(t0=a_, t1=b_, R=r, sf=stops.get(c_, 0.05), adds=[a_], side="short")
                   for a_, b_, r, _ru, c_, side in _tr if side == "short"]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]

    def run(trigs, name, tm=5.0, seeds=(1, 2, 3, 4, 5)):
        A, B, LR = [], [], None
        for sd in seeds:
            rows = build(trigs, name, "tighten", frames, shorts, tm, seed=sd)
            a = evaluate(rows, bear, t_to=cut); b = evaluate(rows, bear, t_from=cut)
            A.append((a["hpm"], a["dd"])); B.append((b["hpm"], b["dd"], b["worst_mo"]))
            LR = sum(x["R"] for x in rows if x["side"] == "long")
        A, B = np.array(A), np.array(B)
        return A, B, LR

    def show(lab, A, B, LR):
        print(f"  {lab:<30}{LR:>+9.0f} | {A[:,0].mean():>+6.2f}% ({A[:,0].min():+.1f}..{A[:,0].max():+.1f})"
              f"{A[:,1].mean():>5.0f}% | {B[:,0].mean():>+6.2f}% ({B[:,0].min():+.1f}..{B[:,0].max():+.1f})"
              f"{B[:,1].mean():>5.0f}%{B[:,2].mean():>+7.1f}%")

    print("1. TIE-BREAK NOISE: 5 random orderings of simultaneous entries. mean (min..max)")
    print(f"  {'':<30}{'long R':>9} | {'TUNE/mo':>21}{'DD':>6} | {'HOLD/mo':>21}{'DD':>6}{'worst':>8}")
    none = {"x": pd.Series(False, index=pd.DatetimeIndex([pd.Timestamp('2019-01-01')]))}
    show("DEPLOYED", *run(none, None))
    show("trail5 + tighten 5x", *run({"t": btc_trail(5)}, "t"))
    show("ema20/50 + tighten 5x", *run({"t": btc_ema(20, 50)}, "t"))
    show("trail3 + tighten 5x", *run({"t": btc_trail(3)}, "t"))

    print("\n2. NEIGHBOURHOOD (seeds 1-3). A real effect holds across nearby settings.")
    print(f"  {'':<30}{'long R':>9} | {'TUNE/mo':>21}{'DD':>6} | {'HOLD/mo':>21}{'DD':>6}{'worst':>8}")
    for k in (4, 5, 6, 8):
        for tm in (3.0, 5.0, 8.0, 10.0):
            show(f"BTC trail{k} 4h, tighten {tm:g}x", *run({"t": btc_trail(k)}, "t", tm, (1, 2, 3)))
    for f, sl in ((10, 30), (20, 50), (50, 100)):
        for tm in (5.0, 10.0):
            show(f"BTC ema{f}/{sl} 4h, tighten {tm:g}x", *run({"t": btc_ema(f, sl)}, "t", tm, (1, 2, 3)))
    for k in (5, 8):
        show(f"BTC trail{k} 12h, tighten 5x", *run({"t": btc_trail(k, "12h")}, "t", 5.0, (1, 2, 3)))

    print("\n3. BY YEAR (sum of R x risk, % of equity, not compounded), seed 1")
    variants = {"deployed": (none, None), "trail5 tighten": ({"t": btc_trail(5)}, "t"),
                "ema20/50 tighten": ({"t": btc_ema(20, 50)}, "t")}
    yr = {}
    for lab, (tg, nm) in variants.items():
        rows = build(tg, nm, "tighten", frames, shorts, 5.0, seed=1)
        dly = evaluate(rows, bear)["daily"]
        yr[lab] = dly.groupby(dly.index.year).sum() * 100
    Y = pd.DataFrame(yr)
    print(Y.round(0).to_string())


if __name__ == "__main__":
    if "--robust" in sys.argv:
        robust()
    else:
        main()
