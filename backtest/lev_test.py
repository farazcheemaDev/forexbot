"""Isolated margin + leverage, tested properly: liquidation as a stop, re-entries allowed.

The idea: post a small isolated margin at high leverage. Downside is capped at the margin;
upside is uncapped. Measured fact that makes it plausible: runners have a median maximum
adverse excursion of 1.04% against 3.28% for everything else, so a tight liquidation line
removes losers preferentially.

The flaw in the first pass: it dropped liquidated positions instead of charging them, and
did not let the signal re-fire. Both are fixed here. Liquidation is modelled as a stop at
avg_entry x (1 - 1/L), which fires whenever it is TIGHTER than the strategy's own stop,
and the R is computed the normal way over all units - so the loss is charged, not ignored.
Real liquidation also involves maintenance margin, fees and slippage, so -1/L is optimistic.
"""
import sys
sys.path.insert(0, "D:/forexbot")
import numpy as np, pandas as pd
from backtest import blend
from backtest.pyramid import FEE_BP
from backtest.shortside import signals
from backtest.timeframes import resample
from bot.core.indicators import atr as atr_ind
from bot.strategies.base import Action

RULES = ["1h", "4h", "12h"]
fee = FEE_BP / 1e4


def walk(df, sig, liq=None):
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    out, pos, nliq = [], None, 0
    for i in range(1, len(df)):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i-1]) and a[i-1] > 0:
            pos = dict(risk=blend.SL_MULT*a[i-1], stop=o[i]-blend.SL_MULT*a[i-1],
                       best=o[i], ents=[o[i]], nxt=1)
        if pos is None:
            continue
        risk = pos["risk"]; e0 = pos["ents"][0]
        eff = pos["stop"]
        was_liq = False
        if liq is not None:
            lvl = float(np.mean(pos["ents"])) * (1.0 - liq)
            if lvl > eff:                      # liquidation is tighter -> it fires first
                eff, was_liq = lvl, True
        if lo[i] <= eff:
            px = eff
            r = (sum(px-e_ for e_ in pos["ents"]) - sum(fee*e_ for e_ in pos["ents"]))/risk
            out.append(r); nliq += 1 if was_liq else 0
            pos = None; continue
        if len(pos["ents"]) < blend.MAX_UNITS:
            if (h[i]-e0)/risk >= pos["nxt"]*blend.ADD_EVERY:
                pos["ents"].append(e0+pos["nxt"]*blend.ADD_EVERY*risk); pos["nxt"] += 1
        pos["best"] = max(pos["best"], h[i])
        cand = pos["best"] - blend.LONG_TRAIL*a[i-1]
        if (pos["best"]-e0)/risk >= blend.BE_AT:
            cand = max(cand, e0)
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None:
        px = c[-1]
        out.append((sum(px-e_ for e_ in pos["ents"])
                    - sum(fee*e_ for e_ in pos["ents"]))/pos["risk"])
    return out, nliq


def total(liq=None):
    rs, nl = [], 0
    for coin in blend.BOOK:
        d = blend.load(coin)
        if d is None: continue
        for rule in RULES:
            df = resample(d, rule)
            if len(df) < 400: continue
            r, n = walk(df, signals(df, "long", "all"), liq)
            rs += r; nl += n
    r = np.asarray(rs)
    return len(r), r.sum(), r.mean(), 100*(r > 0).mean(), nl


print("LIQUIDATION AS A STOP, WITH RE-ENTRIES ALLOWED  (long sleeve, total R)")
print(f"  {'leverage':<12}{'liq at':>9}{'positions':>11}{'liquidated':>12}"
      f"{'win%':>7}{'mean R':>9}{'total R':>11}{'vs base':>10}")
n0, s0, m0, w0, _ = total(None)
print(f"  {'none (deployed)':<12}{'—':>9}{n0:>11,}{0:>12}{w0:>6.0f}%{m0:>+9.3f}"
      f"{s0:>+11,.0f}{'—':>10}")
for L in (3, 5, 10, 20, 50, 100):
    n, s, m, w, nl = total(1.0/L)
    print(f"  {str(L)+'x':<12}{-100.0/L:>8.1f}%{n:>11,}{nl:>12,}{w:>6.0f}%{m:>+9.3f}"
          f"{s:>+11,.0f}{s-s0:>+10,.0f}")
