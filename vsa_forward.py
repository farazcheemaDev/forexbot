"""PRE-REGISTERED FORWARD TEST of the VSA absorption filter.

WHY A PRE-REGISTERED TEST AND NOT MORE BACKTESTING
--------------------------------------------------
The VSA filter (bb_break + dev < -0.5) passed MCPT at p=0.0099, then failed my
cross-asset gate - but that gate turned out to be MISAPPLIED: it averaged the
filter over mostly illiquid coins. Re-examining showed the improvement scales with
liquidity (corr +0.530 across 26 coins, +0.589 within coins never used to select
anything, +0.09 to +0.12R on BTC/ETH/BNB/ES/NQ).

But that liquidity hypothesis was formed AFTER seeing the failure, has NO
mechanism (zero-dev% and range/volume correlation show no liquidity gradient at
all), and does not hold in futures (n=8, t=1.4, filter loses 3/8 there). The
historical crypto holdout has now been spent on this question, so no further
retrospective slicing can settle it.

Only forward data can. It is virgin by definition.

THE PREDICTION, FIXED BEFORE ANY DATA IS COLLECTED
--------------------------------------------------
  H1  On HIGH-liquidity coins, trades taken when dev < -0.5 will have a higher
      mean R than trades taken when dev >= -0.5.
  H2  On LOW-liquidity coins that difference will be ~0.
  H3  (the differential, which is the actual claim)
      difference(HIGH) > difference(LOW)

SUCCESS CRITERION, ALSO FIXED NOW
  * at least 300 trades in each of the four cells, AND
  * difference(HIGH) > 0 by at least 2 standard errors, AND
  * difference(HIGH) > difference(LOW)
Anything less is reported as inconclusive. No post-hoc slicing of this data.

HONEST TIMELINE - READ THIS BEFORE EXPECTING AN ANSWER.
bb_break on 1h fires ~1.1 times/day/coin. With 20 coins that is ~22 trades/day,
but only ~28% of them fall inside the dev < -0.5 cell, so the binding cell fills
at roughly 3/day per liquidity group. Detecting a +0.10R difference at two
standard errors needs about 400 trades in that cell.

    => on the order of FOUR MONTHS before this test can speak.

That is the real cost of having spent the historical holdout. Reporting a verdict
before the cells fill would be precisely the error this whole exercise exposed, so
report() refuses to give one.

Paper only - no exchange orders. The three Bitget demo contracts are occupied by
the fill-rate probe, and this needs 10 symbols anyway.

    python vsa_forward.py --once | (no args = live loop)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest.holdout_sweep import signals_for  # noqa: E402
from backtest.mass_search import FILTERS  # noqa: E402
from backtest.vsa import vsa_indicator  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
STATE = LOGS / "vsaf_state.json"
TRADES = LOGS / "vsaf_trades.csv"

TF = "1h"
SL, TP, FEE_BP = 2.0, 3.0, 10.0
DEV_CUT = -0.5
PRIMARY = ("bb_break", (30, 1.5))

# liquidity groups fixed from measured median $volume/bar on historical data.
# The GROUPS are pre-registered; the forward outcome is not yet known.
# Ranked by measured median $volume/bar on history (BTC 68.3M ... XLM 0.42M).
# Ten per group rather than five, purely to double the sample rate - the groups
# themselves are fixed by liquidity, never by forward performance.
HIGH_LIQ = ["BTC/USDT:USDT", "ETH/USDT:USDT", "XRP/USDT:USDT", "BNB/USDT:USDT",
            "SOL/USDT:USDT", "ARB/USDT:USDT", "LINK/USDT:USDT", "ADA/USDT:USDT",
            "DOGE/USDT:USDT", "DOT/USDT:USDT"]
LOW_LIQ = ["XLM/USDT:USDT", "AAVE/USDT:USDT", "UNI/USDT:USDT", "PEPE/USDT:USDT",
           "ETC/USDT:USDT", "BCH/USDT:USDT", "ATOM/USDT:USDT", "APT/USDT:USDT",
           "NEAR/USDT:USDT", "OP/USDT:USDT"]
SYMBOLS = HIGH_LIQ + LOW_LIQ


def log(msg):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOGS / "vsaf.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state():
    if STATE.exists():
        try:
            return json.load(open(STATE))
        except Exception:
            pass
    return {"open": {}, "seen": {}}


def save_state(s):
    json.dump(s, open(STATE, "w"), indent=1)


def log_trade(row):
    new = not TRADES.exists()
    with open(TRADES, "a", encoding="utf-8") as fh:
        if new:
            fh.write("ts_utc,symbol,liq_group,side,entry,exit,reason,R,dev,"
                     "in_filter\n")
        fh.write(",".join(str(row[k]) for k in
                 ["ts", "symbol", "liq", "side", "entry", "exit", "reason",
                  "R", "dev", "in_filter"]) + "\n")


def cycle(ex, st):
    fee = FEE_BP / 10000.0
    for sym in SYMBOLS:
        liq = "HIGH" if sym in HIGH_LIQ else "LOW"
        try:
            o = ex.fetch_ohlcv(sym, TF, limit=400)
        except Exception as e:
            log(f"[{sym}] ohlcv error: {str(e)[:90]}")
            continue
        df = pd.DataFrame(o, columns=["t", "open", "high", "low", "close", "volume"])
        if len(df) < 350:
            continue
        df["time"] = pd.to_datetime(df["t"], unit="ms")
        closed = df.iloc[:-1].reset_index(drop=True)     # drop the forming bar
        bar_t = int(closed["t"].iloc[-1])
        if st["seen"].get(sym) == bar_t:
            continue
        st["seen"][sym] = bar_t

        hi = float(closed["high"].iloc[-1]); lo = float(closed["low"].iloc[-1])
        # ---- manage an open position against the bar that just closed --------
        pos = st["open"].get(sym)
        if pos:
            d = pos["d"]
            hit_sl = (lo <= pos["sl"]) if d == 1 else (hi >= pos["sl"])
            hit_tp = (hi >= pos["tp"]) if d == 1 else (lo <= pos["tp"])
            px, reason = ((pos["sl"], "SL") if hit_sl else
                          ((pos["tp"], "TP") if hit_tp else (None, "")))
            if px is not None:
                R = (px - pos["e"]) * d / pos["risk"] \
                    - (fee * pos["e"] + fee * abs(px)) / pos["risk"]
                log(f"[{sym}] {liq} EXIT {reason} R={R:+.3f} "
                    f"dev={pos['dev']:+.3f} in_filter={pos['in_filter']}")
                log_trade(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               symbol=sym, liq=liq,
                               side="LONG" if d == 1 else "SHORT",
                               entry=round(pos["e"], 8), exit=round(px, 8),
                               reason=reason, R=round(R, 4),
                               dev=round(pos["dev"], 4),
                               in_filter=int(pos["in_filter"])))
                st["open"].pop(sym, None)
                pos = None

        if pos:
            continue

        # ---- new entry. EVERY signal is taken; the dev value is RECORDED, not
        # used to gate. That gives both cells (in-filter / out-of-filter) from one
        # run, which is a paired design and far more powerful than running the
        # filtered variant alone.
        sig = FILTERS["none"](closed, signals_for(closed, *PRIMARY))
        action = Action(int(sig.iloc[-1]))
        if action == Action.HOLD:
            continue
        a = float(atr_ind(closed, 14).iloc[-2])   # bar i-1 -> causal at next open
        dev_ser = vsa_indicator(closed).shift(1)
        dev = float(dev_ser.iloc[-1]) if np.isfinite(dev_ser.iloc[-1]) else 0.0
        if not np.isfinite(a) or a <= 0:
            continue
        d = 1 if action == Action.BUY else -1
        e = float(closed["close"].iloc[-1])       # paper fill at the close
        risk = SL * a
        st["open"][sym] = dict(d=d, e=e, risk=risk, sl=e - d * risk,
                               tp=e + d * TP * a, dev=dev,
                               in_filter=bool(dev < DEV_CUT),
                               ts=int(time.time()))
        log(f"[{sym}] {liq} ENTRY {'LONG' if d == 1 else 'SHORT'} @{e:.6g} "
            f"dev={dev:+.3f} in_filter={dev < DEV_CUT}")
    save_state(st)


def report():
    if not TRADES.exists():
        log("no trades yet")
        return
    df = pd.read_csv(TRADES)
    log("---- PRE-REGISTERED VSA FORWARD TEST ----")
    log(f"   total trades {len(df)}")
    log(f"   {'group':6} {'cell':14} {'n':>5} {'meanR':>9} {'se':>7}")
    cells = {}
    for liq in ("HIGH", "LOW"):
        for inf in (1, 0):
            g = df[(df.liq_group == liq) & (df.in_filter == inf)]["R"]
            name = "dev<-0.5" if inf else "dev>=-0.5"
            if len(g):
                se = g.std(ddof=1) / np.sqrt(len(g)) if len(g) > 1 else float("nan")
                cells[(liq, inf)] = (g.mean(), se, len(g))
                log(f"   {liq:6} {name:14} {len(g):>5} {g.mean():>+9.4f} {se:>7.4f}")
            else:
                log(f"   {liq:6} {name:14} {0:>5}")
    for liq in ("HIGH", "LOW"):
        if (liq, 1) in cells and (liq, 0) in cells:
            m1, s1, n1 = cells[(liq, 1)]
            m0, s0, n0 = cells[(liq, 0)]
            diff = m1 - m0
            sed = float(np.sqrt(s1 ** 2 + s0 ** 2))
            log(f"   {liq} difference (filter - rest) = {diff:+.4f} "
                f"+/- {sed:.4f}  t={diff/sed if sed else 0:+.2f}")
    need = all(cells.get(k, (0, 0, 0))[2] >= 300
               for k in (("HIGH", 1), ("HIGH", 0), ("LOW", 1), ("LOW", 0)))
    log(f"   pre-registered minimum of 300 per cell reached: {need}")
    if not need:
        log("   -> INCONCLUSIVE by design. No verdict until every cell has 300.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    if args.report:
        report(); return

    ex = ccxt.bitget({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    ex.load_markets()
    log(f"VSA FORWARD TEST (paper) | {TF} | {PRIMARY[0]}{PRIMARY[1]} | "
        f"dev cut {DEV_CUT} | cost {FEE_BP}bp")
    log(f"   HIGH liquidity: {[s.split('/')[0] for s in HIGH_LIQ]}")
    log(f"   LOW  liquidity: {[s.split('/')[0] for s in LOW_LIQ]}")
    log("   every signal is taken; dev is RECORDED not gated -> paired design")
    log("   PREDICTION: diff(HIGH) > 0 and diff(HIGH) > diff(LOW)")

    st = load_state()
    if args.once:
        cycle(ex, st); report(); return
    n = 0
    while True:
        try:
            cycle(ex, st)
            n += 1
            if n % 30 == 0:
                report()
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:150]}")
        time.sleep(120)


if __name__ == "__main__":
    main()
