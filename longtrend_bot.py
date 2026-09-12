"""LEVERAGED LONG TREND — live on the Bitget DEMO.

WHAT THIS IS, NAMED HONESTLY
    Long-only breakout with an UNCAPPED trailing stop. Today's measurements say
    the long side of these families earns +0.38..+0.61R on 2020-24 data while the
    short side earns ~0 (five of eleven families NEGATIVE). So this is a LEVERAGED
    DIRECTIONAL BET ON CRYPTO RISING with disciplined stops - not a market
    inefficiency. It makes money while the asset class rises and will bleed
    through an extended bear market. That is the accepted deal, not a hidden flaw.

CONFIG AND WHY
    bb_break(30, 1.5), 1h, trail 8xATR, 0.5% risk/trade.
    Measured on 9 coins over 2020-2026 at 12bp round-trip taker:
        trail  8x @ 0.5%  ->  +128%/yr, DD 82%, median month +2.52%, 41.8% of
                              months above +10%
        trail 12x @ 0.5%  ->  +231%/yr, DD 80%, median month -5.05%, 36.7% above
    8x is chosen over the higher-CAGR 12x deliberately: the objective is cumulative
    month-on-month growth, and 12x LOSES money in the median month - all its return
    arrives in a few explosive months. 8x has a positive median month and more
    months above +10%.

WHY 1h AND NOT 1m/5m
    Fee drag rises monotonically with trade frequency, measured on identical
    signals:
        trail  3x  18,409 trades (7.7/day)  CAGR  -50.8%
        trail  5x  10,355 trades (4.3/day)  CAGR   -7.5%
        trail  8x   6,937 trades (2.9/day)  CAGR  +81.1%
        trail 12x   5,207 trades (2.2/day)  CAGR +177.6%
    Every increase in trading rate made it worse. Faster bars give faster demo
    feedback but pay for it in fees; backtest/longtrend.py measures the exact cost
    per timeframe.

EXECUTION
    TAKER entries. maker_probe.py measured a 53% fill rate on resting limits
    against the 57% the edge required, so post-only is not dependable here and the
    backtest charged taker rates.

    SIGNALS come from Binance public 1h klines, EXECUTION from Bitget demo. Verified
    2026-09-12: SBTC/SETH/SXRP track their real counterparts within 8bp, so signals
    transfer. Using the demo's own thin candles would not match the backtest.

    STOPS, two layers, deliberately:
      1. A real exchange stop-loss at entry - 2xATR, placed with the order. This is
         the DISASTER BACKSTOP and survives this process dying.
      2. The 8xATR trail, managed in here, exiting at market when breached. The
         trail is the actual strategy exit.
    An internally-managed trail alone would leave the position naked if the bot
    stopped; an exchange trailing stop alone would put the strategy's core logic
    inside a vendor feature whose fill behaviour we have not measured. Hence both.

    CAUSALITY: signals and ATR come from the last CLOSED bar only. The ATR used to
    size a trade is from the bar BEFORE entry. Reading the entry bar's own ATR was
    the look-ahead bug that once inflated MAR to 35.

    python longtrend_bot.py                # live on Bitget demo
    python longtrend_bot.py --dry-run      # decide and log, place nothing
    python longtrend_bot.py --status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
STATE = LOGS / "longtrend_state.json"
TRADES = LOGS / "trades_longtrend.csv"
LOGF = LOGS / "longtrend.log"

# --- DEMO vs LIVE ------------------------------------------------------------
# ALLOW_REAL is a HARD GATE. While it is False this file cannot place an order
# against real funds no matter what --mode is passed. Flipping it is a deliberate,
# human act; nothing in the code path sets it.
#
# The demo venue lists only 3 contracts (SBTC/SETH/SXRP), which caps the strategy
# at ~4%/month. Live Bitget lists all 9 of the book (verified 2026-09-12, every one
# with a $5 minimum order), which is the configuration measured at ~5.3%/month on a
# point-in-time, survivorship-free universe. Breadth is the only difference.
ALLOW_REAL = False

DEMO = dict(product="SUSDT-FUTURES", margin_coin="SUSDT")
LIVE = dict(product="USDT-FUTURES", margin_coin="USDT")
PRODUCT_TYPE, MARGIN_COIN = DEMO["product"], DEMO["margin_coin"]
LEVERAGE, MARGIN_MODE = 10, "isolated"

# --- strategy, frozen ------------------------------------------------------
TF = "1h"
BB_PERIOD, BB_STD = 30, 1.5
ATR_PERIOD = 14
SL_MULT = 2.0            # initial stop, and the unit of R
# CHANGED 2026-09-12 from 8.0 to 12.0, after measuring the strategy on the THREE
# coins this venue actually offers rather than the nine the backtest used. The
# original 8x choice came from 9-coin median-month data and did not transfer:
#
#   9 coins  trail  8x  +168.8%/yr  DD 71.8%  mo>10% 35.4%
#   3 coins  trail  8x   +38.6%/yr  DD 53.8%  mo>10% 20.3%   <- the real book
#   3 coins  trail 12x   +59.7%/yr  DD 49.2%  mo>10% 24.1%   <- dominates on ALL
#
# On 3 coins, 12x gives more return AND less drawdown AND more big months, so this
# is not a return-for-risk trade. Diversification across 9 names was doing most of
# the work in the headline figure; with 3 names expect ~60%/yr, not ~128%.
# WIDENED 12.0 -> 20.0 on 2026-09-12 after sweeping the trail beyond 12x for the
# first time. Same 2xATR stop, same risk, 9 coins, 2400d:
#     trail 12x  +210.8%/yr  DD 81.8%  MAR 2.58  win 17.9%
#     trail 20x  +324.5%/yr  DD 83.4%  MAR 3.89  win 13.2%
# +54% more return for 1.6pp more drawdown. The cost is a lower win rate, which is
# the unavoidable trade: R is measured against the stop, so letting winners run
# further means fewer but larger wins.
#
# The full frontier (stop x trail), for whoever tunes this next:
#     stop 1x  -> 98% DD, unusable at any trail
#     stop 2x  -> ~83% DD   <- here
#     stop 4x  -> ~58% DD, +135%/yr
#     stop 6x  -> ~39% DD,  +84%/yr, win rate 28-35% (the max achievable)
# THE STOP IS THE DRAWDOWN DIAL. The win rate is not a free parameter - maximising
# it (34.7% at stop 6x / trail 8x) costs 87% of the return (+43% vs +324%).
TRAIL_MULT = 20.0        # uncapped trail; NO take-profit anywhere
# --- PYRAMIDING (added 2026-09-12) ------------------------------------------
# The engine took ONE unit per signal for this whole project and it was never
# questioned. Risk-matched on the point-in-time universe it was the largest single
# lever found:
#     1 unit  @0.50%  ->  +138.1%/yr  DD 89.3%  +7.50%/month
#     3 units @0.167% ->  +186.1%/yr  DD 79.2%  +9.15%/month
#     5 units @0.10%  ->  +205.4%/yr  DD 72.2%  +9.75%/month
# More return AND less drawdown at identical total risk - because the added units
# are funded by open profit, so size grows only after price has confirmed, while
# the 87% of trades that fail still lose one unit.
MAX_UNITS = 5            # units per position, including the initial entry (LONGS only)

# SHORT SLEEVE. Point-in-time, survivorship-free, sharing the same slots:
#     long only     +205.4%/yr  DD 72.2%  MAR 2.84  +9.75%/month
#     long + short  +180.2%/yr  DD 64.0%  MAR 2.81  +8.96%/month
# An 8.2-point drawdown cut for 0.8%/month, MAR unchanged - near-pure risk
# reduction. It also rescued the losing years (2022 -27.7%->-8.2%,
# 2025 -29.1%->+3.0% on the fixed universe), so the system no longer requires
# crypto to rise. Shorts run ONE unit with a TIGHT trail; see bb_break_short.
SHORT_ENABLED = True
SHORT_TRAIL_MULT = 5.0   # NOT 20 - shorts are negative at 20xATR
ADD_EVERY_R = 2.0        # add the next unit each time price advances this much R

# RISK PER UNIT. Total exposure = RISK_PCT x MAX_UNITS.
#
# MEASURED at 5 units on the point-in-time universe:
#     0.10%/unit (0.5% total)  ->  DD  72.2%   the validated config
#     0.20%/unit (1.0% total)  ->  DD ~85%
#     0.50%/unit (2.5% total)  ->  DD  99.9%   RUIN - the account does not survive
#
# Set to 0.40 for an aggressive demo run at the user's explicit request. That is
# 2.0% total exposure, just inside the level measured to wipe out. On a demo this
# is informative; on real funds it is a wipeout with extra steps.
RISK_PCT = 0.40
MIN_NOTIONAL = 5.0       # Bitget minimum per order
POLL_S = 60

BOOK = {
    "BTCUSDT": "SBTC/SUSDT:SUSDT",
    "ETHUSDT": "SETH/SUSDT:SUSDT",
    "XRPUSDT": "SXRP/SUSDT:SUSDT",
}

# PAPER BOOK — the configuration that actually hits the target.
#
# Breadth is the binding constraint, not the signal. Measured on 2400d, trail 12x,
# 0.5% risk, 8 concurrent slots:
#     3 coins   +59.7%/yr   DD 49.2%   = +3.98%/month   <- all this venue offers
#     5 coins  +118.8%/yr   DD 63.8%   = +6.74%/month
#     9 coins  +256.9%/yr   DD 78.0%   = +11.18%/month  <- the optimum
#    14 coins  +193.2%/yr   DD 81.4%   = +9.38%/month
#    20 coins  +176.0%/yr   DD 87.8%   = +8.83%/month
#
# It peaks where COINS ~= SLOTS + 1. Fewer and you sit idle; more and the position
# cap binds (8% of signals skipped at 9 coins, 51% at 20) so trades get taken by
# arrival order rather than quality. That is structure, not a fitted parameter.
#
# Bitget's demo lists only 3 contracts, so the 9-coin version cannot be run there.
# Paper mode simulates fills on live Binance prices to track what the real
# configuration would do, while the 3-coin demo book proves the execution path.
PAPER_BOOK = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT",
              "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"]
MAX_POSITIONS = 8        # the slot cap the sizing above assumes


def log(m: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def klines(sym: str, limit: int = 300) -> pd.DataFrame | None:
    u = (f"https://api.binance.com/api/v3/klines?symbol={sym}"
         f"&interval={TF}&limit={limit}")
    for a in range(3):
        try:
            r = json.load(urllib.request.urlopen(u, timeout=20))
            break
        except Exception:
            if a == 2:
                return None
            time.sleep(2)
    if not r:
        return None
    return pd.DataFrame({
        "time": pd.to_datetime([k[0] for k in r], unit="ms"),
        "open": [float(k[1]) for k in r], "high": [float(k[2]) for k in r],
        "low": [float(k[3]) for k in r], "close": [float(k[4]) for k in r]})


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def bb_break_short(df: pd.DataFrame) -> bool:
    """Close of the last CLOSED bar BELOW its lower Bollinger band.

    The short sleeve, added 2026-09-12. Measured on the point-in-time universe it
    cut drawdown 72.2% -> 64.0% for 0.8%/month of return, with MAR unchanged
    (2.84 -> 2.81) - close to a pure risk reduction. It also rescued the two losing
    years: on the fixed universe 2022 went -27.7% -> -8.2% and 2025 -29.1% -> +3.0%.

    ASYMMETRIC EXITS ARE THE WHOLE POINT. Longs improve monotonically out to a
    20xATR trail; shorts peak at 3-5x and go NEGATIVE at 20x, because up-moves
    grind and crashes are fast. Nineteen families were previously reported as
    "no short side" because both were tested with the long trail.

    NO regime filter: gating shorts to below-the-200h-average LOST to ungated on
    every metric. The filter waits until the decline is underway.
    """
    c = df["close"]
    ma = c.rolling(BB_PERIOD).mean()
    sd = c.rolling(BB_PERIOD).std(ddof=0)
    lo = ma - BB_STD * sd
    return bool(c.iloc[-1] < lo.iloc[-1]) and np.isfinite(lo.iloc[-1])


def bb_break_long(df: pd.DataFrame) -> bool:
    """Close of the last CLOSED bar above its upper Bollinger band.

    Bands are computed on closes up to and including that bar, which is known at
    its close - causal. The forming bar is never passed in.
    """
    c = df["close"]
    ma = c.rolling(BB_PERIOD).mean()
    sd = c.rolling(BB_PERIOD).std(ddof=0)
    up = ma + BB_STD * sd
    return bool(c.iloc[-1] > up.iloc[-1]) and np.isfinite(up.iloc[-1])


# ------------------------------------------------------------- exchange ----
def connect():
    import ccxt
    key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                    os.getenv("BITGET_PASSWORD"))
    if not all([key, sec, pw]):
        raise SystemExit("Set BITGET_API_KEY / BITGET_SECRET / BITGET_PASSWORD")
    ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                      "enableRateLimit": True,
                      "options": {"defaultType": "swap"}})
    ex.load_markets()
    try:
        ex.privateMixPostV2MixAccountSetPositionMode(
            {"productType": PRODUCT_TYPE, "posMode": "one_way_mode"})
    except Exception as e:
        log(f"position-mode note: {str(e)[:120]}")
    return ex


def equity(ex) -> float:
    r = ex.privateMixGetV2MixAccountAccounts({"productType": PRODUCT_TYPE})
    for a in r.get("data", []):
        if a.get("marginCoin") == MARGIN_COIN:
            return float(a.get("accountEquity") or 0)
    return 0.0


def positions(ex) -> dict:
    r = ex.privateMixGetV2MixPositionAllPosition(
        {"productType": PRODUCT_TYPE, "marginCoin": MARGIN_COIN})
    return {p["symbol"]: p for p in (r.get("data") or [])
            if float(p.get("total") or 0) > 0}


def ensure_settings(ex, sym: str):
    for fn, args in ((ex.set_margin_mode, (MARGIN_MODE, sym)),
                     (ex.set_leverage, (LEVERAGE, sym))):
        try:
            fn(*args)
        except Exception as e:
            m = str(e).lower()
            if "not modified" not in m and "same" not in m:
                log(f"  [{sym}] setting note: {str(e)[:100]}")


def load_state() -> dict:
    if STATE.exists():
        try:
            s = json.load(open(STATE))
            s.setdefault("open", {})
            s.setdefault("last_bar", {})
            s.setdefault("closed", [])
            return s
        except Exception:
            log("state unreadable - starting fresh")
    return {"open": {}, "last_bar": {}, "closed": [],
            "started": datetime.now(timezone.utc).isoformat()}


def save_state(s: dict):
    json.dump(s, open(STATE, "w"), indent=1)


def log_trade(row: dict):
    new = not TRADES.exists()
    with open(TRADES, "a", encoding="utf-8") as f:
        if new:
            f.write(",".join(row) + "\n")
        f.write(",".join(str(row[k]) for k in row) + "\n")


def cycle(ex, st: dict, dry: bool):
    eq = equity(ex) if ex else 10000.0
    live = positions(ex) if ex else {}

    for base, demo_sym in BOOK.items():
        df = klines(base, 300)
        if df is None or len(df) < BB_PERIOD + ATR_PERIOD + 5:
            log(f"[{base}] no data - skip")
            continue
        closed = df.iloc[:-1]                 # drop the forming bar
        bar = str(closed["time"].iloc[-1])
        a = atr(closed, ATR_PERIOD)
        a_now = float(a.iloc[-1])
        px_last = float(closed["close"].iloc[-1])
        hi_last = float(closed["high"].iloc[-1])
        lo_last = float(closed["low"].iloc[-1])
        if not np.isfinite(a_now) or a_now <= 0:
            continue

        raw = demo_sym.replace("/", "").replace(":SUSDT", "")
        rec = st["open"].get(raw)
        on_exchange = raw in live

        # ---- reconcile: the exchange stop may have fired while we were away ---
        if rec and not on_exchange and ex:
            log(f"[{base}] position gone from exchange - exchange stop fired or "
                f"was closed manually. Clearing local record.")
            log_trade(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                           symbol=base, entry=rec["entry"], exit="",
                           reason="EXCHANGE_STOP_OR_MANUAL", R="",
                           bars=rec.get("bars", 0)))
            st["open"].pop(raw, None)
            rec = None

        # ---- manage an open position: add units, ratchet the trail, exit ------
        if rec:
            rec["bars"] = rec.get("bars", 0) + 1
            rec.setdefault("units", 1)
            rec.setdefault("next_add", 1)
            rec.setdefault("side", "long")
            d = 1 if rec["side"] == "long" else -1
            # one water-mark field, read in the position's own direction: the best
            # price is the HIGH for a long and the LOW for a short
            rec["high_water"] = (max(rec["high_water"], hi_last) if d > 0
                                 else min(rec["high_water"], lo_last))

            # PYRAMID: add a unit once price has advanced ADD_EVERY_R from the
            # FIRST entry. Longs only - the short sleeve runs 1 unit, because its
            # best trail is 5xATR and a crash is over before a 2R-spaced ladder
            # could fill.
            if d > 0 and rec["units"] < MAX_UNITS:
                adv = (hi_last - rec["entry"]) / rec["risk"]
                if adv >= rec["next_add"] * ADD_EVERY_R:
                    add_sz = rec["size_unit"]
                    log(f"[{base}] PYRAMID add unit {rec['units']+1}/{MAX_UNITS} "
                        f"at +{adv:.1f}R (size {add_sz})")
                    if not dry and ex:
                        try:
                            ex.create_order(demo_sym, "market", "buy", add_sz)
                            rec["units"] += 1
                            rec["next_add"] += 1
                            rec["size"] = rec["size"] + add_sz
                        except Exception as e:
                            log(f"[{base}] ADD FAILED: {str(e)[:140]} - position "
                                f"unchanged, will retry next bar")
                    else:
                        rec["units"] += 1
                        rec["next_add"] += 1
                        rec["size"] = rec["size"] + add_sz

            # ASYMMETRIC TRAIL: 20xATR for longs, 5xATR for shorts. Not a
            # preference - measured. Shorts go NEGATIVE at 20x.
            tm = TRAIL_MULT if d > 0 else SHORT_TRAIL_MULT
            cand = rec["high_water"] - d * tm * a_now
            if (cand > rec["stop"]) if d > 0 else (cand < rec["stop"]):
                rec["stop"] = cand            # a stop only ratchets toward profit
            gain_r = (px_last - rec["entry"]) * d / rec["risk"]
            breached = (lo_last <= rec["stop"]) if d > 0 else (hi_last >= rec["stop"])
            if breached:
                exit_px = rec["stop"]
                R = (exit_px - rec["entry"]) * d / rec["risk"]
                log(f"[{base}] TRAIL HIT ({rec['side']}) -> exiting at market. "
                    f"entry {rec['entry']:.4f} stop {rec['stop']:.4f} R={R:+.2f} "
                    f"after {rec['bars']} bars")
                if not dry and ex:
                    try:
                        ex.create_order(demo_sym, "market",
                                        "sell" if d > 0 else "buy",
                                        rec["size"], None,
                                        {"reduceOnly": True})
                    except Exception as e:
                        log(f"[{base}] EXIT ORDER FAILED: {str(e)[:160]} - "
                            f"position left open, exchange stop still in place")
                        st["open"][raw] = rec
                        continue
                log_trade(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               symbol=base, entry=f"{rec['entry']:.6f}",
                               exit=f"{exit_px:.6f}", reason="TRAIL",
                               R=f"{R:+.4f}", bars=rec["bars"]))
                st["open"].pop(raw, None)
            else:
                log(f"[{base}] HOLD {rec['bars']}b  entry {rec['entry']:.4f}  "
                    f"stop {rec['stop']:.4f}  px {px_last:.4f}  "
                    f"open {gain_r:+.2f}R")
                st["open"][raw] = rec
            st["last_bar"][raw] = bar
            continue

        # ---- flat: one decision per closed bar -------------------------------
        if st["last_bar"].get(raw) == bar:
            # Silence must never be ambiguous with death. Without this the bot
            # logs nothing for up to an hour between bars, which is
            # indistinguishable from a crash for anyone checking the log.
            st.setdefault("_hb", {})
            if st["_hb"].get(raw) != bar:
                st["_hb"][raw] = bar
                log(f"[{base}] waiting for next 1h bar (last decided {bar}, "
                    f"px {px_last:.4f})")
            continue
        st["last_bar"][raw] = bar
        go_long = bb_break_long(closed)
        go_short = SHORT_ENABLED and bb_break_short(closed)
        if not (go_long or go_short):
            log(f"[{base}] flat; no breakout either way (close {px_last:.4f})")
            continue
        # a bar cannot be above the upper band and below the lower one, so these
        # are mutually exclusive; longs win if that ever changes
        side = "long" if go_long else "short"
        d = 1 if side == "long" else -1

        risk_amt = eq * RISK_PCT / 100.0
        stop_dist = SL_MULT * a_now
        size = risk_amt / stop_dist
        entry_ref = px_last
        notional = size * entry_ref
        if ex:
            try:
                size = float(ex.amount_to_precision(demo_sym, size))
                mkt = ex.market(demo_sym)
                min_amt = (mkt["limits"]["amount"] or {}).get("min") or 0
                if size < min_amt or notional < MIN_NOTIONAL:
                    log(f"[{base}] SIGNAL but size {size} (${notional:.2f}) below "
                        f"minimum (amt {min_amt}, ${MIN_NOTIONAL}) - skipping. "
                        f"Equity {eq:.2f} too small for {RISK_PCT}% risk here.")
                    continue
            except Exception as e:
                log(f"[{base}] precision/limits note: {str(e)[:120]}")
        stop_px = entry_ref - d * stop_dist     # ABOVE entry for a short

        log(f"[{base}] BREAKOUT -> {side.upper()} {size} @~{entry_ref:.4f} "
            f"(${notional:.2f}) stop {stop_px:.4f} risk ${risk_amt:.2f} "
            f"({RISK_PCT}% of {eq:.2f})")
        if dry:
            log(f"[{base}] DRY RUN - no order placed")
            continue
        if not ex:
            continue
        ensure_settings(ex, demo_sym)
        try:
            ex.create_order(demo_sym, "market", "buy" if d > 0 else "sell",
                            size, None, {
                "stopLoss": {"triggerPrice": float(
                    ex.price_to_precision(demo_sym, stop_px))}})
        except Exception as e:
            log(f"[{base}] ENTRY FAILED: {str(e)[:180]}")
            continue
        st["open"][raw] = dict(entry=entry_ref, size=size, size_unit=size,
                               risk=stop_dist, stop=stop_px, side=side,
                               high_water=(hi_last if d > 0 else lo_last),
                               bars=0, units=1, next_add=1,
                               opened=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}")
        log(f"[{base}] FILLED unit 1/{MAX_UNITS}. exchange stop at {stop_px:.4f} "
            f"as backstop; {TRAIL_MULT}xATR trail managed here; will add a unit "
            f"every +{ADD_EVERY_R}R")


def status(st: dict):
    print(f"\nLEVERAGED LONG TREND - Bitget demo")
    print(f"started {st.get('started','?')}")
    print(f"config: bb_break({BB_PERIOD},{BB_STD}) {TF} | trail {TRAIL_MULT}xATR | "
          f"no take-profit | risk {RISK_PCT}%/trade | lev {LEVERAGE}x")
    print(f"\nopen positions: {len(st.get('open', {}))}")
    for raw, r in st.get("open", {}).items():
        print(f"  {raw:12} entry {r['entry']:.4f} stop {r['stop']:.4f} "
              f"high {r['high_water']:.4f} {r['bars']}b")
    if TRADES.exists():
        d = pd.read_csv(TRADES)
        rs = pd.to_numeric(d.get("R"), errors="coerce").dropna()
        print(f"\nclosed trades: {len(d)}")
        if len(rs):
            print(f"  mean R {rs.mean():+.3f}  total R {rs.sum():+.2f}  "
                  f"win rate {(rs > 0).mean()*100:.0f}%  best {rs.max():+.2f}  "
                  f"worst {rs.min():+.2f}")
    print()


def resolve_mode(mode: str) -> dict:
    """Switch the venue, refusing LIVE unless ALLOW_REAL was deliberately set.

    Returns the book to trade. Live gets the full 9 coins because that is the
    configuration that was validated; demo gets the 3 the venue offers.
    """
    global PRODUCT_TYPE, MARGIN_COIN
    if mode == "live":
        if not ALLOW_REAL:
            raise SystemExit(
                "REFUSING --mode live: ALLOW_REAL is False in longtrend_bot.py.\n"
                "  This is the hard gate on real funds. To trade live you must:\n"
                "    1. set ALLOW_REAL = True in this file (a deliberate human act)\n"
                "    2. confirm the breaker settings in bot/core/adaptive.py are\n"
                "       back to MAX_DD_PCT=10 and MAX_LOSS_STREAK=6\n"
                "    3. fund at least ~$50 — below that, 0.5% risk produces orders\n"
                "       under Bitget's $5 minimum and nothing will fill\n"
                "  Expected: ~5%/month at ~85% drawdown, LONG ONLY, and it bleeds\n"
                "  in a sustained bear market. That is the measured deal.")
        PRODUCT_TYPE, MARGIN_COIN = LIVE["product"], LIVE["margin_coin"]
        return {c: f"{c[:-4]}/USDT:USDT" for c in PAPER_BOOK}
    PRODUCT_TYPE, MARGIN_COIN = DEMO["product"], DEMO["margin_coin"]
    return BOOK


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--mode", default="demo", choices=["demo", "live"],
                    help="demo = Bitget simulated (3 coins). live = real funds "
                         "(9 coins), refused unless ALLOW_REAL is True.")
    args = ap.parse_args()
    global BOOK
    BOOK = resolve_mode(args.mode)
    st = load_state()
    if args.status:
        status(st)
        return
    log("=" * 78)
    log(f"LEVERAGED LONG TREND on Bitget {args.mode.upper()}"
        + ("  *** REAL FUNDS ***" if args.mode == "live" else " (simulated)"))
    log(f"  bb_break({BB_PERIOD},{BB_STD}) {TF} | NO take-profit")
    log(f"  LONG:  trail {TRAIL_MULT}xATR, up to {MAX_UNITS} units "
        f"(+1 every {ADD_EVERY_R}R)")
    if SHORT_ENABLED:
        log(f"  SHORT: trail {SHORT_TRAIL_MULT}xATR, 1 unit, no regime filter "
            f"- shorts share the same slots")
        log(f"         asymmetric by measurement: shorts are NEGATIVE at "
            f"{TRAIL_MULT}xATR")
    else:
        log("  SHORT: disabled")
    log(f"  PYRAMID: up to {MAX_UNITS} units, +1 every {ADD_EVERY_R}R of advance")
    log(f"  risk {RISK_PCT}%/UNIT -> {RISK_PCT*MAX_UNITS:.2f}% total exposure "
        f"| leverage {LEVERAGE}x | taker entries")
    if RISK_PCT * MAX_UNITS >= 2.0:
        log(f"  *** AGGRESSIVE: {RISK_PCT*MAX_UNITS:.1f}% total. Measured drawdown "
            f"at 2.5% total was 99.9% (ruin). Demo only. ***")
    log(f"  book: {', '.join(BOOK.values())}")
    log("  signals from Binance 1h (tracks demo within 8bp), execution on Bitget")
    log(f"  exchange stop at -{SL_MULT}xATR as backstop; {TRAIL_MULT}xATR trail "
        f"managed in-process")
    if args.dry_run:
        log("  *** DRY RUN - no orders will be placed ***")
    ex = None if args.dry_run else connect()
    if ex:
        log(f"  connected. equity {equity(ex):.2f} SUSDT, "
            f"{len(positions(ex))} open positions")
    while True:
        try:
            cycle(ex, st, args.dry_run)
            save_state(st)
        except KeyboardInterrupt:
            log("stopped by user"); save_state(st); return
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:200]}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
