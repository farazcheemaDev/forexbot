@echo off
REM Bitget DEMO trading - single strategy, REAL orders on simulated money.
REM Requires: Bitget account in CLASSIC mode + Demo Trading enabled
REM           BITGET_API_KEY / BITGET_SECRET / BITGET_PASSWORD env vars
REM Logs: logs\demo.log
cd /d "%~dp0"
echo Checking Bitget demo connection...
python crypto_demo.py --check
echo.
echo If the check passed, starting the demo bot. Ctrl+C to stop.
echo (To see signals without sending orders, run: python crypto_demo.py --dry)
pause
python crypto_demo.py
pause
