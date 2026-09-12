@echo off
REM Double-click to run the Bitget crypto PAPER forward-test.
REM No API keys, no real orders - public market data only.
REM Logs: logs\paper.log   Trades: logs\paper_trades.csv
cd /d "%~dp0"
echo Starting Bitget crypto paper forward-test... (close window or Ctrl+C to stop)
python crypto_paper.py
pause
