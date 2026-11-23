@echo off
setlocal
cd /d "%~dp0"
set "PRISM_DATA=%~dp0data"
if not exist "%PRISM_DATA%\prism.sqlite3" (
  echo The local practice workspace is unavailable. See README.md to start a new workspace.
  pause
  exit /b 1
)
set "PRISM_PORT=8765"
set "demo=http://127.0.0.1:8765/?space=8c0a4dd55f7c43c6858305d66675e395#research"
curl.exe -fsS "http://127.0.0.1:8765/api/documents?space=8c0a4dd55f7c43c6858305d66675e395" >nul 2>nul
if not errorlevel 1 (
  start "" "%demo%"
  exit /b
)
start "PRISM AI server" "%ComSpec%" /k "set PRISM_DATA=%PRISM_DATA%&& call ""%~dp0start.cmd"""
powershell -NoProfile -Command "for ($i=0;$i -lt 35;$i++){try{Invoke-RestMethod 'http://127.0.0.1:8765/api/config' -ErrorAction Stop | Out-Null;exit 0}catch{Start-Sleep -Milliseconds 400}};exit 1"
if not errorlevel 1 start "" "%demo%"
