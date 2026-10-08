"""LIVE COMBINATION BOT - the three books of combo_paper.py, executed on ONE Bitget account.

WHAT IT DOES
    The DECISIONS are combo_paper.py's own code, run in this process on this bot's own state:
      trend   blend_paper.cycle(triple=True), sized by the 21-day equity anchor, 9x gross guard
      MN      mn_paper.py's basket functions, 1x, rebalanced every 7 days
      sleeve  the bear breadth sleeve, 1x, only in BTC BEAR regimes
    The EXECUTION is new. Every poll it adds up what the three books want to hold in each coin,
    reads what the account actually holds, and sends ONE market order per coin for the
    difference. A Bitget account in one-way mode holds one net position per coin, so the books
    cannot place their own orders without fighting each other; netting is the only correct way.

SAFETY, IN THE ORDER IT MATTERS
    1. ALLOW_REAL = False below. `--mode live` refuses to start until a HUMAN edits it. Nothing
       in this file sets it.
    2. One account, one bot. Refuses to start in demo/live mode if longtrend_bot.py or another
       combo_bot is running (it would double every order).
    3. CROSS margin, not isolated. With isolated 10x an alt position is liquidated ~9% against
       entry, which is INSIDE many 4h/12h trend stops; cross lets the whole account back every
       position, which is what the backtests' 10x gross guard assumes.
    4. A DISASTER STOP on every net position, 30% beyond the mark, re-placed when the position
       changes. It is not the strategy's exit (the books exit at market); it is the backstop if
       this process or its machine dies. It does NOT protect the market-neutral shorts while the
       bot runs - the netting re-opens a stopped position - which is why 4b exists.
    4b. THE MN SHORT-LEG EXIT (2026-10-08, mn_squeeze_exits): a market-neutral short 50% above the
       price it was opened at is dropped by the book until the next rebalance, so it is closed AND
       stays closed. On one of the 7 weekdays the book could rebalance on, the 2025-09-12 squeeze
       (MYX) cost the unprotected book 99% of the account (backtest/mn_combos.py).
    5. PRICE SANITY: an order is refused if the venue's price differs from Binance's by more
       than 3%, which is what a symbol-name mismatch (1000PEPE vs PEPE) looks like.
    6. Orders under $5 are not sent, except a full close, which always goes.
    7. THE ACCOUNT MUST BE DEDICATED TO THIS BOT. It nets the whole account to what its books
       want, so any position it did not open - a manual trade, another bot's leftover - is
       CLOSED on the first poll. On the demo that is intended (longtrend_bot's leftovers); on
       a real account, never trade it by hand while this runs.

MODES
    demo  Bitget demo (SUSDT-FUTURES). The demo lists only SBTC / SETH / SXRP, so every coin a
          book wants is ROUTED onto one of those three by dollar value. That makes the demo a
          stress test of the order path - netting, crossing zero, reduce-only, stops - and its
          P&L meaningless. Sized as a $221 account (the demo pays from ~2,900 SUSDT).
    dry   No keys, no orders. Live Binance data for every coin, Bitget's REAL market list for
          mapping and precision, and a virtual position ledger. Proves the decisions and the
          symbol mapping for all coins, which the 3-coin demo cannot.
    live  Real USDT-FUTURES with the account's real equity. Refused unless ALLOW_REAL is True.

THE FINAL MACHINE (--final, 2026-10-09, final_books.py)
    Adds to the books above: the MN book ranked half by momentum / half by RSI(14), funding carry at 0.5x, the daily
    Bollinger book with the 20-day-mean exit at 0.5x, the improved capitulation book (capit2) at 0.5x - and holds the
    WHOLE account under 10x gross (the trend book's own guard drops to 6.25x). Its own state in
    logs/combo_bot_<mode>_final/, paper equity $300. On the VM as combo-bot-final.service, --mode dry.

    python combo_bot.py --mode dry --final  the final machine, paper (VM: combo-bot-final.service)
    python combo_bot.py --mode demo       order-path test on the demo account
    python combo_bot.py --mode dry        all coins, no orders
    python combo_bot.py --mode live       real money (after a human sets ALLOW_REAL = True)
    python combo_bot.py --mode demo --status
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import combo_paper as cp  # noqa: E402
import wick_live as wl  # noqa: E402

# ---------------------------------------------------------------- the hard gate
ALLOW_REAL = False

VENUE = {"demo": dict(product="SUSDT-FUTURES", margin="SUSDT", quote="SUSDT", prefix="S"),
         "live": dict(product="USDT-FUTURES", margin="USDT", quote="USDT", prefix=""),
         "dry": dict(product="USDT-FUTURES", margin="USDT", quote="USDT", prefix="")}
DEMO_COINS = ("BTCUSDT", "ETHUSDT", "XRPUSDT")
VIRTUAL_EQUITY = {"demo": 221.0, "dry": 221.0, "live": None}
MIN_ORDER = 5.0
CAT_STOP = 0.30
MN_SHORT_EXIT = 0.50              # backtest/mn_combos.py, logs/mn_rebalance_days.txt (2026-10-08): see mn_squeeze_exits
PRICE_TOL = 0.03
MARGIN_MODE, LEVERAGE = "cross", 20
POLL_S = 120
FAPI = "https://fapi.binance.com"


def log(m: str):
    cp.log(m)


# ---------------------------------------------------------------- targets (pure, tested)

def book_targets(st: dict) -> dict:
    """What the three books want to hold, in COINS per Binance symbol (signed)."""
    out: dict = {}

    def add(sym, q):
        out[sym] = out.get(sym, 0.0) + q
    for key, rec in st["trend"]["open"].items():
        if rec.get("breached"):
            continue                 # its stop was crossed intrabar: out now, see mark_breaches
        d = 1 if rec["side"] == "long" else -1
        add(key.split(":")[0], d * rec.get("units", 1) * rec["notional"] / rec["entry"])
    for sym, q in st.get("exec", {}).get("mn_qty", {}).items():
        add(sym, q)
    sl = st["sleeve"]
    for sym, n in sl["hold"].items():
        px = sl["mark_px"].get(sym)
        if px:
            add(sym, n / px)
    for sym, q in st.get("wick", {}).get("hold", {}).items():   # crash-bid fills (wick_live.py)
        add(sym, q)
    if st.get("fin"):                                            # --final: carry, daily, capit2 (final_books.py)
        import final_books as fb
        for sym, q in fb.targets(st).items():
            add(sym, q)
    return {s: q for s, q in out.items() if abs(q) > 0}


def mark_breaches(st: dict, prices: dict) -> list:
    """Trend stops, checked EVERY POLL against the live price.

    blend_paper.cycle judges a stop when the bar CLOSES, and books the exit at the stop level -
    the backtest's assumption. Live, waiting for the close would exit a 12h position up to 12
    hours after the breach, at whatever price then. So: the moment the live price crosses a
    trend position's stop, the position is flagged and the account exits at market; the paper
    book still books it at the bar close, where the bar's low/high shows the same breach.
    STICKY: if the price bounces back before the close, the flag stays - re-buying a stop-out
    inside the same bar would be a trade the strategy never makes."""
    hit = []
    for key, rec in st["trend"]["open"].items():
        if rec.get("breached"):
            continue
        px = prices.get(key.split(":")[0])
        if not px:
            continue
        if (rec["side"] == "long" and px <= rec["stop"]) or (rec["side"] == "short" and px >= rec["stop"]):
            rec["breached"] = True
            hit.append(key)
            log(f"TREND {key}: live price {px:.6g} crossed the stop {rec['stop']:.6g} - exiting now")
    return hit


def mn_squeeze_exits(st: dict, prices: dict) -> list:
    """The market-neutral book's SHORT-LEG EXIT, checked every poll (added 2026-10-08).

    WHY. backtest/mn_combos.py ran the MN book on all 7 days of the week it could rebalance on (every earlier figure
    used one). On one of them the 2025-09-12 week cost 99% of the account: MYX squeezed the short basket. The 30%
    disaster stop below is no protection - it is a backstop for a dead process, and the netting re-opens a stopped
    position two minutes later because the book still wants it. The fix that tested free on average (Sharpe +1.06 /
    +1.31 vs +1.06 / +1.33 over the 7 days, worst week -29% instead of -99%) is a BOOK exit: once a short's live price
    is MN_SHORT_EXIT above the price the book opened it at, the book drops that name until the next rebalance.

    HOW. The opening price needs no new state: mn_quantities fixed each name's coins at the rebalance as
    weight x base / price, so price = weight x base / coins. The exit removes the name from the basket's weights and
    from mn_qty (so book_targets stops wanting it and plan_orders closes it), and books the book's P&L from its last
    daily mark to the live price plus one side's fee. combo_paper.py, the pre-registered paper book, is NOT changed:
    this lives only in the bot. The next rebalance picks a fresh basket, which may include the name again."""
    mn, ex = st.get("mn", {}), st.setdefault("exec", {})
    qty = ex.get("mn_qty", {})
    out = []
    for s, w in list(mn.get("weights", {}).items()):
        q, px = qty.get(s), prices.get(s)
        if w >= 0 or not q or not px or not mn.get("base"):
            continue
        opened = w * mn["base"] / q
        if px < opened * (1 + MN_SHORT_EXIT):
            continue
        mark = mn.get("mark_px", {}).get(s, opened)
        pnl = mn["base"] * w * (px / mark - 1)
        fee = abs(q) * px * cp.SIDE_FEE
        st["equity"] = st.get("equity", 0.0) + pnl - fee
        cum = st.setdefault("cum", {})
        cum["mn"] = cum.get("mn", 0.0) + pnl
        cum["fees"] = cum.get("fees", 0.0) + fee
        mn["weights"].pop(s, None)
        mn.get("mark_px", {}).pop(s, None)
        qty.pop(s, None)
        ex.setdefault("mn_exits", []).append(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", symbol=s,
                                                  opened=opened, price=px, pnl=round(pnl, 6)))
        cp.append(cp.P["state"].parent / "combo_mn_exits.csv",
                  dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", symbol=s, opened=f"{opened:.8g}",
                       price=f"{px:.8g}", rise=f"{px / opened - 1:+.3f}", pnl=f"{pnl:.4f}", fee=f"{fee:.4f}"))
        log(f"MN EXIT {s}: short opened at {opened:.6g}, live {px:.6g} ({px / opened - 1:+.0%}) - the book drops it "
            f"until the next rebalance (P&L since the last mark {pnl:+.2f}, fee {fee:.2f})")
        out.append(s)
    return out


def mn_quantities(st: dict) -> dict:
    """The MN basket as fixed coin quantities, from the weights and the prices it was set at."""
    mn = st["mn"]
    return {s: w * mn["base"] / mn["mark_px"][s] for s, w in mn["weights"].items()
            if mn["mark_px"].get(s)}


def proxy(sym: str) -> str:
    return sym if sym in DEMO_COINS else DEMO_COINS[zlib.crc32(sym.encode()) % len(DEMO_COINS)]


def route_demo(targets: dict, prices: dict) -> dict:
    """Demo only: every coin onto BTC / ETH / XRP by DOLLAR value (see MODES)."""
    out: dict = {}
    for s, q in targets.items():
        p, pp = prices.get(s), prices.get(proxy(s))
        if not p or not pp:
            continue
        out[proxy(s)] = out.get(proxy(s), 0.0) + q * p / pp
    return out


def plan_orders(targets: dict, actual: dict, prices: dict, min_order: float = MIN_ORDER):
    """Orders that move `actual` to `targets` (both signed coin quantities by symbol).
    Returns [(sym, side, qty, reduce_only, why)]. A position that changes sign is closed
    first (reduce-only) and reopened, so no single order both closes and opens."""
    orders = []
    for s in sorted(set(targets) | set(actual)):
        tgt, act = targets.get(s, 0.0), actual.get(s, 0.0)
        px = prices.get(s)
        if not px:
            continue
        diff = tgt - act
        full_close = tgt == 0 and act != 0
        if abs(diff) * px < min_order and not full_close:
            continue
        if act != 0 and (tgt == 0 or (tgt > 0) != (act > 0)):
            orders.append((s, "sell" if act > 0 else "buy", abs(act), True, "close"))
            if tgt != 0 and abs(tgt) * px >= min_order:
                orders.append((s, "buy" if tgt > 0 else "sell", abs(tgt), False, "open"))
        elif abs(tgt) < abs(act):
            orders.append((s, "sell" if act > 0 else "buy", abs(diff), True, "reduce"))
        else:
            orders.append((s, "buy" if diff > 0 else "sell", abs(diff), False,
                           "open" if act == 0 else "add"))
    return orders


# ---------------------------------------------------------------- exchange plumbing

class Venue:
    """Everything that touches the exchange. `ex` is a ccxt bitget instance (or a fake)."""

    def __init__(self, ex, mode: str):
        self.ex, self.mode, self.v = ex, mode, VENUE[mode]
        self.set_done: set = set()

    def symbol(self, sym: str) -> "str | None":
        base = sym[:-4]
        s = f"{self.v['prefix']}{base}/{self.v['quote']}:{self.v['quote']}"
        return s if s in self.ex.markets else None

    def rules(self, s: str) -> tuple:
        """(amount step, minimum amount, minimum order value) for s, from the venue's OWN market
        record (load_markets), not a table. Bitget's amount minimum is also its step - 1 whole
        LINK, 0.1 LTC, 10,000 SHIB - and its value floor is $5 (backtest/bitget_minimums.py).
        ccxt reports bitget's precision as a TICK SIZE; a decimal-places exchange is converted."""
        m = self.ex.market(s)
        p = (m.get("precision") or {}).get("amount")
        step = float(p or 0.0)
        if p and getattr(self.ex, "precisionMode", 4) == 2:      # ccxt DECIMAL_PLACES
            step = 10.0 ** -float(p)
        lim = m.get("limits") or {}
        amin = float((lim.get("amount") or {}).get("min") or 0.0)
        cmin = float((lim.get("cost") or {}).get("min") or MIN_ORDER)
        return step, amin, cmin

    def contracts(self, s: str, qty: float, nearest: bool = False) -> float:
        """qty coins as venue contracts. nearest=True rounds to the NEAREST step: ccxt's
        amount_to_precision truncates, which at a 1-LINK step turned 1.9 LINK into 1 - every
        accepted order biased small (median 9.4% on LINK at $221, CLAUDE.md 7b)."""
        cs = float(self.ex.market(s).get("contractSize") or 1.0)
        n = abs(qty) / cs
        step = self.rules(s)[0]
        if nearest and step > 0:
            n = round(n / step) * step + step * 1e-9      # the nudge survives the truncation
        return float(self.ex.amount_to_precision(s, n))

    def refusal(self, s: str, n: float, px: float, reduce: bool) -> "str | None":
        """Why the venue would refuse n contracts at px - or None. The reason is a fixed phrase
        (no sizes in it) so a refusal is logged once, not once per poll."""
        step, amin, cmin = self.rules(s)
        cs = float(self.ex.market(s).get("contractSize") or 1.0)
        if n <= 0:
            return "rounds to zero at the venue's step"
        if n < amin - 1e-12:
            return f"under the {amin:g}-contract minimum amount"
        if not reduce and n * cs * px < cmin:
            return f"under the ${cmin:g} minimum order value"
        return None

    def positions(self) -> dict:
        """{venue symbol: signed coin quantity}."""
        r = self.ex.privateMixGetV2MixPositionAllPosition(
            {"productType": self.v["product"], "marginCoin": self.v["margin"]})
        by_id = {m["id"]: k for k, m in self.ex.markets.items()}
        out = {}
        for p in (r.get("data") or []):
            q = float(p.get("total") or 0)
            if q <= 0:
                continue
            sign = -1 if str(p.get("holdSide", "")).lower() in ("short", "sell") else 1
            s = by_id.get(p["symbol"])
            if s:
                out[s] = out.get(s, 0.0) + sign * q
        return out

    def equity(self) -> float:
        r = self.ex.privateMixGetV2MixAccountAccounts({"productType": self.v["product"]})
        for a in r.get("data", []):
            if a.get("marginCoin") == self.v["margin"]:
                return float(a.get("accountEquity") or 0)
        return 0.0

    def settings(self, s: str):
        if s in self.set_done:
            return
        for fn, args in ((self.ex.set_margin_mode, (MARGIN_MODE, s)),
                         (self.ex.set_leverage, (LEVERAGE, s))):
            try:
                fn(*args)
            except Exception as e:
                m = str(e).lower()
                if "not modified" not in m and "same" not in m:
                    log(f"  [{s}] setting note: {str(e)[:120]}")
        self.set_done.add(s)

    def last(self, s: str) -> float:
        return float(self.ex.fetch_ticker(s)["last"])

    def order(self, s: str, side: str, contracts: float, reduce: bool):
        params = {"reduceOnly": True} if reduce else {}
        return self.ex.create_order(s, "market", side, contracts, None, params)

    def stop(self, s: str, side: str, contracts: float, trigger: float):
        return self.ex.create_order(s, "market", side, contracts, None,
                                    {"triggerPrice": float(self.ex.price_to_precision(s, trigger)),
                                     "reduceOnly": True})

    def cancel(self, s: str, oid: str):
        self.ex.cancel_order(oid, s, {"trigger": True})

    # ---- the crash-bid desk (wick_live.py): limit buys only
    def coin_size(self, s: str) -> float:
        return float(self.ex.market(s).get("contractSize") or 1.0)

    def prev_close(self, s: str, H: int) -> "float | None":
        """The close of the venue's own 1-hour candle that ended at H (seconds)."""
        for c in self.ex.fetch_ohlcv(s, "1h", since=(H - 3600) * 1000, limit=3):
            if int(c[0]) == (H - 3600) * 1000:
                return float(c[4])
        return None

    def limit_buy(self, s: str, contracts: float, price: float):
        return self.ex.create_order(s, "limit", "buy", contracts,
                                    float(self.ex.price_to_precision(s, price)), {"postOnly": True})

    def cancel_limit(self, s: str, oid: str):
        self.ex.cancel_order(oid, s)

    def pending(self) -> dict:
        """{order id: filled contracts} for every resting (non-trigger) order on the account."""
        r = self.ex.privateMixGetV2MixOrderOrdersPending({"productType": self.v["product"]})
        by_id = {m["id"]: k for k, m in self.ex.markets.items()}
        out = {}
        for x in ((r.get("data") or {}).get("entrustedList") or []):
            s = by_id.get(x.get("symbol"))
            cs = self.coin_size(s) if s else 1.0
            out[str(x["orderId"])] = float(x.get("baseVolume") or 0) / cs
        return out

    def filled(self, s: str, oid: str) -> float:
        return float(self.ex.fetch_order(oid, s).get("filled") or 0)


def fill_price(ex, o, fallback: float, sym: "str | None" = None):
    """The price the order REALLY filled at, and where that number came from. Bitget's
    create-order response carries no fill price (the first demo poll logged every fill as
    'assumed'), so the order is re-read by id, as longtrend_bot.actual_fill does. Any failure
    falls back to the assumed price and says so - recording must never break trading."""
    if isinstance(o, dict):
        for k in ("average", "price"):
            if o.get(k):
                try:
                    return float(o[k]), k
                except (TypeError, ValueError):
                    pass
        if o.get("id") and sym and ex is not None:
            for _ in range(3):
                try:
                    r = ex.fetch_order(o["id"], sym)
                    for k in ("average", "price"):
                        if r.get(k):
                            return float(r[k]), f"fetch_order.{k}"
                except Exception:
                    pass
                time.sleep(0.5)
    return float(fallback), "assumed"


def binance_prices() -> dict:
    with urllib.request.urlopen(f"{FAPI}/fapi/v1/ticker/price", timeout=20) as r:
        return {x["symbol"]: float(x["price"]) for x in json.loads(r.read().decode())}


# ---------------------------------------------------------------- execution

def execute(st: dict, venue: "Venue | None", mode: str, prices: dict, dry: bool):
    """Reconcile the account (or the dry-run ledger) to the books. Returns orders sent."""
    ex_state = st.setdefault("exec", {})
    mark_breaches(st, prices)
    mn_squeeze_exits(st, prices)
    if st.get("fin"):
        import final_books as fb
        fb.carry_squeeze_exits(st, prices, MN_SHORT_EXIT, rec=final_record)
    tgt = book_targets(st)
    if mode == "demo":
        tgt = route_demo(tgt, prices)
    # translate to venue symbols; unmappable coins are skipped, and said so once each
    vt, vp, skipped = {}, {}, ex_state.setdefault("unmapped", [])
    for sym, q in tgt.items():
        s = venue.symbol(sym) if venue else sym
        if s is None:
            if sym not in skipped:
                skipped.append(sym)
                log(f"EXEC: {sym} is not listed on this venue - that book's {q:+.6g} is not traded")
            continue
        vt[s] = vt.get(s, 0.0) + q
        vp[s] = prices.get(sym)
    actual = dict(ex_state.get("virtual_pos", {})) if (dry or venue is None) else venue.positions()
    # a held coin no book wants any more needs a price too, or it is never closed. Until 2026-10-09 only the venue
    # branch looked these up, so the DRY ledger kept every position its books had exited (tests/test_final_books.py)
    by_venue = ({venue.symbol(b): b for b in prices if b.endswith("USDT")} if venue else {b: b for b in prices}) \
        if actual else {}
    for s in actual:
        if s not in vp and s in by_venue:
            vp[s] = prices.get(by_venue[s])
    sent = []
    refused = ex_state.setdefault("refused", {})
    orders = plan_orders(vt, actual, vp)
    if st.get("fin"):
        # THE ACCOUNT-LEVEL 10x GUARD (--final): the books are sized separately, so their sum is held here
        import final_books as fb
        orders, over = fb.gross_gate(orders, actual, vp, float(st["equity"]))
        for s, side, qty, reduce, why in over:
            if refused.get(s) != "gross":
                refused[s] = "gross"
                log(f"EXEC {s}: {side} {qty:.6g} ({why}) NOT SENT - the account would pass {fb.GROSS_CAP:g}x gross")
    for s, side, qty, reduce, why in orders:
        px = vp.get(s)
        if not px:
            continue
        if venue is not None:
            # THE VENUE'S OWN MINIMUMS (fixed 2026-09-29). Before this, anything over a flat $5
            # was sent and Bitget refused what was under its per-coin amount minimum - and the
            # bot re-sent it every poll: 188 of the demo's 230 order failures, one every 2:10,
            # which also made the two-week PASS check unreadable. Now: round to the nearest
            # step, and an order the venue cannot accept is NOT SENT, logged once. A full close
            # always goes - the position was accepted when it was opened.
            n = venue.contracts(s, qty, nearest=(why != "close"))
            no = None if why == "close" else venue.refusal(s, n, px, reduce)
            if no:
                if refused.get(s) != no:
                    refused[s] = no
                    log(f"EXEC {s}: {side} {qty:.6g} ({why}) BELOW VENUE MINIMUM, not sent - {no}. "
                        f"Held as is until the target moves.")
                continue
            refused.pop(s, None)
            qty = n * float(venue.ex.market(s).get("contractSize") or 1.0)   # what is traded
        if venue is not None and not dry:
            try:
                vlast = venue.last(s)
            except Exception as e:
                log(f"EXEC {s}: no venue price ({str(e)[:80]}) - skipped this poll"); continue
            if abs(vlast / px - 1) > PRICE_TOL:
                log(f"EXEC {s}: venue {vlast:.6g} vs Binance {px:.6g} differ > {PRICE_TOL:.0%} "
                    f"- REFUSED (symbol mismatch?)"); continue
            try:
                if n <= 0:
                    continue
                if not reduce:
                    venue.settings(s)
                o = venue.order(s, side, n, reduce)
                got, src = fill_price(venue.ex, o, vlast, s)
            except Exception as e:
                log(f"EXEC {s}: ORDER FAILED {side} {qty:.6g} ({why}): {str(e)[:160]}"); continue
        else:
            got, src = px, "dry"
            vpos = ex_state.setdefault("virtual_pos", {})
            vpos[s] = vpos.get(s, 0.0) + (qty if side == "buy" else -qty)
            if abs(vpos[s]) * px < 1e-9:
                vpos.pop(s)
        slip = (got / px - 1) * 1e4 * (1 if side == "buy" else -1)
        cp.append(cp.P["state"].parent / "combo_exec.csv",
                  dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", mode=mode, symbol=s,
                       side=side, qty=f"{qty:.8g}", why=why, reduce=int(reduce), ref_px=f"{px:.8g}",
                       fill=f"{got:.8g}", src=src, slip_bp=f"{slip:+.1f}", notional=f"{qty*px:.2f}"))
        log(f"EXEC {s}: {side.upper()} {qty:.6g} (${qty*px:.2f}, {why}{', reduce-only' if reduce else ''}) "
            f"filled {got:.6g} [{src}] slip {slip:+.1f}bp")
        sent.append((s, side, qty, reduce, why))
    if venue is not None and not dry:
        stops(st, venue)
    return sent


def stops(st: dict, venue: "Venue"):
    """One disaster stop per net position, CAT_STOP beyond the mark, re-placed when the
    position's size or side changes, cancelled when it is flat."""
    have = st["exec"].setdefault("stops", {})
    try:
        pos = venue.positions()
    except Exception as e:
        log(f"STOPS: cannot read positions ({str(e)[:100]})"); return
    for s in list(have):
        if s not in pos or abs(have[s]["qty"] - pos[s]) > 1e-12:
            try:
                venue.cancel(s, have[s]["id"])
            except Exception as e:
                log(f"STOP {s}: cancel note {str(e)[:100]}")
            have.pop(s)
    for s, q in pos.items():
        if s in have:
            continue
        try:
            px = venue.last(s)
            trig = px * (1 - CAT_STOP) if q > 0 else px * (1 + CAT_STOP)
            o = venue.stop(s, "sell" if q > 0 else "buy", venue.contracts(s, q), trig)
            have[s] = dict(id=str(o.get("id")), qty=q, trigger=trig)
            log(f"STOP {s}: disaster stop for {q:+.6g} at {trig:.6g} ({CAT_STOP:.0%} beyond {px:.6g})")
        except Exception as e:
            log(f"STOP {s}: FAILED to place ({str(e)[:140]}) - position has no exchange backstop")


# ---------------------------------------------------------------- one account, one bot

def running_bots() -> list:
    """Command lines of OTHER python processes that trade a Bitget account: longtrend_bot.py,
    or another combo_bot.py (not --status). This process is excluded BY PID."""
    me = os.getpid()
    procs = {}
    try:
        if platform.system() == "Windows":
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                  "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | "
                                  "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
                                 capture_output=True, text=True, timeout=30).stdout
            data = json.loads(out) if out.strip() else []
            data = [data] if isinstance(data, dict) else data
            procs = {int(d["ProcessId"]): (d.get("CommandLine") or "") for d in data}
        else:
            out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True,
                                 timeout=30).stdout
            for ln in out.splitlines():
                pid, _, args = ln.strip().partition(" ")
                if pid.isdigit():
                    procs[int(pid)] = args
    except Exception:
        return ["<cannot list processes - refusing to guess>"]
    return [f"pid {p}: {c}" for p, c in procs.items() if p != me and (
        "longtrend_bot.py" in c or ("combo_bot.py" in c and "--status" not in c))]


def guard_one_bot(mode: str, lister=running_bots):
    if mode == "dry":
        return
    others = [x for x in lister() if "--mode dry" not in x]
    if others:
        raise SystemExit("REFUSING TO START: another bot is trading this account (one account, "
                         "one bot - two would double every order):\n  " + "\n  ".join(others)
                         + "\nStop it first (the demo account ran longtrend_bot.py).")


def resolve(mode: str):
    if mode == "live" and not ALLOW_REAL:
        raise SystemExit("REFUSING --mode live: ALLOW_REAL is False in combo_bot.py. This is the "
                         "hard gate on real funds, and only a human sets it.")


def connect(mode: str):
    import ccxt
    if mode == "dry":
        ex = ccxt.bitget({"enableRateLimit": True, "options": {"defaultType": "swap"}})
        ex.load_markets()
        return ex
    key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                    os.getenv("BITGET_PASSWORD"))
    if not all([key, sec, pw]):
        raise SystemExit("Set BITGET_API_KEY / BITGET_SECRET / BITGET_PASSWORD in the environment")
    ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw, "enableRateLimit": True,
                      "options": {"defaultType": "swap"}})
    ex.load_markets()
    try:
        ex.privateMixPostV2MixAccountSetPositionMode(
            {"productType": VENUE[mode]["product"], "posMode": "one_way_mode"})
    except Exception as e:
        log(f"position-mode note: {str(e)[:120]}")
    return ex


# ---------------------------------------------------------------- the two-week check

PASS_DAYS, PASS_SLIP_BP, FLIP_S = 14, 5.0, 90


def flips(x) -> int:
    """Positions that changed side in one go. plan_orders sends a reduce-only CLOSE and then an
    OPEN on the same symbol, on the same side (closing a long and opening a short are both
    sells), in the same poll - so they sit next to each other in combo_exec.csv, seconds apart."""
    r = x.sort_values("ts", kind="stable").reset_index(drop=True)
    return sum(1 for i in range(1, len(r))
               if r.why[i - 1] == "close" and r.why[i] == "open" and r.symbol[i - 1] == r.symbol[i]
               and r.side[i - 1] == r.side[i] and (r.ts[i] - r.ts[i - 1]).total_seconds() <= FLIP_S)


def verdict(x, lg: str, days: float) -> list:
    """What the two-week check still lacks; an empty list is a PASS. 'A few bp' is read as a
    median slippage of at most PASS_SLIP_BP against us."""
    miss = [] if days >= PASS_DAYS else [f"{days:.1f} of {PASS_DAYS} days"]
    for key, lab in (("ORDER FAILED", "order failures"), ("FAILED to place", "stop placement failures"),
                     ("poll error", "poll errors")):
        if lg.count(key):
            miss.append(f"{lg.count(key)} {lab}")
    if (x.src == "assumed").any():
        miss.append(f"{int((x.src == 'assumed').sum())} unpriced fills")
    real = x[x.src.astype(str).str.startswith(("fetch_order", "average", "price"))]
    if len(real) and real.slip_bp.median() > PASS_SLIP_BP:
        miss.append(f"median slippage {real.slip_bp.median():+.1f}bp > {PASS_SLIP_BP:g}bp")
    miss += [f"no {k} yet" for k in ("open", "add", "reduce", "close") if not (x.why == k).any()]
    if not flips(x):
        miss.append("no flip yet")
    return miss


def report(d: Path):
    """What the demo (or dry) run has proved so far, in one screen."""
    import pandas as pd
    f = d / "combo_exec.csv"
    lg = (d / "combo_paper.log").read_text(encoding="utf-8", errors="replace") if (d / "combo_paper.log").exists() else ""
    print(f"\nCOMBO BOT CHECK - {d.name}")
    if not f.exists():
        print("  no orders yet"); return
    x = pd.read_csv(f)
    x["ts"] = pd.to_datetime(x["ts"])
    days = max((x.ts.max() - x.ts.min()).total_seconds() / 86400, 0)
    print(f"  orders {len(x)} over {days:.1f} days | by kind: " + ", ".join(
        f"{k} {v}" for k, v in x.why.value_counts().items()) + f" | reduce-only {int(x.reduce.sum())}")
    real = x[x.src.astype(str).str.startswith(("fetch_order", "average", "price"))]
    if len(real):
        print(f"  REAL fills {len(real)}: slippage vs the Binance reference median {real.slip_bp.median():+.1f}bp, "
              f"mean {real.slip_bp.mean():+.1f}bp, worst {real.slip_bp.max():+.1f}bp against us")
    print(f"  fills with no recorded price ('assumed'): {int((x.src == 'assumed').sum())}")
    for key, lab in (("ORDER FAILED", "order failures"), ("STOP", "stop events"), ("FAILED to place", "stop placement failures"),
                     ("REFUSED", "price-sanity refusals"), ("crossed the stop", "intrabar trend exits"),
                     ("poll error", "poll errors"), ("not listed on this venue", "unmapped coins"),
                     ("BELOW VENUE MINIMUM", "held under the venue min")):
        print(f"  {lab:<26}{lg.count(key):>5}")
    print(f"  {'flips (long <-> short)':<26}{flips(x):>5}")
    print(f"  PASS when: {PASS_DAYS} days, no order failures, no stop placement failures, no poll errors,\n"
          f"  every fill priced, median slippage <= {PASS_SLIP_BP:g}bp, and at least one of each: open, add,\n"
          "  reduce, close, a flip.")
    miss = verdict(x, lg, days)
    print("  VERDICT: PASS - the order path works. Going live is a human decision (ALLOW_REAL).\n"
          if not miss else "  VERDICT: NOT YET - " + "; ".join(miss) + "\n")


# ---------------------------------------------------------------- the crash-bid desk

def make_desk(st: dict, venue, args):
    """wick_live.WickDesk wired to this bot: the demo bids only on its three coins; live and dry use
    the top-40 (wick_paper.universe) and the BTC label (wick_paper.label)."""
    import wick_paper as wp
    mode = args.mode
    coins = (lambda m: list(DEMO_COINS)) if mode == "demo" else wp.universe

    def equity():
        return venue.equity() if VIRTUAL_EQUITY[mode] is None else float(st["equity"])
    desk = wl.WickDesk(venue, coins, wp.label, equity, log,
                       dist=args.wick_dist if args.wick_dist is not None else wl.BID_K,
                       cap=args.wick_cap if args.wick_cap is not None else wl.CAP, dry=(mode == "dry"),
                       record=lambda row: cp.append(cp.P["state"].parent / "combo_wick.csv", row),
                       size_usd=args.wick_usd)
    log(f"  CRASH DESK on: bids {desk.dist:.1%} under the last close, cap {desk.cap} fills an hour, "
        f"checked every {wl.TICK_S}s; sold at the hour's close through the netting")
    return desk


# ---------------------------------------------------------------- main

def warm_start(st: dict) -> int:
    """Entry signals only from bars that close AFTER this process starts.

    blend_paper.cycle acts on the last CLOSED bar. On a fresh start (or after downtime) that bar
    can have closed hours ago - up to 12h on the 12h sleeve - and the paper book books the entry
    at that old close. Paper does not care; a live order would fill at today's price instead.
    The first dry run showed it: LTC 12h 'entered' at 62.04 while LTC traded at 66.90, 8% away.
    So every coin/timeframe WITHOUT an open position is marked as having seen its latest closed
    bar. Open positions are untouched: they keep being managed bar by bar."""
    tr = st["trend"]
    n = 0
    for base in cp.bp.BOOK:
        raw = cp.bp.klines(base)
        if raw is None or len(raw) < 3:
            continue
        for rule in cp.bp.SLEEVES:
            key = f"{base}:{rule}"
            if key in tr["open"]:
                continue
            df = cp.bp.resample(raw, rule)
            if len(df) < 2:
                continue
            tr["last_bar"][key] = str(df.iloc[:-1]["time"].iloc[-1])
            n += 1
    log(f"warm start: {n} coin/timeframe pairs act only on bars that close from now on")
    return n


def final_record(row: dict):
    cp.append(cp.P["state"].parent / "combo_final_trades.csv", row)


def poll(st: dict, venue, mode: str, caches: tuple, desk=None, prices_fn=None):
    ve = VIRTUAL_EQUITY[mode]
    if ve is None and venue is not None:
        st["equity"] = venue.equity()            # live: the books size off the real account
    today = f"{datetime.now(timezone.utc):%Y-%m-%d}"
    st.setdefault("exec", {})         # a FRESH state has none; found by the first dry run
    prices = (prices_fn or binance_prices)() if st.get("fin") else None
    if st["last_day"] != today:
        before = st["mn"].get("last_rebal")
        cp.daily(st)
        if st["mn"].get("last_rebal") != before or "mn_qty" not in st["exec"]:
            st["exec"]["mn_qty"] = mn_quantities(st)
        st["exec"]["mn_qty"] = {s: q for s, q in st["exec"]["mn_qty"].items() if s in st["mn"]["weights"]}
    if st.get("fin"):
        import final_books as fb
        fb.daily_books(st, prices, rec=final_record)
        fb.capit2_poll(st, prices, int(time.time() * 1000), rec=final_record)
    cp.trend_poll(st, *caches)
    if desk is not None:
        desk.watch(st)                   # a fill not yet in `hold` would be netted away
    execute(st, venue, mode, (prices_fn or binance_prices)(), dry=(mode == "dry"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["demo", "dry", "live"], required=True)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--report", action="store_true", help="the two-week check: orders, fills, failures")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--wick", action="store_true", help="run the crash-bid desk (wick_live.py, doc 16)")
    ap.add_argument("--wick-dist", type=float, default=None, help="bid distance (default 0.10); tests only")
    ap.add_argument("--wick-cap", type=int, default=None, help="fills per hour before cancelling (default 10)")
    ap.add_argument("--wick-usd", type=float, default=None, help="fixed $ per bid; tests only")
    ap.add_argument("--final", action="store_true",
                    help="THE FINAL MACHINE (final_books.py): + MN blend, carry, daily book, capit2, 10x account cap; "
                         "its own state in logs/combo_bot_<mode>_final")
    args = ap.parse_args()
    cp.set_dir(ROOT / "logs" / f"combo_bot_{args.mode}{'_final' if args.final else ''}")
    if args.final:
        import final_books as fb
        fb.enable(cp)                    # after set_dir, which sets the trend guard to 9x: this lowers it to 6.25x
        VIRTUAL_EQUITY.update({k: fb.EQUITY for k, v in VIRTUAL_EQUITY.items() if v is not None})
    new_state = not cp.P["state"].exists()
    st = cp.load()
    if VIRTUAL_EQUITY[args.mode] and new_state:
        st["equity"] = VIRTUAL_EQUITY[args.mode]
        st["peak"] = VIRTUAL_EQUITY[args.mode]
    if args.final:
        st.setdefault("fin", fb.fresh())
    if args.report:
        report(cp.P["state"].parent)
        return
    if args.status:
        cp.status(st)
        e = st.get("exec", {})
        print(f"  EXECUTION ({args.mode}): targets {book_targets(st)}")
        print(f"  unmapped coins: {e.get('unmapped', [])}")
        print(f"  disaster stops: {len(e.get('stops', {}))}   virtual ledger: {e.get('virtual_pos', {})}")
        if st.get("fin"):
            import final_books as fb
            fb.status(st)
        wk = st.get("wick")
        if wk:
            print(f"  crash desk: hour {wk['hour']}, {len(wk['orders'])} bids, {wk['fills']} fills this hour, "
                  f"holding {wk['hold']} | {wk['hours']} hours, {wk['total_fills']} fills, cap hit {wk['caps_hit']}x")
        return
    resolve(args.mode)
    guard_one_bot(args.mode)
    lock = cp.P["state"].parent / "combo_bot.pid"
    cp.P["pid"] = lock
    cp.single_instance()
    log("=" * 70)
    log(f"COMBO BOT --mode {args.mode} | trend (triple + 21d anchor) + market-neutral 1x + bear "
        f"sleeve 1x on ONE account, netted per coin | cross margin, {CAT_STOP:.0%} disaster stops")
    if args.final:
        log(f"  FINAL MACHINE: MN ranked half momentum / half RSI(14), funding carry {fb.K_CARRY}x, daily Bollinger "
            f"book (20-day exit) {fb.K_DAILY}x, capit2 {fb.K_CAPIT2}x | trend guard {cp.bp.MAX_LEVERAGE}x, account "
            f"cap {fb.GROSS_CAP:g}x | paper equity ${st['equity']:.2f}")
    if args.mode == "demo":
        log("  DEMO: every coin routed onto SBTC/SETH/SXRP by dollar value - an ORDER-PATH test; "
            "its P&L means nothing. Sized as $221.")
    if args.mode == "dry":
        log("  DRY: no orders. Real Bitget market list, virtual ledger, all coins.")
    ex = connect(args.mode)
    venue = Venue(ex, args.mode)
    if args.mode != "dry":
        log(f"  connected: account equity {venue.equity():.2f} {VENUE[args.mode]['margin']}, "
            f"{len(venue.positions())} open positions")
    caches = ({}, {})
    warm_start(st)
    desk = make_desk(st, venue, args) if args.wick else None
    cp.save(st)
    while True:
        try:
            poll(st, venue, args.mode, caches, desk)
            cp.save(st)
        except KeyboardInterrupt:
            cp.save(st); log("stopped"); return
        except Exception as e:
            log(f"poll error: {type(e).__name__}: {str(e)[:200]}")
        if args.once:
            return
        end = time.time() + POLL_S
        while time.time() < end:
            if desk is not None:
                try:
                    if desk.tick(st):            # an hour closed: sell its fills NOW, not at the next poll
                        execute(st, venue, args.mode, binance_prices(), dry=(args.mode == "dry"))
                    cp.save(st)
                except KeyboardInterrupt:
                    cp.save(st); log("stopped"); return
                except Exception as e:
                    log(f"wick error: {type(e).__name__}: {str(e)[:200]}")
            time.sleep(wl.TICK_S if desk is not None else max(end - time.time(), 0))


if __name__ == "__main__":
    main()
