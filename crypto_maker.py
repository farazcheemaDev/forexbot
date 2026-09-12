"""MAKER-ONLY execution on Bitget demo — measuring the one number backtests can't.

WHY THIS BOT EXISTS
-------------------
On untouched crypto data the momentum edge breaks even at 6-8.5bp round trip.
Bitget taker is ~12bp, maker ~4bp. So the sign of the edge is set by execution,
not by the signal - and every previous test and bot used MARKET orders, i.e. the
losing side of breakeven.

But the backtest could not settle it, because the answer hinges on FILL RATE:

    re-post each bar, touch=fill      -> +0.09R  (positive)
    re-post each bar, 0.10 ATR through-> +0.04R  (positive)
    one shot, 0.05 ATR through        -> -0.01R  (negative)
    market orders (taker)            -> -0.01R  (negative)

Whether a resting order at a price the market merely grazes actually executes
depends on queue position, which OHLC bars do not contain. No amount of
backtesting can resolve it. A live order book can, in days.

SO THIS BOT MEASURES, IT DOES NOT ASSUME:
    signals generated / orders posted / orders filled / orders expired
    -> the true fill rate
    intended limit price vs actual fill price
    -> the true slippage (should be <= 0 for maker fills)

HOW IT TRADES
-------------
post-only LIMIT entry at (price - 0.5 ATR) for longs, re-posted on each new bar
while the signal persists (that re-posting is what made the backtest positive:
one-shot misses every trade where price runs away without a pullback, and those
are the winners). Orders expire after WAIT_BARS unfilled. Exchange-side SL/TP
attach on fill. postOnly means Bitget REJECTS an order that would take -
a rejection is information, not an error, and is logged as such.

    python crypto_maker.py --check | --dry | --once | (no args = live loop)
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
from bot.core import adaptive  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
STATE = LOGS / "maker_state.json"

PRODUCT_TYPE, MARGIN_COIN = "SUSDT-FUTURES", "SUSDT"
RISK_PCT = 4.0      # DEMO AGGRESSIVE (was 0.5)
MAX_POSITIONS = 3
LEVERAGE, MARGIN_MODE = 5, "isolated"
SL_MULT, TP_MULT = 2.0, 3.0

OFFSET_ATR = 0.5        # post this far BELOW market for a long (the backtest optimum)
WAIT_BARS = 4           # cancel an unfilled order after this many bars

# bb_break had the best net expectancy under maker fees; rsi_mom/roc_mom next.
BOOK = {
    "BTC/USDT:USDT": dict(demo="SBTC/SUSDT:SUSDT", raw="SBTCSUSDT",
                          fam="bb_break", p=(30, 1.5), filt="none", tf="1h"),
    "ETH/USDT:USDT": dict(demo="SETH/SUSDT:SUSDT", raw="SETHSUSDT",
                          fam="bb_break", p=(30, 1.5), filt="none", tf="15m"),
    "XRP/USDT:USDT": dict(demo="SXRP/SUSDT:SUSDT", raw="SXRPSUSDT",
                          fam="rsi_mom", p=(7, 40, 60), filt="none", tf="15m"),
}


def sid_of(c):
    return f"maker_{c['fam']}_{c['tf']}"


def log(msg):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOGS / "maker.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_trade(sid, row):
    f = LOGS / f"trades_{sid}.csv"
    new = not f.exists()
    with open(f, "a", encoding="utf-8") as fh:
        if new:
            fh.write("ts_utc,symbol,side,entry,exit,R,pnl,slip_bp,equity\n")
        fh.write(",".join(str(row[k]) for k in
                 ["ts", "symbol", "side", "entry", "exit", "R", "pnl",
                  "slip_bp", "equity"]) + "\n")


def log_fill_event(row):
    """Every signal/post/fill/expiry — this file IS the experiment."""
    f = LOGS / "maker_fills.csv"
    new = not f.exists()
    with open(f, "a", encoding="utf-8") as fh:
        if new:
            fh.write("ts_utc,sid,symbol,event,side,limit,fill,slip_bp,bars_waited,note\n")
        fh.write(",".join(str(row.get(k, "")) for k in
                 ["ts", "sid", "symbol", "event", "side", "limit", "fill",
                  "slip_bp", "bars_waited", "note"]) + "\n")


def load_state():
    if STATE.exists():
        return json.load(open(STATE))
    return {"open": {}, "orders": {}, "closed_ids": [], "seen": {},
            "_active": {}, "_tripped": {},
            "stats": {"signals": 0, "posted": 0, "filled": 0, "expired": 0,
                      "rejected": 0, "slip_bp_sum": 0.0}}


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
    try:
        ex.privateMixPostV2MixAccountSetPositionMode(
            {"productType": PRODUCT_TYPE, "posMode": "one_way_mode"})
    except Exception as e:
        log(f"position mode note: {str(e)[:120]}")
    return ex


def demo_equity(ex):
    r = ex.privateMixGetV2MixAccountAccounts({"productType": PRODUCT_TYPE})
    for a in r.get("data", []):
        if a.get("marginCoin") == MARGIN_COIN:
            return float(a.get("accountEquity") or 0)
    return 0.0


def demo_positions(ex):
    r = ex.privateMixGetV2MixPositionAllPosition(
        {"productType": PRODUCT_TYPE, "marginCoin": MARGIN_COIN})
    return {p["symbol"]: p for p in (r.get("data") or [])
            if float(p.get("total") or 0)}


def open_orders(ex):
    try:
        r = ex.privateMixGetV2MixOrderOrdersPending({"productType": PRODUCT_TYPE})
        return {str(o.get("orderId")): o for o in (r.get("data") or {}).get("entrustedList") or []}
    except Exception as e:
        log(f"open-orders fetch note: {str(e)[:130]}")
        return {}


def ensure_settings(ex, demo_sym):
    for fn, args in ((ex.set_margin_mode, (MARGIN_MODE, demo_sym)),
                     (ex.set_leverage, (LEVERAGE, demo_sym))):
        try:
            fn(*args)
        except Exception as e:
            m = str(e).lower()
            if "not modified" not in m and "same" not in m:
                log(f"  [{demo_sym}] setting note: {str(e)[:100]}")


def log_closed(ex, st, eq):
    try:
        r = ex.privateMixGetV2MixPositionHistoryPosition(
            {"productType": PRODUCT_TYPE, "limit": "50"})
    except Exception as e:
        log(f"history fetch note: {str(e)[:130]}"); return
    for p in (r.get("data") or {}).get("list") or []:
        pid = str(p.get("positionId"))
        if pid in st["closed_ids"]:
            continue
        raw = p.get("symbol")
        rec = st["open"].get(raw)
        if not rec:
            st["closed_ids"].append(pid); continue
        pnl = float(p.get("netProfit") or 0)
        risk_amt = rec.get("risk_amt") or 1.0
        R = pnl / risk_amt if risk_amt else 0.0
        log(f"[{rec['sid']}] CLOSED {raw} pnl={pnl:+.2f} R={R:+.2f} "
            f"(entry slip {rec.get('slip_bp', 0):+.2f}bp)")
        log_trade(rec["sid"], dict(
            ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", symbol=raw,
            side=rec.get("side"), entry=p.get("openAvgPrice"),
            exit=p.get("closeAvgPrice"), R=round(R, 3), pnl=round(pnl, 4),
            slip_bp=round(rec.get("slip_bp", 0.0), 3), equity=round(eq, 2)))
        st["closed_ids"].append(pid)
        st["open"].pop(raw, None)
    st["closed_ids"] = st["closed_ids"][-400:]


def reconcile_orders(ex, st, pos):
    """Decide what happened to each resting order: filled, expired, or gone."""
    live = open_orders(ex)
    stats = st["stats"]
    for raw, od in list(st["orders"].items()):
        oid = str(od.get("order_id"))
        still_open = oid in live
        if still_open:
            od["bars_waited"] = od.get("bars_waited", 0)
            continue
        if raw in pos:                       # order vanished and we hold a position
            p = pos[raw]
            fill = float(p.get("openAvgPrice") or od["limit"])
            d = 1 if od["side"] == "buy" else -1
            # negative slip = filled better than posted (normal for a maker fill)
            slip_bp = (fill - od["limit"]) * d / od["limit"] * 10000.0
            stats["filled"] += 1
            stats["slip_bp_sum"] += slip_bp
            log(f"[{od['sid']}] FILLED {raw} limit={od['limit']:.6g} "
                f"fill={fill:.6g} slip={slip_bp:+.2f}bp after {od.get('bars_waited',0)} bars")
            log_fill_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               sid=od["sid"], symbol=raw, event="FILLED",
                               side=od["side"], limit=od["limit"], fill=fill,
                               slip_bp=round(slip_bp, 3),
                               bars_waited=od.get("bars_waited", 0)))
            st["open"][raw] = dict(sid=od["sid"], side=od["side"], entry=fill,
                                   risk_amt=od["risk_amt"], slip_bp=slip_bp,
                                   ts=int(time.time()))
        else:
            stats["expired"] += 1
            log(f"[{od['sid']}] order gone unfilled on {raw} "
                f"(waited {od.get('bars_waited',0)} bars)")
            log_fill_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               sid=od["sid"], symbol=raw, event="UNFILLED",
                               side=od["side"], limit=od["limit"],
                               bars_waited=od.get("bars_waited", 0)))
        st["orders"].pop(raw, None)


def cancel(ex, st, raw, od, why):
    try:
        ex.cancel_order(od["order_id"], od["demo"],
                        {"productType": PRODUCT_TYPE})
        log(f"[{od['sid']}] cancelled resting order on {raw} ({why})")
    except Exception as e:
        log(f"[{od['sid']}] cancel note: {str(e)[:110]}")
    log_fill_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                       sid=od["sid"], symbol=raw, event="CANCELLED",
                       side=od["side"], limit=od["limit"],
                       bars_waited=od.get("bars_waited", 0), note=why))
    st["orders"].pop(raw, None)


def cycle(ex, st, dry=False):
    eq = demo_equity(ex)
    log_closed(ex, st, eq)
    adaptive.refresh(st, [sid_of(c) for c in BOOK.values()], log, RISK_PCT)
    pos = demo_positions(ex)
    reconcile_orders(ex, st, pos)
    s = st["stats"]
    fr = (s["filled"] / s["posted"] * 100) if s["posted"] else 0.0
    avg_slip = (s["slip_bp_sum"] / s["filled"]) if s["filled"] else 0.0
    log(f"equity={eq:.2f} SUSDT | pos={len(pos)} | resting={len(st['orders'])} | "
        f"FILL RATE {s['filled']}/{s['posted']} = {fr:.1f}% | avg slip {avg_slip:+.2f}bp")

    for real_sym, c in BOOK.items():
        sid, demo_sym, raw = sid_of(c), c["demo"], c["raw"]
        try:
            o = ex.fetch_ohlcv(real_sym, c["tf"], limit=300)
        except Exception as e:
            log(f"[{sid}] ohlcv error: {e}"); continue
        df = pd.DataFrame(o, columns=["t", "open", "high", "low", "close", "volume"])
        if len(df) < 250:
            continue
        closed = df.iloc[:-1].reset_index(drop=True)
        bar_t = int(closed["t"].iloc[-1])
        new_bar = st["seen"].get(real_sym) != bar_t
        if not new_bar:
            continue
        if not dry:
            st["seen"][real_sym] = bar_t

        if raw in pos:
            log(f"[{sid}] holding {pos[raw].get('holdSide')} "
                f"uPnL={pos[raw].get('unrealizedPL')}")
            continue

        sig = FILTERS[c["filt"]](closed, gen_signals(closed, c["fam"], c["p"]))
        action = Action(int(sig.iloc[-1]))
        a = float(atr_ind(closed, 14).iloc[-1])
        resting = st["orders"].get(raw)

        # signal gone or flipped -> pull the order
        if resting:
            resting["bars_waited"] = resting.get("bars_waited", 0) + 1
            want = ("buy" if action == Action.BUY else
                    "sell" if action == Action.SELL else None)
            if want is None or want != resting["side"]:
                if not dry:
                    cancel(ex, st, raw, resting, "signal gone/flipped")
                resting = None
            elif resting["bars_waited"] >= WAIT_BARS:
                if not dry:
                    cancel(ex, st, raw, resting, f"expired after {WAIT_BARS} bars")
                resting = None
            else:
                # RE-POST: move the limit with the market. This is the behaviour
                # that made the backtest positive - a static order misses every
                # trade where price runs away without pulling back.
                if not dry:
                    cancel(ex, st, raw, resting, "re-post at new bar")
                resting = None

        if action == Action.HOLD or not np.isfinite(a) or a <= 0:
            log(f"[{sid}] {c['tf']} flat; {action.name}")
            continue
        if len(pos) + len(st["orders"]) >= MAX_POSITIONS:
            continue
        if not st.get("_active", {}).get(sid, True):
            why = "BREAKER TRIPPED" if st.get("_tripped", {}).get(sid) else "CUT by adaptive"
            log(f"[{sid}] {why} - no new orders")
            continue

        st["stats"]["signals"] += 1
        side = "buy" if action == Action.BUY else "sell"
        d = 1 if side == "buy" else -1
        price = float(closed["close"].iloc[-1])
        limit = price - d * OFFSET_ATR * a          # post BEHIND the market
        risk_dist = SL_MULT * a
        sl, tp = limit - d * risk_dist, limit + d * TP_MULT * a
        risk_amt = eq * RISK_PCT / 100.0
        amount = risk_amt / max(risk_dist, 1e-12)
        try:
            amount = float(ex.amount_to_precision(demo_sym, amount))
            limit = float(ex.price_to_precision(demo_sym, limit))
            min_amt = ex.market(demo_sym)["limits"]["amount"]["min"] or 0
            if amount < min_amt:
                log(f"[{sid}] signal but size {amount} < min {min_amt}"); continue
        except Exception as e:
            log(f"[{sid}] sizing error: {e}"); continue

        log(f"[{sid}] {c['tf']} SIGNAL {action.name} -> POST-ONLY {side} {amount} "
            f"@{limit:.6g} (mkt {price:.6g}, {OFFSET_ATR}xATR behind) "
            f"sl={sl:.6g} tp={tp:.6g}")
        if dry:
            log(f"[{sid}] DRY: not sent"); continue

        ensure_settings(ex, demo_sym)
        try:
            r = ex.create_order(demo_sym, "limit", side, amount, limit, {
                "marginMode": MARGIN_MODE, "postOnly": True,
                "stopLoss": {"triggerPrice": float(ex.price_to_precision(demo_sym, sl))},
                "takeProfit": {"triggerPrice": float(ex.price_to_precision(demo_sym, tp))}})
            oid = str(r.get("id"))
            st["stats"]["posted"] += 1
            st["orders"][raw] = dict(sid=sid, side=side, order_id=oid, demo=demo_sym,
                                     limit=limit, risk_amt=risk_amt,
                                     risk_dist=risk_dist, bars_waited=0,
                                     ts=int(time.time()))
            log(f"[{sid}] POSTED id={oid}")
            log_fill_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               sid=sid, symbol=raw, event="POSTED", side=side,
                               limit=limit, bars_waited=0))
        except Exception as e:
            msg = str(e)[:200]
            # a post-only rejection means our limit would have crossed - useful data
            rej = "post" in msg.lower() or "40762" in msg or "immediately" in msg.lower()
            st["stats"]["rejected" if rej else "expired"] += 1
            log(f"[{sid}] ORDER {'REJECTED (would take)' if rej else 'FAILED'}: {msg}")
            log_fill_event(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               sid=sid, symbol=raw,
                               event="REJECTED" if rej else "FAILED",
                               side=side, limit=limit, note=msg[:80]))
    save_state(st)


def standings(st):
    s = st["stats"]
    log("---- maker standings ----")
    log(f"   signals={s['signals']} posted={s['posted']} filled={s['filled']} "
        f"unfilled/expired={s['expired']} rejected={s['rejected']}")
    if s["posted"]:
        log(f"   FILL RATE = {s['filled']/s['posted']*100:.1f}%  "
            f"(backtest needed >~60% at 0.5xATR to stay positive)")
    if s["filled"]:
        log(f"   avg entry slippage = {s['slip_bp_sum']/s['filled']:+.3f}bp "
            f"(<=0 expected for genuine maker fills)")
    flags, trips = st.get("_active", {}), st.get("_tripped", {})
    for c in BOOK.values():
        sid = sid_of(c)
        v = adaptive.evaluate(sid, flags.get(sid, True), RISK_PCT, bool(trips.get(sid)))
        mark = ("TRIPPED" if trips.get(sid) else
                "ACTIVE " if flags.get(sid, True) else "**CUT**")
        log(f"   {sid:24} {mark} trades={v.n:3} meanR={v.mean_r:+.3f} "
            f"dd={v.dd_pct:5.2f}% ({c['tf']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--reset-breakers", action="store_true")
    args = ap.parse_args()

    if args.reset_breakers:
        st = load_state(); done = adaptive.reset_breaker(st); save_state(st)
        log(f"breakers reset: {done or 'none were tripped'}"); return

    ex = connect()
    log(f"Bitget DEMO MAKER-ONLY | risk {RISK_PCT}% | offset {OFFSET_ATR}xATR | "
        f"expire {WAIT_BARS} bars | {LEVERAGE}x {MARGIN_MODE}")
    for rs, c in BOOK.items():
        log(f"   {c['demo']:20} <- {c['fam']}{c['p']}+{c['filt']} @ {c['tf']}")
    try:
        log(f"equity: {demo_equity(ex):.2f} SUSDT | positions: {len(demo_positions(ex))} "
            f"| resting orders: {len(open_orders(ex))}")
    except Exception as e:
        log(f"ACCOUNT READ FAILED: {str(e)[:220]}"); return
    if args.check:
        return

    st = load_state()
    if args.once or args.dry:
        cycle(ex, st, dry=args.dry); standings(st); return
    n = 0
    while True:
        try:
            cycle(ex, st)
            n += 1
            if n % 20 == 0:
                standings(st)
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:180]}")
        time.sleep(60)


if __name__ == "__main__":
    main()
