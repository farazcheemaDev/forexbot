#!/usr/bin/env bash
# Oracle Cloud (Ubuntu ARM64) setup for the forexbot paper runners.
# Idempotent: safe to re-run.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/forexbot}"
SERVICE_USER="${SERVICE_USER:-$(whoami)}"

echo "== 1. UTC clock =="
# The bots key off hourly bar timestamps. A VM on local time decides bars at the
# wrong moment and the whole schedule drifts.
sudo timedatectl set-timezone UTC
timedatectl | head -3

echo "== 2. system packages =="
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip build-essential

echo "== 3. virtualenv =="
cd "$APP_DIR"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip -q
# NOTE: MetaTrader5 from requirements.txt is deliberately EXCLUDED - it is
# Windows-only and is needed solely by the MT5 forex bot, not by these.
./.venv/bin/pip install -q "pandas>=2.0" "numpy>=1.24" "pyyaml>=6.0" \
                           "requests>=2.31" "ccxt"
echo "installed:"; ./.venv/bin/python -c "import pandas,numpy,ccxt;print(' pandas',pandas.__version__,'numpy',numpy.__version__,'ccxt',ccxt.__version__)"

echo "== 4. smoke test (no orders, no keys needed) =="
./.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from longtrend_bot import klines, bb_break_long
d=klines('BTCUSDT',60)
assert d is not None and len(d)>40, 'Binance public API unreachable from this VM'
print(' price feed OK, last close', float(d['close'].iloc[-1]))
"

echo "== 5. install services =="
for u in deploy/*.service; do
  n=$(basename "$u")
  sudo sed -e "s|__APP_DIR__|$APP_DIR|g" -e "s|__USER__|$SERVICE_USER|g" "$u" \
    | sudo tee "/etc/systemd/system/$n" >/dev/null
  echo " installed $n"
done
sudo systemctl daemon-reload

echo
echo "DONE. Start the paper runners (no API keys required):"
echo "  sudo systemctl enable --now longtrend-paper xs-paper status-server"
echo
echo "Check them:"
echo "  systemctl status longtrend-paper --no-pager"
echo "  journalctl -u longtrend-paper -f"
echo "  curl localhost:8080 | head -40"
echo
echo "To expose the status page, open the port in Oracle's VCN security list AND:"
echo "  sudo iptables -I INPUT 6 -p tcp --dport 8080 -j ACCEPT"
echo "  sudo netfilter-persistent save"
echo "Set a token first so it is not world-readable:"
echo "  sudo systemctl edit status-server   ->   [Service]"
echo "                                            Environment=STATUS_TOKEN=pickone"
