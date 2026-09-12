"""LEVERAGED LONG TREND — the chosen strategy, across timeframes.

WHAT THIS IS, NAMED HONESTLY
    Long-only breakout/momentum with an uncapped trailing stop. Today's evidence
    says the long side of these families earns +0.38..+0.61R on 2020-24 data while
    the short side earns ~0 (five of eleven families NEGATIVE). So this is a
    LEVERAGED DIRECTIONAL BET ON CRYPTO RISING with disciplined stops - not a
    market inefficiency. It produces large returns while the asset class rises and
    will bleed through an extended bear market. That is the deal being accepted.

THE OBJECTIVE IS CUMULATIVE, NOT MONTHLY-GUARANTEED
    No strategy delivers >10% every month. At 0.5%/trade the 1h version gave 38%
    of months above +10% with a median month of +1.5%, compounding to +174%/yr -
    which IS >10%/month on average, with a ~79% drawdown en route. So the metric
    ranked here is CAGR and P(month > +10%), not mean R.

WHY LOWER TIMEFRAMES ARE TESTED, AND THE TRAP IN THEM
    Faster bars mean more trades and therefore faster demo feedback, which is a
    legitimate engineering goal. But fees scale with trade count, and this project
    has already measured that wall repeatedly: a 6-hour reversal sleeve paid
    129%/yr in fees. Worse, "8xATR" is not one thing across timeframes - ATR(5m)
    is a fraction of ATR(1h), so the same multiple is a far TIGHTER trail in price
    terms on fast bars, which means more stop-outs and more fees. So the trail
    multiple is swept per timeframe rather than carried across, and fee drag is
    printed as its own column in every row.

COSTS
    12bp round trip (Bitget taker 6bp/side). The earlier convex.py runs used 10bp;
    12 is the honest number and is used here.

    python -m backtest.longtrend
    python -m backtest.longtrend --tf 5m
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import describe, run_uncapped  # noqa: E402
from backtest.mass_search import fetch, gen_signals  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
         "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
DEMO_COINS = ["BTCUSDT", "ETHUSDT", "XRPUSDT"]      # what Bitget's demo offers

TF_DAYS = {"1h": 2400, "15m": 1000, "5m": 540, "1m": 180}
# trail widths worth trying per timeframe. Fast bars need WIDER multiples because
# ATR shrinks with the bar - see docstring.
TF_TRAILS = {"1h": (3.0, 5.0, 8.0, 12.0),
             "15m": (5.0, 8.0, 12.0, 20.0),
             "5m": (8.0, 12.0, 20.0, 30.0),
             "1m": (12.0, 20.0, 30.0, 50.0)}
# Parameter shapes per backtest.mass_search.SPACE — donchian takes (period,) only.
# The guard in main() rejects a wrong shape or an unknown family before any
# compute is spent.
FAMS = [("donchian", (20,)), ("donchian", (55,)),
        ("bb_break", (30, 1.5)), ("roc_mom", (24, 2.0)),
        ("rsi_mom", (7, 40, 60))]
RISKS = (0.25, 0.5, 1.0)


def long_only(sig: pd.Series) -> pd.Series:
    """Drop every short signal. Shorts earned ~0R in every family measured."""
    return sig.where(sig != Action.SELL, Action.HOLD)


_DATA: dict = {}


def load(c: str, tf: str, days: int):
    """Cache parsed frames in memory.

    pool() is called ~180 times per timeframe (60 cells, plus two extra passes per
    cell for the zero-fee fee measurement). Calling fetch() inside it re-parsed
    9 JSON files of ~155k bars from disk EVERY time, which is what made the 5m run
    appear to hang - the work was disk and JSON parsing, not simulation.
    """
    k = (c, tf, days)
    if k not in _DATA:
        try:
            _DATA[k] = fetch(c, tf, days)
        except Exception:
            _DATA[k] = None
    return _DATA[k]


def pool(coins, tf, fam, p, trail, days, risk, fee_bp=FEE_BP):
    Rs, Ts = [], []
    for c in coins:
        df = load(c, tf, days)
        if df is None or len(df) < 2000:
            continue
        sig = gen_signals(df, fam, p)
        if sig is None:
            continue
        R, idx, _b, _d = run_uncapped(df, long_only(sig), sl_mult=2.0,
                                      fee_bp=fee_bp, mode="trail_atr",
                                      trail=trail)
        if len(R):
            Rs.append(R); Ts.append(df["time"].iloc[idx])
    if not Rs:
        return None
    o = np.argsort(np.concatenate([t.values for t in Ts]))
    R = np.concatenate(Rs)[o]
    T = pd.Series(np.concatenate([t.values for t in Ts])[o])
    d = describe(R, T, risk)
    if d:
        d["trades_per_day"] = len(R) / max(
            (T.iloc[-1] - T.iloc[0]).total_seconds() / 86400, 1e-9)
    return d


def fee_cost_r(coins, tf, fam, p, trail, days, fee_bp=FEE_BP) -> float:
    """Fee cost per trade IN R, measured by differencing a zero-fee run.

    The first version of this tried to derive a "share of gross" arithmetically
    and produced 243%-2207% - nonsense, because fee_bp/1e4 is a fraction of PRICE
    while R is a multiple of the 2xATR stop distance. The conversion is
    fee * price / (2 * ATR), which varies per trade and is not recoverable from
    the pooled R array. Differencing two runs gives it exactly and cannot be
    unit-confused. This is the number that decides whether a timeframe is viable,
    so it is worth the second pass.
    """
    a = pool(coins, tf, fam, p, trail, days, 1.0, fee_bp=fee_bp)
    b = pool(coins, tf, fam, p, trail, days, 1.0, fee_bp=0.0)
    if not (a and b):
        return float("nan")
    return b["mean"] - a["mean"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="all")
    ap.add_argument("--demo-only", action="store_true",
                    help="restrict to the 3 coins Bitget's demo actually offers")
    args = ap.parse_args()

    tfs = list(TF_DAYS) if args.tf == "all" else [args.tf]
    coins = DEMO_COINS if args.demo_only else COINS

    # FAIL LOUDLY on a bad family name. gen_signals returns an all-HOLD series for
    # an unknown family rather than raising, so a typo ("donch" for "donchian")
    # silently produces no trades while still costing two pool calls per cell on
    # the fee measurement. That typo sat in convex.py for a whole run, narrowing it
    # from 7 families to 3 without a single warning.
    from backtest.mass_search import SPACE
    probe = load(coins[0], "1h", 900)
    bad = []
    for fam, p in FAMS:
        if fam not in SPACE:
            bad.append(f"{fam} (not in SPACE: {sorted(SPACE)})")
            continue
        try:
            s = gen_signals(probe, fam, p) if probe is not None else None
        except Exception as e:
            bad.append(f"{fam}{p} raised {type(e).__name__}: {e} "
                       f"(expected shape like {SPACE[fam][0]})")
            continue
        if s is None or int((s != Action.HOLD).sum()) == 0:
            bad.append(f"{fam}{p} produced ZERO signals")
    if bad:
        raise SystemExit("invalid family config:\n  " + "\n  ".join(bad))
    print(f"LEVERAGED LONG TREND   {len(coins)} coins   fee {FEE_BP}bp round trip")
    print("  LONG ONLY (shorts earned ~0R in every family measured today)")
    print("  uncapped trailing stop, no profit target")
    print("  ranked by CAGR and P(month > +10%), NOT by mean R\n")

    best = []
    for tf in tfs:
        days = TF_DAYS[tf]
        print("=" * 122)
        print(f"TIMEFRAME {tf}   ({days}d of history)")
        print("=" * 122)
        print(f"{'family':<16} {'trail':>6} {'risk':>5} {'n':>7} {'trd/day':>8} "
              f"{'meanR':>8} {'feeR':>7} {'fee%gross':>9} {'CAGR':>9} {'DD':>7} "
              f"{'MAR':>6} {'medmo':>7} {'mo>10%':>7}")
        for fam, p in FAMS:
            for tr in TF_TRAILS[tf]:
                fr = fee_cost_r(coins, tf, fam, p, tr, days)
                for rk in RISKS:
                    d = pool(coins, tf, fam, p, tr, days, rk)
                    if not d:
                        continue
                    ru = " RUIN" if d["ruined"] else ""
                    # gross mean R = net + fee; the share the fee takes of it
                    gross = d["mean"] + fr
                    share = fr / abs(gross) if abs(gross) > 1e-9 else float("nan")
                    print(f"{fam+str(p):<16} {tr:>5.0f}x {rk:>4.2f}% {d['n']:>7} "
                          f"{d['trades_per_day']:>8.2f} {d['mean']:>+8.3f} "
                          f"{fr:>7.3f} {share:>9.1%} "
                          f"{d['cagr']:>+8.1f}% {d['dd']:>6.1f}% {d['mar']:>+6.2f} "
                          f"{d['mo_med']:>+6.2f}% {d['mo_over10']:>6.1f}%{ru}",
                          flush=True)
                    if not d["ruined"] and d["dd"] < 85:
                        best.append((d["cagr"], tf, fam, str(p), tr, rk, d))
        print()

    if not best:
        print("nothing survived with DD < 85% and no ruin")
        return
    print("=" * 122)
    print("RANKED BY CAGR, among runs that did NOT wipe out and kept DD < 85%")
    print("=" * 122)
    best.sort(reverse=True)
    for cg, tf, fam, p, tr, rk, d in best[:15]:
        print(f"{tf:>4} {fam+p:<16} trail {tr:>4.0f}x risk {rk:>4.2f}% -> "
              f"CAGR {cg:>+8.1f}%  DD {d['dd']:>5.1f}%  MAR {d['mar']:>+5.2f}  "
              f"median mo {d['mo_med']:>+6.2f}%  mo>10% {d['mo_over10']:>5.1f}%  "
              f"{d['trades_per_day']:>5.2f} trd/day")
    print(f"\nsearched {len(best)} surviving cells — a best-of-{len(best)} table, "
          f"so the timeframe\nPATTERN matters more than the top row. Anything "
          f"picked here needs the virgin-coin\ngate (backtest/convex_wide.py) "
          f"before it is believed.")
    print("\nfeeR is the cost per trade in R, measured by differencing a zero-fee "
          "run.\nfee%gross is what share of the gross edge that consumes. Watch it "
          "climb as the\ntimeframe drops — that is the wall that killed every fast "
          "strategy in this project.\nIf fee%gross approaches 100% the timeframe is "
          "unusable no matter how good the signal.")


if __name__ == "__main__":
    main()
