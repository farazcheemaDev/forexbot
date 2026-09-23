"""LIQUIDATION CASCADES, RE-TESTED ON FOUR YEARS INSTEAD OF THIRTY DAYS.

WHY THIS IS A RE-TEST AND NOT A NEW IDEA
    liq_cascade.py (day 1) found that 5-minute bars where price fell hard AND open interest
    fell hard - positions being force-closed - bounced far more than bars with the same price
    drop on RISING open interest: +46.4bp difference, t +3.79, 7.4 events/day. A forced
    seller has no opinion, so whoever absorbs it is paid for liquidity: a non-informational,
    capacity-limited mechanism - exactly what a small account can reach and a fund cannot.
    It was never settled. Its OI came from Binance's openInterestHist endpoint, which serves
    ONLY THE LAST 30 DAYS; its headline measured the bounce "from low to close" (the low is
    not known in advance); and cascade_ticks.py found 9 usable tick events and stopped at "too
    few events to conclude". No verdict was ever written.

    What changed: metrics_fetch.py has since cached Binance's 5-minute metrics archive for 13
    symbols back to 2021-12 (5,989,482 rows). Price at each stamp = OI value / OI contracts,
    so no separate klines are needed.

THE TEST
    Per coin: 5-minute log return and OI change, each z-scored against its own trailing 30
    days (strictly past). Quadrants at |z| > 2:
        forced sell   price z < -2, OI z < -2     -> should bounce UP
        forced buy    price z > +2, OI z < -2     -> should fall back
        voluntary     same price moves on OI z > +2 -> no reversion expected
    Entry at the stamp that REVEALS the bar (its close - OI is published per stamp), exits
    +15 / +30 / +60 minutes. 12bp taker round trip. Month-block t. Split 60/40 in time.

REGISTERED PREDICTIONS (before running)
    1. The mechanism shows in the signs: forced sells revert up, forced buys down, voluntary
       moves do not - the day-1 result, now on 4 years.
    2. Measured from the CLOSE (not the low), the forced-sell bounce is +10 to +25bp gross at
       15-30 minutes, i.e. roughly at or under the 12bp cost: net ~0. Expected verdict: a
       real mechanism that a taker cannot harvest; maker entry would be the only route.

    python -m backtest.cascade_redux
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

METRICS = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "metrics"
FEE = 12 / 1e4
Z = 2.0
WIN = 30 * 288                     # 30 days of 5-minute stamps
HORIZ = {15: 3, 30: 6, 60: 12}


def coin(f):
    m = pd.read_csv(f, usecols=["create_time", "sum_open_interest", "sum_open_interest_value"])
    m["t"] = pd.to_datetime(m["create_time"])
    m = m.drop_duplicates("t").set_index("t").sort_index()
    m = m[(m.sum_open_interest > 0) & (m.sum_open_interest_value > 0)]
    # a regular 5-minute grid; gaps stay gaps (no forward-filled returns across them)
    g = m.reindex(pd.date_range(m.index[0], m.index[-1], freq="5min"))
    px = g.sum_open_interest_value / g.sum_open_interest
    oi = g.sum_open_interest
    r = np.log(px).diff(); d = np.log(oi).diff()

    def z(x):
        mu = x.rolling(WIN, min_periods=WIN // 3).mean().shift(1)
        sd = x.rolling(WIN, min_periods=WIN // 3).std().shift(1)
        return (x - mu) / sd
    out = pd.DataFrame({"r": r, "rz": z(r), "dz": z(d), "px": px})
    for mins, k in HORIZ.items():
        out[f"f{mins}"] = px.shift(-k) / px - 1          # from the revealing stamp's price
    out["sym"] = f.name.split(".")[0]
    return out.dropna(subset=["rz", "dz"])


def month_t(x, t):
    s = pd.Series(np.asarray(x, float), index=t).groupby(pd.DatetimeIndex(t).to_period("M")).mean()
    return float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))) if len(s) > 3 else np.nan


def main():
    D = pd.concat([coin(f) for f in sorted(METRICS.glob("*.csv.gz"))])
    D = D[np.isfinite(D.rz) & np.isfinite(D.dz)]
    cut = D.index.to_series().quantile(0.6)
    print(f"{len(D):,} five-minute stamps, {D.sym.nunique()} coins, {D.index.min():%Y-%m} .. "
          f"{D.index.max():%Y-%m}; tune < {cut:%Y-%m-%d} <= holdout\n")
    Q = {"forced SELL (px down, OI down)": (D.rz < -Z) & (D.dz < -Z),
         "voluntary sell (px down, OI up)": (D.rz < -Z) & (D.dz > Z),
         "forced BUY (px up, OI down)": (D.rz > Z) & (D.dz < -Z),
         "voluntary buy (px up, OI up)": (D.rz > Z) & (D.dz > Z)}
    print(f"  {'quadrant':<34}{'n':>7}" + "".join(f"{'+%dm' % m:>9}" for m in HORIZ) +
          "   gross bp in the direction of REVERSION")
    for lab, m in Q.items():
        g = D[m]
        sgn = 1 if "SELL" in lab or "sell" in lab else -1          # reversion direction
        print(f"  {lab:<34}{len(g):>7}" + "".join(f"{sgn * g[f'f{h}'].mean()*1e4:>+9.1f}" for h in HORIZ))
    print("\n  TRADE: fade the forced move at the revealing stamp, taker 12bp round trip")
    for lab in ("forced SELL (px down, OI down)", "forced BUY (px up, OI down)"):
        g = D[Q[lab]]
        sgn = 1 if "SELL" in lab else -1
        for h in HORIZ:
            net = sgn * g[f"f{h}"] - FEE
            ok = net.notna()
            net, gt = net[ok], g.index[ok]
            tu = gt < cut
            print(f"    {lab[:11]:<12} +{h:<3}m n {len(net):>5}  net {net.mean()*1e4:>+7.1f}bp  "
                  f"t {month_t(net, gt):>+5.2f}  tune {net[tu].mean()*1e4:>+7.1f}  hold "
                  f"{net[~tu].mean()*1e4:>+7.1f}  win {(net > 0).mean()*100:.0f}%")
    g = D[Q["forced SELL (px down, OI down)"]]
    print("\n  forced-sell +30m net by year: " + "  ".join(
        f"{y}: {v.mean()*1e4:+.0f}bp (n{len(v)})" for y, v in
        (g["f30"] - FEE).dropna().groupby(g["f30"].dropna().index.year)))


if __name__ == "__main__":
    main()
