@echo off
REM Double-click to run the 4-strategy live DEMO comparison overnight.
REM Requirements: MT5 desktop OPEN, logged into the demo account, Algo Trading GREEN.
REM Watch trades appear in the Exness / MT5 app on your phone.
REM Close this window (or Ctrl+C) to stop.
cd /d "%~dp0"
echo Starting 4-strategy demo portfolio... keep this window open.
echo Logs: logs\bot.log   Trades: logs\trades.csv
python portfolio_bot.py
pause
