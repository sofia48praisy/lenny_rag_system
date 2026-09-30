param([string]$RuntimeRoot = 'D:\lenny-runtime')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$localRoot = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Path $localRoot -Force | Out-Null
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install backend dependencies first. See README.' }
& $pythonExe (Join-Path $PSScriptRoot 'initialize_local.py') --runtime $RuntimeRoot
if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
$env:OLLAMA_MODELS = Join-Path $RuntimeRoot 'models'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_CONTEXT_LENGTH = '8192'
try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null }
catch {
  Start-Process -FilePath (Join-Path $RuntimeRoot 'ollama\ollama.exe') -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $localRoot 'ollama.out.log') -RedirectStandardError (Join-Path $localRoot 'ollama.err.log')
}
if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $pythonExe -WorkingDirectory (Join-Path $projectRoot 'backend') -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $localRoot 'backend.out.log') -RedirectStandardError (Join-Path $localRoot 'backend.err.log')
}
if (-not (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
  $nodeExe = (Get-Command node -ErrorAction Stop).Source
  Start-Process -FilePath $nodeExe -WorkingDirectory (Join-Path $projectRoot 'frontend') -ArgumentList 'node_modules/vite/bin/vite.js','--host','127.0.0.1' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $localRoot 'frontend.out.log') -RedirectStandardError (Join-Path $localRoot 'frontend.err.log')
}
Write-Output 'Open http://127.0.0.1:5173. If the archive is empty, run ingestion as described in docs/windows-local.md.'
