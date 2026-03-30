param(
  [switch]$Volumes
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "==> Apagando stack Docker..." -ForegroundColor Cyan

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
  if ($Volumes) {
    docker compose down -v
    Write-Host "Stack detenido y volumenes eliminados." -ForegroundColor Yellow
  } else {
    docker compose down
    Write-Host "Stack detenido." -ForegroundColor Yellow
  }
}
finally {
  Pop-Location
}

