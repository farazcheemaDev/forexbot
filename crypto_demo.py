"""Multi-strategy DEMO trading on Bitget with R logging + adaptive layer.

Bitget demo is a simulated PRODUCT TYPE (SUSDT-FUTURES) on the normal API - do
NOT call set_sandbox_mode(). Only 3 demo contracts exist, and positions NET per
symbol, so each strategy gets its own symbol.

Closed positions are detected from Bitget's position history and logged in
R-multiples, which feeds the adaptive layer (cuts strategies that stop working).

Frequency note: BTC stays on the validated 1h. ETH/XRP run 15m purely to
generate trades faster - more DATA, not more risk per trade.

    python crypto_demo.py --check | --dry | --once | (no args = live loop)
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
STATE = LOGS / "demo_state.json"

PRODUCT_TYPE, MARGIN_COIN = "SUSDT-FUTURES", "SUSDT"
RISK_PCT = 0.5                  # unchanged: frequency is the lever, not size
MAX_POSITIONS = 3
LEVERAGE, MARGIN_MODE = 5, "isolated"
SL_MULT, TP_MULT = 2.0, 3.0

# real symbol (signal source) -> demo contract, strategy, timeframe
BOOK = {
    "BTC/USDT:USDT": dict(demo="SBTC/SUSDT:SUSDT", raw="SBTCSUSDT",
                          fam="rsi_mom", p=(7, 40, 60), filt="er30", tf="1h"),
    "ETH/USDT:USDT": dict(demo="SETH/SUSDT:SUSDT", raw="SETHSUSDT",
                          fam="roc_mom", p=(20, 1.0), filt="er30", tf="15m"),
    "XRP/USDT:USDT": dict(demo="SXRP/SUSDT:SUSDT", raw="SXRPSUSDT",
                          fam="bb_break", p=(30, 1.5), filt="er30", tf="15m"),
}


def sid_of(c):     # strategy id used for logs + adaptive layer
    return f"demo_{c['fam']}_{c['tf']}"


def log(msg):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOGS / "demo.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_trade(sid, row):
    f = LOGS / f"trades_{sid}.csv"
    new = not f.exists()
    with open(f, "a", encoding="utf-8") as fh:
        if new:
            fh.write("ts_utc,symbol,side,entry,exit,R,pnl,equity\n")
        fh.write(",".join(str(row[k]) for k in
                 ["ts", "symbol", "side", "entry", "exit", "R", "pnl", "equity"]) + "\n")


def load_state():
    if STATE.exists():
        return json.load(open(STATE))
    return {"open": {}, "closed_ids": [], "seen": {}, "_active": {}}


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


def log_closed(ex, st, eq):
    """Detect positions Bitget has closed and record them in R."""
    try:
        r = ex.privateMixGetV2MixPositionHistoryPosition(
            {"productType": PRODUCT_TYPE, "limit": "50"})
    except Exception as e:
        log(f"history fetch note: {str(e)[:130]}"); return
    rows = (r.get("data") or {}).get("list") or []
    for p in rows:
        pid = str(p.get("positionId"))
        if pid in st["closed_ids"]:
            continue
        raw = p.get("symbol")
        rec = st["open"].get(raw)
        if not rec:                      # opened before tracking existed
            st["closed_ids"].append(pid); continue
        pnl = float(p.get("netProfit") or 0)
        risk_amt = rec.get("risk_amt") or 1.0
        R = pnl / risk_amt if risk_amt else 0.0
        log(f"[{rec['sid']}] CLOSED {raw} pnl={pnl:+.2f} R={R:+.2f}")
        log_trade(rec["sid"], dict(
            ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", symbol=raw,
            side=rec.get("side"), entry=p.get("openAvgPrice"),
            exit=p.get("closeAvgPrice"), R=round(R, 3), pnl=round(pnl, 4),
            equity=round(eq, 2)))
        st["closed_ids"].append(pid)
        st["open"].pop(raw, None)
    st["closed_ids"] = st["closed_ids"][-400:]


def ensure_settings(ex, demo_sym):
    for fn, args in ((ex.set_margin_mode, (MARGIN_MODE, demo_sym)),
                     (ex.set_leverage, (LEVERAGE, demo_sym))):
        try:
            fn(*args)
        except Exception as e:
            m = str(e).lower()
            if "not modified" not in m and "same" not in m:
                log(f"  [{demo_sym}] setting note: {str(e)[:100]}")


def cycle(ex, st, dry=False):
    eq = demo_equity(ex)
    log_closed(ex, st, eq)
    adaptive.refresh(st, [sid_of(c) for c in BOOK.values()], log, RISK_PCT)
    pos = demo_positions(ex)
    log(f"demo equity={eq:.2f} SUSDT | open={len(pos)} {list(pos)}")

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
        if st["seen"].get(real_sym) == bar_t:
            continue
        if not dry:
            st["seen"][real_sym] = bar_t

        if raw in pos:
            log(f"[{sid}] holding {pos[raw].get('holdSide')} "
                f"uPnL={pos[raw].get('unrealizedPL')}")
            continue
        if len(pos) >= MAX_POSITIONS:
            continue
        if not st.get("_active", {}).get(sid, True):
            why = "BREAKER TRIPPED" if st.get("_tripped", {}).get(sid) else "CUT by adaptive layer"
            log(f"[{sid}] {why} - no new entries")
            continue

        sig = FILTERS[c["filt"]](closed, gen_signals(closed, c["fam"], c["p"]))
        action = Action(int(sig.iloc[-1]))
        a = float(atr_ind(closed, 14).iloc[-1])
        if action == Action.HOLD or not np.isfinite(a) or a <= 0:
            log(f"[{sid}] {c['tf']} flat; {action.name}")
            continue

        side = "buy" if action == Action.BUY else "sell"
        d = 1 if side == "buy" else -1
        price = float(closed["close"].iloc[-1])
        risk_dist = SL_MULT * a
        sl, tp = price - d * risk_dist, price + d * TP_MULT * a
        risk_amt = eq * RISK_PCT / 100.0
        amount = risk_amt / max(risk_dist, 1e-12)
        try:
            amount = float(ex.amount_to_precision(demo_sym, amount))
            min_amt = ex.market(demo_sym)["limits"]["amount"]["min"] or 0
            if amount < min_amt:
                log(f"[{sid}] signal but size {amount} < min {min_amt}"); continue
        except Exception as e:
            log(f"[{sid}] sizing error: {e}"); continue

        log(f"[{sid}] {c['tf']} SIGNAL {action.name} -> {side} {amount} @~{price:.4f} "
            f"sl={sl:.4f} tp={tp:.4f} risk={risk_amt:.2f}")
        if dry:
            log(f"[{sid}] DRY: not sent"); continue

        ensure_settings(ex, demo_sym)
        try:
            r = ex.create_order(demo_sym, "market", side, amount, None, {
                "marginMode": MARGIN_MODE,
                "stopLoss": {"triggerPrice": float(ex.price_to_precision(demo_sym, sl))},
                "takeProfit": {"triggerPrice": float(ex.price_to_precision(demo_sym, tp))}})
            log(f"[{sid}] ORDER OK id={r.get('id')}")
            st["open"][raw] = dict(sid=sid, side=side, entry=price,
                                   risk_amt=risk_amt, risk_dist=risk_dist,
                                   ts=int(time.time()))
            pos[raw] = {"symbol": raw}
        except Exception as e:
            log(f"[{sid}] ORDER FAILED: {type(e).__name__}: {str(e)[:200]}")
    save_state(st)


def standings(st):
    log("---- demo standings ----")
    flags, trips = st.get("_active", {}), st.get("_tripped", {})
    for c in BOOK.values():
        sid = sid_of(c)
        v = adaptive.evaluate(sid, flags.get(sid, True), RISK_PCT, bool(trips.get(sid)))
        mark = ("TRIPPED" if trips.get(sid) else
                "ACTIVE " if flags.get(sid, True) else "**CUT**")
        log(f"   {sid:22} {mark} trades={v.n:3} meanR={v.mean_r:+.3f} "
            f"net={v.net_pct:+6.2f}% dd={v.dd_pct:5.2f}% streak={v.streak}  ({c['tf']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--reset-breakers", action="store_true",
                    help="manually close any latched circuit breakers")
    args = ap.parse_args()

    if args.reset_breakers:
        st = load_state()
        done = adaptive.reset_breaker(st)
        save_state(st)
        log(f"breakers reset: {done or 'none were tripped'}")
        return

    ex = connect()
    log(f"Bitget DEMO | risk {RISK_PCT}% | max {MAX_POSITIONS} | {LEVERAGE}x {MARGIN_MODE}")
    for rs, c in BOOK.items():
        log(f"   {c['demo']:20} <- {c['fam']}{c['p']}+{c['filt']} @ {c['tf']}")
    try:
        log(f"demo equity: {demo_equity(ex):.2f} SUSDT | positions: {len(demo_positions(ex))}")
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
