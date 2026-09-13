"""FAST BARS FOR A MICRO ACCOUNT — why the old "5m is dead" verdict may not apply.

THE OLD VERDICT AND ITS SCOPE
    1m, 5m and 15m crypto were tested and killed on COST. The metric that killed them:

        fee toll in R = fee_fraction / stop_fraction

    A faster bar has a smaller ATR, so a 2xATR stop is a smaller percentage move, so
    the same 12bp round trip eats a bigger share of every trade. At 1h the toll is
    ~0.048R; each step down roughly doubles it.

    That verdict was measured on a NORMALLY SIZED account, where the fee toll is the
    only thing the timeframe changes.

WHY A $10 ACCOUNT IS A DIFFERENT PROBLEM
    Bitget's $5 minimum order means dollar risk per trade is $5 x stop_fraction - the
    account does not choose it. So the timeframe sets the forced risk:

        1h   stop ~2.5%  -> $0.126 per trade -> 1.26% of $10
        15m  stop ~1.2%  -> $0.060           -> 0.60%
        5m   stop ~0.7%  -> $0.035           -> 0.35%
        1m   stop ~0.3%  -> $0.015           -> 0.15%

    Forced over-risk is the single thing killing the micro account - 70% of paths die -
    and NO other lever touched it. A faster bar cuts it by 2-8x. That is a real force
    pulling the opposite way from the fee toll, and the two have never been weighed
    against each other because the earlier test had no reason to.

    Second effect, also in favour: far more trades per day, which matters when the
    objective is reaching a multiple inside a short horizon rather than compounding
    for years.

THE COMPARISON MUST BE ON ONE WINDOW
    1m data is expensive to fetch, so the temptation is to test 1h over six years and
    1m over four months. That is not a comparison - it is two different markets. Every
    timeframe here runs over the SAME recent window, and 1h over its full history is
    printed separately for context only.

REGISTERED PREDICTION (2026-09-14, before running)
    15m is the interesting one: toll ~0.10R against 1h's 0.048R, but forced risk
    halved. I expect 15m to roughly match 1h on P(reach $50) and to have clearly lower
    ruin, which for this objective is a win. 5m I expect to be marginal and 1m dead -
    a 0.40R toll cannot be paid by an edge whose honest mean is +0.076R at 1h.

    If 1m or 5m comes out AHEAD, I will check the fee model before believing it,
    because a toll that size dominating nothing would mean the edge per trade grew
    faster than the cost, and that is not what the earlier timeframe work found in the
    other direction.

    python -m backtest.fastbars_micro
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import run_uncapped  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.microacct import simulate  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
SL_MULT, BE_AT = 2.0, 3.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MIN_ORDER = 5.00
HINDSIGHT = 3.0
# Six of the Bitget $5-tradeable set. Fewer than ten because 1m data is ~170,000 bars
# per coin per 120 days and the point is the timeframe, not the breadth.
BOOK = ["XRPUSDT", "ADAUSDT", "DOGEUSDT", "DOTUSDT", "AVAXUSDT", "LTCUSDT"]
WINDOW_DAYS = 120          # the common window every timeframe is measured on
_D: dict = {}


def load(sym, interval, days):
    k = (sym, interval, days)
    if k not in _D:
        try:
            _D[k] = fetch(sym, interval, days)
        except Exception as e:
            print(f"   ({sym} {interval} {days}d failed: {str(e)[:60]})", flush=True)
            _D[k] = None
    return _D[k]


def measure(interval, days, clip_days=None):
    """Mean R, stop fraction and trade rate for one timeframe.

    clip_days trims every series to the same recent window so timeframes are compared
    on one market rather than on whatever history each happens to have.
    """
    Rs, Ts, sfs = [], [], []
    for c in BOOK:
        df = load(c, interval, days)
        if df is None or len(df) < 500:
            continue
        if clip_days:
            cut = df["time"].iloc[-1] - pd.Timedelta(days=clip_days)
            df = df[df["time"] >= cut].reset_index(drop=True)
            if len(df) < 500:
                continue
        a = (atr_ind(df, 14) / df["close"]).replace([np.inf, -np.inf],
                                                    np.nan).dropna()
        if len(a):
            sfs.append(float(a.median()) * SL_MULT)
        for side, trail in (("long", LONG_TRAIL), ("short", SHORT_TRAIL)):
            sig = signals(df, side, "all")
            if int((sig != Action.HOLD).sum()) == 0:
                continue
            R, idx, _b, _d = run_uncapped(df, sig, sl_mult=SL_MULT, fee_bp=FEE_BP,
                                          mode="trail_atr", trail=trail, be_at=BE_AT)
            if len(R):
                Rs.append(R); Ts.append(df["time"].iloc[idx].to_numpy())
    if not Rs or not sfs:
        return None
    o = np.argsort(np.concatenate(Ts))
    R = np.concatenate(Rs)[o]
    T = pd.DatetimeIndex(np.concatenate(Ts)[o])
    days_span = max((T[-1] - T[0]).days, 1)
    sf = float(np.median(sfs))
    return dict(R=R, sf=sf, tpd=len(R) / days_span, n=len(R),
                toll=(FEE_BP / 1e4) / sf, forced=MIN_ORDER * sf / 10.0 * 100,
                span=days_span)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=WINDOW_DAYS)
    args = ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: 15m roughly matches 1h on P($50) with clearly")
    print("lower ruin; 5m marginal; 1m dead. If 1m or 5m WINS I check the fee model")
    print("first.\n")

    print(f"fetching — every timeframe clipped to the same {args.days}-day window "
          f"({len(BOOK)} coins)")
    specs = [("1h", 400), ("15m", 200), ("5m", 150), ("1m", 130)]
    res = {}
    for iv, dl in specs:
        d = measure(iv, dl, clip_days=args.days)
        if d:
            res[iv] = d
            print(f"   {iv:>4}: {d['n']:>7,} trades over {d['span']}d", flush=True)
        else:
            print(f"   {iv:>4}: no data")
    if "1h" not in res:
        print("no 1h control — aborting")
        return

    print("\n" + "=" * 112)
    print(f"THE COST/RISK TRADE-OFF — same {args.days} days, same coins, same rules")
    print("=" * 112)
    print(f"{'bars':>5} {'stop %':>8} {'fee toll R':>11} {'forced risk $10':>16} "
          f"{'trades/day':>11} {'meanR':>8} {'honest':>8} {'win%':>6}")
    for iv in ("1h", "15m", "5m", "1m"):
        if iv not in res:
            continue
        d = res[iv]
        R = d["R"]
        hon = R.mean() / HINDSIGHT
        print(f"{iv:>5} {d['sf']*100:>7.2f}% {d['toll']:>11.3f} "
              f"{d['forced']:>15.2f}% {d['tpd']:>11.1f} {R.mean():>+8.3f} "
              f"{hon:>+8.3f} {float((R>0).mean())*100:>6.1f}", flush=True)

    print("\n" + "=" * 112)
    print("WHAT IT MEANS FOR $10 -> $50 (5x), risk 4% asked, Bitget $5 floor")
    print("=" * 112)
    print(f"{'bars':>5} {'P($50)':>8} {'P(ruin)':>9} {'med trades':>11} "
          f"{'elapsed':>9}  note")
    rng = np.random.default_rng(20260914)
    rows = []
    for iv in ("1h", "15m", "5m", "1m"):
        if iv not in res:
            continue
        d = res[iv]
        defl = d["R"] - (2.0 / 3.0) * d["R"].mean()
        s = simulate(defl, d["sf"], 10.0, 4.0, 5.0, rng)
        elapsed = s["med"] / d["tpd"] if d["tpd"] and np.isfinite(s["med"]) \
            else float("nan")
        note = ""
        if defl.mean() <= 0:
            note = "NEGATIVE edge after fees — dead"
        rows.append((iv, s, elapsed, defl.mean()))
        print(f"{iv:>5} {s['p']:>7.1f}% {s['ruin']:>8.1f}% {s['med']:>11.0f} "
              f"{elapsed:>8.0f}d  {note}", flush=True)

    print("\n" + "=" * 112)
    print("VERDICT")
    print("=" * 112)
    base = next((r for r in rows if r[0] == "1h"), None)
    if not base:
        return
    print(f"  1h control on this window: {base[1]['p']:.1f}% chance of $50, "
          f"{base[1]['ruin']:.1f}% ruin, ~{base[2]:.0f} days")
    better = [r for r in rows if r[0] != "1h" and r[3] > 0
              and (r[1]["p"] > base[1]["p"] or r[1]["ruin"] < base[1]["ruin"] - 3)]
    if not better:
        print("\n  No faster timeframe beat 1h on either the chance or the ruin rate.")
        print("  The halved forced risk did not pay for the doubled fee toll, which")
        print("  means the old '5m is dead' verdict holds even under this different")
        print("  lens - and the lens was worth checking, because the mechanism that")
        print("  would have made it wrong is real.")
    else:
        for iv, s, el, m in better:
            print(f"  {iv:>4}: {s['p']:.1f}% chance ({s['p']-base[1]['p']:+.1f}), "
                  f"{s['ruin']:.1f}% ruin ({s['ruin']-base[1]['ruin']:+.1f}), "
                  f"~{el:.0f} days, honest meanR {m:+.4f}")
        print("\n  Before acting on this: the fee is 12bp ROUND TRIP and no slippage")
        print("  is modelled. On a fast timeframe slippage is a larger share of the")
        print("  move than on 1h, so a marginal win here is probably not a real one.")
    print(f"\n  NOTE: this window is {args.days} days, not the 6.5 years the 1h book")
    print("  was validated on. It is a fair comparison BETWEEN timeframes and a poor")
    print("  estimate of any of them in absolute terms.")


if __name__ == "__main__":
    main()
