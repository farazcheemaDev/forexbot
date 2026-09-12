"""One-shot execution smoke test on DEMO: open a minimal 0.01-lot BUY with
SL/TP, verify it appears, then immediately close it and report P/L. Proves the
order plumbing (execution.py) works before the forward-test relies on it.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import MetaTrader5 as mt5  # noqa: E402
from bot.core import execution as ex  # noqa: E402
from bot.core.instrument import get_spec  # noqa: E402


def main():
    cfg = yaml.safe_load(open(Path(__file__).parent / "config" / "config.yaml", encoding="utf-8"))
    symbol = cfg["trading"]["symbol"]
    magic = cfg["trading"]["magic_number"]

    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    acct = mt5.account_info()
    if acct.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        mt5.shutdown()
        raise SystemExit("Refusing: not a demo account.")
    print(f"DEMO {acct.login} balance={acct.balance:.2f} {acct.currency}")

    mt5.symbol_select(symbol, True)
    spec = get_spec(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or tick.ask == 0:
        mt5.shutdown()
        raise SystemExit(f"No tick for {symbol} — market may be closed.")

    entry = tick.ask
    min_d = ex.min_stop_distance(symbol)
    # comfortable distances for gold: ~$5 SL / $10 TP, and well beyond min stop
    sl_d = max(500 * spec.pip_size, min_d * 2)
    tp_d = max(1000 * spec.pip_size, min_d * 2)
    sl, tp = entry - sl_d, entry + tp_d
    lots = ex.normalize_lots(symbol, 0.01)

    print(f"placing TEST BUY {symbol} lots={lots} entry~{entry:.3f} sl={sl:.3f} tp={tp:.3f}")
    res = ex.open_position(symbol, "BUY", lots, sl, tp, magic, comment="smoketest")
    print(f"  open retcode={getattr(res,'retcode',None)} comment={getattr(res,'comment','')} "
          f"deal={getattr(res,'deal',None)}")
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        mt5.shutdown()
        raise SystemExit("Open FAILED — see retcode above.")

    time.sleep(2)
    positions = ex.our_positions(symbol, magic)
    print(f"  open positions (our magic): {len(positions)}")
    for p in positions:
        print(f"    ticket={p.ticket} vol={p.volume} price_open={p.price_open} "
              f"sl={p.sl} tp={p.tp} profit={p.profit}")

    # close it right back
    for p in positions:
        cres = ex.close_position(p)
        print(f"  close ticket={p.ticket} retcode={getattr(cres,'retcode',None)} "
              f"comment={getattr(cres,'comment','')}")

    time.sleep(1)
    remaining = ex.our_positions(symbol, magic)
    print(f"  positions after close: {len(remaining)}")
    acct2 = mt5.account_info()
    print(f"  balance now={acct2.balance:.2f} equity={acct2.equity:.2f}")
    print("SMOKE TEST PASSED" if len(remaining) == 0 else "WARNING: position still open")
    mt5.shutdown()


if __name__ == "__main__":
    main()
