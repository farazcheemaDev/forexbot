"""Multi-strategy crypto forward test on Bitget.

Runs SEVERAL strategies side by side on the same symbols, each with its own
virtual equity and trade log, so we can compare them on identical live data.
Includes deliberate controls (a mean-reversion strategy we expect to lose) so we
can tell signal from noise.

Modes:
    paper  (default) - simulated fills, NO api keys, NO orders
    demo             - place real orders on Bitget DEMO (requires api keys)

    python crypto_multi.py --once            # one cycle, paper
    python crypto_multi.py                   # live loop, paper
    python crypto_multi.py --mode demo       # live loop, Bitget demo orders
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
STATE = LOGS / "multi_state.json"

SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT",
           "XRP/USDT:USDT", "BNB/USDT:USDT", "AVAX/USDT:USDT"]
TIMEFRAME = "1h"
START_EQUITY = 1000.0
MAKER, TAKER = 0.0002, 0.0006

# id, family, params, filter, sl_mult, tp_mult, risk%, max concurrent
STRATEGIES = [
    dict(id="rsi_mom_er30_r05",  fam="rsi_mom",  p=(7, 40, 60),  filt="er30", sl=2.0, tp=3.0, risk=0.5, maxpos=3),
    dict(id="rsi_mom_er30_r10",  fam="rsi_mom",  p=(7, 40, 60),  filt="er30", sl=2.0, tp=3.0, risk=1.0, maxpos=3),
    dict(id="rsi_mom_er30_r20",  fam="rsi_mom",  p=(7, 40, 60),  filt="er30", sl=2.0, tp=3.0, risk=2.0, maxpos=3),
    dict(id="rsi_mom_nocap_r10", fam="rsi_mom",  p=(7, 40, 60),  filt="er30", sl=2.0, tp=3.0, risk=1.0, maxpos=6),
    dict(id="roc_mom_er30_r10",  fam="roc_mom",  p=(20, 1.0),    filt="er30", sl=2.0, tp=3.0, risk=1.0, maxpos=3),
    dict(id="bb_break_er30_r10", fam="bb_break", p=(30, 1.5),    filt="er30", sl=2.0, tp=3.0, risk=1.0, maxpos=3),
    dict(id="rsi_mom_nofilt_r10", fam="rsi_mom", p=(7, 40, 60),  filt="none", sl=2.0, tp=3.0, risk=1.0, maxpos=3),
    dict(id="donchian_trend_r10", fam="donchian", p=(20,),       filt="none", sl=2.0, tp=3.0, risk=1.0, maxpos=3),
    # CONTROL: expected to lose. If this "wins" we know we're reading noise.
    dict(id="CONTROL_bb_rev_r10", fam="bb_rev",  p=(20, 2.0),    filt="none", sl=2.0, tp=3.0, risk=1.0, maxpos=3),
]


def log(msg):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOGS / "multi.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state():
    if STATE.exists():
        return json.load(open(STATE))
    return {s["id"]: {"equity": START_EQUITY, "positions": {}, "pending": {}}
            for s in STRATEGIES} | {"_last_bar": {}}


def save_state(st):
    json.dump(st, open(STATE, "w"), indent=1)


def log_trade(sid, row):
    f = LOGS / f"trades_{sid}.csv"
    new = not f.exists()
    with open(f, "a", encoding="utf-8") as fh:
        if new:
            fh.write("ts_utc,symbol,side,entry,exit,reason,R,pnl_pct,equity\n")
        fh.write(",".join(str(row[k]) for k in
                 ["ts", "symbol", "side", "entry", "exit", "reason", "R", "pnl_pct", "equity"]) + "\n")


def evaluate(strat, st, sym, closed, bar):
    """One strategy, one symbol, on a newly closed bar."""
    sid = strat["id"]
    S = st[sid]
    d_sl, d_tp = strat["sl"], strat["tp"]

    # 1. fill pending at this bar's open
    pend = S["pending"].pop(sym, None)
    if pend and sym not in S["positions"] and len(S["positions"]) < strat["maxpos"]:
        entry = float(bar["open"]); d = pend["dir"]; risk = pend["risk"]
        S["positions"][sym] = dict(dir=d, entry=entry, risk=risk,
                                   sl=entry - d * risk,
                                   tp=entry + d * d_tp * pend["atr"],
                                   risk_amt=S["equity"] * strat["risk"] / 100.0)
        log(f"[{sid}] ENTRY {'LONG' if d==1 else 'SHORT'} {sym} @{entry:.4f}")

    # 2. manage open position
    pos = S["positions"].get(sym)
    if pos:
        d = pos["dir"]; hi, lo = float(bar["high"]), float(bar["low"])
        px, reason, taker_exit = None, "", True
        if (lo <= pos["sl"]) if d == 1 else (hi >= pos["sl"]):
            px, reason, taker_exit = pos["sl"], "SL", True
        elif (hi >= pos["tp"]) if d == 1 else (lo <= pos["tp"]):
            px, reason, taker_exit = pos["tp"], "TP", False
        if px is not None:
            R = (px - pos["entry"]) * d / pos["risk"]
            R -= (MAKER + (TAKER if taker_exit else MAKER)) * pos["entry"] / pos["risk"]
            pnl = R * pos["risk_amt"]
            S["equity"] += pnl
            log(f"[{sid}] EXIT {reason} {sym} @{px:.4f} R={R:+.2f} eq={S['equity']:.2f}")
            log_trade(sid, dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                                symbol=sym, side="LONG" if d == 1 else "SHORT",
                                entry=round(pos["entry"], 6), exit=round(px, 6),
                                reason=reason, R=round(R, 3),
                                pnl_pct=round(R * strat["risk"], 3),
                                equity=round(S["equity"], 2)))
            S["positions"].pop(sym)

    # 3. new signal -> pending for next bar (only if adaptive layer allows it)
    if not st.get("_active", {}).get(sid, True):
        return                      # deactivated: manage existing, take no new trades
    if sym not in S["positions"] and sym not in S["pending"] \
       and len(S["positions"]) < strat["maxpos"]:
        sig = FILTERS[strat["filt"]](closed, gen_signals(closed, strat["fam"], strat["p"]))
        action = Action(int(sig.iloc[-1]))
        a = float(atr_ind(closed, 14).iloc[-1])
        if action != Action.HOLD and np.isfinite(a) and a > 0:
            S["pending"][sym] = dict(dir=1 if action == Action.BUY else -1,
                                     atr=a, risk=d_sl * a)


RISKS = {s["id"]: s["risk"] for s in STRATEGIES}   # arms the circuit breaker


def cycle(ex, st):
    # adaptive layer: statistical cut (dead edge) + circuit breaker (drawdown)
    adaptive.refresh(st, [s["id"] for s in STRATEGIES], log, RISKS)
    for sym in SYMBOLS:
        try:
            o = ex.fetch_ohlcv(sym, TIMEFRAME, limit=300)
        except Exception as e:
            log(f"[{sym}] fetch error: {e}"); continue
        df = pd.DataFrame(o, columns=["t", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["t"], unit="ms")
        if len(df) < 250:
            continue
        closed = df.iloc[:-1].reset_index(drop=True)   # drop forming bar
        bar_t = int(closed["t"].iloc[-1])
        if st["_last_bar"].get(sym) == bar_t:
            continue
        st["_last_bar"][sym] = bar_t
        bar = closed.iloc[-1]
        for strat in STRATEGIES:
            try:
                evaluate(strat, st, sym, closed, bar)
            except Exception as e:
                log(f"[{strat['id']}][{sym}] error: {e}")
    save_state(st)


def summary(st):
    log("---- standings ----")
    rows = []
    for s in STRATEGIES:
        S = st[s["id"]]
        f = LOGS / f"trades_{s['id']}.csv"
        n = sum(1 for _ in open(f)) - 1 if f.exists() else 0
        rows.append((s["id"], S["equity"], n, len(S["positions"])))
    flags, trips = st.get("_active", {}), st.get("_tripped", {})
    for sid, eq, n, op in sorted(rows, key=lambda x: -x[1]):
        v = adaptive.evaluate(sid, flags.get(sid, True), RISKS[sid], bool(trips.get(sid)))
        mark = ("TRIPPED " if trips.get(sid) else
                "ACTIVE  " if flags.get(sid, True) else "**CUT** ")
        log(f"   {sid:22} {mark} equity={eq:9.2f} ({(eq/START_EQUITY-1)*100:+6.2f}%) "
            f"trades={n:4} open={op} meanR={v.mean_r:+.3f} dd={v.dd_pct:5.1f}% "
            f"streak={v.streak}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--mode", default="paper", choices=["paper", "demo"])
    ap.add_argument("--reset-breakers", action="store_true",
                    help="manually close any latched circuit breakers")
    args = ap.parse_args()

    if args.reset_breakers:
        st = load_state()
        done = adaptive.reset_breaker(st)
        save_state(st)
        log(f"breakers reset: {done or 'none were tripped'}")
        return

    if args.mode == "demo":
        key, sec, pw = (os.getenv("BITGET_API_KEY"), os.getenv("BITGET_SECRET"),
                        os.getenv("BITGET_PASSWORD"))
        if not all([key, sec, pw]):
            raise SystemExit("demo mode needs BITGET_API_KEY / BITGET_SECRET / BITGET_PASSWORD env vars")
        ex = ccxt.bitget({"apiKey": key, "secret": sec, "password": pw,
                          "options": {"defaultType": "swap"}})
        ex.set_sandbox_mode(True)
        log("MODE=demo (Bitget simulated futures) — verifying connection...")
        log(f"balance: {ex.fetch_balance().get('USDT', {})}")
    else:
        ex = ccxt.bitget({"options": {"defaultType": "swap"}})
        log("MODE=paper (simulated fills, no keys, no orders)")

    ex.load_markets()
    st = load_state()
    log(f"multi-strategy forward test | {len(STRATEGIES)} strategies x {len(SYMBOLS)} symbols")
    if args.once:
        cycle(ex, st); summary(st); return
    n = 0
    while True:
        try:
            cycle(ex, st)
            n += 1
            if n % 15 == 0:
                summary(st)
        except Exception as e:
            log(f"cycle error: {e}")
        time.sleep(120)


if __name__ == "__main__":
    main()
