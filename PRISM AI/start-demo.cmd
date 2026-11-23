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

:: 1. Ensure Ollama is running
curl.exe -fsS "http://127.0.0.1:11434/api/version" >nul 2>nul
if errorlevel 1 (
  echo [PRISM AI] Starting Ollama engine in background...
  if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    start "Ollama" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
  ) else (
    start "Ollama" /min ollama serve
  )
  powershell -NoProfile -Command "for ($i=0;$i -lt 20;$i++){try{Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -ErrorAction Stop | Out-Null;exit 0}catch{Start-Sleep -Milliseconds 300}};exit 0"
)

:: 2. Check if PRISM AI backend is already active
curl.exe -fsS "http://127.0.0.1:8765/api/documents?space=8c0a4dd55f7c43c6858305d66675e395" >nul 2>nul
if not errorlevel 1 (
  echo [PRISM AI] Server is already running. Opening browser...
  start "" "%demo%"
  exit /b
)

:: 3. Start PRISM AI backend server
echo [PRISM AI] Starting backend server on port %PRISM_PORT%...
start "PRISM AI Server" "%ComSpec%" /k "set PRISM_DATA=%PRISM_DATA%&& call ""%~dp0start.cmd"""
powershell -NoProfile -Command "for ($i=0;$i -lt 35;$i++){try{Invoke-RestMethod 'http://127.0.0.1:8765/api/config' -ErrorAction Stop | Out-Null;exit 0}catch{Start-Sleep -Milliseconds 400}};exit 1"
if not errorlevel 1 (
  echo [PRISM AI] All components online! Opening browser...
  start "" "%demo%"
) else (
  echo [PRISM AI] Server is still initializing. Check the PRISM AI Server window.
)
