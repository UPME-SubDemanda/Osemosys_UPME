param(
  [Parameter(Mandatory = $true)]
  [string]$ExcelPath,
  [string]$ScenarioName = "SAND_04_02_2026",
  [string]$SheetName = "Parameters",
  [ValidateSet("highs", "glpk")]
  [string]$Solver = "highs",
  [string]$OutputDir = "backend/tmp/local",
  [switch]$Replace,
  [string]$SeedUsername = "seed",
  [switch]$WithCharts,
  [switch]$DumpAllTables
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
if (-not (Test-Path -LiteralPath $ExcelPath)) {
  throw "No existe el Excel en: $ExcelPath"
}

$resolvedOutputDir = Join-Path $repoRoot $OutputDir

$cliArgs = @(
  "scripts/run_sand_excel_test.py",
  "--excel", $ExcelPath,
  "--scenario-name", $ScenarioName,
  "--sheet-name", $SheetName,
  "--solver", $Solver,
  "--output-dir", $resolvedOutputDir,
  "--seed-username", $SeedUsername
)
if ($Replace) {
  $cliArgs += "--replace"
}

Write-Host "==> Ejecutando pipeline local Excel -> simulación..." -ForegroundColor Cyan
Invoke-Checked -Command $venvPython -Arguments $cliArgs -WorkingDirectory $backendDir

if ($WithCharts) {
  $resultJson = Join-Path $resolvedOutputDir "simulation_result.json"
  $chartsDir = Join-Path $resolvedOutputDir "charts"
  Write-Host "==> Generando gráficas (HTML + PNG)..." -ForegroundColor Cyan
  Invoke-Checked -Command $venvPython -Arguments @(
    "scripts/generate_simulation_charts.py",
    "--result-json", $resultJson,
    "--output-dir", $chartsDir
  ) -WorkingDirectory $backendDir
}

if ($DumpAllTables) {
  $tablesDir = Join-Path $resolvedOutputDir "tables"
  Write-Host "==> Exportando todas las tablas a CSV..." -ForegroundColor Cyan
  Invoke-Checked -Command $venvPython -Arguments @(
    "scripts/local_db_tools.py",
    "dump-all-tables",
    "--output-dir", $tablesDir
  ) -WorkingDirectory $backendDir
}

Write-Host "==> Listo. Artefactos en: $resolvedOutputDir" -ForegroundColor Green

