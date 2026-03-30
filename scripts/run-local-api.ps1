param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
  throw "No se encontro .venv. Ejecuta primero .\scripts\setup-local.ps1"
}

if (-not (Test-Path (Join-Path $backendDir ".env.local"))) {
  throw "No se encontro backend/.env.local. Ejecuta primero .\scripts\setup-local.ps1"
}

Write-Host "==> Levantando API local en puerto $Port..." -ForegroundColor Cyan
Push-Location $backendDir
try {
  & $venvPython -m uvicorn app.main:app --host 0.0.0.0 --port $Port --reload
}
finally {
  Pop-Location
}

