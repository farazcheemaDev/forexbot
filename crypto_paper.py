"""Live PAPER-trading forward test on Bitget (no API keys, no real orders).

Mirrors the backtest exactly: a signal computed from a CLOSED bar is entered at
the NEXT bar's open, with ATR stop/target, and exits are checked against real
subsequent price action. Everything is simulated locally and logged, so the
forward record is directly comparable to the backtest.

    python crypto_paper.py --once     # single cycle (safe to test)
    python crypto_paper.py            # live loop, checks each hour
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

from backtest.mass_search import FILTERS, gen_signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "logs" / "paper_state.json"
TRADES = ROOT / "logs" / "paper_trades.csv"

SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT",
           "XRP/USDT:USDT", "BNB/USDT:USDT", "AVAX/USDT:USDT"]
TIMEFRAME = "1h"
FAM, PARAMS, FILT = "rsi_mom", (7, 40, 60), "er30"
SL_MULT, TP_MULT = 2.0, 3.0
RISK_PCT = 1.0          # of equity per trade
START_EQUITY = 1000.0
MAKER_FEE, TAKER_FEE = 0.0002, 0.0006


def log(msg):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(ROOT / "logs" / "paper.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state():
    if STATE.exists():
        return json.load(open(STATE))
    return {"equity": START_EQUITY, "positions": {}, "pending": {}, "last_bar": {}}


def save_state(s):
    STATE.parent.mkdir(exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=1)


def log_trade(row):
    new = not TRADES.exists()
    with open(TRADES, "a", encoding="utf-8") as f:
        if new:
            f.write("ts_utc,symbol,side,entry,exit,reason,R,pnl_pct,equity\n")
        f.write(",".join(str(row[k]) for k in
                ["ts", "symbol", "side", "entry", "exit", "reason", "R", "pnl_pct", "equity"]) + "\n")


def fetch_df(ex, symbol, limit=300):
    o = ex.fetch_ohlcv(symbol, TIMEFRAME, limit=limit)
    df = pd.DataFrame(o, columns=["t", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["t"], unit="ms")
    return df


def cycle(ex, st):
    for sym in SYMBOLS:
        try:
            df = fetch_df(ex, sym)
        except Exception as e:
            log(f"[{sym}] fetch error: {e}")
            continue
        if len(df) < 250:
            continue
        # the last row is the still-forming bar; the last CLOSED bar is -2
        closed = df.iloc[:-1].reset_index(drop=True)
        bar_t = int(closed["t"].iloc[-1])
        if st["last_bar"].get(sym) == bar_t:
            continue                      # already processed this bar
        st["last_bar"][sym] = bar_t
        bar = closed.iloc[-1]
        log(f"[{sym}] new closed bar {bar['time']:%m-%d %H:%M} close={bar['close']}")

        # --- 1. fill any pending entry at THIS bar's open ---
        pend = st["pending"].pop(sym, None)
        if pend and sym not in st["positions"]:
            entry = float(bar["open"])
            risk = pend["risk"]
            d = pend["dir"]
            st["positions"][sym] = {
                "dir": d, "entry": entry, "risk": risk,
                "sl": entry - d * risk, "tp": entry + d * TP_MULT * pend["atr"],
                "opened": bar_t}
            log(f"[{sym}] PAPER ENTRY {'LONG' if d==1 else 'SHORT'} @ {entry:.4f} "
                f"sl={st['positions'][sym]['sl']:.4f} tp={st['positions'][sym]['tp']:.4f}")

        # --- 2. manage open position against this bar ---
        pos = st["positions"].get(sym)
        if pos:
            d = pos["dir"]
            hi, lo = float(bar["high"]), float(bar["low"])
            exit_px, reason = None, ""
            if (lo <= pos["sl"]) if d == 1 else (hi >= pos["sl"]):
                exit_px, reason = pos["sl"], "SL"
            elif (hi >= pos["tp"]) if d == 1 else (lo <= pos["tp"]):
                exit_px, reason = pos["tp"], "TP"
            if exit_px is not None:
                R = (exit_px - pos["entry"]) * d / pos["risk"]
                R -= (MAKER_FEE + TAKER_FEE) * pos["entry"] / pos["risk"]
                pnl_pct = R * RISK_PCT
                st["equity"] *= (1 + pnl_pct / 100.0)
                log(f"[{sym}] PAPER EXIT {reason} @ {exit_px:.4f}  R={R:+.2f}  "
                    f"equity={st['equity']:.2f}")
                log_trade({"ts": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                           "symbol": sym, "side": "LONG" if d == 1 else "SHORT",
                           "entry": round(pos["entry"], 6), "exit": round(exit_px, 6),
                           "reason": reason, "R": round(R, 3),
                           "pnl_pct": round(pnl_pct, 3), "equity": round(st["equity"], 2)})
                st["positions"].pop(sym)

        # --- 3. new signal from the closed bar -> pending entry next bar ---
        if sym not in st["positions"] and sym not in st["pending"]:
            sig = FILTERS[FILT](closed, gen_signals(closed, FAM, PARAMS))
            action = Action(int(sig.iloc[-1]))
            a = float(atr_ind(closed, 14).iloc[-1])
            if action != Action.HOLD and np.isfinite(a) and a > 0:
                d = 1 if action == Action.BUY else -1
                st["pending"][sym] = {"dir": d, "atr": a, "risk": SL_MULT * a}
                log(f"[{sym}] SIGNAL {action.name} -> will enter at next bar open "
                    f"(atr={a:.4f})")
    save_state(st)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    (ROOT / "logs").mkdir(exist_ok=True)
    ex = ccxt.bitget()
    ex.load_markets()
    st = load_state()
    log(f"paper forward-test start | equity={st['equity']:.2f} | {len(SYMBOLS)} symbols "
        f"| {FAM}{PARAMS}+{FILT} | PAPER ONLY, no orders, no API keys")
    if args.once:
        cycle(ex, st)
        return
    while True:
        try:
            cycle(ex, st)
        except Exception as e:
            log(f"cycle error: {e}")
        time.sleep(120)


if __name__ == "__main__":
    main()
