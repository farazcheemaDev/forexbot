"""FINAL out-of-sample test — the last step of the validation framework.

Why this exists (credit to a comment from a 15-year quant):

    Walk-forward is not a clean out-of-sample estimate if YOU chose the
    walk-forward's own settings after looking at the data. Training window,
    refit frequency, exit multiples, which filters were even candidates - all
    of those were decisions I made having already seen 2024-2026 gold. The
    trades were out-of-sample; the PROCEDURE was not.

    A real CAGR number requires data that played no part in any decision.

THE FROZEN PROTOCOL. Every setting below was fixed BEFORE looking at the
holdout, and is copied from what the live bot / earlier tests already used.
Nothing here may be changed after seeing the result - if it is, this stops
being a holdout and the number becomes worthless.

    family grid ....... donch_lo + macd_trend  (what portfolio_bot trades)
    filters ........... none | er30
    exits ............. 2.0 ATR stop / 3.0 ATR target
    training window ... 8760 bars (~1 year)
    refit step ........ 2160 bars (~quarterly)
    costs ............. 10bp round trip
    metric ............ CAGR, max drawdown, MAR (=CAGR/maxDD)

THE HOLDOUT: PAXG 1h from listing (2020-08) up to the start of the 900-day
window used in every previous experiment (2024-03). Never loaded, never
plotted, never used to choose anything. It also spans gold's 2021-2022
range/drawdown regime, which the 2024-2026 sample entirely lacks.

    python -m backtest.final_oos
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import fetch  # noqa: E402
from backtest.rtest import run_r  # noqa: E402
from backtest.mcpt import (GRIDS, SL, TP, build_grid,  # noqa: E402
                           walkforward_signals)

TRAIN, STEP = 8760, 2160
FEE_BP = 10.0
USED_DAYS = 900          # the window every previous experiment used


def trade_rs(df: pd.DataFrame, grid) -> tuple[np.ndarray, pd.Series]:
    """Run the frozen walk-forward and return per-trade R plus exit times.

    SCALE-FREE R via backtest.rtest — run_backtest clamps lots to broker limits,
    which makes dollar P&L depend on price level and R = pnl/100 invalid. See
    rtest.py. (Original version of this file used that broken path.)
    """
    sig = walkforward_signals(df, grid, TRAIN, STEP)
    sig.iloc[:TRAIN] = 0                      # score out-of-sample only
    R, idx = run_r(df, sig, SL, TP, FEE_BP)
    if len(R) == 0:
        return np.array([]), pd.Series(dtype="datetime64[ns]")
    return R, df["time"].iloc[idx].reset_index(drop=True)


def stats(R: np.ndarray, yrs: float, risk_pct: float) -> dict:
    eq, curve = 1.0, [1.0]
    for r in R:
        eq *= (1 + r * risk_pct / 100.0)
        curve.append(max(eq, 1e-12))
    c = np.array(curve)
    peak = np.maximum.accumulate(c)
    dd = float(((peak - c) / peak).max() * 100)
    cagr = float((c[-1] ** (1 / yrs) - 1) * 100) if c[-1] > 0 else -100.0
    return dict(final=float(c[-1]), cagr=cagr, dd=dd,
                mar=(cagr / dd if dd > 0 else float("inf")))


def report(name: str, df: pd.DataFrame, grid) -> dict | None:
    R, ts = trade_rs(df, grid)
    if len(R) < 30:
        print(f"\n{name}: only {len(R)} trades — not enough to judge")
        return None
    yrs = float(pd.Timedelta(pd.Timestamp(ts.iloc[-1])
                             - pd.Timestamp(ts.iloc[0])).days) / 365.25
    buyhold = (df["close"].iloc[-1] / df["close"].iloc[TRAIN] - 1) * 100

    print(f"\n{'='*72}\n{name}\n{'='*72}")
    print(f"  OOS span      {pd.Timestamp(ts.iloc[0]).date()} -> "
          f"{pd.Timestamp(ts.iloc[-1]).date()}  ({yrs:.2f} years)")
    print(f"  gold itself   {buyhold:+.1f}% over the same span (buy & hold)")
    print(f"  trades        {len(R)}  ({len(R)/(yrs*12):.1f}/month)")
    print(f"  win rate      {(R > 0).mean()*100:.1f}%")
    print(f"  mean R        {R.mean():+.4f}   profit factor "
          f"{R[R>0].sum()/abs(R[R<0].sum()):.3f}" if (R < 0).any() else "")
    print(f"\n  {'risk%':>6} {'final':>8} {'CAGR%':>8} {'maxDD%':>8} {'MAR':>6}")
    out = {}
    for rp in (0.5, 1.0, 2.0, 3.0):
        s = stats(R, yrs, rp)
        out[rp] = s
        print(f"  {rp:>6.1f} {s['final']:>7.2f}x {s['cagr']:>8.1f} "
              f"{s['dd']:>8.1f} {s['mar']:>6.2f}")

    # per calendar year — does the edge survive outside a bull run?
    ser = pd.Series(R, index=pd.to_datetime(ts.to_numpy()))
    print(f"\n  {'year':>6} {'trades':>7} {'meanR':>8} {'sumR':>8}   gold that year")
    for y, g in ser.groupby(ser.index.year):
        gy = df[df.time.dt.year == y]["close"]
        gr = (gy.iloc[-1] / gy.iloc[0] - 1) * 100 if len(gy) > 1 else float("nan")
        print(f"  {y:>6} {len(g):>7} {g.mean():>+8.3f} {g.sum():>+8.1f}   {gr:>+7.1f}%")
    return out


def main():
    full = fetch("PAXGUSDT", "1h", 2400)
    cut = full.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
    virgin = full[full.time < cut].reset_index(drop=True)
    used = full[full.time >= cut].reset_index(drop=True)
    grid = build_grid(GRIDS["forex"])

    print(f"PAXG 1h: {len(full)} bars total")
    print(f"  HOLDOUT (never touched): {len(virgin)} bars "
          f"{virgin.time.iloc[0].date()} -> {virgin.time.iloc[-1].date()}")
    print(f"  previously used:         {len(used)} bars "
          f"{used.time.iloc[0].date()} -> {used.time.iloc[-1].date()}")
    print(f"  frozen protocol: grid={len(grid)} cfgs, train={TRAIN}, step={STEP}, "
          f"exits {SL}/{TP} ATR, {FEE_BP}bp")

    v = report("VIRGIN HOLDOUT — first and only look", virgin, grid)
    u = report("PREVIOUSLY USED WINDOW (for comparison — contaminated)", used, grid)

    if v and u:
        print(f"\n{'='*72}\nVERDICT\n{'='*72}")
        print(f"  {'risk%':>6} {'holdout CAGR':>13} {'used CAGR':>11} "
              f"{'holdout MAR':>12} {'used MAR':>9}")
        for rp in (1.0, 2.0, 3.0):
            print(f"  {rp:>6.1f} {v[rp]['cagr']:>12.1f}% {u[rp]['cagr']:>10.1f}% "
                  f"{v[rp]['mar']:>12.2f} {u[rp]['mar']:>9.2f}")
        m = v[1.0]["mar"]
        print(f"\n  Holdout MAR at 1% risk: {m:.2f}")
        print("  The 2:1 rule of thumb says a real strategy tops out near MAR 2.")
        print("  ->", "consistent with a real edge" if 0.3 <= m <= 2.5 else
              ("still above the plausible ceiling - treat with suspicion" if m > 2.5
               else "edge does not survive on unseen data"))


if __name__ == "__main__":
    main()
