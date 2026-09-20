"""Do the runners ever dip before they run? — the leverage question, measured.

With ISOLATED margin at high leverage the maximum loss is the margin posted, which is
exactly the appeal: capped downside, uncapped upside. But leverage also sets the
LIQUIDATION distance: at Lx you are closed at roughly -1/L of price. This strategy's own
stop is 2xATR, about 10% of price, so any leverage above ~10x liquidates you BEFORE your
strategy would exit.

So the whole idea rests on one measurable fact: how far below entry does a winning
position go before it wins? That is the maximum adverse excursion (MAE). If the runners
dip, high leverage removes you from the trades that make all the money.
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
fee = FEE_BP/1e4


def walk(df, sig):
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    out, pos = [], None
    for i in range(1, len(df)):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i-1]) and a[i-1] > 0:
            pos = dict(risk=blend.SL_MULT*a[i-1], stop=o[i]-blend.SL_MULT*a[i-1],
                       best=o[i], ents=[o[i]], nxt=1, peak=0.0, worst=o[i])
        if pos is None:
            continue
        risk = pos["risk"]; e0 = pos["ents"][0]
        pos["worst"] = min(pos["worst"], lo[i])          # lowest price ever touched
        pos["peak"] = max(pos["peak"], sum(h[i]-e_ for e_ in pos["ents"])/risk)
        if lo[i] <= pos["stop"]:
            px = pos["stop"]
            r = (sum(px-e_ for e_ in pos["ents"]) - sum(fee*e_ for e_ in pos["ents"]))/risk
            out.append((pos["peak"], r, (e0-pos["worst"])/e0))
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
        e0 = pos["ents"][0]; px = c[-1]
        r = (sum(px-e_ for e_ in pos["ents"]) - sum(fee*e_ for e_ in pos["ents"]))/pos["risk"]
        out.append((pos["peak"], r, (e0-pos["worst"])/e0))
    return out


rows = []
for coin in blend.BOOK:
    d = blend.load(coin)
    if d is None: continue
    for rule in RULES:
        df = resample(d, rule)
        if len(df) >= 400:
            rows += walk(df, signals(df, "long", "all"))
T = pd.DataFrame(rows, columns=["peak", "exit", "mae"])
T["runner"] = T.peak >= 100
run = T[T.runner]
print(f"{len(T):,} positions, {len(run)} runners (peak >= +100R)\n")
print("HOW FAR BELOW ENTRY DID A POSITION GO BEFORE IT WON?  (max adverse excursion)")
print(f"  {'group':<22}{'n':>7}{'median MAE':>12}{'75th':>9}{'90th':>9}{'worst':>9}")
for lab, g in (("ALL positions", T), ("RUNNERS (>= +100R)", run),
               ("non-runners", T[~T.runner])):
    m = g.mae*100
    print(f"  {lab:<22}{len(g):>7}{m.median():>11.2f}%{m.quantile(.75):>8.2f}%"
          f"{m.quantile(.90):>8.2f}%{m.max():>8.2f}%")
print()
print("WHAT FRACTION OF THE RUNNERS SURVIVE AT EACH LEVERAGE?")
print("  (liquidation at roughly -1/L of price, ignoring maintenance margin,")
print("   so these are OPTIMISTIC)")
print(f"  {'leverage':>10}{'liq at':>10}{'runners surviving':>20}{'all surviving':>16}")
for L in (2,3,5,10,20,50,100):
    liq = 1.0/L
    print(f"  {L:>9}x{-liq*100:>9.1f}%{100*(run.mae < liq).mean():>19.1f}%"
          f"{100*(T.mae < liq).mean():>15.1f}%")
print()
tot = T.exit.sum()
for L in (10,20,50,100):
    liq = 1.0/L
    surv = T[T.mae < liq]
    lost = T[T.mae >= liq]
    print(f"  at {L}x: {len(surv):,} positions survive to their own exit "
          f"({surv.exit.sum():+,.0f}R), {len(lost):,} liquidated first")
