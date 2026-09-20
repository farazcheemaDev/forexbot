"""Does the 3x conclusion survive compounding by DATE instead of by trade order?

blend.run and bear_side.run both apply each trade's P&L in order of trade OPEN time
(mistake #6 in docs/03). Shorts exit in hours on a 5xATR trail; pyramided longs run for
weeks on 20xATR. So changing the long/short mix changes the holding-period mix, which is
precisely what an open-order equity curve mis-times. The entire case for 3x is a
drawdown U-shape, so it has to be rechecked on a curve built by CLOSE DATE.

Still not full mark-to-market - open positions are not marked - so these drawdowns are
understated in absolute terms. But they are consistently understated across variants,
which is what the comparison needs.
"""
import sys
sys.path.insert(0, "D:/forexbot")
import numpy as np, pandas as pd
from backtest import blend
from backtest.bear_side import all_trades, sleeve_sided, SLOTS

tr, stops = all_trades()
bear = blend.btc_bear()
ts_all = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
cut = ts_all[int(len(ts_all) * 0.6)]
f0 = blend.RISK / 100.0


def curve_by_date(lm, sm, t_from=None, t_to=None):
    opens, rows = [], []
    for a_, b_, r, _rule, _c, side in tr:
        if t_from is not None and a_ < t_from: continue
        if t_to is not None and a_ >= t_to: continue
        opens = [u for u in opens if u > a_]
        if len(opens) >= SLOTS: continue
        try: ib = bool(bear.asof(a_))
        except Exception: ib = False
        f = f0 * ((lm if side == "long" else sm) if ib else 1.0)
        if f <= 0: continue
        opens.append(b_)
        rows.append((pd.Timestamp(b_), r * f))
    if len(rows) < 30: return None
    s = pd.Series([x[1] for x in rows], index=pd.DatetimeIndex([x[0] for x in rows]))
    daily = s.resample("D").sum()
    cur = np.cumprod(1.0 + daily.values)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    yrs = max((daily.index[-1] - daily.index[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 1e-12) ** (1 / yrs) - 1) * 100
    hc = cagr / blend.HINDSIGHT
    mon = daily.resample("ME").sum()
    return dict(dd=dd, hpm=((1 + hc/100) ** (1/12) - 1) * 100, n=len(rows),
                worst_mo=float(mon.min()*100), win=float((mon>0).mean()*100))

print("COMPOUNDED BY CLOSE DATE (mistake #6 fixed), long multiplier 0.25")
print(f"  {'short':>7}| {'TUNE /mo':>9}{'DD':>7}| {'HOLD /mo':>9}{'DD':>7}"
      f"{'worst mo':>10}{'win%':>7}")
rows = []
for sm in (0.25, 0.50, 1.00, 1.50, 2.00, 3.00, 4.00, 6.00):
    a = curve_by_date(0.25, sm, t_to=cut)
    b = curve_by_date(0.25, sm, t_from=cut)
    if not (a and b): continue
    rows.append((sm, a, b))
    print(f"  {sm:>6.2f}x|{a['hpm']:>+9.2f}%{a['dd']:>6.1f}%|{b['hpm']:>+9.2f}%"
          f"{b['dd']:>6.1f}%{b['worst_mo']:>+9.1f}%{b['win']:>6.0f}%")

dds_t = [a['dd'] for _, a, _ in rows]; dds_h = [b['dd'] for _, _, b in rows]
mults = [m for m, _, _ in rows]
print(f"\n  minimum drawdown: tune at {mults[int(np.argmin(dds_t))]}x, "
      f"holdout at {mults[int(np.argmin(dds_h))]}x")
mar_h = [b['hpm']/b['dd'] for _, _, b in rows]
print(f"  peak MAR on holdout at {mults[int(np.argmax(mar_h))]}x")
print(f"\n  by trade-order (previous run) the holdout DD minimum was at 3.00x (70.6%).")
