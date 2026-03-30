param(
  [Parameter(Mandatory = $true)]
  [string]$ResultJson,
  [string]$OutputDir = ""
)

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
  if ($WorkingDirectory) { Push-Location $WorkingDirectory }
  try {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Fallo el comando: $Command $($Arguments -join ' ')"
    }
  } finally {
    if ($WorkingDirectory) { Pop-Location }
  }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
  throw "No se encontro .venv. Ejecuta primero .\scripts\setup-local.ps1"
}
if (-not (Test-Path -LiteralPath $ResultJson)) {
  throw "No existe el JSON de resultado: $ResultJson"
}

$cliArgs = @(
  "scripts/generate_simulation_charts.py",
  "--result-json", $ResultJson
)
if ($OutputDir) {
  $resolvedOutputDir = Join-Path $repoRoot $OutputDir
  $cliArgs += @("--output-dir", $resolvedOutputDir)
}

Write-Host "==> Generando gráficas locales (HTML + PNG)..." -ForegroundColor Cyan
Invoke-Checked -Command $venvPython -Arguments $cliArgs -WorkingDirectory $backendDir
Write-Host "==> Gráficas generadas." -ForegroundColor Green

