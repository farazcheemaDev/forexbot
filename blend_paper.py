"""THE VALIDATED CONFIGURATION, LIVE ON PAPER — $221, 12 coins, three timeframes.

WHY THIS FILE EXISTS AND NOT A BITGET DEMO BOT
    Bitget's demo lists exactly THREE contracts (SBTC, SETH, SXRP). The validated
    strategy needs twelve, and three coins was measured at +3.98%/month against the
    twelve-coin blend's ~+12%. A Bitget demo run therefore cannot test this strategy
    at all - it can only test the ORDER PLUMBING, which longtrend_bot.py already does.

    Second reason: the $221 floor is a MEXC number. On Bitget's $5-per-order minimum
    the same book needs $585 (binding coin ENA, whose 12h stop is 14.84% wide). At
    $221 on Bitget most signals would be rejected for size, which is a test of the
    venue, not of the strategy.

    So: live Binance prices, simulated fills, MEXC's real per-coin minimums.

THE CONFIGURATION, AND WHERE EACH PIECE WAS VALIDATED
    universe    12 cheap-but-reputable alts        backtest/cheap_wide.py
    sleeves     1h + 4h + 12h, sharing 8 slots     backtest/blend.py
                   monthly correlation 1h vs 4h = +0.178; the blend turns 2022 from
                   -217% (long only) to +64%
    entry       close beyond the Bollinger band (30, 1.5)
    stop        2 x ATR(14) of that sleeve's own bars = 1R
    long exit   20 x ATR trail, 5-unit pyramid adding every 2R
    short exit  5 x ATR trail, ONE unit            backtest/shortside.py
                   shorts are a HEDGE, not a profit source: -0.036R standalone under
                   a strict fill, yet they cut drawdown 78.5% -> 68.9% and RAISE
                   compounded return, because less drawdown means less volatility drag
    breakeven   stop to entry once +3R             backtest/ddcontrol.py
                   12 of 12 cells reduced drawdown; both risk levels peaked at 3R
    regime      risk x0.25 while BTC < its 200h average    backtest/opt200.py
                   the only one of 26 cells that survived the holdout on all three of
                   return, drawdown and capital floor
    risk        0.30% of equity per unit
    expectation ~+12%/month full history, ~+8%/month on the last two years, 57.7% DD

    PLAN AGAINST +8%. The strategy made 40% of its lifetime profit in 2021 and was
    close to flat through 2025-2026 (2.5% of profit on 30% of trades). A month of
    this proves the machinery, not the return.

WHAT IS SIMULATED AND WHAT IS NOT
    Fills at the bar close, 12bp round trip. Slippage is NOT modelled. The per-coin
    MEXC minimum IS enforced and every rejection is counted - that count is the honest
    measure of whether $221 is enough.

    The trail advances ONCE PER CLOSED BAR and is checked from the following bar,
    which is exactly how a bar-close bot behaves: during a bar its stop sits at the
    previous bar's level. (backtest/strictfill.py models a continuously-updating trail
    instead and is therefore over-pessimistic for this implementation; it was run as a
    robustness check and the result survived it.)

    python blend_paper.py            live loop
    python blend_paper.py --status   report and exit
    python blend_paper.py --once     one cycle and exit
"""
from __future__ import annotations

import argparse
import json
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
STATE = LOGS / "blend_state.json"
TRADES = LOGS / "trades_blend.csv"
LOGF = LOGS / "blend_paper.log"

START_EQ = 221.0
RISK_PCT = 0.30                  # per unit
SLOTS = 8                        # shared across every coin AND every timeframe
FEE_BP = 12.0
BB_PERIOD, BB_STD = 30, 1.5
ATR_PERIOD = 14
SL_MULT = 2.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MAX_UNITS, ADD_EVERY_R = 5, 2.0
BE_AT_R = 3.0
REGIME_MA, REGIME_MULT = 200, 0.25
MAX_LEVERAGE = 10.0
POLL_S = 120
SLEEVES = ("1h", "4h", "12h")
BARS_NEEDED = 900                # 12h resample needs ~(30+14)*12 = 528 hours; margin

BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT"]
# MEXC minimum order value in USDT, measured 2026-09-13 by backtest/venue_floor.py.
# These move with price - a step of 1 contract costs whatever the contract costs - so
# re-measure before trusting them with real funds.
MIN_ORDER = {"XRPUSDT": 1.338, "SUIUSDT": 0.708, "ADAUSDT": 0.203,
             "LINKUSDT": 1.130, "AVAXUSDT": 0.729, "LTCUSDT": 0.535,
             "ENAUSDT": 1.388, "SHIBUSDT": 0.005, "WLDUSDT": 0.388,
             "NEARUSDT": 2.282, "DOTUSDT": 0.100, "ARBUSDT": 0.137}


def log(m: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def klines(symbol: str, limit: int = BARS_NEEDED) -> pd.DataFrame | None:
    """Binance 1h closes. Signals come from Binance because it has the deepest
    history and the paper book is priced consistently with the backtests."""
    u = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
         f"&interval=1h&limit={limit}")
    for attempt in range(3):
        try:
            raw = json.load(urllib.request.urlopen(u, timeout=25))
            break
        except Exception as e:
            if attempt == 2:
                log(f"[{symbol}] klines failed: {type(e).__name__}: {str(e)[:80]}")
                return None
            time.sleep(2)
    d = pd.DataFrame(raw, columns=["t", "open", "high", "low", "close", "volume",
                                   "ct", "qv", "n", "tb", "tq", "ig"])
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["time"] = pd.to_datetime(d["t"], unit="ms")
    return d[["time", "open", "high", "low", "close", "volume"]].dropna()


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """1h -> 4h/12h. OHLC aggregation must be first/max/min/last; taking `last` for
    `high` would silently disable every stop and trail check."""
    if rule == "1h":
        return df.reset_index(drop=True)
    d = df.set_index("time")
    out = d.resample(rule, label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"}).dropna()
    return out.reset_index()


def atr(df: pd.DataFrame, n: int = ATR_PERIOD) -> pd.Series:
    h, lo, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - lo, (h - c).abs(), (lo - c).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def bands(df: pd.DataFrame):
    c = df["close"]
    ma = c.rolling(BB_PERIOD).mean()
    sd = c.rolling(BB_PERIOD).std(ddof=0)
    return ma - BB_STD * sd, ma + BB_STD * sd


def fresh() -> dict:
    return {"equity": START_EQ, "open": {}, "last_bar": {}, "hb": {},
            "taken": 0, "taken_long": 0, "taken_short": 0, "declined": 0,
            "too_small": 0, "no_margin": 0,
            "started": datetime.now(timezone.utc).isoformat()}


def load_state() -> dict:
    if STATE.exists():
        try:
            s = json.load(open(STATE))
            for k, v in fresh().items():
                s.setdefault(k, v)
            return s
        except Exception:
            log("state unreadable — starting fresh")
    return fresh()


def save_state(s: dict):
    tmp = STATE.with_suffix(".tmp")
    json.dump(s, open(tmp, "w"), indent=1)
    tmp.replace(STATE)                # atomic, so a kill mid-write cannot corrupt it


def rec_trade(row: dict):
    new = not TRADES.exists()
    with open(TRADES, "a", encoding="utf-8") as f:
        if new:
            f.write(",".join(row) + "\n")
        f.write(",".join(str(v) for v in row.values()) + "\n")


def btc_bear(cache: dict) -> bool:
    """True while BTC's last CLOSED 1h bar is below its 200h average. Cached per bar
    so one poll does not fetch BTC twelve times."""
    d = klines("BTCUSDT", 300)
    if d is None or len(d) < REGIME_MA + 2:
        return cache.get("bear", False)
    closed = d.iloc[:-1]
    ma = closed["close"].rolling(REGIME_MA).mean().iloc[-1]
    bear = bool(closed["close"].iloc[-1] < ma) if np.isfinite(ma) else False
    cache["bear"] = bear
    return bear


def manage(st, key, rec, bar, hi, lo, a):
    """One position against the bar that just closed.

    ORDER MATTERS. The stop is checked FIRST, against the level it已 held during this
    bar - the level set at the END of the previous bar. Only then does the trail
    advance off this bar's extreme. That is how a bar-close bot behaves and it is the
    convention every backtest in this project uses.
    """
    d = 1 if rec["side"] == "long" else -1
    # the entry bar's own extremes predate the position; never judge a stop on them
    if rec.get("entry_bar") == bar:
        return None
    rec["bars"] += 1
    breached = (lo <= rec["stop"]) if d == 1 else (hi >= rec["stop"])
    if breached:
        return rec["stop"]
    # water mark, then trail, then the breakeven floor
    rec["water"] = (max(rec["water"], hi) if d == 1 else min(rec["water"], lo))
    gain_r = (rec["water"] - rec["entry"]) * d / rec["risk"]
    if d > 0 and rec["units"] < MAX_UNITS:
        if gain_r >= rec["next_add"] * ADD_EVERY_R:
            used = sum(r.get("notional", 0) * r.get("units", 1)
                       for r in st["open"].values())
            if used + rec["notional"] <= st["equity"] * MAX_LEVERAGE:
                rec["units"] += 1
                rec.setdefault("adds", []).append(
                    rec["entry"] + (rec["units"] - 1) * ADD_EVERY_R * rec["risk"])
                rec["next_add"] += 1
                log(f"[{key}] PYRAMID unit {rec['units']}/{MAX_UNITS} at "
                    f"+{gain_r:.1f}R")
            elif not rec.get("lev_warned"):
                rec["lev_warned"] = True
                log(f"[{key}] PYRAMID BLOCKED at unit {rec['units']} — no margin")
    tm = LONG_TRAIL if d > 0 else SHORT_TRAIL
    cand = rec["water"] - d * tm * a
    if gain_r >= BE_AT_R:
        cand = max(cand, rec["entry"]) if d > 0 else min(cand, rec["entry"])
    if (cand > rec["stop"]) if d > 0 else (cand < rec["stop"]):
        rec["stop"] = cand
    return None


def cycle(st: dict, regime_cache: dict):
    fee = FEE_BP / 1e4
    bear = btc_bear(regime_cache)
    for base in BOOK:
        raw = klines(base)
        if raw is None or len(raw) < BARS_NEEDED // 2:
            continue
        for rule in SLEEVES:
            df = resample(raw, rule)
            if len(df) < BB_PERIOD + ATR_PERIOD + 5:
                continue
            closed = df.iloc[:-1]                  # never the forming bar
            bar = str(closed["time"].iloc[-1])
            key = f"{base}:{rule}"
            a = float(atr(closed).iloc[-1])
            px = float(closed["close"].iloc[-1])
            hi = float(closed["high"].iloc[-1])
            lo = float(closed["low"].iloc[-1])
            if not np.isfinite(a) or a <= 0:
                continue
            rec = st["open"].get(key)

            if rec:
                if st["last_bar"].get(key) == bar:
                    continue                       # once per closed bar, not per poll
                st["last_bar"][key] = bar
                exit_px = manage(st, key, rec, bar, hi, lo, a)
                if exit_px is None:
                    st["open"][key] = rec
                    continue
                d = 1 if rec["side"] == "long" else -1
                entries = [rec["entry"]] + rec.get("adds", [])
                R = sum((exit_px - e) * d - fee * e for e in entries) / rec["risk"]
                st["equity"] *= (1 + R * rec["risk_used"] / 100.0)
                log(f"[{key}] EXIT {rec['side']} R={R:+.2f} "
                    f"({rec.get('units',1)}u, {rec['bars']}b) "
                    f"equity {st['equity']:.2f}")
                rec_trade(dict(
                    ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                    symbol=base, sleeve=rule, side=rec["side"],
                    entry=f"{rec['entry']:.8f}", exit=f"{exit_px:.8f}",
                    units=rec.get("units", 1), R=f"{R:+.4f}", bars=rec["bars"],
                    risk_pct=f"{rec['risk_used']:.3f}",
                    equity=f"{st['equity']:.2f}"))
                st["open"].pop(key, None)
                continue

            if st["last_bar"].get(key) == bar:
                continue
            st["last_bar"][key] = bar
            lo_b, up_b = bands(closed)
            if not (np.isfinite(up_b.iloc[-1]) and np.isfinite(lo_b.iloc[-1])):
                continue
            go_long = px > up_b.iloc[-1]
            go_short = px < lo_b.iloc[-1]
            if not (go_long or go_short):
                continue
            side = "long" if go_long else "short"
            d = 1 if go_long else -1
            if len(st["open"]) >= SLOTS:
                st["declined"] += 1
                log(f"[{key}] {side.upper()} DECLINED — {SLOTS} slots full "
                    f"({st['declined']} so far)")
                continue
            # REGIME GATE: quarter risk while BTC is below its 200h average. Stored on
            # the position, because the risk that sized it is the risk that must be
            # used when it closes - reading the gate again at exit would apply a
            # different fraction to the same trade.
            risk_used = RISK_PCT * (REGIME_MULT if bear else 1.0)
            risk = SL_MULT * a
            risk_usd = st["equity"] * risk_used / 100.0
            notional = risk_usd / (risk / px) if px > 0 else 0.0
            used = sum(r.get("notional", 0) * r.get("units", 1)
                       for r in st["open"].values())
            if used + notional > st["equity"] * MAX_LEVERAGE:
                st["no_margin"] += 1
                log(f"[{key}] {side.upper()} SKIPPED — no margin "
                    f"({st['no_margin']} so far)")
                continue
            floor = MIN_ORDER.get(base, 5.0)
            if notional < floor:
                st["too_small"] += 1
                log(f"[{key}] {side.upper()} SKIPPED — unit ${notional:.3f} below "
                    f"the ${floor:.3f} MEXC minimum (equity ${st['equity']:.2f}, "
                    f"stop {risk/px*100:.2f}%). {st['too_small']} so far")
                continue
            st["open"][key] = dict(side=side, entry=px, risk=risk,
                                   stop=px - d * risk,
                                   water=(hi if d > 0 else lo), bars=0, units=1,
                                   next_add=1, notional=notional,
                                   risk_used=risk_used, entry_bar=bar)
            st["taken"] += 1
            st[f"taken_{side}"] += 1
            log(f"[{key}] {side.upper()} @{px:.8g} stop {px-d*risk:.8g} "
                f"trail {LONG_TRAIL if d>0 else SHORT_TRAIL:.0f}xATR "
                f"unit ${notional:.2f} risk {risk_used:.3f}%"
                f"{' [BTC BEAR]' if bear else ''} "
                f"({len(st['open'])}/{SLOTS} slots, trade #{st['taken']})")


def status(st: dict):
    print(f"\nBLEND PAPER — {len(BOOK)} coins x {len(SLEEVES)} timeframes, "
          f"{SLOTS} shared slots")
    print(f"started {st.get('started','?')}")
    print(f"config: bb({BB_PERIOD},{BB_STD}) | long {LONG_TRAIL:.0f}xATR x{MAX_UNITS}u"
          f" | short {SHORT_TRAIL:.0f}xATR x1u | BE@{BE_AT_R:.0f}R | "
          f"risk {RISK_PCT}%/unit, x{REGIME_MULT} in BTC bear")
    eq = st["equity"]
    print(f"\nequity {eq:.2f}  ({eq/START_EQ*100-100:+.2f}%  from ${START_EQ:.0f})")
    print(f"entries {st['taken']} ({st.get('taken_long',0)}L/"
          f"{st.get('taken_short',0)}S)  declined(slots) {st['declined']}  "
          f"skipped(min order) {st.get('too_small',0)}  "
          f"skipped(margin) {st.get('no_margin',0)}")
    if st.get("too_small", 0) > max(st["taken"], 1):
        print("  >> the minimum order rejects more signals than it accepts:")
        print(f"     ${START_EQ:.0f} is too small for this config. That is the")
        print("     finding, not a bug.")
    print(f"open {len(st['open'])}/{SLOTS}")
    for k, r in sorted(st["open"].items()):
        print(f"  {k:<18} {r['side']:<5} entry {r['entry']:.6g} "
              f"stop {r['stop']:.6g} {r.get('units',1)}u {r['bars']}b")
    if TRADES.exists():
        d = pd.read_csv(TRADES)
        rs = pd.to_numeric(d["R"], errors="coerce").dropna()
        if len(rs):
            print(f"\nclosed {len(rs)}  mean R {rs.mean():+.3f}  total {rs.sum():+.2f}R"
                  f"  win {(rs>0).mean()*100:.0f}%  best {rs.max():+.2f}  "
                  f"worst {rs.min():+.2f}")
            for col in ("side", "sleeve"):
                if col in d.columns:
                    for v, g in d.groupby(col):
                        gr = pd.to_numeric(g["R"], errors="coerce").dropna()
                        if len(gr):
                            print(f"    {col:<7} {str(v):<6} n={len(gr):<4} "
                                  f"mean R {gr.mean():+.3f}  total {gr.sum():+.2f}R")
    print("\nexpect ~+8%/month and a LOSING month more often than not. 4 of 5 trades")
    print("lose; a handful of months carry the year. Any read under ~30 closed")
    print("trades is noise.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    st = load_state()
    if args.status:
        status(st); return
    log("=" * 78)
    log(f"BLEND PAPER — ${START_EQ:.0f}, {len(BOOK)} coins x {len(SLEEVES)} "
        f"timeframes, {SLOTS} shared slots")
    log(f"  sleeves {', '.join(SLEEVES)} | bb({BB_PERIOD},{BB_STD}) | "
        f"long {LONG_TRAIL:.0f}xATR x{MAX_UNITS}u every {ADD_EVERY_R}R | "
        f"short {SHORT_TRAIL:.0f}xATR x1u")
    log(f"  breakeven at +{BE_AT_R:.0f}R | risk {RISK_PCT}%/unit, "
        f"x{REGIME_MULT} while BTC < {REGIME_MA}h average")
    log(f"  per-coin MEXC minimum enforced | fee {FEE_BP}bp | simulated fills")
    log("  expectation ~+8%/month on recent data, 57.7% drawdown. PLAN AGAINST +8%,")
    log("  not the +12% full-history figure — 2021 carried 40% of lifetime profit.")
    log("  shorts are a HEDGE (-0.036R standalone); they earn their place by cutting")
    log("  drawdown, which raises compounded return.")
    regime_cache: dict = {}
    if args.once:
        cycle(st, regime_cache); save_state(st); status(st); return
    while True:
        try:
            cycle(st, regime_cache)
            newest = max(st["last_bar"].values(), default=None)
            if newest and st["hb"].get("logged") != newest:
                st["hb"]["logged"] = newest
                log(f"alive | bar {newest} | equity {st['equity']:.2f} | "
                    f"{len(st['open'])}/{SLOTS} slots | taken {st['taken']} "
                    f"({st.get('taken_long',0)}L/{st.get('taken_short',0)}S) | "
                    f"declined {st['declined']} | too small {st.get('too_small',0)}")
            save_state(st)
        except KeyboardInterrupt:
            log("stopped"); save_state(st); return
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:200]}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
