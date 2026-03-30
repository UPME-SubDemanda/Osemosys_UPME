param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments,
    [Parameter(Mandatory = $false)]
    [string]$WorkingDirectory
  )

  if ($WorkingDirectory) {
    Push-Location $WorkingDirectory
  }
  try {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Fallo el comando: $Command $($Arguments -join ' ')"
    }
  }
  finally {
    if ($WorkingDirectory) {
      Pop-Location
    }
  }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
  throw "No se encontro .venv. Ejecuta primero .\scripts\setup-local.ps1"
}

if (-not (Test-Path (Join-Path $backendDir ".env.local"))) {
  throw "No se encontro backend/.env.local. Ejecuta primero .\scripts\setup-local.ps1"
}

Write-Host "==> Inicializando base de datos local..." -ForegroundColor Cyan
Invoke-Checked -Command $venvPython -Arguments @("scripts/init_local_db.py") -WorkingDirectory $backendDir

Write-Host "==> Ejecutando seed mínimo..." -ForegroundColor Cyan
Invoke-Checked -Command $venvPython -Arguments @("scripts/seed.py") -WorkingDirectory $backendDir

Write-Host "==> Base local inicializada." -ForegroundColor Green

