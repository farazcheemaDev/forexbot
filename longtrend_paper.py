"""LONG TREND at full breadth — paper, 9 coins. The configuration that hits 10%/mo.

WHY THIS RUNS ALONGSIDE THE DEMO BOT
    longtrend_bot.py places real orders on Bitget's demo, which lists exactly three
    contracts. Three coins is not a limitation of the strategy, it is a limitation
    of the venue, and it costs most of the return:

        3 coins   +59.7%/yr   DD 49.2%   = +3.98%/month
        5 coins  +118.8%/yr   DD 63.8%   = +6.74%/month
        9 coins  +256.9%/yr   DD 78.0%   = +11.18%/month   <- this file
       14 coins  +193.2%/yr   DD 81.4%   = +9.38%/month
       20 coins  +176.0%/yr   DD 87.8%   = +8.83%/month

    The peak sits where COINS ~= SLOTS + 1. Below it capital idles; above it the
    8-slot cap binds (8% of signals declined at 9 coins, 51% at 20) and trades get
    taken in arrival order rather than by quality. So breadth beyond your slot
    count actively hurts - which is also why the 96-coin new-listing test came out
    at -28%/yr despite a positive per-trade edge.

    So: demo bot proves the EXECUTION path, this proves the STRATEGY at the breadth
    it needs. Neither alone is the answer.

WHAT IS SIMULATED AND WHAT IS NOT
    Real, live Binance 1h closes. Simulated fills at the bar close, charged 12bp
    round trip (Bitget taker). Slippage is NOT modelled, which makes this
    optimistic by an estimated 1-3bp per side on these liquid names.

    The 8-slot cap IS enforced - a signal arriving with every slot full is
    declined and counted. That count is the honest measure of whether the strategy
    is outgrowing one account.

HONEST STATUS OF THE FIGURES
    In-sample, on 2400 days of coins this project has examined all day, at a ~75%
    drawdown. Equal-weight buy-and-hold on these same coins returned ~40%/yr over
    the window, so the claim is roughly 6x buy-and-hold, not magic.

    The SHORT SLEEVE was added 2026-09-13, because until then this file ran long
    only while every quoted number came from the two-sided config - it was forward
    testing a strategy nobody intended to run. Shorts are weak standalone
    (+0.056R against the long side's +0.674R); they are here because they earn in
    the years the long book bleeds, and they only work with their own much tighter
    exit. Details at the SHORT_ENABLED constant below.

    And the MEDIAN month is -0.16% while 38% of months exceed +10%. It is not
    "up every month"; it is flat-to-down most months with rare explosive ones. Any
    read before ~30 closed trades is noise.

    python longtrend_paper.py
    python longtrend_paper.py --status
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from longtrend_bot import (ADD_EVERY_R, ATR_PERIOD, BB_PERIOD, BB_STD,  # noqa
                          MAX_POSITIONS, MAX_UNITS, PAPER_BOOK, RISK_PCT,
                          SHORT_TRAIL_MULT, SL_MULT, TRAIL_MULT, atr,
                          bb_break_long, bb_break_short, klines)

LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
STATE = LOGS / "ltp_state.json"
TRADES = LOGS / "trades_ltpaper.csv"
LOGF = LOGS / "longtrend_paper.log"

FEE_BP = 12.0

# RISK OVERRIDE. longtrend_bot runs 0.40%/unit because an aggressive demo was
# asked for explicitly. This file exists to forward-test the CONFIGURATION WE
# ACTUALLY BELIEVE, which is the point-in-time measured optimum:
#     0.10%/unit  +205.4%/yr long-only, DD 72.2%
#     0.13%/unit  +240.1%/yr with shorts, DD 74.8%, ~+10.7%/month   <- this
# Running the demo risk here would test a setting no one intends to use.
RISK_PCT = 0.13

# STARTING EQUITY set to $20 to run the small-account case for real rather than on
# paper arithmetic. At this size the EXCHANGE MINIMUM ORDER becomes the binding
# constraint, not the strategy, so it is enforced below - without that check this
# would silently trade $2 positions no venue would accept and the result would be
# a fantasy.
#
# At $20 with 0.4% risk per unit, notional = 0.4% x 20 / stop%:
#     BTC  (stop ~1.24%)  ->  $6.45   clears a $5 floor
#     DOGE (stop ~2.40%)  ->  $3.33   REJECTED, too small
# So some coins will trade and some will be skipped. That asymmetry is exactly
# what a real $20 account experiences and it is worth seeing rather than modelling.
START_EQ = 20.0
MIN_ORDER = 5.0          # Bitget/Bybit floor. MEXC/Gate are far lower (~$0.21-2)

# MAX LEVERAGE. The second constraint a small account hits, and it bites harder
# than the order minimum. At $20 with 0.4% risk and today's tight stops, one unit
# is ~$13 of notional; 9 positions x 5 units would be ~$585, or 29x. The exchange
# allows 10x, so a $20 account can hold ~$200 total and the pyramid CANNOT fully
# develop - it runs out of margin long before it runs out of signals.
#
# Without this cap the run would quietly assume unlimited margin and reproduce
# exactly the class of error that made new-listing momentum look profitable.
MAX_LEVERAGE = 10.0
POLL_S = 120

# SHORT SLEEVE, added 2026-09-13. Until now this file was LONG ONLY while the
# validated configuration - the one every quoted number comes from - includes
# shorts. So the forward test was measuring a strategy nobody intends to run:
#
#     long only          +205.4%/yr   DD 72.2%   = +9.75%/month
#     long + short       +240.1%/yr   DD 74.8%   = +10.7%/month   <- validated
#
# Three things the short sleeve does NOT share with the long sleeve, all measured,
# none of them preferences:
#   * 5xATR trail, not 20x. Longs improve monotonically out to 20x; shorts peak at
#     3-5x and turn NEGATIVE at 20x. Up-moves grind, crashes are fast, so a wide
#     trail hands the crash back before it triggers. Nineteen indicator families
#     were wrongly reported as having "no short side" because both directions were
#     tested with the long trail.
#   * ONE unit, no pyramid. A 2R-spaced ladder cannot fill inside a move that is
#     over in a few bars.
#   * NO regime filter. Gating shorts to below the 200h average LOST on every
#     metric - the filter waits until the decline is already underway.
#
# Shorts share the SAME 8 slots as longs. They must compete for them, or this
# quietly runs twice the exposure and the comparison to the backtest is void.
SHORT_ENABLED = True


def log(m: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fresh() -> dict:
    return {"equity": START_EQ, "open": {}, "last_bar": {}, "hb": {},
            "taken": 0, "declined": 0,
            "started": datetime.now(timezone.utc).isoformat()}


def load() -> dict:
    if STATE.exists():
        try:
            s = json.load(open(STATE))
            for k, v in fresh().items():
                s.setdefault(k, v)
            return s
        except Exception:
            log("state unreadable - starting fresh")
    return fresh()


def save(s: dict):
    json.dump(s, open(STATE, "w"), indent=1)


def rec_trade(row: dict):
    new = not TRADES.exists()
    with open(TRADES, "a", encoding="utf-8") as f:
        if new:
            f.write(",".join(row) + "\n")
        f.write(",".join(str(row[k]) for k in row) + "\n")


def cycle(st: dict):
    fee = FEE_BP / 1e4
    for base in PAPER_BOOK:
        df = klines(base, 300)
        if df is None or len(df) < BB_PERIOD + ATR_PERIOD + 5:
            continue
        closed = df.iloc[:-1]                      # never the forming bar
        bar = str(closed["time"].iloc[-1])
        a = float(atr(closed, ATR_PERIOD).iloc[-1])
        px = float(closed["close"].iloc[-1])
        hi = float(closed["high"].iloc[-1])
        lo = float(closed["low"].iloc[-1])
        if not np.isfinite(a) or a <= 0:
            continue
        rec = st["open"].get(base)

        if rec:
            if st["last_bar"].get(base) == bar:
                continue
            st["last_bar"][base] = bar
            rec["bars"] += 1
            rec.setdefault("units", 1)
            rec.setdefault("next_add", 1)
            rec.setdefault("side", "long")        # positions opened before shorts
            d = 1 if rec["side"] == "long" else -1
            # ONE water-mark field, read in the position's own direction: the best
            # price is the HIGH for a long and the LOW for a short. Kept as one
            # field rather than two so it cannot silently be updated the wrong way.
            rec["high_water"] = (max(rec["high_water"], hi) if d > 0
                                 else min(rec["high_water"], lo))

            # PYRAMID, matching longtrend_bot and backtest/pyramid: add a unit
            # each time price advances ADD_EVERY_R from the FIRST entry. Risk-
            # matched on the point-in-time universe this was worth +138%/yr at
            # 89% DD -> +205%/yr at 72% DD, i.e. better on BOTH axes.
            # LONGS ONLY - see the SHORT_ENABLED note at the top.
            if d > 0 and rec["units"] < MAX_UNITS:
                adv = (hi - rec["entry"]) / rec["risk"]
                used = sum(r.get("notional", 0) * r.get("units", 1)
                           for r in st["open"].values())
                room = st["equity"] * MAX_LEVERAGE - used
                if adv >= rec["next_add"] * ADD_EVERY_R and \
                        rec.get("notional", 0) > room:
                    if not rec.get("lev_warned"):
                        rec["lev_warned"] = True
                        log(f"[{base}] PYRAMID BLOCKED at unit "
                            f"{rec['units']}/{MAX_UNITS} - no margin room "
                            f"(${used:.0f} of ${st['equity']*MAX_LEVERAGE:.0f} "
                            f"used at {MAX_LEVERAGE:.0f}x)")
                elif adv >= rec["next_add"] * ADD_EVERY_R:
                    rec["units"] += 1
                    rec["next_add"] += 1
                    # the added unit's own entry, at the trigger level
                    rec.setdefault("adds", []).append(
                        rec["entry"] + (rec["units"] - 1) * ADD_EVERY_R * rec["risk"])
                    log(f"[{base}] PYRAMID unit {rec['units']}/{MAX_UNITS} "
                        f"at +{adv:.1f}R")

            # ASYMMETRIC TRAIL: 20xATR for longs, 5xATR for shorts. Measured, not
            # chosen. A short at 20x is NEGATIVE.
            tm = TRAIL_MULT if d > 0 else SHORT_TRAIL_MULT
            cand = rec["high_water"] - d * tm * a
            # a stop only ever ratchets TOWARD profit, which is up for a long and
            # down for a short
            if (cand > rec["stop"]) if d > 0 else (cand < rec["stop"]):
                rec["stop"] = cand
            breached = (lo <= rec["stop"]) if d > 0 else (hi >= rec["stop"])
            if breached:
                exit_px = rec["stop"]
                # every unit exits at the shared stop; R is summed per unit of
                # the ORIGINAL risk so it stays comparable with every other
                # number in this project.
                #
                # DIRECTION LIVES IN `d`, NOT IN A TRANSFORMED PRICE. The fee term
                # stays fee * e on the REAL entry price for both directions. An
                # earlier backtest mirrored prices to reuse the long maths and got
                # the fee sign wrong on any coin that had doubled, flattering
                # shorts 4x. See strategy_analysis/validation_protocol.md.
                entries = [rec["entry"]] + rec.get("adds", [])
                R = sum((exit_px - e) * d - fee * e for e in entries) / rec["risk"]
                st["equity"] *= (1 + R * RISK_PCT / 100.0)
                log(f"[{base}] TRAIL HIT ({rec['side']}) R={R:+.2f} "
                    f"({rec.get('units',1)} units) after {rec['bars']}b  "
                    f"equity {st['equity']:.2f}")
                rec_trade(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               symbol=base, side=rec["side"],
                               entry=f"{rec['entry']:.6f}",
                               exit=f"{exit_px:.6f}", R=f"{R:+.4f}",
                               bars=rec["bars"], equity=f"{st['equity']:.2f}"))
                st["open"].pop(base, None)
            else:
                st["open"][base] = rec
            continue

        if st["last_bar"].get(base) == bar:
            if st["hb"].get(base) != bar:
                st["hb"][base] = bar
            continue
        st["last_bar"][base] = bar
        # Mutually exclusive by construction: a close cannot be both above the
        # upper band and below the lower one.
        go_long = bb_break_long(closed)
        go_short = SHORT_ENABLED and bb_break_short(closed)
        if not (go_long or go_short):
            continue
        side = "long" if go_long else "short"
        d = 1 if go_long else -1
        if len(st["open"]) >= MAX_POSITIONS:
            st["declined"] += 1
            log(f"[{base}] {side.upper()} BREAK DECLINED - all {MAX_POSITIONS} "
                f"slots full ({st['declined']} declined so far)")
            continue
        risk = SL_MULT * a
        # EXCHANGE MINIMUM. notional = risk_dollars / stop_fraction. A real venue
        # rejects anything below MIN_ORDER, and each pyramid unit is a separate
        # order that must clear it too. Skipping here rather than silently trading
        # an impossible size is the whole point of running at $20.
        risk_usd = st["equity"] * RISK_PCT / 100.0
        notional = risk_usd / (risk / px) if px > 0 else 0.0
        used = sum(r.get("notional", 0) * r.get("units", 1)
                   for r in st["open"].values())
        if used + notional > st["equity"] * MAX_LEVERAGE:
            st["no_margin"] = st.get("no_margin", 0) + 1
            log(f"[{base}] BREAKOUT SKIPPED - no margin. ${used:.0f} of "
                f"${st['equity']*MAX_LEVERAGE:.0f} used at {MAX_LEVERAGE:.0f}x "
                f"({st['no_margin']} skipped for margin so far)")
            continue
        if notional < MIN_ORDER:
            st["too_small"] = st.get("too_small", 0) + 1
            log(f"[{base}] {side.upper()} SKIPPED - unit would be "
                f"${notional:.2f}, below the ${MIN_ORDER:.0f} minimum "
                f"(equity ${st['equity']:.2f}, stop {risk/px*100:.2f}%). "
                f"{st['too_small']} skipped so far")
            continue
        # water mark starts at the bar's extreme in the trade's own direction, and
        # the stop starts one risk unit ADVERSE - below for a long, above for a
        # short.
        st["open"][base] = dict(entry=px, risk=risk, stop=px - d * risk,
                                high_water=(hi if d > 0 else lo), bars=0,
                                units=1, next_add=1, notional=notional,
                                side=side)
        st["taken"] = st.get("taken", 0) + 1
        st[f"taken_{side}"] = st.get(f"taken_{side}", 0) + 1
        log(f"[{base}] {side.upper()} @{px:.6g} stop {px - d*risk:.6g} "
            f"trail {TRAIL_MULT if d > 0 else SHORT_TRAIL_MULT:.0f}xATR "
            f"unit ${notional:.2f} "
            f"({len(st['open'])}/{MAX_POSITIONS} slots used, trade #{st['taken']})")


def status(st: dict):
    print(f"\nLONG TREND PAPER — {len(PAPER_BOOK)} coins, {MAX_POSITIONS} slots")
    print(f"started {st.get('started','?')}")
    print(f"config: bb_break({BB_PERIOD},{BB_STD}) 1h | long trail "
          f"{TRAIL_MULT}xATR x{MAX_UNITS} units | short trail "
          f"{SHORT_TRAIL_MULT}xATR x1 unit | no take-profit | risk {RISK_PCT}%")
    print(f"\nequity {st['equity']:.2f}  ({st['equity']/START_EQ*100-100:+.2f}%)")
    print(f"entries taken {st['taken']} "
          f"({st.get('taken_long', 0)} long / {st.get('taken_short', 0)} short)"
          f"   declined for full slots "
          f"{st['declined']}   SKIPPED below ${MIN_ORDER:.0f} min "
          f"{st.get('too_small', 0)}")
    if st.get("too_small", 0) > max(st["taken"], 1):
        print("  >> the exchange minimum rejects more signals than it accepts.")
        print("     This account is too small for this config - that is the "
              "finding, not a bug.")
    print(f"open positions {len(st['open'])}/{MAX_POSITIONS}")
    for s, r in st["open"].items():
        print(f"  {s:10} {r.get('side','long'):<5} entry {r['entry']:.6g} "
              f"stop {r['stop']:.6g} {r['bars']}b")
    if TRADES.exists():
        d = pd.read_csv(TRADES)
        rs = pd.to_numeric(d["R"], errors="coerce").dropna()
        if len(rs):
            print(f"\nclosed {len(rs)}  mean R {rs.mean():+.3f}  total "
                  f"{rs.sum():+.2f}R  win {(rs>0).mean()*100:.0f}%  "
                  f"best {rs.max():+.2f}  worst {rs.min():+.2f}")
            if "side" in d.columns:
                for sd, g in d.groupby("side"):
                    gr = pd.to_numeric(g["R"], errors="coerce").dropna()
                    if len(gr):
                        print(f"    {sd:<6} n={len(gr):<4} mean R "
                              f"{gr.mean():+.3f}  total {gr.sum():+.2f}R")
            print("  (expect mostly small losses early — 38% of months carry the "
                  "return)")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    st = load()
    if args.status:
        status(st)
        return
    log("=" * 78)
    log(f"LONG TREND PAPER — {len(PAPER_BOOK)} coins, max {MAX_POSITIONS} "
        f"concurrent positions")
    log(f"  bb_break({BB_PERIOD},{BB_STD}) 1h | "
        f"{'LONG + SHORT' if SHORT_ENABLED else 'LONG ONLY'} | NO take-profit")
    log(f"    LONG  trail {TRAIL_MULT}xATR, up to {MAX_UNITS} units "
        f"(+1 every {ADD_EVERY_R}R)")
    if SHORT_ENABLED:
        log(f"    SHORT trail {SHORT_TRAIL_MULT}xATR, 1 unit, no regime filter "
            f"- asymmetric BY MEASUREMENT, a short at {TRAIL_MULT}x is negative")
    log(f"  risk {RISK_PCT}%/trade | fee {FEE_BP}bp round trip | simulated fills")
    log(f"  both sleeves share the SAME {MAX_POSITIONS} slots - shorts compete "
        f"for them, they are not extra exposure")
    log(f"  book: {', '.join(PAPER_BOOK)}")
    log(f"  expectation (point-in-time, survivorship-free, risk-matched):")
    if SHORT_ENABLED:
        log(f"    +240.1%/yr = +10.7%/month at 74.8% DD  <- the validated config")
        log(f"    long-only was +205.4%/yr = +9.75%/month at 72.2% DD")
    else:
        log(f"    +205.4%/yr = +9.75%/month at 72.2% DD with {MAX_UNITS} units")
    log(f"    the 1-unit version was +138.1%/yr at 89.3% DD - pyramiding is the difference")
    log(f"  NOTE: 85% of profit comes from <1% of trades. Flat months are normal.")
    while True:
        try:
            cycle(st)
            # HEARTBEAT, once per closed bar. Without it this log is silent until
            # something trades, and 12 quiet hours are indistinguishable from a
            # dead process - which is the exact ambiguity that got a duplicate bot
            # started on one account earlier. One line an hour makes "working and
            # quiet" readable.
            newest = max(st["last_bar"].values(), default=None)
            if newest and st["hb"].get("logged") != newest:
                st["hb"]["logged"] = newest
                log(f"alive | bar {newest} | equity {st['equity']:.2f} | "
                    f"{len(st['open'])}/{MAX_POSITIONS} slots | taken "
                    f"{st.get('taken',0)} ({st.get('taken_long',0)}L/"
                    f"{st.get('taken_short',0)}S) | declined {st['declined']} | "
                    f"too small {st.get('too_small',0)}")
            save(st)
        except KeyboardInterrupt:
            log("stopped"); save(st); return
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:200]}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
