@echo off
setlocal
cd /d "%~dp0"
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
