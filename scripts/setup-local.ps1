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

function Resolve-PythonCommand {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    return @("py", "-3")
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    return @("python")
  }
  throw "No se encontro Python en PATH. Instala Python 3.11+."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$venvDir = Join-Path $repoRoot ".venv"
$envLocal = Join-Path $backendDir ".env.local"
$envLocalExample = Join-Path $backendDir ".env.local.example"

$pythonCmd = Resolve-PythonCommand
$pyExe = $pythonCmd[0]
$pyArgsBase = @()
if ($pythonCmd.Count -gt 1) {
  $pyArgsBase = $pythonCmd[1..($pythonCmd.Count - 1)]
}

Write-Host "==> Preparando entorno virtual local..." -ForegroundColor Cyan
if (-not (Test-Path $venvDir)) {
  Invoke-Checked -Command $pyExe -Arguments ($pyArgsBase + @("-m", "venv", $venvDir))
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  throw "No se encontro python del venv en $venvPython"
}

Write-Host "==> Instalando dependencias backend..." -ForegroundColor Cyan
Invoke-Checked -Command $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked -Command $venvPython -Arguments @("-m", "pip", "install", "-r", "requirements.txt") -WorkingDirectory $backendDir

if (-not (Test-Path $envLocal)) {
  if (-not (Test-Path $envLocalExample)) {
    throw "No se encontro backend/.env.local.example"
  }
  Copy-Item $envLocalExample $envLocal
  Write-Host "==> Se creo backend/.env.local desde el ejemplo." -ForegroundColor Yellow
}

Write-Host "==> Setup local completado." -ForegroundColor Green
Write-Host "Siguientes pasos:" -ForegroundColor Green
Write-Host "  1) .\scripts\init-local-db.ps1"
Write-Host "  2) .\scripts\run-local-api.ps1"

