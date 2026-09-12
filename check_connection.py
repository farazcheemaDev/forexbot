"""Step 1 smoke test: connect to your logged-in MT5 demo terminal and print
account info + a few EURUSD candles. Run this AFTER you:
  1. install requirements  (pip install -r requirements.txt)
  2. open MetaTrader 5 and log into your DEMO account
  3. enable Algo Trading in MT5

    python check_connection.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from bot.core.broker import Broker  # noqa: E402


def load_config() -> dict:
    cfg_path = Path(__file__).parent / "config" / "config.yaml"
    if not cfg_path.exists():
        print("!! config/config.yaml not found. Copy config/config.example.yaml "
              "to config/config.yaml and fill it in.")
        sys.exit(1)
    with open(cfg_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> None:
    cfg = load_config()
    broker = Broker(path=cfg["mt5"].get("path"))
    try:
        info = broker.connect()
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Could not connect to MT5: {exc}")
        print("Checklist: MT5 open? logged into DEMO? Algo Trading green?")
        sys.exit(1)

    print("[OK] Connected to MetaTrader 5")
    print(f"  Login:    {info.login}")
    print(f"  Server:   {info.server}")
    print(f"  Balance:  {info.balance:.2f} {info.currency}")
    print(f"  Equity:   {info.equity:.2f} {info.currency}")
    print(f"  Leverage: 1:{info.leverage}")

    symbol = cfg["trading"]["symbol"]
    tf = cfg["trading"]["timeframe"]
    if not broker.symbol_ready(symbol):
        print(f"[WARN] Symbol {symbol} not available on this account.")
    else:
        df = broker.get_candles(symbol, tf, count=5)
        print(f"\n[OK] Last 5 {symbol} {tf} candles:")
        print(df[["time", "open", "high", "low", "close"]].to_string(index=False))

    broker.shutdown()
    print("\nDone. If you see account info + candles above, Step 1 is complete.")


if __name__ == "__main__":
    main()
