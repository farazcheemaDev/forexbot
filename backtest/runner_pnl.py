"""Does the atr_ratio filter make MONEY, or is it another statistic?

runner_id.py found atr_ratio separates runners from reversals at +20R (AUC 0.647 on the
holdout, p=0.001, survives Holm). giveback.py showed why that is not enough: exiting early
raises the position count, and a fresh entry is a 77%-loser lottery, so six high-threshold
trails all captured more per winner and still lost total R.

So: exit at the CLOSE of the crossing bar when atr_ratio is below a threshold, otherwise
hold under the deployed rule. Re-entries are allowed to happen normally, which is what
makes this a P&L test rather than a statistic.
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
CROSS_R = 20.0
fee = FEE_BP / 1e4


def walk(df, sig, cut_below=None):
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    out, pos = [], None
    for i in range(1, len(df)):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i-1]) and a[i-1] > 0:
            pos = dict(risk=blend.SL_MULT*a[i-1], stop=o[i]-blend.SL_MULT*a[i-1],
                       best=o[i], bar=i, ents=[o[i]], nxt=1, peak=0.0, done=False)
        if pos is None:
            continue
        risk = pos["risk"]; e0 = pos["ents"][0]
        mark = sum(h[i]-e_ for e_ in pos["ents"]) / risk
        pos["peak"] = max(pos["peak"], mark)
        if lo[i] <= pos["stop"]:
            px = pos["stop"]
            out.append((sum(px-e_ for e_ in pos["ents"])
                        - sum(fee*e_ for e_ in pos["ents"]))/risk)
            pos = None; continue
        # the filter: at the FIRST crossing, judge volatility expansion and maybe exit
        if cut_below is not None and not pos["done"] and mark >= CROSS_R:
            pos["done"] = True
            ar = a[i]/a[pos["bar"]-1] if a[pos["bar"]-1] > 0 else 1.0
            if ar < cut_below:
                px = c[i]                     # close of the crossing bar, never its high
                out.append((sum(px-e_ for e_ in pos["ents"])
                            - sum(fee*e_ for e_ in pos["ents"]))/risk)
                pos = None; continue
        if len(pos["ents"]) < blend.MAX_UNITS:
            if (h[i]-e0)/risk >= pos["nxt"]*blend.ADD_EVERY:
                pos["ents"].append(e0 + pos["nxt"]*blend.ADD_EVERY*risk); pos["nxt"] += 1
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
    return out


def total(cut_below=None):
    rs = []
    for coin in blend.BOOK:
        d = blend.load(coin)
        if d is None: continue
        for rule in RULES:
            df = resample(d, rule)
            if len(df) < 400: continue
            rs += walk(df, signals(df, "long", "all"), cut_below)
    r = np.asarray(rs)
    return len(r), r.sum(), r.mean()


print("EXIT AT +20R WHEN VOLATILITY HAS NOT EXPANDED  (long sleeve, total R)")
print(f"  {'rule':<34}{'positions':>11}{'total R':>11}{'mean R':>9}{'vs base':>10}")
n0, s0, m0 = total(None)
print(f"  {'deployed (hold everything)':<34}{n0:>11,}{s0:>+11,.0f}{m0:>+9.3f}{'—':>10}")
for th in (1.5, 1.8, 1.9, 2.0, 2.5):
    n, s, m = total(th)
    print(f"  {'exit if atr_ratio < ' + f'{th}':<34}{n:>11,}{s:>+11,.0f}{m:>+9.3f}"
          f"{s-s0:>+10,.0f}")
print()
print("  atr_ratio medians from runner_id: runners 1.95, reversals 1.78.")
print("  A threshold of 1.8-1.9 is where the two distributions actually part.")
