param(
  [switch]$SkipBuild,
  [switch]$SkipSeed
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Fallo el comando: $Command $($Arguments -join ' ')"
  }
}

Write-Host "==> Preparando entorno Docker (up)..." -ForegroundColor Cyan

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendEnv = Join-Path $repoRoot "backend\.env"

if (-not (Test-Path $backendEnv)) {
  throw "No se encontro backend/.env. Crea este archivo antes de levantar el stack."
}

Push-Location $repoRoot
try {
  if ($SkipBuild) {
    Invoke-Checked -Command "docker" -Arguments @("compose", "up", "-d")
  } else {
    Invoke-Checked -Command "docker" -Arguments @("compose", "build", "--no-cache")
    Invoke-Checked -Command "docker" -Arguments @("compose", "up", "-d")
  }

  Invoke-Checked -Command "docker" -Arguments @("compose", "exec", "api", "alembic", "upgrade", "head")

  if (-not $SkipSeed) {
    Invoke-Checked -Command "docker" -Arguments @("compose", "exec", "api", "python", "scripts/seed.py")
  } else {
    Write-Host "Seed omitido por bandera -SkipSeed" -ForegroundColor Yellow
  }

  Invoke-Checked -Command "docker" -Arguments @("compose", "ps")
  $frontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "8080" }
  $apiPort = if ($env:API_PORT) { $env:API_PORT } else { "8010" }
  Write-Host "==> Stack listo. Frontend: http://localhost:$frontendPort | API docs: http://localhost:$apiPort/docs" -ForegroundColor Green
}
finally {
  Pop-Location
}

