# PRISM AI Single-Command Unified Launcher
$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   PRISM AI: MULTIMODAL RAG UNIFIED LAUNCHER      " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Ensure Ollama is running
try {
    $ollamaCheck = Invoke-RestMethod "http://127.0.0.1:11434/api/version" -TimeoutSec 2
    Write-Host "[1/3] Ollama engine: ALREADY ACTIVE (v$($ollamaCheck.version))" -ForegroundColor Green
} catch {
    Write-Host "[1/3] Starting Ollama engine in background..." -ForegroundColor Yellow
    $ollamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (Test-Path $ollamaExe) {
        Start-Process $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
    } else {
        $ollamaCommand = Get-Command ollama.exe -ErrorAction SilentlyContinue
        if ($ollamaCommand) {
            Start-Process $ollamaCommand.Source -ArgumentList "serve" -WindowStyle Hidden
        } else {
            Write-Warning "Ollama is not installed. Install Ollama and the models configured in PRISM AI/.env to enable Ask question."
        }
    }
    
    # Wait for Ollama
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 300
        try {
            $check = Invoke-RestMethod "http://127.0.0.1:11434/api/version" -TimeoutSec 1
            if ($check.version) { $ready = $true; break }
        } catch {}
    }
    if ($ready) {
        Write-Host "      Ollama engine active." -ForegroundColor Green
    } else {
        Write-Host "      Warning: Ollama engine starting up..." -ForegroundColor DarkYellow
    }
}

# 2. Check and start PRISM AI backend
$demoUrl = "http://127.0.0.1:8765/#research"
try {
    $serverCheck = Invoke-RestMethod "http://127.0.0.1:8765/api/config" -TimeoutSec 2
    Write-Host "[2/3] PRISM AI backend: ALREADY ACTIVE (port 8765)" -ForegroundColor Green
} catch {
    Write-Host "[2/3] Starting PRISM AI Python backend..." -ForegroundColor Yellow
    $prismDir = Join-Path $PSScriptRoot "PRISM AI"
    if (-not (Test-Path $prismDir)) { $prismDir = $PSScriptRoot }
    
    $pythonExe = Join-Path $prismDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        $pythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    }
    if (-not (Test-Path $pythonExe)) {
        $pythonExe = Join-Path $env:USERPROFILE ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
    }
    if (-not (Test-Path $pythonExe)) {
        throw "Python is unavailable. Install Python and the packages in PRISM AI/requirements.txt."
    }
    
    $serverPy = Join-Path $prismDir "server.py"
    $dataDir = Join-Path $prismDir "data"
    
    Start-Process $pythonExe -ArgumentList "`"$serverPy`"" -WorkingDirectory $prismDir -WindowStyle Hidden -Environment @{ "PRISM_DATA" = $dataDir }
    
    # Wait for backend
    $serverReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 400
        try {
            $check = Invoke-RestMethod "http://127.0.0.1:8765/api/config" -TimeoutSec 1
            if ($check) { $serverReady = $true; break }
        } catch {}
    }
    if ($serverReady) {
        Write-Host "      Backend started successfully on port 8765." -ForegroundColor Green
    } else {
        Write-Host "      Backend is initializing..." -ForegroundColor DarkYellow
    }
}

# 3. Launch browser
Write-Host "[3/3] Opening PRISM AI Web Interface..." -ForegroundColor Cyan
Start-Process $demoUrl

Write-Host "==================================================" -ForegroundColor Green
Write-Host "   PRISM AI IS RUNNING AT:                        " -ForegroundColor Green
Write-Host "   $demoUrl" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Green
