"""MICRO ACCOUNT, GO FOR BROKE — $5-10 on real Bitget, sized for a multiple.

THE ODDS. READ THESE BEFORE FUNDING ANYTHING.
    Measured in backtest/microacct.py: 6,000 bootstrapped paths per cell on the
    hindsight-deflated edge, Bitget's real $5 order minimum enforced.

        from $10 -> $50   (5x)    29.7% chance   70.3% RUIN    ~91 trades (~3-4 wks)
        from $10 -> $100 (10x)    22.7% chance   77.3% RUIN    ~84 trades
        from $5  -> $25   (5x)    24.4% chance   75.5% RUIN    ~49 trades
        from $5  -> $50  (10x)    17.8% chance   82.2% RUIN    ~73 trades

    THE MOST LIKELY SINGLE OUTCOME IS ZERO. Roughly a 1-in-3 shot at 5x from $10.
    This file is a deliberate lottery ticket with a positive expected value and a
    majority chance of total loss. Fund it only with money that can vanish.

    AND THOSE ODDS ARE OPTIMISTIC, for one reason stated plainly: the simulation runs
    trades SEQUENTIALLY. A real bot holds several at once, they are correlated, and
    correlated simultaneous losses kill accounts faster than a sequential draw does.
    Real ruin is therefore ABOVE 70%. MAX_POSITIONS below is set low to limit that,
    but the size of the gap is unmeasured.

WHY THIS CONFIGURATION, AND WHERE EACH CHOICE CAME FROM
    UNIVERSE  10 coins whose Bitget minimum order is at or under $5. LINK ($11.35),
              BNB ($7.16), BTC ($7.68), SOL ($9.98) and ETH ($24.83) are excluded by
              their own contract step - a $10 account cannot place one.
              Bitget REAL lists 783 USDT perps and 742 accept a $5 order; the
              3-contract limit people hit is a DEMO restriction only.

    RISK 4%   Not a guess, and the opposite of what I predicted. Sweeping 0.30% /
              2% / 4% asked, P(reach $50 from $10) went 25.3% -> 28.4% -> 28.2% at a
              2xATR stop, and 24.6% -> 28.7% -> 29.7% at 3xATR. Adding risk HELPED.
              The textbook result - that timid play maximises the chance of reaching
              a goal when your edge is positive - assumes you can bet arbitrarily
              small. The $5 floor already forces ~1.26% on a $10 account, so
              timidity is not on the menu; and inside a finite horizon more risk
              reaches the target sooner.

    STOP 2x   Also the opposite of what I predicted. A tighter stop reduces FORCED
              risk on a floor-bound account ($5 x stop width), so it looked like the
              obvious lever - but the edge itself shrinks faster: honest mean R is
              +0.035 at 0.5xATR against +0.086 at 1.5x and +0.076 at 2.0x. The noise
              cost beats the arithmetic saving. 2x and 3x tie within noise; 2x is
              kept because every other file in this project uses it.

    1 UNIT    No pyramid. Each added unit is another $5 order; five units is $25 of
              notional, which a $10 account cannot fund.

    NO REGIME GATE, deliberately. The BTC-below-200h gate is the single best
              improvement found for the $221 book. Here it would CUT risk, and the
              sweep above says cutting risk LOWERS the chance of reaching the target
              on a floor-bound account. Turn it on and you make this safer and less
              likely to work, which is the opposite of the stated goal.

    STOP AT THE TARGET. The bot stops opening positions once equity reaches
              TARGET_MULT x the starting stake, because that is exactly what the
              simulation measures. A bot that keeps compounding past the target has
              different - worse - odds of ever being up.

HARD GATE ON REAL MONEY
    ALLOW_REAL is False. --mode live refuses to start until a human edits this file.
    I will not flip it. Demo runs without it, but note Bitget demo lists only SBTC,
    SETH and SXRP, so a demo run here tests the plumbing, not the strategy.

    python micro_bot.py --mode demo --dry-run     no orders at all
    python micro_bot.py --mode demo                demo orders
    python micro_bot.py --mode live                refuses unless ALLOW_REAL
    python micro_bot.py --status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from longtrend_bot import acquire_lock, atr, klines  # noqa: E402

LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
STATE = LOGS / "micro_state.json"
TRADES = LOGS / "trades_micro.csv"
LOGF = LOGS / "micro.log"

# ---- THE HARD GATE. A human must edit this line to risk real funds. ----------
ALLOW_REAL = False

DEMO = dict(product="SUSDT-FUTURES", margin_coin="SUSDT")
LIVE = dict(product="USDT-FUTURES", margin_coin="USDT")
PRODUCT_TYPE, MARGIN_COIN = DEMO["product"], DEMO["margin_coin"]

TF = "1h"
BB_PERIOD, BB_STD = 30, 1.5
ATR_PERIOD = 14
SL_MULT = 2.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
BE_AT_R = 3.0
RISK_PCT = 4.0                 # the measured best cell — see the docstring
MAX_POSITIONS = 3              # concurrency is UNMEASURED; keep it small
MAX_LEVERAGE = 10.0
MIN_NOTIONAL = 5.0             # Bitget
TARGET_MULT = 5.0              # stop opening at 5x the starting stake
POLL_S = 60

# Bitget minimum order <= $5 for every one of these, checked 2026-09-14.
BOOK = ["XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "SUIUSDT",
        "LTCUSDT", "SHIBUSDT", "ARBUSDT", "NEARUSDT"]
DEMO_BOOK = {"SBTCSUSDT": "SBTC/SUSDT:SUSDT", "SETHSUSDT": "SETH/SUSDT:SUSDT",
             "SXRPSUSDT": "SXRP/SUSDT:SUSDT"}


def log(m: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def bands(df):
    c = df["close"]
    ma = c.rolling(BB_PERIOD).mean()
    sd = c.rolling(BB_PERIOD).std(ddof=0)
    return ma - BB_STD * sd, ma + BB_STD * sd


def fresh():
    return {"open": {}, "last_bar": {}, "hb": {}, "start_eq": None,
            "taken": 0, "declined": 0, "too_small": 0, "target_hit": False,
            "started": datetime.now(timezone.utc).isoformat()}


def load_state():
    if STATE.exists():
        try:
            s = json.load(open(STATE))
            for k, v in fresh().items():
                s.setdefault(k, v)
            return s
        except Exception:
            log("state unreadable — starting fresh")
    return fresh()


def save_state(s):
    tmp = STATE.with_suffix(".tmp")
    json.dump(s, open(tmp, "w"), indent=1)
    tmp.replace(STATE)


def rec_trade(row):
    new = not TRADES.exists()
    with open(TRADES, "a", encoding="utf-8") as f:
        if new:
            f.write(",".join(row) + "\n")
        f.write(",".join(str(v) for v in row.values()) + "\n")


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
    return ex


def equity(ex) -> float:
    r = ex.privateMixGetV2MixAccountAccounts({"productType": PRODUCT_TYPE})
    for a in r.get("data", []):
        if a.get("marginCoin") == MARGIN_COIN:
            return float(a.get("accountEquity") or 0)
    return 0.0


def resolve_mode(mode: str) -> dict:
    global PRODUCT_TYPE, MARGIN_COIN
    if mode == "live":
        if not ALLOW_REAL:
            raise SystemExit(
                "REFUSING --mode live: ALLOW_REAL is False in micro_bot.py.\n"
                "  This is the hard gate on real funds and I will not flip it for\n"
                "  you. To trade live you must edit this file yourself.\n"
                "\n"
                "  BEFORE YOU DO, THE MEASURED ODDS FROM $10:\n"
                "     29.7% chance of reaching $50\n"
                "     70.3% chance of losing everything\n"
                "     and that 70.3% is OPTIMISTIC — the simulation ran trades one\n"
                "     at a time, while this bot holds up to 3 at once and they are\n"
                "     correlated.\n"
                "\n"
                "  The most likely single outcome is zero. Fund it only with money\n"
                "  you are content to lose entirely.")
        PRODUCT_TYPE, MARGIN_COIN = LIVE["product"], LIVE["margin_coin"]
        return {c: f"{c[:-4]}/USDT:USDT" for c in BOOK}
    PRODUCT_TYPE, MARGIN_COIN = DEMO["product"], DEMO["margin_coin"]
    log("DEMO MODE: Bitget demo lists only SBTC/SETH/SXRP, so this tests the ORDER")
    log("  PLUMBING and not the strategy — the strategy needs the 10-coin book.")
    return DEMO_BOOK


def signal_source(raw_sym: str) -> str:
    """Signals always come from the REAL Binance symbol, even in demo. Bitget's demo
    'SBTC' series is thin and its own candles are not the market."""
    s = raw_sym.replace("SUSDT", "USDT")
    return "BTCUSDT" if s.startswith("SBTC") else s.lstrip("S") if s.startswith(
        ("SETH", "SXRP")) and s not in BOOK else s


def manage(rec, bar, hi, lo, a):
    """Returns an exit price, or None to hold. Stop is checked against the level it
    held DURING this bar — set at the end of the previous one — before the trail
    advances. Never judges the entry bar, whose extremes predate the position."""
    d = 1 if rec["side"] == "long" else -1
    if rec.get("entry_bar") == bar:
        return None
    rec["bars"] += 1
    if (lo <= rec["stop"]) if d == 1 else (hi >= rec["stop"]):
        return rec["stop"]
    rec["water"] = max(rec["water"], hi) if d == 1 else min(rec["water"], lo)
    gain = (rec["water"] - rec["entry"]) * d / rec["risk"]
    tm = LONG_TRAIL if d > 0 else SHORT_TRAIL
    cand = rec["water"] - d * tm * a
    if gain >= BE_AT_R:
        cand = max(cand, rec["entry"]) if d > 0 else min(cand, rec["entry"])
    if (cand > rec["stop"]) if d > 0 else (cand < rec["stop"]):
        rec["stop"] = cand
    return None


def cycle(ex, st, book, dry):
    eq = equity(ex) if ex else float(st.get("start_eq") or 10.0)
    if st["start_eq"] is None:
        st["start_eq"] = eq
        log(f"starting equity recorded as {eq:.4f} {MARGIN_COIN}; "
            f"target {eq*TARGET_MULT:.2f}")
    target = st["start_eq"] * TARGET_MULT
    if eq >= target and not st["target_hit"]:
        st["target_hit"] = True
        log(f"*** TARGET REACHED: {eq:.2f} >= {target:.2f}. No new positions. "
            f"Open ones will be managed to their exits. ***")

    for raw, sym in book.items():
        src = signal_source(raw)
        df = klines(src, 300)
        if df is None or len(df) < BB_PERIOD + ATR_PERIOD + 5:
            continue
        closed = df.iloc[:-1]
        bar = str(closed["time"].iloc[-1])
        a = float(atr(closed, ATR_PERIOD).iloc[-1])
        px = float(closed["close"].iloc[-1])
        hi = float(closed["high"].iloc[-1]); lo = float(closed["low"].iloc[-1])
        if not np.isfinite(a) or a <= 0:
            continue
        rec = st["open"].get(raw)

        if rec:
            if st["last_bar"].get(raw) == bar:
                continue
            st["last_bar"][raw] = bar
            exit_px = manage(rec, bar, hi, lo, a)
            if exit_px is None:
                st["open"][raw] = rec
                continue
            d = 1 if rec["side"] == "long" else -1
            R = (exit_px - rec["entry"]) * d / rec["risk"]
            log(f"[{raw}] EXIT {rec['side']} R={R:+.2f} after {rec['bars']}b")
            if not dry and ex:
                try:
                    ex.create_order(sym, "market",
                                    "sell" if d == 1 else "buy", rec["size"],
                                    params={"reduceOnly": True})
                except Exception as e:
                    log(f"[{raw}] CLOSE FAILED: {str(e)[:140]} — retrying next bar")
                    st["open"][raw] = rec
                    continue
            rec_trade(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                           symbol=raw, side=rec["side"],
                           entry=f"{rec['entry']:.8f}", exit=f"{exit_px:.8f}",
                           R=f"{R:+.4f}", bars=rec["bars"],
                           equity=f"{eq:.4f}"))
            st["open"].pop(raw, None)
            continue

        if st["last_bar"].get(raw) == bar:
            continue
        st["last_bar"][raw] = bar
        if st["target_hit"]:
            continue
        lo_b, up_b = bands(closed)
        if not (np.isfinite(up_b.iloc[-1]) and np.isfinite(lo_b.iloc[-1])):
            continue
        go_long, go_short = px > up_b.iloc[-1], px < lo_b.iloc[-1]
        if not (go_long or go_short):
            continue
        side = "long" if go_long else "short"
        d = 1 if go_long else -1
        if len(st["open"]) >= MAX_POSITIONS:
            st["declined"] += 1
            log(f"[{raw}] {side.upper()} DECLINED — {MAX_POSITIONS} slots full "
                f"({st['declined']} so far)")
            continue
        risk = SL_MULT * a
        notional = (eq * RISK_PCT / 100.0) / (risk / px)
        if notional < MIN_NOTIONAL:
            # The floor overrides upward: take the $5 order and accept the higher
            # risk, which is what the simulation modelled. Counted so the log shows
            # how often the venue, not the config, is choosing the size.
            st["too_small"] += 1
            notional = MIN_NOTIONAL
        if notional > eq * MAX_LEVERAGE:
            log(f"[{raw}] {side.upper()} SKIPPED — ${notional:.2f} exceeds "
                f"{MAX_LEVERAGE:.0f}x on {eq:.2f}")
            continue
        size = notional / px
        try:
            size = float(ex.amount_to_precision(sym, size)) if ex else size
        except Exception:
            pass
        if size <= 0:
            continue
        real_risk = size * px * (risk / px) / eq * 100
        log(f"[{raw}] {side.upper()} @{px:.8g} stop {px-d*risk:.8g} "
            f"size {size} (${size*px:.2f}, {real_risk:.2f}% of equity) "
            f"trail {LONG_TRAIL if d>0 else SHORT_TRAIL:.0f}xATR")
        if not dry and ex:
            try:
                ex.create_order(sym, "market", "buy" if d == 1 else "sell", size)
            except Exception as e:
                log(f"[{raw}] ENTRY FAILED: {str(e)[:140]}")
                continue
        st["open"][raw] = dict(side=side, entry=px, risk=risk,
                               stop=px - d * risk,
                               water=(hi if d > 0 else lo), bars=0,
                               size=size, entry_bar=bar)
        st["taken"] += 1


def status(st):
    print(f"\nMICRO BOT — {MAX_POSITIONS} slots, {RISK_PCT}% risk/trade, "
          f"stop {SL_MULT}xATR, target {TARGET_MULT:.0f}x")
    print(f"started {st.get('started','?')}   start equity "
          f"{st.get('start_eq')}   target hit: {st.get('target_hit')}")
    print(f"entries {st['taken']}  declined {st['declined']}  "
          f"venue-forced size {st.get('too_small',0)}")
    print(f"open {len(st['open'])}/{MAX_POSITIONS}")
    for k, r in sorted(st["open"].items()):
        print(f"  {k:<12} {r['side']:<5} entry {r['entry']:.6g} "
              f"stop {r['stop']:.6g} {r['bars']}b")
    if TRADES.exists():
        d = pd.read_csv(TRADES)
        rs = pd.to_numeric(d["R"], errors="coerce").dropna()
        if len(rs):
            print(f"\nclosed {len(rs)}  mean R {rs.mean():+.3f}  "
                  f"total {rs.sum():+.2f}R  win {(rs>0).mean()*100:.0f}%")
    print("\nMEASURED ODDS FROM $10: 29.7% reach $50, 70.3% lose everything.")
    print("The most likely single outcome is zero.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["demo", "live"], default="demo")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    st = load_state()
    if args.status:
        status(st); return
    book = resolve_mode(args.mode)
    acquire_lock("micro_bot")
    log("=" * 78)
    log(f"MICRO BOT — {args.mode.upper()}{' DRY-RUN' if args.dry_run else ''} | "
        f"{len(book)} contracts | {MAX_POSITIONS} slots | risk {RISK_PCT}%/trade")
    log(f"  stop {SL_MULT}xATR | long trail {LONG_TRAIL:.0f}x | "
        f"short trail {SHORT_TRAIL:.0f}x | BE@{BE_AT_R:.0f}R | 1 unit, no pyramid")
    log(f"  stops opening at {TARGET_MULT:.0f}x the starting stake")
    log("  ODDS FROM $10: 29.7% reach $50 | 70.3% RUIN | most likely outcome is ZERO")
    log("  ruin is understated: the sim ran trades sequentially, this holds 3 at once")
    ex = None if args.dry_run and args.mode == "demo" else connect()
    if ex:
        log(f"  connected, equity {equity(ex):.4f} {MARGIN_COIN}")
    while True:
        try:
            cycle(ex, st, book, args.dry_run)
            newest = max(st["last_bar"].values(), default=None)
            if newest and st["hb"].get("logged") != newest:
                st["hb"]["logged"] = newest
                log(f"alive | bar {newest} | {len(st['open'])}/{MAX_POSITIONS} "
                    f"open | taken {st['taken']} | declined {st['declined']}")
            save_state(st)
        except KeyboardInterrupt:
            log("stopped"); save_state(st); return
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:200]}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
