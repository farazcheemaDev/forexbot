@echo off
REM Double-click to start the live DEMO forward-test.
REM Requirements: MT5 desktop open, logged into the demo account, Algo Trading GREEN.
cd /d "%~dp0"
echo Starting forex demo bot... (close this window or press Ctrl+C to stop)
python live_bot.py
pause
