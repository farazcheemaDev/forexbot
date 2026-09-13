"""SHOULD A SMALL ACCOUNT TAKE PROFIT? — the survival question, not the growth one.

THE IDEA BEING TESTED (user's, 2026-09-13)
    Make the bot ADAPTIVE IN EQUITY. At $10-20 it takes profit at a fixed target to
    climb to a threshold; past $30 it behaves differently; past $50 differently
    again. The claim is that a small account needs a different rule from a large
    one.

WHY THIS IS NOT OBVIOUSLY WRONG, DESPITE THE PROFIT-CAP FINDING
    Capping winners is the single worst error this project made: it turned 11
    profitable trend families into 3, because the top 25 of 6,054 trades produced
    102.3% of all profit. So a fixed target LOWERS expected growth. That is settled.

    But expected growth is the wrong objective near an absorbing barrier. A $20
    account on Bitget dies at roughly $5-10 - it cannot place another order - and
    recovery requires trading. When the barrier is a few bad trades away, the
    objective is P(reach the target BEFORE hitting the barrier), and that is a
    different optimisation. Capping the right tail cuts VARIANCE hard in a
    fat-tailed distribution, and less variance can raise P(survive to target) even
    at a lower mean. Whether it does here is empirical.

THE CONSTRAINT NEITHER SIDE OF THE ARGUMENT HAD PRICED
    The venue forces small accounts to over-risk. A $5 minimum order against a ~2%
    stop risks $0.10 per trade no matter what the config says:

        $10 account -> 1.0% risk/trade      (7.7x the validated 0.13%)
        $20 account -> 0.5%                 (3.8x)
        $50 account -> 0.2%                 (1.5x)

    2.5% total exposure was measured at 99.9% drawdown. So a small account is pushed
    toward wipeout by arithmetic before any strategy choice is made. This simulation
    enforces that: position size is max(MIN_ORDER, risk-target size), so forced
    over-risk appears automatically rather than being assumed away.

WHAT IS SIMULATED
    Real per-trade R sequences from the validated book, resampled in BLOCKS to
    preserve loss clustering - an i.i.d. bootstrap would scatter the losing streaks
    that actually kill small accounts and would flatter every variant equally.

    Modes:
        TRAIL       uncapped trailing exit (the validated rule)
        TP@1R/2R/3R fixed target, the "bootstrap mode" being proposed
        TIERED      TP@2R until equity reaches the switch level, then TRAIL

    Scored on:
        P(reach target)   target = 5x the starting stake
        P(ruin)           equity below what can fund one minimum order
        median trades to target, and median final equity

    SINGLE UNIT, no pyramiding. At $20 a 5-unit pyramid needs 5 separate $5 orders -
    $25 of notional the account cannot fund - so modelling the validated 5-unit
    distribution here would assume away the very constraint under test.

REGISTERED PREDICTION (2026-09-13, before running)
    Profit-taking RAISES P(reach target) from $10 and $20, because forced risk is so
    high there that variance, not mean, dominates survival. It LOSES from $50 up,
    where the barrier is far enough away that the mean matters more. If so, the
    user's tiered idea is right and the switch level is roughly where the two
    curves cross. If TP loses at every starting size, the idea is wrong and the
    reason is that the cap destroys more mean than variance.

    python -m backtest.bootstrap_tier
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import run_uncapped  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.rtest import run_r  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.small_book import SHORT_TRAIL, stop_fraction  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

FEE_BP = 12.0
LONG_TRAIL = 20.0
BOOK = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
        "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
MIN_ORDER = 5.0            # Bitget/Bybit floor
MAX_LEV = 10.0
BLOCK = 20                 # bootstrap block length, in trades
N_PATHS = 4000
MAX_TRADES = 3000
_D: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def r_sequences():
    """Per-trade R for each exit rule, pooled across the book in time order, plus
    the median stop fraction (needed to turn a risk target into a notional)."""
    out = {}
    sfs = []
    for tag in ("TRAIL", "TP@1R", "TP@2R", "TP@3R"):
        Rs, Ts = [], []
        for c in BOOK:
            df = load(c)
            if df is None or len(df) < 3000:
                continue
            if tag == "TRAIL":
                for side, trail in (("long", LONG_TRAIL), ("short", SHORT_TRAIL)):
                    R, idx, _b, _d = run_uncapped(df, signals(df, side, "all"),
                                                  sl_mult=2.0, fee_bp=FEE_BP,
                                                  mode="trail_atr", trail=trail)
                    if len(R):
                        Rs.append(R); Ts.append(df["time"].iloc[idx].to_numpy())
            else:
                tp = float(tag.split("@")[1].rstrip("R"))
                for side in ("long", "short"):
                    R, idx = run_r(df, signals(df, side, "all"), 2.0, tp, FEE_BP)
                    if len(R):
                        Rs.append(R); Ts.append(df["time"].iloc[idx].to_numpy())
        if not Rs:
            continue
        o = np.argsort(np.concatenate(Ts))
        out[tag] = np.concatenate(Rs)[o]
    for c in BOOK:
        df = load(c)
        if df is not None:
            sfs.append(stop_fraction(df))
    return out, float(np.median([s for s in sfs if np.isfinite(s)]))


def simulate(seq_map, stop_frac, start, risk_pct, target_mult, mode,
             switch_at=0.0, rng=None, min_order=MIN_ORDER):
    """One mode, N_PATHS block-bootstrapped paths. Returns survival statistics.

    Position sizing is the whole point:
        want     = equity x risk_pct / stop_frac        the config's intent
        notional = max(MIN_ORDER, want)                 the venue's floor wins
        risk$    = notional x stop_frac                 so risk RISES as equity falls
    That last line is the trap a percentage-only simulation hides: a shrinking
    account does not risk a shrinking amount, it risks a rising FRACTION.
    """
    rng = rng or np.random.default_rng(20260913)
    target = start * target_mult
    reached = ruined = stuck = 0
    n_to_target, finals = [], []
    for _ in range(N_PATHS):
        eq = start
        cur_mode = mode
        seq = seq_map["TP@2R" if mode == "TIERED" else mode]
        t = 0
        hit = False
        while t < MAX_TRADES:
            # block bootstrap: draw a contiguous run so losing streaks survive
            i0 = int(rng.integers(0, max(len(seq) - BLOCK, 1)))
            for r in seq[i0:i0 + BLOCK]:
                want = eq * risk_pct / 100.0 / stop_frac
                notional = max(min_order, want)
                if notional > eq * MAX_LEV:
                    stuck += 1                  # cannot fund the minimum order
                    eq = 0.0
                    break
                eq += float(r) * notional * stop_frac
                t += 1
                if eq <= min_order / MAX_LEV:
                    eq = 0.0
                    break
                if eq >= target:
                    hit = True
                    break
                if mode == "TIERED" and cur_mode != "TRAIL" and eq >= switch_at:
                    cur_mode = "TRAIL"
                    seq = seq_map["TRAIL"]
                    break               # re-draw from the new rule's distribution
            if hit or eq <= 0.0:
                break
        finals.append(eq)
        if hit:
            reached += 1
            n_to_target.append(t)
        elif eq <= 0.0:
            ruined += 1
    return dict(p_target=reached / N_PATHS * 100, p_ruin=ruined / N_PATHS * 100,
                med_trades=float(np.median(n_to_target)) if n_to_target else float("nan"),
                med_final=float(np.median(finals)),
                forced=min_order * stop_frac / start * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=5.0, help="multiple of stake")
    args = ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: profit-taking WINS from $10-20 and LOSES from")
    print("$50 up. If so the tiered idea is right and the switch is where they "
          "cross.\n")

    seqs, sf = r_sequences()
    print(f"stop fraction (median across {len(BOOK)} coins): {sf*100:.2f}% of price")
    for k, v in seqs.items():
        print(f"  {k:<6} n={len(v):>6}  meanR {v.mean():+.4f}  "
              f"sdR {v.std(ddof=1):.3f}  maxR {v.max():>8.1f}  "
              f"win {float((v>0).mean())*100:.1f}%")
    print(f"\n{N_PATHS} block-bootstrapped paths per cell, block {BLOCK} trades, "
          f"target {args.target:.0f}x the stake")
    print(f"minimum order ${MIN_ORDER:.0f}, max leverage {MAX_LEV:.0f}x\n")

    print("=" * 112)
    print(f"{'stake':>6} {'forced risk':>12} {'mode':<10} {'P(reach '
          f'{args.target:.0f}x)':>13} {'P(ruin)':>9} {'med trades':>11} "
          f"{'med final $':>12}")
    print("=" * 112)
    for start in (10.0, 20.0, 50.0, 150.0):
        # the config asks for 0.13%/unit; the venue floor overrides it upward
        forced = MIN_ORDER * sf / start * 100
        best = None
        for mode in ("TRAIL", "TP@1R", "TP@2R", "TP@3R"):
            d = simulate(seqs, sf, start, 0.13, args.target, mode)
            if best is None or d["p_target"] > best[1]["p_target"]:
                best = (mode, d)
            print(f"{start:>6.0f} {forced:>11.2f}% {mode:<10} "
                  f"{d['p_target']:>12.1f}% {d['p_ruin']:>8.1f}% "
                  f"{d['med_trades']:>11.0f} {d['med_final']:>12,.0f}",
                  flush=True)
        d = simulate(seqs, sf, start, 0.13, args.target, "TIERED",
                     switch_at=start * 2.5)
        print(f"{start:>6.0f} {forced:>11.2f}% {'TIERED':<10} "
              f"{d['p_target']:>12.1f}% {d['p_ruin']:>8.1f}% "
              f"{d['med_trades']:>11.0f} {d['med_final']:>12,.0f}"
              f"   (TP@2R until ${start*2.5:.0f}, then TRAIL)")
        print(f"       -> best from ${start:.0f}: {best[0]} at "
              f"{best[1]['p_target']:.1f}%\n")

    # ------------------------------------------------------------------------
    # THE SAME TABLE ON AN HONEST EDGE.
    #
    # Every R above comes from a FIXED book of coins that are listed and liquid
    # TODAY, and that hindsight is worth 3.0x in CAGR (cross-checked twice). So the
    # survival probabilities above are built on an edge roughly three times the one
    # a real account would have had, and quoting them as odds would be the same
    # over-promise this project has already made three times on capital.
    #
    # Deflation used: subtract 2/3 of the mean from every R. That cuts the MEAN by
    # 3x while leaving the variance and the shape of the tail intact, which is the
    # conservative choice - the fat right tail that makes this strategy work is
    # preserved, only its average is cut.
    print("=" * 112)
    print("THE SAME QUESTION ON AN HONEST EDGE — mean R cut 3x for hindsight, "
          "tail shape kept")
    print("=" * 112)
    deflated = {k: v - (2.0 / 3.0) * v.mean() for k, v in seqs.items()}
    for k, v in deflated.items():
        print(f"  {k:<6} meanR {v.mean():+.4f} (was {seqs[k].mean():+.4f})  "
              f"sdR {v.std(ddof=1):.3f}")
    print(f"\n{'stake':>6} {'mode':<10} {'P(reach '
          f'{args.target:.0f}x)':>13} {'P(ruin)':>9} {'med trades':>11} "
          f"{'med final $':>12}")
    for start in (10.0, 20.0, 50.0, 150.0, 500.0):
        for mode in ("TRAIL", "TP@2R"):
            d = simulate(deflated, sf, start, 0.13, args.target, mode)
            print(f"{start:>6.0f} {mode:<10} {d['p_target']:>12.1f}% "
                  f"{d['p_ruin']:>8.1f}% {d['med_trades']:>11.0f} "
                  f"{d['med_final']:>12,.0f}", flush=True)
        print()
    print("These are the numbers to plan against. The panel above them is what a")
    print("backtest on today's coin list would promise.\n")

    # ------------------------------------------------------------------------
    # THE ACTUAL CAUSE OF THE RUIN NUMBERS, AND IT IS NOT THE STRATEGY.
    #
    # Every row above uses Bitget's $5 minimum order. Against a 2.43% stop that
    # forces $0.12 of risk per trade, which on a $20 account is 0.61% - nearly 5x
    # the validated 0.13%. The small account is not choosing to gamble; the venue
    # is making it gamble.
    #
    # MEXC declares no minimum order COST, so its floor is the contract step: ADA
    # $0.205, AVAX $0.733, LINK $1.135, XRP $1.343. On a book of those, a $20
    # account can size at its intended risk and the forced over-risk disappears
    # entirely. That is an adaptive answer - just adaptive in VENUE rather than in
    # exit rule.
    print("=" * 112)
    print("THE CAUSE: THE VENUE'S MINIMUM ORDER, NOT THE EXIT RULE")
    print("=" * 112)
    print("Same honest edge, same trailing exit, only the minimum order changes.")
    # label built from args.target, not hardcoded - it said "P(reach 5x)" while
    # actually reporting whatever --target was passed, which would have had me
    # quoting 2.5x results as 5x ones.
    print(f"{'stake':>6} {'venue floor':>12} {'forced risk':>12} "
          f"{f'P(reach {args.target:g}x)':>12} {'P(ruin)':>9} {'med final $':>12}")
    for label, mo in (("Bitget $5.00", 5.00),
                      ("MEXC XRP $1.34", 1.343),
                      ("MEXC ADA $0.21", 0.205)):
        for start in (10.0, 20.0, 50.0):
            d = simulate(deflated, sf, start, 0.13, args.target, "TRAIL",
                         min_order=mo)
            forced = max(mo * sf, start * 0.0013) / start * 100
            print(f"{start:>6.0f} {label:>12} {forced:>11.2f}% "
                  f"{d['p_target']:>11.1f}% {d['p_ruin']:>8.1f}% "
                  f"{d['med_final']:>12,.0f}", flush=True)
        print()
    print("If the ruin column falls sharply as the venue floor falls, then the")
    print("small-account problem was never the strategy or the exit rule - it was")
    print("trading a $20 account on a venue with a $5 minimum.\n")

    print("=" * 112)
    print("HOW TO READ THIS")
    print("=" * 112)
    print("P(reach target) is the only column that answers the question. A mode")
    print("with lower expected growth can still win here, because growth you never")
    print("collect because the account died is worth nothing.")
    print("\nIf TP beats TRAIL at $10-20 and loses at $150, the adaptive idea is")
    print("CORRECT and the crossover sets the switch level. If TP loses everywhere,")
    print("the cap destroys more mean than it saves in variance, and the answer to")
    print("small capital is capital - not a different rule.")


if __name__ == "__main__":
    main()
