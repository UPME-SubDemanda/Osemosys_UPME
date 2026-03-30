param(
  [string]$ExcelPath = "C:\Users\jchav\OneDrive - Universidad de los Andes\Documentos\Trabajo UPME\Archivos osmosys\Excel\SAND_04_02_2026.xlsm"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendTmp = Join-Path $repoRoot "backend\tmp"
$containerExcelPath = "/app/tmp/SAND_04_02_2026.xlsm"
$containerResultPath = "/app/tmp/sand_04_02_2026_result.json"
$hostResultPath = Join-Path $backendTmp "sand_04_02_2026_result.json"

# 1. Comprobar que el archivo Excel existe
if (-not (Test-Path -LiteralPath $ExcelPath)) {
  Write-Host "[ERROR] No existe el archivo Excel: $ExcelPath" -ForegroundColor Red
  Write-Host "        Usa -ExcelPath para indicar la ruta correcta." -ForegroundColor Yellow
  exit 1
}

Write-Host "==> Prueba SAND (Excel Parameters)" -ForegroundColor Cyan
Write-Host "    Excel: $ExcelPath" -ForegroundColor Gray

# 2. Comprobar que el stack está arriba
Push-Location $repoRoot
try {
  $null = docker compose ps 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Compose no está disponible o el stack no está levantado." -ForegroundColor Red
    Write-Host "        Ejecuta primero: .\scripts\stack-up.ps1" -ForegroundColor Yellow
    exit 1
  }

  # 3. Copiar el Excel al contenedor
  Write-Host "==> Copiando Excel al contenedor..." -ForegroundColor Cyan
  docker compose cp "$ExcelPath" "api:$containerExcelPath"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] No se pudo copiar el archivo al contenedor." -ForegroundColor Red
    exit 1
  }

  # 4. Ejecutar run_sand_excel_test.py en el contenedor
  Write-Host "==> Ejecutando importación y simulación (solver glpk)..." -ForegroundColor Cyan
  docker compose exec api python scripts/run_sand_excel_test.py --excel $containerExcelPath --replace --solver glpk
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] La simulación falló." -ForegroundColor Red
    exit 1
  }

  # 5. Crear backend/tmp en el host si no existe y copiar el resultado
  if (-not (Test-Path $backendTmp)) {
    New-Item -ItemType Directory -Path $backendTmp -Force | Out-Null
  }
  Write-Host "==> Copiando resultado al host..." -ForegroundColor Cyan
  docker compose cp "api:$containerResultPath" "$backendTmp"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] No se pudo copiar el resultado del contenedor." -ForegroundColor Red
    exit 1
  }

  # 6. Resumen
  Write-Host ""
  Write-Host "==> Prueba SAND completada." -ForegroundColor Green
  Write-Host "    Resultado (host): $hostResultPath" -ForegroundColor Gray
  Write-Host ""
  Write-Host "Para comparar con el notebook Jupyter:" -ForegroundColor Cyan
  Write-Host "  1. Usa el mismo Excel y hoja 'Parameters', solver glpk." -ForegroundColor Gray
  Write-Host "  2. Compara métricas (objective_value, total_demand, total_dispatch, total_unmet, coverage_ratio)." -ForegroundColor Gray
  Write-Host "  3. Si exportas del notebook un JSON de referencia:" -ForegroundColor Gray
  Write-Host "     docker compose exec api python scripts/compare_results.py --ref referencia_notebook.json --actual tmp/sand_04_02_2026_result.json --tolerance 1e-4" -ForegroundColor Gray
  Write-Host ""
}
finally {
  Pop-Location
}
