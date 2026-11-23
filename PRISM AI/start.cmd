@echo off
setlocal
cd /d "%~dp0"

:: Add Ollama to PATH for this session so "ollama" works in this terminal
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
  set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
)

:: Auto-start Ollama in background if not already running
curl.exe -fsS "http://127.0.0.1:11434/api/version" >nul 2>nul
if errorlevel 1 (
  echo [PRISM AI] Starting Ollama engine...
  start "Ollama" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
  powershell -NoProfile -Command "for($i=0;$i-lt 20;$i++){try{Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -ErrorAction Stop|Out-Null;exit 0}catch{Start-Sleep -Milliseconds 300}};exit 0"
  echo [PRISM AI] Ollama engine ready.
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" server.py
  exit /b
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" server.py
  exit /b
)
where python >nul 2>nul
if not errorlevel 1 (
  python server.py
  exit /b
)
py -3 server.py
if errorlevel 1 pause
