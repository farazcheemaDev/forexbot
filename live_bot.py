"""Live DEMO trading bot.

Runs the locked strategy (long-only Donchian breakout + ATR stops on gold) on a
new-bar loop against your MetaTrader 5 demo account. Places market orders with
broker-side SL/TP, one position at a time, sized by the risk manager.

SAFETY: refuses to run unless the connected account is a DEMO account (override
requires mt5.allow_real: true in config, which we never set).

    python live_bot.py --dry-run     # no orders, just prints decisions
    python live_bot.py --once        # one decision cycle then exit
    python live_bot.py               # live demo loop
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import MetaTrader5 as mt5  # noqa: E402
from bot.core import execution as ex  # noqa: E402
from bot.core import tradelog as log  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402
from bot.core.risk import lot_size  # noqa: E402
from bot.strategies.donchian_breakout import DonchianBreakout  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

_TF = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}
_TF_SECONDS = {"M15": 900, "H1": 3600, "H4": 14400}


def load_config() -> dict:
    with open(Path(__file__).parent / "config" / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def connect(cfg: dict):
    path = cfg["mt5"].get("path")
    ok = mt5.initialize(path) if path else mt5.initialize()
    if not ok:
        raise SystemExit(f"MT5 init failed: {mt5.last_error()} (open MT5 + log into demo)")
    acct = mt5.account_info()
    if acct is None:
        raise SystemExit("Connected but no account — log into the demo account in MT5.")
    is_demo = acct.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
    if not is_demo and not cfg["mt5"].get("allow_real", False):
        mt5.shutdown()
        raise SystemExit(
            f"REFUSING TO RUN: account {acct.login} is NOT a demo account "
            f"(trade_mode={acct.trade_mode}). This bot is demo-only.")
    log.event(f"connected login={acct.login} server={acct.server} "
              f"{'DEMO' if is_demo else 'REAL'} balance={acct.balance:.2f} {acct.currency}")
    return acct


def build_strategy(cfg: dict):
    s = cfg["strategy"]
    return DonchianBreakout(period=s["period"], use_trend=s["use_trend"],
                            long_only=s["long_only"])


def decide_and_act(cfg, spec, strat, dry_run: bool):
    symbol = cfg["trading"]["symbol"]
    tf = cfg["trading"]["timeframe"]
    magic = cfg["trading"]["magic_number"]
    ex_cfg, risk = cfg["exits"], cfg["risk"]

    rates = mt5.copy_rates_from_pos(symbol, _TF[tf], 0, 400)
    if rates is None or len(rates) < 210:
        log.event(f"WARN not enough data ({0 if rates is None else len(rates)} bars)")
        return
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    positions = ex.our_positions(symbol, magic)
    sig = strat.signals(df)
    action = Action(int(sig.iloc[-1]))       # based on the just-closed bar
    a = atr_ind(df, ex_cfg["atr_period"])
    atr_val = float(a.iloc[-2])               # last CLOSED bar's ATR

    if positions:
        log.event(f"holding {len(positions)} position(s); signal={action.name} (SL/TP managed by broker)")
        return
    if action != Action.BUY:                  # long-only: only BUY entries
        log.event(f"flat; signal={action.name}; no entry")
        return

    # daily loss guard
    acct = mt5.account_info()
    if _daily_loss_hit(acct, risk):
        log.event("daily loss cap hit — skipping entries for today")
        return

    tick = mt5.symbol_info_tick(symbol)
    entry = tick.ask
    sl_dist = ex_cfg["atr_sl_mult"] * atr_val
    tp_dist = ex_cfg["atr_tp_mult"] * atr_val
    min_dist = ex.min_stop_distance(symbol)
    sl_dist = max(sl_dist, min_dist * 1.2)
    tp_dist = max(tp_dist, min_dist * 1.2)
    sl = entry - sl_dist
    tp = entry + tp_dist
    sl_pips = sl_dist / spec.pip_size
    lots = ex.normalize_lots(symbol, lot_size(acct.balance, risk["risk_per_trade_pct"],
                                              sl_pips, spec.pip_value_per_lot))

    log.event(f"BUY signal {symbol} entry~{entry:.3f} sl={sl:.3f} tp={tp:.3f} "
              f"lots={lots} (atr={atr_val:.3f}, risk={risk['risk_per_trade_pct']}%)")
    if dry_run:
        log.event("DRY-RUN: order not sent")
        return

    res = ex.open_position(symbol, "BUY", lots, sl, tp, magic)
    ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
    log.event(f"order {'OK' if ok else 'FAILED'} retcode="
              f"{getattr(res, 'retcode', None)} comment={getattr(res, 'comment', '')}")
    log.trade(event="OPEN" if ok else "OPEN_FAIL", symbol=symbol, side="BUY",
              lots=lots, price=entry, sl=sl, tp=tp,
              retcode=getattr(res, "retcode", None), comment=getattr(res, "comment", ""),
              balance=acct.balance, equity=acct.equity)


def _daily_loss_hit(acct, risk) -> bool:
    # simple guard: equity below balance by more than the daily cap
    if acct.balance <= 0:
        return False
    dd = (acct.balance - acct.equity) / acct.balance * 100.0
    return dd >= risk["max_daily_loss_pct"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    connect(cfg)
    spec = get_spec(cfg["trading"]["symbol"])
    strat = build_strategy(cfg)
    tf = cfg["trading"]["timeframe"]
    poll = cfg["trading"]["poll_seconds"]
    log.event(f"strategy={strat.name} {strat.params} symbol={cfg['trading']['symbol']} "
              f"tf={tf} spec(pip={spec.pip_size},$ /pip/lot={spec.pip_value_per_lot})")

    # --dry-run and --once both do a single decision cycle and exit (never loop)
    if args.once or args.dry_run:
        decide_and_act(cfg, spec, strat, dry_run=args.dry_run)
        mt5.shutdown()
        return

    last_bar_time = None
    log.event("live loop started — waiting for new bars (Ctrl+C to stop)")
    try:
        while True:
            rates = mt5.copy_rates_from_pos(cfg["trading"]["symbol"], _TF[tf], 0, 2)
            if rates is not None and len(rates) >= 1:
                cur = int(rates[-1]["time"])
                if last_bar_time is None:
                    last_bar_time = cur
                elif cur != last_bar_time:      # a new bar opened -> prior bar closed
                    last_bar_time = cur
                    log.event("--- new bar ---")
                    decide_and_act(cfg, spec, strat, dry_run=False)
            time.sleep(poll)
    except KeyboardInterrupt:
        log.event("stopped by user")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
