$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = $PSScriptRoot

Write-Host "==> Reinicio limpio del stack (down -v + up)..." -ForegroundColor Cyan

& (Join-Path $scriptDir "stack-down.ps1") -Volumes
& (Join-Path $scriptDir "stack-up.ps1")

Write-Host "==> Reset completado." -ForegroundColor Green

