"""THE DEPLOYED BLEND ON BINANCE FUTURES TESTNET — real orders, real fills, fake money.

    set BINANCE_TESTNET_KEY=...        (get them at testnet.binancefuture.com)
    set BINANCE_TESTNET_SECRET=...
    python -u blend_testnet.py --dry-run     # no orders, validates the loop
    python -u blend_testnet.py               # places orders on TESTNET
    python -u blend_testnet.py --status

WHY THIS EXISTS
    blend_paper.py tests the STRATEGY and assumes its fills. longtrend_bot.py tests the
    ORDER PATH but Bitget's demo lists only 3 contracts (SBTC/SETH/SXRP), so it measures
    slippage on the two most liquid coins on earth - not on ENA, WLD, SUI or ARB, which
    is what going live would actually depend on.

    Binance's futures testnet lists all 12 of the book (verified 2026-09-21: 605 trading
    symbols, every book coin present, $5 minimum notional, SHIB as 1000SHIBUSDT). So the
    real configuration - 12 coins x 3 timeframes, 12 shared slots - can finally be run
    against a real matching engine.

    The only number this exists to produce: **what the fills actually cost.** Every order
    records the price asked for, the price received, and the gap in basis points.

THE PROBLEM blend_paper.py NEVER HAD TO SOLVE
    The strategy holds LOGICAL positions keyed by coin AND sleeve - the live book right
    now has DOTUSDT:1h and DOTUSDT:4h open at the same time, and the same for LINK and
    NEAR. An exchange holds ONE NET POSITION PER SYMBOL. There is no way to give a
    venue two separate long positions in DOT.

    So this bot keeps the logical book internally and sends only the NET DELTA per
    symbol. Target size for DOTUSDT is the sum of every logical DOT position's signed
    size; each cycle it compares that against what the exchange actually holds and
    trades the difference. That is the correct architecture and it is what any live
    deployment will need - blend_paper has been simulating something not directly
    executable, which is worth knowing before real money is involved.

NO EXCHANGE STOP, DELIBERATELY
    longtrend_bot.py places a stop order at the exchange as a backstop, which works
    because one logical position maps to one exchange position. Under netting it does
    not: three sleeves with three different stops cannot be expressed as one stop on the
    net. So stops are managed in-process only.

    **That means a dead bot leaves positions unprotected.** Acceptable here because the
    money is fake and the point is measuring fills - but it is the reason this design
    cannot be lifted to a live account unchanged. A live version needs either one sleeve
    per coin, or a disaster stop on the net at the worst sleeve's level.

SAFETY
    * Credentials come from the environment ONLY. Never a file, never an argument, never
      logged. Same rule as pull_history.py.
    * Sandbox mode is forced on and then ASSERTED against the resolved URL. If the
      endpoint is not testnet the bot refuses to start. There is no flag that points
      this at live Binance.
    * A pid lock, because two instances would double every order.
    * Reconciliation runs BOTH ways every cycle: a logical position the exchange does
      not have is cleared, and an exchange position the book does not know about is
      reported and left alone rather than adopted - adopting one means inventing an
      entry, a stop and a water mark, and every one would be a guess. That lesson cost
      longtrend_bot two duplicate instances on 2026-09-12.
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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import blend_paper as BP  # noqa: E402  the strategy, reused rather than reimplemented

LOGS = ROOT / "logs"
STATE = LOGS / "blend_testnet_state.json"
TRADES = LOGS / "trades_blend_testnet.csv"
LOGF = LOGS / "blend_testnet.log"
PIDF = LOGS / "blend_testnet.pid"

START_EQUITY = 221.0          # mirrors the paper book so the two are comparable
LEVERAGE = 5
POLL_S = 60
# Binance futures lists SHIB in thousands; everything else matches.
EX_SYMBOL = {c: (f"1000{c[:-4]}/USDT:USDT" if c == "SHIBUSDT"
                 else f"{c[:-4]}/USDT:USDT") for c in BP.BOOK}
CONTRACT_MULT = {"SHIBUSDT": 1000.0}      # 1 contract = 1000 SHIB


def log(m: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def connect():
    """ccxt on the TESTNET, asserted. Keys from the environment only."""
    import ccxt
    key = os.environ.get("BINANCE_TESTNET_KEY")
    sec = os.environ.get("BINANCE_TESTNET_SECRET")
    if not key or not sec:
        raise SystemExit(
            "BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET are not set.\n"
            "  Create a key at https://testnet.binancefuture.com (fake money) and\n"
            "  export it in this shell only. Never put it in a file in this repo.")
    ex = ccxt.binanceusdm({"apiKey": key, "secret": sec,
                           "enableRateLimit": True,
                           "options": {"defaultType": "future"}})
    ex.set_sandbox_mode(True)
    # HARD GATE: refuse to run unless the resolved endpoint is the testnet.
    url = json.dumps(ex.urls.get("api", ""))
    if "testnet" not in url:
        raise SystemExit(f"REFUSING: endpoint is not testnet -> {url[:200]}")
    ex.load_markets()
    log(f"connected to TESTNET ({len(ex.markets)} markets)")
    return ex


def acquire_lock():
    if PIDF.exists():
        try:
            old = int(PIDF.read_text().strip())
        except ValueError:
            old = None
        if old:
            import subprocess
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-Process -Id {old} -ErrorAction SilentlyContinue) -ne $null"],
                capture_output=True, text=True).stdout.strip().lower()
            if out == "true":
                raise SystemExit(f"REFUSING: pid {old} already holds {PIDF}. "
                                 "Two instances would double every order.")
            log(f"clearing stale lock from dead pid {old}")
    PIDF.write_text(str(os.getpid()))


def fresh() -> dict:
    return dict(open={}, last_bar={}, equity=START_EQUITY, taken=0, taken_long=0,
                taken_short=0, declined=0, too_small=0, no_margin=0, orphan={},
                started=datetime.now(timezone.utc).isoformat())


def load_state() -> dict:
    if STATE.exists():
        try:
            s = json.load(open(STATE, encoding="utf-8"))
            for k, v in fresh().items():
                s.setdefault(k, v)
            return s
        except Exception as e:
            log(f"state unreadable ({e}) - starting fresh")
    return fresh()


def save_state(s: dict):
    json.dump(s, open(STATE, "w"), indent=1)


def rec_trade(row: dict):
    new = not TRADES.exists()
    with open(TRADES, "a", encoding="utf-8") as f:
        if new:
            f.write(",".join(row) + "\n")
        f.write(",".join(str(row[k]) for k in row) + "\n")


def fill_price(ex, order, sym, fallback):
    """What the order REALLY filled at, and where that number came from.
    Same three-source ladder as longtrend_bot.actual_fill - see the note there."""
    if isinstance(order, dict):
        for k in ("average", "price"):
            if order.get(k):
                try:
                    return float(order[k]), k
                except (TypeError, ValueError):
                    pass
        if order.get("id"):
            try:
                o = ex.fetch_order(order["id"], sym)
                for k in ("average", "price"):
                    if o.get(k):
                        return float(o[k]), f"fetch_order.{k}"
            except Exception:
                pass
    try:
        tr = ex.fetch_my_trades(sym, limit=10) or []
        if tr and tr[-1].get("price"):
            return float(tr[-1]["price"]), "fetch_my_trades"
    except Exception:
        pass
    return float(fallback), "assumed"


def exchange_positions(ex):
    """{coin: signed contracts} for the book, from the venue."""
    out = {}
    try:
        for p in ex.fetch_positions(list(EX_SYMBOL.values())) or []:
            amt = float(p.get("contracts") or 0)
            if abs(amt) < 1e-12:
                continue
            side = str(p.get("side", "")).lower()
            sym = p.get("symbol")
            for coin, s in EX_SYMBOL.items():
                if s == sym:
                    out[coin] = amt * (-1 if side == "short" else 1)
    except Exception as e:
        log(f"fetch_positions FAILED: {str(e)[:160]}")
        return None
    return out


def target_contracts(st, coin, px):
    """Net contracts the logical book wants in this coin, signed."""
    mult = CONTRACT_MULT.get(coin, 1.0)
    tot = 0.0
    for key, rec in st["open"].items():
        if not key.startswith(coin + ":"):
            continue
        d = 1 if rec["side"] == "long" else -1
        qty = rec["notional"] * rec.get("units", 1) / px / mult
        tot += d * qty
    return tot


def trade_delta(ex, st, coin, px, dry):
    """Send the NET difference between what the book wants and what the venue holds."""
    sym = EX_SYMBOL[coin]
    want = target_contracts(st, coin, px)
    have = st.setdefault("_exch", {}).get(coin, 0.0)
    delta = want - have
    mkt = ex.market(sym) if ex else None
    if mkt:
        step = float(mkt.get("precision", {}).get("amount") or 0) or None
        mn = float((mkt.get("limits", {}).get("cost", {}) or {}).get("min") or 5.0)
        if abs(delta) * px * CONTRACT_MULT.get(coin, 1.0) < mn:
            return None                         # below the venue minimum: nothing to do
        try:
            delta = float(ex.amount_to_precision(sym, abs(delta))) * np.sign(delta)
        except Exception:
            pass
        if abs(delta) <= 0:
            return None
    side = "buy" if delta > 0 else "sell"
    if dry or not ex:
        log(f"[{coin}] DRY would {side} {abs(delta):.8g} contracts "
            f"(want {want:.6g}, have {have:.6g})")
        return None
    try:
        o = ex.create_order(sym, "market", side, abs(delta))
    except Exception as e:
        log(f"[{coin}] ORDER FAILED {side} {abs(delta):.8g}: {str(e)[:170]}")
        return None
    got, src = fill_price(ex, o, sym, px)
    slip = (got - px) / px * 1e4 * (1 if side == "buy" else -1)
    log(f"[{coin}] {side.upper()} {abs(delta):.8g} @ {got:.8g} "
        f"(wanted {px:.8g}, {src}) slip {slip:+.1f}bp")
    st["_exch"][coin] = want
    return dict(coin=coin, side=side, qty=abs(delta), want_px=px, got=got,
                src=src, slip_bp=slip)


def reconcile(ex, st):
    """Both directions, every cycle. See the SAFETY note in the module docstring."""
    live = exchange_positions(ex)
    if live is None:
        return False
    st["_exch"] = live
    for coin in EX_SYMBOL:
        keys = [k for k in st["open"] if k.startswith(coin + ":")]
        on_ex = abs(live.get(coin, 0.0)) > 1e-12
        if keys and not on_ex:
            log(f"[{coin}] book holds {len(keys)} sleeve(s) but the venue is FLAT - "
                f"clearing {', '.join(keys)}")
            for k in keys:
                st["open"].pop(k, None)
        if on_ex and not keys:
            if st.setdefault("orphan", {}).get(coin) != "seen":
                st["orphan"][coin] = "seen"
                log(f"[{coin}] ORPHAN {live[coin]:+.8g} contracts on the venue with no "
                    f"local record. NOT adopting it - close it by hand if unwanted.")
    return True


def cycle(ex, st, regime_cache, dry):
    """blend_paper's strategy decisions, then one netted order per coin that changed."""
    fee = BP.FEE_BP / 1e4
    bear = BP.btc_bear(regime_cache)
    if ex and not reconcile(ex, st):
        return
    for base in BP.BOOK:
        raw = BP.klines(base)
        if raw is None or len(raw) < BP.BARS_NEEDED // 2:
            continue
        changed, last_px = False, None
        for rule in BP.SLEEVES:
            df = BP.resample(raw, rule)
            if len(df) < BP.BB_PERIOD + BP.ATR_PERIOD + 5:
                continue
            closed = df.iloc[:-1]
            bar = str(closed["time"].iloc[-1])
            key = f"{base}:{rule}"
            a = float(BP.atr(closed).iloc[-1])
            px = float(closed["close"].iloc[-1])
            hi = float(closed["high"].iloc[-1])
            lo = float(closed["low"].iloc[-1])
            last_px = px
            if not np.isfinite(a) or a <= 0:
                continue
            rec = st["open"].get(key)

            if rec:
                if st["last_bar"].get(key) == bar:
                    continue
                st["last_bar"][key] = bar
                units_before = rec.get("units", 1)
                exit_px = BP.manage(st, key, rec, bar, hi, lo, a)
                if exit_px is None:
                    st["open"][key] = rec
                    if rec.get("units", 1) != units_before:
                        changed = True          # pyramided: the net size grew
                    continue
                d = 1 if rec["side"] == "long" else -1
                entries = [rec["entry"]] + rec.get("adds", [])
                R = sum((exit_px - e) * d - fee * e for e in entries) / rec["risk"]
                st["equity"] *= (1 + R * rec["risk_used"] / 100.0)
                log(f"[{key}] EXIT {rec['side']} R={R:+.2f} "
                    f"({rec.get('units',1)}u, {rec['bars']}b) "
                    f"equity {st['equity']:.2f}")
                st["open"].pop(key, None)
                changed = True
                rec_trade(dict(
                    ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                    symbol=base, sleeve=rule, side=rec["side"],
                    entry=f"{rec['entry']:.8f}", exit=f"{exit_px:.8f}",
                    units=rec.get("units", 1), R=f"{R:+.4f}", bars=rec["bars"],
                    risk_pct=f"{rec['risk_used']:.3f}",
                    equity=f"{st['equity']:.2f}", event="EXIT",
                    fill="", fill_src="", slip_bp=""))
                continue

            if st["last_bar"].get(key) == bar:
                continue
            st["last_bar"][key] = bar
            lo_b, up_b = BP.bands(closed)
            if not (np.isfinite(up_b.iloc[-1]) and np.isfinite(lo_b.iloc[-1])):
                continue
            go_long = px > up_b.iloc[-1]
            go_short = px < lo_b.iloc[-1]
            if not (go_long or go_short):
                continue
            side = "long" if go_long else "short"
            d = 1 if go_long else -1
            if len(st["open"]) >= BP.SLOTS:
                st["declined"] += 1
                continue
            risk_used = BP.RISK_PCT * (BP.REGIME_MULT if bear else 1.0)
            risk = BP.SL_MULT * a
            notional = st["equity"] * risk_used / 100.0 / (risk / px) if px > 0 else 0
            used = sum(r.get("notional", 0) * r.get("units", 1)
                       for r in st["open"].values())
            if used + notional > st["equity"] * LEVERAGE:
                st["no_margin"] += 1
                log(f"[{key}] SKIPPED - no margin at {LEVERAGE}x")
                continue
            # the VENUE's minimum, not the MEXC table blend_paper uses
            mn = 5.0
            try:
                mn = float((ex.market(EX_SYMBOL[base])["limits"]["cost"]["min"])
                           or 5.0) if ex else 5.0
            except Exception:
                pass
            if notional < mn:
                st["too_small"] += 1
                log(f"[{key}] SKIPPED - unit ${notional:.2f} below the ${mn:.2f} "
                    f"Binance minimum")
                continue
            st["open"][key] = dict(side=side, entry=px, risk=risk,
                                   stop=px - d * risk,
                                   water=(hi if d > 0 else lo), bars=0, units=1,
                                   next_add=1, notional=notional,
                                   risk_used=risk_used, entry_bar=bar)
            st["taken"] += 1
            st[f"taken_{side}"] += 1
            changed = True
            log(f"[{key}] {side.upper()} @{px:.8g} stop {px-d*risk:.8g} "
                f"unit ${notional:.2f} risk {risk_used:.3f}%"
                f"{' [BTC BEAR]' if bear else ''} "
                f"({len(st['open'])}/{BP.SLOTS} slots, #{st['taken']})")

        if changed and last_px:
            r = trade_delta(ex, st, base, last_px, dry)
            if r:
                rec_trade(dict(
                    ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                    symbol=base, sleeve="NET", side=r["side"],
                    entry="", exit="", units="", R="", bars="",
                    risk_pct="", equity=f"{st['equity']:.2f}", event="FILL",
                    fill=f"{r['got']:.8f}", fill_src=r["src"],
                    slip_bp=f"{r['slip_bp']:+.1f}"))


def status(st):
    print(f"\nBLEND TESTNET - Binance futures testnet, {len(BP.BOOK)} coins x "
          f"{len(BP.SLEEVES)} timeframes, {BP.SLOTS} slots")
    print(f"started {st.get('started')}")
    print(f"equity {st['equity']:.2f} (from {START_EQUITY:.2f})")
    print(f"taken {st['taken']} ({st.get('taken_long',0)}L/"
          f"{st.get('taken_short',0)}S)  declined {st['declined']}  "
          f"too small {st['too_small']}  no margin {st['no_margin']}")
    print(f"open {len(st['open'])}/{BP.SLOTS}")
    for k, r in sorted(st["open"].items()):
        print(f"  {k:<18} {r['side']:<5} entry {r['entry']:.8g} "
              f"stop {r['stop']:.8g} {r.get('units',1)}u {r['bars']}b")
    if TRADES.exists():
        import pandas as pd
        d = pd.read_csv(TRADES)
        f = d[d.event == "FILL"] if "event" in d else d.iloc[0:0]
        if len(f):
            s = f.slip_bp.astype(float)
            print(f"\nFILLS: {len(f)}  median slip {s.median():+.1f}bp  "
                  f"mean {s.mean():+.1f}bp  worst {s.min():+.1f}bp")
            print("  sources: " + ", ".join(
                f"{k}={v}" for k, v in f.fill_src.value_counts().items()))
            print("  (negative = worse than the price the strategy assumed)")
        else:
            print("\nFILLS: none yet - nothing to say about slippage")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="run the loop, place no orders")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    st = load_state()
    if a.status:
        status(st)
        return
    ex = None if a.dry_run else connect()
    if not a.dry_run:
        acquire_lock()
        for coin, sym in EX_SYMBOL.items():
            try:
                ex.set_leverage(LEVERAGE, sym)
            except Exception as e:
                log(f"[{coin}] set_leverage failed (continuing): {str(e)[:90]}")
    log("=" * 78)
    log(f"BLEND on BINANCE TESTNET - {len(BP.BOOK)} coins x {len(BP.SLEEVES)} "
        f"timeframes, {BP.SLOTS} shared slots")
    log(f"  bb({BP.BB_PERIOD},{BP.BB_STD}) | long {BP.LONG_TRAIL:.0f}xATR x"
        f"{BP.MAX_UNITS}u | short {BP.SHORT_TRAIL:.0f}xATR x1u | "
        f"BE@{BP.BE_AT_R:.0f}R | risk {BP.RISK_PCT}%/unit")
    log(f"  NO exchange stop - netting makes per-sleeve stops incoherent. A dead bot "
        f"leaves positions unprotected. Fake money; see the docstring.")
    if a.dry_run:
        log("  *** DRY RUN - no orders will be placed ***")
    regime = {}
    while True:
        try:
            cycle(ex, st, regime, a.dry_run)
            save_state(st)
        except KeyboardInterrupt:
            log("stopped by hand")
            break
        except Exception as e:
            log(f"CYCLE ERROR {type(e).__name__}: {str(e)[:200]}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
