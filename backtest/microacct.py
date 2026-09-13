"""$5-$10 ON BITGET — the odds, and what actually maximises them.

WHAT IS BEING ASKED
    Deposit $5-10 on Bitget, accept large risk, and go for a big multiple. The
    question is not "is this sensible" - it is "given that this is the plan, what
    maximises the chance of hitting the target, and what is that chance?"

    Bitget real (not demo) lists 783 USDT perps and 742 of them accept a $5 order, so
    the universe is not the constraint. The demo's 3-contract limit is a demo
    restriction only.

THE CONSTRAINT THAT DEFINES THIS PROBLEM
    Bitget's minimum order is $5. With a 2x ATR stop of ~2.43%:

        risk per trade = $5 x 2.43% = $0.12
                       = 1.22% of a $10 account
                       = 2.43% of a $5 account

    You do not choose that. The venue does. 2.5% total exposure was measured at a
    99.9% drawdown, so a $5 account is forced to the wipeout level before any
    strategy choice is made.

THE LEVER NOBODY HAS PULLED - specific to a micro account
    Because the $5 floor binds, dollar risk per trade is $5 x stop_fraction. So a
    TIGHTER stop directly REDUCES forced risk:

        2.0 x ATR -> stop 2.43% -> $0.122 per trade -> 1.22% of $10
        1.0 x ATR -> stop 1.22% -> $0.061 per trade -> 0.61% of $10
        0.5 x ATR -> stop 0.61% -> $0.030 per trade -> 0.30% of $10

    On a NORMAL account a tighter stop is strictly worse: backtest/tightstop.py showed
    drawdown rising from 66% to 94% as the stop went 2.0x -> 1.0x, because risk per
    trade was held constant and only the noise went up. On a MINIMUM-ORDER-BOUND
    account the causality reverses - the tighter stop is what lets you risk less - and
    mean R barely moved across that range (+2.372 at 2.0x, +2.344 at 1.0x).

    Whether the lower forced risk outweighs the extra noise is the question this file
    exists to answer. It has never been tested because every prior test held risk
    fixed and swept the stop, which is the opposite of a micro account's situation.

SCORING
    Not CAGR. P(reach the target before ruin), because on $10 the account either gets
    somewhere or it dies, and an average return over paths that ended at zero is
    meaningless.

    Ruin = equity below what can margin one $5 order. Target = 5x and 10x.
    Block bootstrap (blocks of 20 trades) so losing streaks survive - an i.i.d.
    resample scatters exactly the runs that kill small accounts.

    The edge is DEFLATED 3x for hindsight before any probability is quoted. On the
    raw edge $20 showed a 66.5% chance of 5x; deflated it is 25.2%. Quoting the raw
    figure would be the fourth over-promise this project has made on capital.

REGISTERED PREDICTION (2026-09-14, before running)
    A tighter stop WINS for the micro account, and the best cell is the tightest one
    that still has a positive edge - probably 1.0x ATR. Deliberately adding risk
    ABOVE the forced floor LOWERS P(reach target), because the edge is positive and
    with a positive edge timid play maximises the chance of reaching a goal; boldness
    only helps when the edge is negative. Best realistic odds from $10 to $50: 25-40%,
    with ruin above 50%.

    python -m backtest.microacct
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
from bot.core.indicators import atr as atr_ind  # noqa: E402

FEE_BP = 12.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
BE_AT = 3.0
MIN_ORDER = 5.00            # Bitget, every coin in the tradeable set
MAX_LEV = 10.0
BLOCK, N_PATHS, MAX_TRADES = 20, 6000, 4000
HINDSIGHT = 3.0
# Coins a $10 Bitget account can actually trade: minimum order at or under $5, real
# liquidity, and enough history to measure. LINK ($11.35), BNB ($7.16), BTC ($7.68),
# SOL ($9.98) and ETH ($24.83) are all excluded by their own step size.
BOOK = ["XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "SUIUSDT",
        "LTCUSDT", "SHIBUSDT", "ARBUSDT", "NEARUSDT"]
_D: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def r_and_stop(sl_mult):
    """Pooled R (both sleeves, single unit) and the median stop fraction, at one stop
    width. Single unit because a $10 account cannot fund a 5-order pyramid: each added
    unit is another $5 order, and 5 units is $25 of notional on a $10 account."""
    Rs, Ts, sfs = [], [], []
    for c in BOOK:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        a = (atr_ind(df, 14) / df["close"]).replace([np.inf, -np.inf],
                                                    np.nan).dropna()
        if len(a):
            sfs.append(float(a.median()) * sl_mult)
        for side, trail in (("long", LONG_TRAIL), ("short", SHORT_TRAIL)):
            R, idx, _b, _d = run_uncapped(df, signals(df, side, "all"),
                                          sl_mult=sl_mult, fee_bp=FEE_BP,
                                          mode="trail_atr", trail=trail,
                                          be_at=BE_AT)
            if len(R):
                Rs.append(R); Ts.append(df["time"].iloc[idx].to_numpy())
    if not Rs:
        return None, None
    o = np.argsort(np.concatenate(Ts))
    return np.concatenate(Rs)[o], float(np.median(sfs))


def simulate(seq, stop_frac, start, risk_pct, target_mult, rng):
    """P(reach target) and P(ruin). Position size is max(MIN_ORDER, risk-target size),
    so the venue floor overrides the config upward and forced over-risk appears on its
    own rather than being assumed."""
    target = start * target_mult
    reached = ruined = 0
    n_to = []
    for _ in range(N_PATHS):
        eq, t, hit = start, 0, False
        while t < MAX_TRADES:
            i0 = int(rng.integers(0, max(len(seq) - BLOCK, 1)))
            for r in seq[i0:i0 + BLOCK]:
                want = eq * risk_pct / 100.0 / stop_frac
                notional = max(MIN_ORDER, want)
                if notional > eq * MAX_LEV:        # cannot margin the minimum order
                    eq = 0.0
                    break
                eq += float(r) * notional * stop_frac
                t += 1
                if eq <= MIN_ORDER / MAX_LEV:
                    eq = 0.0
                    break
                if eq >= target:
                    hit = True
                    break
            if hit or eq <= 0.0:
                break
        if hit:
            reached += 1; n_to.append(t)
        elif eq <= 0.0:
            ruined += 1
    return dict(p=reached / N_PATHS * 100, ruin=ruined / N_PATHS * 100,
                med=float(np.median(n_to)) if n_to else float("nan"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stake", type=float, default=10.0)
    args = ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: a TIGHTER stop wins for a micro account; adding")
    print("risk above the forced floor LOWERS P(target) because the edge is positive.")
    print("Best odds $10 -> $50: 25-40%, ruin above 50%.\n")

    rng = np.random.default_rng(20260914)
    # trades per day, to turn "median trades" into a wait
    tpd = None
    print("=" * 112)
    print(f"EDGE BY STOP WIDTH — {len(BOOK)} Bitget-tradeable coins, single unit, "
          f"BE@{BE_AT:.0f}R")
    print("=" * 112)
    print(f"{'stop':>6} {'stop %':>8} {'meanR raw':>10} {'meanR honest':>13} "
          f"{'forced risk on $10':>19} {'n':>7}")
    data = {}
    for sl in (0.5, 1.0, 1.5, 2.0, 3.0):
        seq, sf = r_and_stop(sl)
        if seq is None:
            continue
        defl = seq - (2.0 / 3.0) * seq.mean()      # cut the mean 3x, keep the tail
        data[sl] = (defl, sf, seq)
        forced = MIN_ORDER * sf / 10.0 * 100
        print(f"{sl:>6.2f} {sf*100:>7.2f}% {seq.mean():>+10.3f} "
              f"{defl.mean():>+13.3f} {forced:>18.2f}% {len(seq):>7,}", flush=True)
        if tpd is None:
            tpd = len(seq)
    print()

    for stake in (args.stake, 5.0):
        for tgt, tname in ((5.0, f"${stake*5:.0f}"), (10.0, f"${stake*10:.0f}")):
            print("=" * 112)
            print(f"FROM ${stake:.0f} TO {tname}  ({tgt:.0f}x)   "
                  f"— honest edge, {N_PATHS:,} paths per cell")
            print("=" * 112)
            print(f"{'stop':>6} {'risk asked':>11} {'risk actual':>12} "
                  f"{'P(target)':>10} {'P(ruin)':>9} {'med trades':>11}")
            best = None
            for sl, (defl, sf, _raw) in data.items():
                for risk in (0.30, 2.0, 4.0):
                    d = simulate(defl, sf, stake, risk, tgt, rng)
                    actual = max(MIN_ORDER * sf, stake * risk / 100.0) / stake * 100
                    star = ""
                    if best is None or d["p"] > best[2]["p"]:
                        best = (sl, risk, d); star = ""
                    print(f"{sl:>6.2f} {risk:>10.2f}% {actual:>11.2f}% "
                          f"{d['p']:>9.1f}% {d['ruin']:>8.1f}% "
                          f"{d['med']:>11.0f}{star}", flush=True)
            if best:
                sl, risk, d = best
                print(f"\n  BEST: stop {sl:.2f}xATR at {risk:.2f}% asked  ->  "
                      f"{d['p']:.1f}% chance of {tname}, {d['ruin']:.1f}% ruin")
            print()

    print("=" * 112)
    print("HOW TO READ THIS")
    print("=" * 112)
    print("'risk asked' is the config; 'risk actual' is what the $5 floor forces. Where")
    print("they differ, the venue is choosing your position size, not you.")
    print("\nIf the tightest stops win, the reason is arithmetic and not a market edge:")
    print("dollar risk on a floor-bound account is $5 x stop width, so halving the")
    print("stop halves what every trade costs you. The cost is a noisier exit, and the")
    print("table says whether that trade is worth taking.")
    print("\nIf adding risk above the floor LOWERS P(target), that is the classic")
    print("result for a POSITIVE edge: boldness only raises your chance of hitting a")
    print("goal when the edge is against you.")


if __name__ == "__main__":
    main()
