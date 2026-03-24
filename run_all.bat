@echo off
setlocal

cd /d %~dp0

echo [1/3] Starting manual trigger API on http://127.0.0.1:8000 ...
start "iMouseGuard API" powershell -NoExit -Command "cd iMouseGuard\dev\manual_trigger_api; uvicorn app:app --host 127.0.0.1 --port 8000"

timeout /t 2 >nul

echo [2/3] Starting WS forwarder ...
start "iMouseGuard Forwarder" powershell -NoExit -Command "cd iMouseGuard; python bin\zmes_ws_to_telegram.py"

timeout /t 2 >nul

echo [3/3] Opening browser UI ...
start "" "http://127.0.0.1:8000"

echo.
echo iMouseGuard dev stack started.
echo API:      http://127.0.0.1:8000
echo API Docs: http://127.0.0.1:8000/docs
echo.
