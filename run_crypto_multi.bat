@echo off
REM Multi-strategy crypto forward test on Bitget.
REM   paper mode = simulated fills, no API keys, no orders (default)
REM   demo  mode = real orders on Bitget DEMO (needs BITGET_* env vars)
REM Logs: logs\multi.log  Trades: logs\trades_<strategy>.csv
cd /d "%~dp0"
echo Starting multi-strategy crypto forward test (PAPER mode)...
echo For Bitget demo orders instead, run:  python crypto_multi.py --mode demo
python crypto_multi.py
pause
