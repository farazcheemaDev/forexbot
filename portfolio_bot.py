"""Multi-strategy live DEMO runner.

Runs every strategy in config['portfolio'] side by side on the same demo account,
each with its own magic number so results are tracked and compared separately.
Same safety guard as live_bot: DEMO accounts only.

    python portfolio_bot.py --dry-run    # evaluate every strategy once, no orders
    python portfolio_bot.py --once       # one cycle, place orders, exit
    python portfolio_bot.py              # continuous live loop
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import MetaTrader5 as mt5  # noqa: E402
from bot.core import adaptive  # noqa: E402
from bot.core import execution as ex  # noqa: E402
from bot.core import tradelog as log  # noqa: E402
from bot.core.filters import (apply_adx_filter, apply_atr_quantile_filter,  # noqa: E402
                              apply_session_filter)
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.core.instrument import InstrumentSpec, get_spec  # noqa: E402
from bot.core.risk import lot_size  # noqa: E402
from bot.strategies.base import Action  # noqa: E402
from bot.strategies.factory import build_strategy  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
       "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}


@dataclass
class Runner:
    id: str
    strategy: object
    symbol: str
    timeframe: str
    magic: int
    risk_pct: float
    exits: dict
    filters: dict
    spec: InstrumentSpec
    last_bar_time: int | None = None


_LOGGED_PATH = Path(__file__).parent / "logs" / "logged_deals.txt"
_RISK_PATH = Path(__file__).parent / "logs" / "forex_open_risk.json"
_ADAPT_PATH = Path(__file__).parent / "logs" / "forex_adaptive.json"
_ACTIVE: dict[str, bool] = {}      # sleeve id -> adaptive layer allows new entries


def _load_adaptive() -> dict:
    """Adaptive flags + latched circuit breakers. Persisted because a breaker
    that forgets it tripped on restart is not a breaker."""
    if _ADAPT_PATH.exists():
        try:
            return json.load(open(_ADAPT_PATH))
        except Exception:
            pass
    return {"_active": {}, "_tripped": {}}


def _save_adaptive(d: dict) -> None:
    _ADAPT_PATH.parent.mkdir(exist_ok=True)
    json.dump(d, open(_ADAPT_PATH, "w"), indent=1)


def _load_risk() -> dict:
    """Risk amount ($) staked on each open position, so exits can be scored in R."""
    if _RISK_PATH.exists():
        try:
            return json.load(open(_RISK_PATH))
        except Exception:
            return {}
    return {}


def _save_risk(d: dict) -> None:
    _RISK_PATH.parent.mkdir(exist_ok=True)
    json.dump(d, open(_RISK_PATH, "w"), indent=1)


def _log_r(sid: str, row: dict) -> None:
    """Per-strategy R log, same format the adaptive layer reads."""
    f = Path(__file__).parent / "logs" / f"trades_{sid}.csv"
    new = not f.exists()
    with open(f, "a", encoding="utf-8") as fh:
        if new:
            fh.write("ts_utc,symbol,side,exit,reason,R,pnl,equity\n")
        fh.write(",".join(str(row[k]) for k in
                 ["ts", "symbol", "side", "exit", "reason", "R", "pnl", "equity"]) + "\n")


def _load_logged() -> set[int]:
    if _LOGGED_PATH.exists():
        return {int(x) for x in _LOGGED_PATH.read_text().split() if x.strip().isdigit()}
    return set()


def log_exits(magic_to_id: dict[int, str], logged: set[int]) -> None:
    """Poll closed deals and log any exit we haven't recorded yet. Catches
    broker-side SL/TP closes, which the bot never sees as an action."""
    frm = datetime.now() - timedelta(days=3)
    deals = mt5.history_deals_get(frm, datetime.now() + timedelta(hours=12)) or []
    new = False
    for d in deals:
        if d.entry != mt5.DEAL_ENTRY_OUT or d.magic not in magic_to_id:
            continue
        if d.ticket in logged:
            continue
        sleeve = magic_to_id[d.magic]
        c = (d.comment or "").lower()
        reason = "SL" if "sl" in c else ("TP" if "tp" in c else "close")
        pnl = d.profit + d.commission + d.swap
        acct = mt5.account_info()
        # score the trade in R using the risk staked at entry
        risks = _load_risk()
        key = f"{d.magic}:{d.symbol}"
        risk_amt = risks.pop(key, None)
        if risk_amt:
            R = pnl / risk_amt
            _log_r(sleeve, dict(ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                symbol=d.symbol, side="SELL" if d.type == mt5.DEAL_TYPE_SELL else "BUY",
                                exit=d.price, reason=reason, R=round(R, 3),
                                pnl=round(pnl, 2),
                                equity=round(acct.equity, 2) if acct else ""))
            _save_risk(risks)
            log.event(f"[{sleeve}] EXIT {reason} {d.symbol} @{d.price} "
                      f"profit={pnl:.2f} R={R:+.2f}")
        else:
            log.event(f"[{sleeve}] EXIT {reason} {d.symbol} @{d.price} profit={pnl:.2f} "
                      f"(no risk record - not scored in R)")
        log.trade(event=f"CLOSE:{sleeve}", symbol=d.symbol,
                  side="SELL" if d.type == mt5.DEAL_TYPE_SELL else "BUY",
                  lots=d.volume, price=d.price, profit=round(pnl, 2), reason=reason,
                  deal=d.ticket, comment=d.comment,
                  balance=acct.balance if acct else "", equity=acct.equity if acct else "")
        logged.add(d.ticket)
        new = True
    if new:
        _LOGGED_PATH.parent.mkdir(exist_ok=True)
        _LOGGED_PATH.write_text("\n".join(str(t) for t in sorted(logged)))


def connect(cfg):
    path = cfg["mt5"].get("path")
    ok = mt5.initialize(path) if path else mt5.initialize()
    if not ok:
        raise SystemExit(f"MT5 init failed: {mt5.last_error()} (open MT5 + log into demo)")
    acct = mt5.account_info()
    if acct is None:
        raise SystemExit("Connected but no account — log into the demo account in MT5.")
    if acct.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO and not cfg["mt5"].get("allow_real", False):
        mt5.shutdown()
        raise SystemExit(f"REFUSING TO RUN: account {acct.login} is not DEMO.")
    log.event(f"connected login={acct.login} {acct.server} DEMO balance={acct.balance:.2f}")
    return acct


def build_runners(cfg) -> list[Runner]:
    runners = []
    for e in cfg["portfolio"]:
        mt5.symbol_select(e["symbol"], True)
        runners.append(Runner(
            id=e["id"], strategy=build_strategy(e["strategy"], e.get("params")),
            symbol=e["symbol"], timeframe=e["timeframe"], magic=e["magic"],
            risk_pct=e["risk_pct"], exits=e["exits"], filters=e.get("filters") or {},
            spec=get_spec(e["symbol"]),
        ))
        log.event(f"loaded [{e['id']}] {e['strategy']} {e.get('params')} "
                  f"{e['symbol']} {e['timeframe']} magic={e['magic']} filters={e.get('filters') or {}}")
    return runners


def signal_for(r: Runner, df: pd.DataFrame) -> Action:
    sig = r.strategy.signals(df)
    f = r.filters
    if "adx" in f:
        sig = apply_adx_filter(sig, df, min_adx=f["adx"])
    if "atrq" in f:
        sig = apply_atr_quantile_filter(sig, df, min_quantile=f["atrq"])
    if f.get("session"):
        sig = apply_session_filter(sig, df)
    return Action(int(sig.iloc[-1]))


def evaluate(r: Runner, dry_run: bool):
    rates = mt5.copy_rates_from_pos(r.symbol, _TF[r.timeframe], 0, 400)
    if rates is None or len(rates) < 210:
        log.event(f"[{r.id}] WARN insufficient data")
        return
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    action = signal_for(r, df)
    atr_val = float(atr_ind(df, r.exits["atr_period"]).iloc[-2])
    positions = ex.our_positions(r.symbol, r.magic)

    if positions:
        held = "BUY" if positions[0].type == mt5.POSITION_TYPE_BUY else "SELL"
        opposite = (action == Action.SELL and held == "BUY") or (action == Action.BUY and held == "SELL")
        if opposite and not dry_run:
            for p in positions:
                ex.close_position(p)
            log.event(f"[{r.id}] closed {held} on opposite signal {action.name}")
        else:
            log.event(f"[{r.id}] holding {held}; signal={action.name}")
        return

    if action == Action.HOLD:
        log.event(f"[{r.id}] flat; HOLD")
        return
    if not _ACTIVE.get(r.id, True):
        log.event(f"[{r.id}] BLOCKED (adaptive/breaker) - no new entries")
        return

    side = "BUY" if action == Action.BUY else "SELL"
    acct = mt5.account_info()
    tick = mt5.symbol_info_tick(r.symbol)
    entry = tick.ask if side == "BUY" else tick.bid
    min_d = ex.min_stop_distance(r.symbol)
    sl_d = max(r.exits["atr_sl_mult"] * atr_val, min_d * 1.2)
    tp_d = max(r.exits["atr_tp_mult"] * atr_val, min_d * 1.2)
    direction = 1 if side == "BUY" else -1
    sl = entry - direction * sl_d
    tp = entry + direction * tp_d
    lots = ex.normalize_lots(r.symbol, lot_size(acct.balance, r.risk_pct,
                                                sl_d / r.spec.pip_size, r.spec.pip_value_per_lot))

    log.event(f"[{r.id}] {side} {r.symbol} entry~{entry:.3f} sl={sl:.3f} tp={tp:.3f} lots={lots}")
    if dry_run:
        log.event(f"[{r.id}] DRY-RUN: order not sent")
        return
    res = ex.open_position(r.symbol, side, lots, sl, tp, r.magic, comment=r.id)
    ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
    if ok:   # remember what we staked so the exit can be scored in R
        risks = _load_risk()
        risks[f"{r.magic}:{r.symbol}"] = (sl_d / r.spec.pip_size) * r.spec.pip_value_per_lot * lots
        _save_risk(risks)
    log.event(f"[{r.id}] order {'OK' if ok else 'FAIL'} retcode={getattr(res,'retcode',None)}")
    log.trade(event=f"OPEN:{r.id}" if ok else f"FAIL:{r.id}", symbol=r.symbol, side=side,
              lots=lots, price=entry, sl=sl, tp=tp, retcode=getattr(res, "retcode", None),
              comment=r.id, balance=acct.balance, equity=acct.equity)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--reset-breakers", action="store_true",
                    help="manually close any latched circuit breakers")
    args = ap.parse_args()

    if args.reset_breakers:                 # no MT5 needed, just state on disk
        st = _load_adaptive()
        done = adaptive.reset_breaker(st)
        _save_adaptive(st)
        print(f"breakers reset: {done or 'none were tripped'}")
        return

    cfg = yaml.safe_load(open(Path(__file__).parent / "config" / "config.yaml", encoding="utf-8"))
    connect(cfg)
    runners = build_runners(cfg)
    poll = cfg["trading"]["poll_seconds"]

    if args.dry_run or args.once:
        for r in runners:
            evaluate(r, dry_run=args.dry_run)
        mt5.shutdown()
        return

    magic_to_id = {r.magic: r.id for r in runners}
    logged = _load_logged()
    log_exits(magic_to_id, logged)      # catch up on any exits since last run
    _adaptive_state = _load_adaptive()
    risks = {r.id: r.risk_pct for r in runners}     # arms the circuit breaker
    _ACTIVE.update(_adaptive_state.get("_active", {}))
    for sid, on in sorted(_adaptive_state.get("_tripped", {}).items()):
        if on:
            log.event(f"[BREAKER] {sid}: still LATCHED from a previous run "
                      f"(--reset-breakers to clear)")
    log.event(f"portfolio loop started: {len(runners)} strategies "
              f"| breaker at -{adaptive.MAX_DD_PCT}% or {adaptive.MAX_LOSS_STREAK} "
              f"straight losses (Ctrl+C to stop)")
    try:
        while True:
            log_exits(magic_to_id, logged)
            # adaptive layer: statistical cut (dead edge) + circuit breaker (drawdown)
            adaptive.refresh(_adaptive_state, [r.id for r in runners], log.event, risks)
            _ACTIVE.update(_adaptive_state["_active"])
            _save_adaptive(_adaptive_state)
            for r in runners:
                rates = mt5.copy_rates_from_pos(r.symbol, _TF[r.timeframe], 0, 2)
                if rates is None or len(rates) < 1:
                    continue
                cur = int(rates[-1]["time"])
                if r.last_bar_time is None:
                    r.last_bar_time = cur
                elif cur != r.last_bar_time:
                    r.last_bar_time = cur
                    log.event(f"--- new {r.timeframe} bar for {r.id} ---")
                    evaluate(r, dry_run=False)
            time.sleep(poll)
    except KeyboardInterrupt:
        log.event("stopped by user")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
