"""DOES A CHEAP 4-COIN BOOK WORK? — the test that decides whether ~$100 can trade.

WHY THIS EXISTS
    backtest/venue_floor.py measured the capital floor for the validated 9-coin
    book at ~$1,500, and the binding constraint is ONE contract: ETH's smallest
    step is 0.01 ETH, about $25 of notional. Drop the expensive contracts and the
    floor collapses:

        9 coins (validated)            ~$1,500
        6 cheapest                     ~$470
        4 cheapest (ADA AVAX LINK XRP)   ~$82   on MEXC

    That is an 18x reduction from a change the strategy might not care about - it
    has no opinion about WHICH coins it trades. Might not. This file finds out,
    because assuming it would be exactly the class of error that has cost this
    project most.

WHAT COULD GO WRONG, STATED BEFORE RUNNING
    1. BREADTH. Already measured on the top-N-by-volume book:
           3 coins   +59.7%/yr  DD 49.2%
           5 coins  +118.8%/yr  DD 63.8%
           9 coins  +256.9%/yr  DD 78.0%
       Return scales hard with breadth because 8 slots sit idle at low coin
       counts. A 4-coin book should land near +80-90%/yr, roughly +5.3%/month -
       HALF the headline figure. That is the expected cost and it is not a
       failure, it is a trade: half the return for 18x less capital required.
    2. CHARACTER. The cheap contracts are cheap because their unit price is low,
       which correlates with smaller market cap and higher volatility. That could
       cut either way - more volatility means more breakouts, and also more false
       ones.
    3. CONCENTRATION. With 4 coins the book is one correlated bet. A 74.8%
       drawdown on 9 coins could be worse, not better, on 4.

REGISTERED PREDICTION (2026-09-13, before the first run)
    Cheap-4 lands between +60% and +110%/yr with drawdown between 45% and 70%,
    i.e. clearly worse than the 9-coin book on return and somewhat better on
    drawdown. If cheap-4 BEATS the 9-coin book on return I will distrust it and
    look for a bug, because that would contradict the breadth sweep.

SEPARATING TWO EFFECTS
    "Fewer coins" and "cheaper coins" are different variables. Both orderings are
    run at every size:
        cheap-first     ADA AVAX LINK XRP BNB BTC DOGE SOL ETH   (by min order)
        volume-first    BTC ETH SOL XRP BNB DOGE ADA AVAX LINK   (by liquidity)
    If cheap-4 and volume-4 land in the same place, breadth is the only thing that
    matters and the venue constraint is free. If cheap-4 is much worse, the cheap
    contracts are themselves the problem.

ONE ENGINE, ONE COMPARISON
    Every number here comes from THIS file's portfolio loop on a FIXED book. They
    are NOT comparable to the +240.1%/yr point-in-time figure, which re-picks its
    universe monthly and is a different (better) test. Quoting the two side by
    side is a mistake this project has already made once.

    python -m backtest.small_book
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
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.shortside import signals  # noqa: E402

FEE_BP = 12.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MAX_UNITS, ADD_EVERY = 5, 2.0
RISK_PER_UNIT = 0.13          # percent of equity, the validated setting

# MINIMUM ORDER VALUE IN USDT, measured 2026-09-13 by backtest/venue_floor.py from
# live ccxt market metadata. REFRESH THESE before acting on the output - they move
# with price (a step size of 0.01 ETH costs whatever ETH costs) and venues change
# them. They are a claim to verify with one real demo order, not a fact.
MIN_ORDER = {
    #          MEXC    Bitget
    "ADAUSDT":  (0.205,  5.000),
    "AVAXUSDT": (0.733,  5.000),
    "LINKUSDT": (1.135, 11.349),
    "XRPUSDT":  (1.343,  5.000),
    "BNBUSDT":  (7.181,  7.157),
    "BTCUSDT":  (7.677,  7.676),
    "DOGEUSDT": (8.355,  5.000),
    "SOLUSDT":  (9.984,  9.982),
    "ETHUSDT": (24.820, 24.825),
}
CHEAP_FIRST = ["ADAUSDT", "AVAXUSDT", "LINKUSDT", "XRPUSDT", "BNBUSDT",
               "BTCUSDT", "DOGEUSDT", "SOLUSDT", "ETHUSDT"]
VOLUME_FIRST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
                "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"]
_D: dict = {}


def load(c, days=2400):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", days)
        except Exception:
            _D[c] = None
    return _D[c]


def stop_fraction(df, atr_period=14):
    """Median stop distance as a fraction of price — 2 x ATR / close.

    This replaces the 1%-ATR ASSUMPTION that venue_floor.py had to make. It
    matters because the capital floor is linear in it: a coin with a 2% stop needs
    half the notional of a coin with a 1% stop to carry the same dollar risk, so a
    quiet coin has a HIGHER floor for the same minimum order.
    """
    from bot.core.indicators import atr as atr_ind
    a = atr_ind(df, atr_period)
    frac = (2.0 * a / df["close"]).replace([np.inf, -np.inf], np.nan).dropna()
    return float(frac.median()) if len(frac) else float("nan")


def trades_for(df, include_short):
    """The validated two-sided configuration, one coin.

    Direction is native (run_uncapped's d = -1); nothing is mirrored. Returns
    (entry_time, exit_time, R, side) so the portfolio loop can enforce slots.
    """
    t = df["time"].to_numpy()
    out = []
    R, idx, _u, held = run_pyramid(df, signals(df, "long", "all"), sl_mult=2.0,
                                   trail=LONG_TRAIL, max_units=MAX_UNITS,
                                   add_every=ADD_EVERY, fee_bp=FEE_BP)
    out += [(t[max(int(i) - int(h), 0)], t[int(i)], float(r), "L")
            for r, i, h in zip(R, idx, held)]
    if include_short:
        R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"),
                                        sl_mult=2.0, fee_bp=FEE_BP,
                                        mode="trail_atr", trail=SHORT_TRAIL)
        out += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r), "S")
                for r, i, b in zip(R, idx, bars)]
    return out


def portfolio(coins, slots, risk, include_short=True):
    tr = []
    for c in coins:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        tr += trades_for(df, include_short)
    if len(tr) < 30:
        return None
    tr.sort(key=lambda x: x[0])
    f = risk / 100.0
    eq, curve, times, opens = 1.0, [], [], []
    taken = {"L": 0, "S": 0}
    declined = 0
    ruined = False
    for a, b, r, side in tr:
        opens = [u for u in opens if u > a]
        if len(opens) >= slots:
            declined += 1
            continue
        opens.append(b)
        taken[side] += 1
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 0.01:                 # practical ruin, not 1e-9
                eq, ruined = 0.0, True
        curve.append(eq); times.append(b)
    if sum(taken.values()) < 30:
        return None
    cur = np.asarray(curve)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    return dict(L=taken["L"], S=taken["S"], declined=declined, cagr=cagr, dd=dd,
                ruined=ruined,
                pm=((1 + cagr / 100) ** (1 / 12) - 1) * 100 if cagr > -100 else -100)


def floor_for(coins, dd, venue_ix):
    """Capital needed so the WORST coin still clears its minimum order after the
    measured drawdown.

        equity_needed(coin) = min_order(coin) x stop_fraction(coin) / risk_frac
        floor               = max over coins, / (1 - drawdown)

    Divided by (1 - dd) because an account that cannot place an order cannot
    recover - the minimum is an absorbing barrier, not an inconvenience.
    """
    worst, worst_c = 0.0, None
    for c in coins:
        df = load(c)
        if df is None:
            continue
        sf = stop_fraction(df)
        mo = MIN_ORDER[c][venue_ix]
        need = mo * sf / (RISK_PER_UNIT / 100.0)
        if need > worst:
            worst, worst_c = need, c
    if dd >= 99.0 or worst == 0:
        return float("nan"), worst_c
    return worst / (1 - dd / 100.0), worst_c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", type=int, default=8)
    ap.add_argument("--risk", type=float, default=RISK_PER_UNIT)
    args = ap.parse_args()

    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: cheap-4 lands +60% to +110%/yr, DD 45-70%.")
    print("If cheap-4 BEATS the 9-coin book I will look for a bug first.\n")
    print(f"engine: fixed book, {args.slots} shared slots, {args.risk}%/unit, "
          f"long pyramid {MAX_UNITS}u trail {LONG_TRAIL:.0f}x + short 1u trail "
          f"{SHORT_TRAIL:.0f}x, fee {FEE_BP}bp")
    print("NOT comparable to the +240.1%/yr point-in-time figure - different "
          "engine, fixed universe.\n")

    print("=" * 118)
    print(f"{'ordering':<13} {'k':>2} {'book':<34} {'longs':>6} {'shorts':>7} "
          f"{'decl':>5} {'CAGR':>9} {'DD':>7} {'/month':>8} "
          f"{'floor MEXC':>11} {'floor Bitget':>13}")
    print("=" * 118)
    rows = []
    for name, order in (("cheap-first", CHEAP_FIRST),
                        ("volume-first", VOLUME_FIRST)):
        for k in (3, 4, 5, 6, 9):
            coins = order[:k]
            d = portfolio(coins, args.slots, args.risk)
            if not d:
                print(f"{name:<13} {k:>2} (no result)")
                continue
            fm, wm = floor_for(coins, d["dd"], 0)
            fb, wb = floor_for(coins, d["dd"], 1)
            rows.append((name, k, coins, d, fm, wm, fb, wb))
            short = " ".join(c.replace("USDT", "") for c in coins)
            ru = " RUIN" if d["ruined"] else ""
            print(f"{name:<13} {k:>2} {short:<34} {d['L']:>6} {d['S']:>7} "
                  f"{d['declined']:>5} {d['cagr']:>+8.1f}% {d['dd']:>6.1f}% "
                  f"{d['pm']:>+7.2f}% {fm:>10,.0f} {fb:>12,.0f}{ru}",
                  flush=True)
        print()

    if not rows:
        return
    print("=" * 118)
    print("WHAT DID THE CHEAP CONSTRAINT COST? — same k, cheap-first vs volume-first")
    print("=" * 118)
    for k in (3, 4, 5, 6, 9):
        c = next((r for r in rows if r[0] == "cheap-first" and r[1] == k), None)
        v = next((r for r in rows if r[0] == "volume-first" and r[1] == k), None)
        if not (c and v):
            continue
        print(f"  k={k}: cheap {c[3]['cagr']:+8.1f}%/yr DD {c[3]['dd']:5.1f}%  |  "
              f"volume {v[3]['cagr']:+8.1f}%/yr DD {v[3]['dd']:5.1f}%  |  "
              f"cheap costs {c[3]['cagr'] - v[3]['cagr']:+.1f}pp of CAGR, "
              f"needs ${c[4]:,.0f} vs ${v[4]:,.0f} on MEXC")

    print("\n" + "=" * 118)
    print("RANKED BY WHAT ACTUALLY MATTERS: monthly return per dollar of capital "
          "required")
    print("=" * 118)
    ok = [r for r in rows if not r[3]["ruined"] and np.isfinite(r[4]) and r[4] > 0]
    ok.sort(key=lambda r: -r[3]["pm"] / r[4] * 1000)
    for name, k, coins, d, fm, wm, fb, wb in ok[:8]:
        print(f"  {name:<13} k={k}  {d['pm']:+6.2f}%/month  floor ${fm:>7,.0f} "
              f"(MEXC, binding: {wm.replace('USDT','') if wm else '?'})  "
              f"DD {d['dd']:5.1f}%")
    print("\nThe floor column is the whole point. A configuration you cannot fund")
    print("has a return of zero, whatever the backtest says.")

    # ------------------------------------------------------------------------
    # THE HONEST NUMBERS. Everything above is a FIXED book of coins that are
    # listed and liquid TODAY, which is the hindsight universe. The premium for
    # that was measured independently at 3.03-3.05x in backtest/pit_universe.py.
    #
    # A cross-check that this is the right correction, not an excuse: the 9-coin
    # row here comes out at +719.8%/yr against the point-in-time 9-coin figure of
    # +240.1%/yr. That ratio is 3.00x - the separately measured premium, arrived at
    # from a different direction. Two independent measurements agreeing is the
    # reason to trust the divisor.
    HINDSIGHT = 3.0
    PIT_REF = 240.1
    nine = next((r for r in rows if r[1] == 9), None)
    print("\n" + "=" * 118)
    print("HONEST EXPECTATION — every row above divided by the measured "
          f"{HINDSIGHT:.1f}x hindsight premium")
    print("=" * 118)
    if nine:
        print(f"  cross-check: the 9-coin fixed book reads "
              f"{nine[3]['cagr']:+.1f}%/yr here against {PIT_REF:+.1f}%/yr "
              f"point-in-time = {nine[3]['cagr']/PIT_REF:.2f}x")
        print(f"  the premium was measured independently at 3.03-3.05x. Two "
              f"routes agreeing is why this divisor is used.\n")
    print(f"{'ordering':<13} {'k':>2} {'book':<28} {'raw /mo':>8} "
          f"{'HONEST /mo':>11} {'DD':>7} {'floor MEXC':>11} {'binding':>8}")
    for name, k, coins, d, fm, wm, fb, wb in rows:
        if d["ruined"]:
            continue
        # Divide the CAGR PERCENTAGE, not the growth multiplier. The premium was
        # measured as a ratio of percentage CAGRs (719.8 / 240.1 = 3.00), so
        # dividing (1 + cagr) instead gives +173%/yr for the 9-coin book against
        # the +240.1% it is supposed to reproduce - internally inconsistent with
        # the cross-check printed above. Caught exactly that way.
        #
        # This is a LINEAR correction anchored at the single k where both
        # measurements exist. It is an approximation, not a law.
        hc = d["cagr"] / HINDSIGHT if d["cagr"] > -100 else -100
        hpm = ((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100
        short = " ".join(c.replace("USDT", "") for c in coins)
        print(f"{name:<13} {k:>2} {short:<28} {d['pm']:>+7.2f}% "
              f"{hpm:>+10.2f}% {d['dd']:>6.1f}% {fm:>10,.0f} "
              f"{(wm or '?').replace('USDT',''):>8}")
    print("\nThe HONEST column is the one to plan against. The raw column is what")
    print("a backtest on today's coin list reports, and it is wrong by 3x for a")
    print("reason that has nothing to do with the strategy.")
    print("\nMinimum-order figures are from 2026-09-13 metadata and MUST be "
          "re-verified\nwith one real demo order before any of this is acted on.")


if __name__ == "__main__":
    main()
