@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

echo Starting backend and frontend...
echo Backend: http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173

start "mog_v2_backend" cmd /k "cd /d ""%ROOT_DIR%"" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
start "mog_v2_frontend" cmd /k "cd /d ""%ROOT_DIR%\frontend"" && npm run dev -- --host 0.0.0.0 --port 5173"

endlocal
