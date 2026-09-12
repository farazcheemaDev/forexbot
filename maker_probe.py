"""EXECUTION PROBE — measures one number: do post-only limits actually fill?

THE QUESTION
------------
On untouched data, momentum breaks even around 6-8.5bp round trip. Bitget taker
is ~12bp, maker ~4bp. So maker execution flips the edge positive — IF orders fill.
Backtest, on both 1h and 5m data, predicts a 62% fill rate at 0.5xATR behind
market with a 4-bar expiry. But that assumes a price TOUCH equals a fill, and
OHLC bars contain nothing about queue position. Only a live order book can answer.

WHY THIS IS A PROBE AND NOT A STRATEGY
--------------------------------------
5m bars are used because they generate ~65 entry attempts per symbol per day
versus ~1 at 1h — so ~30 resolved attempts in about 4 hours instead of weeks.

1-MINUTE WAS TESTED AND REJECTED: at 1m, 0.5xATR is only 4.2 ticks on XRP and
1.73bp on BTC (vs Bitget's ~0.5-1bp spread), so post-only would either be
rejected or fill trivially - and the simulated rate itself shifts to 46-51%,
so a 1m number would not transfer to the hourly strategy. 5m keeps 0.5xATR at
6-8bp and 11-443 ticks, comfortably clear of the spread.

But 5m is NOT tradeable:
the stop distance shrinks while fees stay proportional to price, so fees cost
~0.4R/trade there and expectancy is -0.22R. So this probe deliberately:

    * uses MINIMUM order size            -> P&L is noise, not the point
    * CLOSES immediately after any fill  -> frees the symbol to post again,
                                            maximising independent attempts
    * ignores profit entirely            -> it measures mechanics, nothing else

The live rate is compared to the probe-matched SIMULATED rate (PROBE_TARGET),
not to the real strategy's 62% - those are different attempt populations. The
ratio between them isolates the queue effect, which is then applied to 62% to
predict the real strategy's fill rate. Once known, crypto_maker.py runs the
real edge test on validated timeframes.

Bitget only offers 3 demo contracts and positions net per symbol, so this cannot
run at the same time as crypto_maker.py.

    python maker_probe.py --check | --once | (no args = live loop)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest.mass_search import FILTERS, gen_signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
STATE = LOGS / "probe_state.json"

PRODUCT_TYPE, MARGIN_COIN = "SUSDT-FUTURES", "SUSDT"
LEVERAGE, MARGIN_MODE = 5, "isolated"
OFFSET_ATR = 0.5
WAIT_BARS = 4
TF = "5m"
MIN_NOTIONAL = 6.5      # Bitget rejects under 5 USDT (err 45110); aim above it

# THREE DIFFERENT NUMBERS - do not conflate them:
#   PROBE_TARGET  simulated fill rate for THIS probe's exact rule: post EVERY bar
#                 (direction = previous bar), ONE resting order at a time, rest
#                 WAIT_BARS, then resolve. BTC 67.3 / ETH 67.1 / XRP 67.7 at 5m
#                 -> 67.4% over 63,560 simulated attempts. The live rate is
#                 compared against THIS to isolate the queue effect.
#                 (signal-gated variants gave 72.1% and 62.0% - different
#                  populations, which is why the target has been wrong twice.)
#   EDGE_FILL     simulated fill rate for the REAL strategy, whose population is
#                 different again: it RE-POSTS each bar while the signal holds, so
#                 attempts overlap and each bar is a fresh chance. 62% at 1h and 5m.
#                 Three populations, three numbers - conflating them cost two
#                 wrong targets already (55, then 62).
#   EDGE_BREAKEVEN  fill rate below which maker execution stops rescuing the
#                 edge (~57% gives +0.05R; the taker baseline is -0.01R).
MIN_SAMPLE = 30        # no verdict below this; binomial SE is meaningless
PROBE_TARGET = 67.4
EDGE_FILL = 62.0
EDGE_BREAKEVEN = 57.0

BOOK = {
    "BTC/USDT:USDT": dict(demo="SBTC/SUSDT:SUSDT", raw="SBTCSUSDT",
                          fam="bb_break", p=(30, 1.5)),
    "ETH/USDT:USDT": dict(demo="SETH/SUSDT:SUSDT", raw="SETHSUSDT",
                          fam="bb_break", p=(30, 1.5)),
    "XRP/USDT:USDT": dict(demo="SXRP/SUSDT:SUSDT", raw="SXRPSUSDT",
                          fam="rsi_mom", p=(7, 40, 60)),
}


def log(msg):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOGS / "probe.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_event(row):
    f = LOGS / "probe_fills.csv"
    new = not f.exists()
    with open(f, "a", encoding="utf-8") as fh:
        if new:
            fh.write("ts_utc,symbol,event,side,limit,fill,slip_bp,bars_waited,note\n")
        fh.write(",".join(str(row.get(k, "")) for k in
                 ["ts", "symbol", "event", "side", "limit", "fill", "slip_bp",
                  "bars_waited", "note"]) + "\n")


def load_state():
    if STATE.exists():
        return json.load(open(STATE))
    return {"orders": {}, "seen": {},
            "stats": {"posted": 0, "filled": 0, "unfilled": 0, "rejected": 0,
                      "signal_lost": 0, "errors": 0,
                      "slip_bp_sum": 0.0, "wait_sum": 0}}


def save_state(s):
    json.dump(s, open(STATE, "w"), indent=1)


def connect():
    key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                    os.getenv("BITGET_PASSWORD"))
    if not all([key, sec, pw]):
        raise SystemExit("Set BITGET_API_KEY / BITGET_SECRET / BITGET_PASSWORD")
    ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                      "enableRateLimit": True, "options": {"defaultType": "swap"}})
    ex.load_markets()
    return ex


def equity(ex):
    r = ex.privateMixGetV2MixAccountAccounts({"productType": PRODUCT_TYPE})
    for a in r.get("data", []):
        if a.get("marginCoin") == MARGIN_COIN:
            return float(a.get("accountEquity") or 0)
    return 0.0


def positions(ex):
    r = ex.privateMixGetV2MixPositionAllPosition(
        {"productType": PRODUCT_TYPE, "marginCoin": MARGIN_COIN})
    return {p["symbol"]: p for p in (r.get("data") or [])
            if float(p.get("total") or 0)}


def pending(ex):
    """Resting orders, or None if the fetch FAILED.

    Returning {} on error would be catastrophic: reconcile treats "my order is not
    in the pending list" as resolved, so one transient API hiccup would mark every
    resting order UNFILLED and silently poison the fill statistics. None means
    "unknown" and the caller skips reconciliation this cycle.
    """
    try:
        r = ex.privateMixGetV2MixOrderOrdersPending({"productType": PRODUCT_TYPE})
        return {str(o.get("orderId")): o
                for o in (r.get("data") or {}).get("entrustedList") or []}
    except Exception as e:
        log(f"pending fetch FAILED ({str(e)[:90]}) - skipping reconcile this cycle")
        return None


def flatten(ex, raw, demo_sym, p):
    """Close immediately — we want the symbol free to post again, not the P&L."""
    side = "sell" if p.get("holdSide") == "long" else "buy"
    size = float(p.get("total") or 0)
    try:
        ex.create_order(demo_sym, "market", side, size, None,
                        {"reduceOnly": True, "marginMode": MARGIN_MODE})
        log(f"  flattened {raw} ({side} {size}) to free the slot")
    except Exception as e:
        log(f"  flatten note {raw}: {str(e)[:120]}")


def ensure_settings(ex, demo_sym):
    for fn, args in ((ex.set_margin_mode, (MARGIN_MODE, demo_sym)),
                     (ex.set_leverage, (LEVERAGE, demo_sym))):
        try:
            fn(*args)
        except Exception as e:
            m = str(e).lower()
            if "not modified" not in m and "same" not in m:
                log(f"  [{demo_sym}] setting note: {str(e)[:90]}")


def report(st):
    s = st["stats"]
    tried = s["filled"] + s["unfilled"]
    log("---- PROBE: post-only fill statistics ----")
    log(f"   posted={s['posted']} filled={s['filled']} unfilled={s['unfilled']} "
        f"signal_lost={s['signal_lost']} postonly_rejected={s['rejected']} "
        f"errors={s.get('errors', 0)}")
    if tried:
        fr = s["filled"] / tried * 100
        # binomial standard error, so we know when the estimate is trustworthy
        se = (fr * (100 - fr) / tried) ** 0.5
        log(f"   FILL RATE = {fr:.1f}% +/- {se:.1f}%  on {tried} resolved attempts")
        # Below MIN_SAMPLE the standard error is meaningless (at n=1 it is 0, so
        # ANY value reads DIVERGENT). Withhold the verdict instead of crying wolf.
        if tried >= MIN_SAMPLE:
            log(f"   simulated rate for THIS population = {PROBE_TARGET:.1f}%  ->  "
                f"{'CONSISTENT' if abs(fr - PROBE_TARGET) <= 2 * se else 'DIVERGENT'}")
        else:
            log(f"   simulated rate for THIS population = {PROBE_TARGET:.1f}%  ->  "
                f"no verdict yet ({tried}/{MIN_SAMPLE} attempts)")
        # Two-step inference. The probe flattens instantly, so it samples a denser
        # attempt population than a real trade (which blocks re-entry until its
        # stop/target). Comparing the probe's live rate to the probe-matched
        # SIMULATED rate isolates the queue effect - the one thing bars cannot
        # show. That ratio is then applied to the real strategy's 62%.
        if tried >= MIN_SAMPLE:
            ratio = fr / PROBE_TARGET if PROBE_TARGET else 0.0
            eff = EDGE_FILL * ratio
            log(f"   queue discount = {ratio:.2f}x  ->  real strategy fill "
                f"{EDGE_FILL:.0f}% x {ratio:.2f} = {eff:.1f}%")
            log(f"   needs >~{EDGE_BREAKEVEN:.0f}% to keep the edge  ->  "
                f"{'PASSES' if eff >= EDGE_BREAKEVEN else 'FAILS'}")
        else:
            log(f"   (need {MIN_SAMPLE}+ resolved attempts before inferring anything)")
    if s["filled"]:
        log(f"   avg entry slip = {s['slip_bp_sum']/s['filled']:+.3f}bp "
            f"(<=0 expected for a genuine maker fill)")
        log(f"   avg bars waited to fill = {s['wait_sum']/s['filled']:.2f}")


def cycle(ex, st):
    eq = equity(ex)
    pos = positions(ex)
    live = pending(ex)
    s = st["stats"]
    if live is None:                       # order book state unknown - do nothing
        log(f"eq={eq:.2f} | pending unknown, holding {len(st['orders'])} orders")
        return

    # resolve every resting order, then flatten anything that filled
    for raw, od in list(st["orders"].items()):
        if str(od["order_id"]) in live:
            continue
        if raw in pos:
            p = pos[raw]
            fill = float(p.get("openPriceAvg") or od["limit"])
            d = 1 if od["side"] == "buy" else -1
            slip = (fill - od["limit"]) * d / od["limit"] * 10000.0
            s["filled"] += 1; s["slip_bp_sum"] += slip
            s["wait_sum"] += od.get("bars_waited", 0)
            log(f"FILLED {raw} limit={od['limit']:.6g} fill={fill:.6g} "
                f"slip={slip:+.2f}bp waited={od.get('bars_waited',0)} bars")
            log_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                           symbol=raw, event="FILLED", side=od["side"],
                           limit=od["limit"], fill=fill, slip_bp=round(slip, 3),
                           bars_waited=od.get("bars_waited", 0)))
            flatten(ex, raw, od["demo"], p)
        else:
            s["unfilled"] += 1
            log(f"UNFILLED {raw} limit={od['limit']:.6g} "
                f"after {od.get('bars_waited',0)} bars")
            log_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                           symbol=raw, event="UNFILLED", side=od["side"],
                           limit=od["limit"], bars_waited=od.get("bars_waited", 0)))
        st["orders"].pop(raw, None)

    tried = s["filled"] + s["unfilled"]
    fr = (s["filled"] / tried * 100) if tried else 0.0
    log(f"eq={eq:.2f} | pos={len(pos)} resting={len(st['orders'])} | "
        f"fills {s['filled']}/{tried} = {fr:.1f}% (probe target {PROBE_TARGET:.0f}%)")

    for real_sym, c in BOOK.items():
        demo_sym, raw = c["demo"], c["raw"]
        try:
            o = ex.fetch_ohlcv(real_sym, TF, limit=300)
        except Exception as e:
            log(f"[{raw}] ohlcv error: {e}"); continue
        df = pd.DataFrame(o, columns=["t", "open", "high", "low", "close", "volume"])
        if len(df) < 250:
            continue
        closed = df.iloc[:-1].reset_index(drop=True)
        bar_t = int(closed["t"].iloc[-1])
        if st["seen"].get(real_sym) == bar_t:
            continue
        st["seen"][real_sym] = bar_t

        if raw in pos:                     # still flattening from last fill
            flatten(ex, raw, demo_sym, pos[raw]); continue

        od = st["orders"].get(raw)
        # UNCONDITIONAL posting: direction = previous bar's direction, no strategy
        # signal required. The queue effect (does a touched price actually fill?)
        # is a property of the ORDER BOOK, not of why we posted - so measuring it
        # unconditionally is valid and 3x faster (14.7 attempts/hour vs ~5).
        # Simulated unconditional rate on the same rule is 67.4% (63,560 attempts).
        a = float(atr_ind(closed, 14).iloc[-1])
        up = float(closed["close"].iloc[-1]) >= float(closed["close"].iloc[-2])
        action = Action.BUY if up else Action.SELL

        if od:                             # age it; expire or pull it, never re-post
            od["bars_waited"] = od.get("bars_waited", 0) + 1
            # unconditional mode: an order only ever expires, never "loses" a signal
            reason = None if od["bars_waited"] < WAIT_BARS else "expired"
            if reason is None:
                # LEAVE IT RESTING. Cancelling and re-posting every bar (an earlier
                # version of this file) reset bars_waited to 0 so orders could never
                # reach the expiry branch - `unfilled` never incremented and the
                # fill rate was pinned at 100% by construction. Each order must be
                # one clean Bernoulli trial: rest the full WAIT_BARS, then resolve.
                continue
            try:
                ex.cancel_order(od["order_id"], demo_sym,
                                {"productType": PRODUCT_TYPE})
            except Exception as e:
                log(f"[{raw}] cancel note: {str(e)[:100]}")
            if reason == "signal lost":
                s["signal_lost"] += 1
                log_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               symbol=raw, event="SIGNAL_LOST", side=od["side"],
                               limit=od["limit"],
                               bars_waited=od["bars_waited"]))
            elif reason == "expired":
                s["unfilled"] += 1
                log(f"UNFILLED {raw} expired after {WAIT_BARS} bars")
                log_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               symbol=raw, event="UNFILLED", side=od["side"],
                               limit=od["limit"], bars_waited=od["bars_waited"],
                               note="expired"))
            st["orders"].pop(raw, None)
            if reason:
                continue                   # done with this symbol this bar

        if action == Action.HOLD or not np.isfinite(a) or a <= 0:
            continue

        side = "buy" if action == Action.BUY else "sell"
        d = 1 if side == "buy" else -1
        price = float(closed["close"].iloc[-1])
        limit = price - d * OFFSET_ATR * a
        try:
            limit = float(ex.price_to_precision(demo_sym, limit))
            # Bitget enforces a 5 USDT MINIMUM NOTIONAL (err 45110), which is a
            # different constraint from ccxt's limits.amount.min. Aim slightly
            # above it so rounding cannot drop us under.
            mkt = ex.market(demo_sym)
            need = MIN_NOTIONAL / max(limit, 1e-12)
            amount = float(ex.amount_to_precision(
                demo_sym, max(need, mkt["limits"]["amount"]["min"] or 0)))
            if amount * limit < 5.0:       # precision rounded us back under
                amount = float(ex.amount_to_precision(demo_sym, amount * 1.5))
            if amount <= 0:
                log(f"[{raw}] cannot size a valid minimum order"); continue
        except Exception as e:
            log(f"[{raw}] sizing error: {e}"); continue

        ensure_settings(ex, demo_sym)
        try:
            r = ex.create_order(demo_sym, "limit", side, amount, limit,
                                {"marginMode": MARGIN_MODE, "postOnly": True})
            st["stats"]["posted"] += 1
            st["orders"][raw] = dict(order_id=str(r.get("id")), demo=demo_sym,
                                     side=side, limit=limit, bars_waited=0)
            log(f"POSTED {raw} {side} {amount} @{limit:.6g} "
                f"(mkt {price:.6g}, {OFFSET_ATR}xATR behind)")
            log_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                           symbol=raw, event="POSTED", side=side, limit=limit,
                           bars_waited=0))
        except Exception as e:
            msg = str(e)[:180]
            # a post-only rejection means our limit would have crossed the book -
            # that is MEASUREMENT. Any other error is a bug and must not be
            # silently folded into the fill statistics.
            rej = "post" in msg.lower() or "40762" in msg
            st["stats"]["rejected" if rej else "errors"] += 1
            log(f"[{raw}] {'REJECTED (would take)' if rej else 'ORDER ERROR'}: {msg}")
            log_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                           symbol=raw, event="REJECTED" if rej else "FAILED",
                           side=side, limit=limit, note=msg[:70]))
    save_state(st)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    # SINGLE INSTANCE ONLY. Two probes ran concurrently on 2026-09-11, sharing one
    # state file and three contracts, and produced nonsense ("UNFILLED after 0
    # bars" 14 seconds after posting). A stale-PID-aware lock makes that impossible.
    lock = LOGS / "probe.lock"
    if lock.exists():
        try:
            old_pid = int(lock.read_text().strip())
        except Exception:
            old_pid = -1
        alive = False
        if old_pid > 0:
            try:
                import subprocess
                out = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}"],
                                     capture_output=True, text=True).stdout
                alive = str(old_pid) in out
            except Exception:
                alive = True            # cannot tell -> assume it is, refuse
        if alive:
            raise SystemExit(f"another probe is already running (pid {old_pid}). "
                             f"Stop it first, or delete {lock} if it is stale.")
        log(f"clearing stale lock from dead pid {old_pid}")
    lock.write_text(str(os.getpid()))
    import atexit
    atexit.register(lambda: lock.unlink(missing_ok=True))

    ex = connect()
    log(f"EXECUTION PROBE | {TF} bars | offset {OFFSET_ATR}xATR | expire {WAIT_BARS} "
        f"bars | MIN size | flatten-on-fill")
    log("measuring FILL RATE only — P&L is deliberately meaningless here")
    try:
        log(f"equity {equity(ex):.2f} | positions {len(positions(ex))} | "
            f"resting {len(pending(ex))}")
    except Exception as e:
        log(f"ACCOUNT READ FAILED: {str(e)[:200]}"); return
    if args.check:
        return

    st = load_state()
    if args.once:
        cycle(ex, st); report(st); return
    n = 0
    while True:
        try:
            cycle(ex, st)
            n += 1
            if n % 10 == 0:
                report(st)
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:170]}")
        time.sleep(45)


if __name__ == "__main__":
    main()
