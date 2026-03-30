param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet("list-tables", "dump-table", "dump-all-tables", "query")]
  [string]$Command,
  [string]$TableName,
  [string]$Sql,
  [string]$OutputFile,
  [int]$Limit = 0,
  [switch]$WithCounts
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

$cliArgs = @("scripts/local_db_tools.py", $Command)

switch ($Command) {
  "list-tables" {
    if ($WithCounts) {
      $cliArgs += "--with-counts"
    }
  }
  "dump-table" {
    if (-not $TableName) {
      throw "Para dump-table debes pasar -TableName."
    }
    $cliArgs += @("--table-name", $TableName)
    if ($OutputFile) {
      $cliArgs += @("--output-file", $OutputFile)
    }
    if ($Limit -gt 0) {
      $cliArgs += @("--limit", "$Limit")
    }
  }
  "query" {
    if (-not $Sql) {
      throw "Para query debes pasar -Sql."
    }
    $cliArgs += @("--sql", $Sql)
    if ($OutputFile) {
      $cliArgs += @("--output-file", $OutputFile)
    }
    if ($Limit -gt 0) {
      $cliArgs += @("--limit", "$Limit")
    }
  }
  "dump-all-tables" {
    if ($OutputFile) {
      $cliArgs += @("--output-dir", $OutputFile)
    }
    if ($Limit -gt 0) {
      $cliArgs += @("--limit", "$Limit")
    }
  }
}

Invoke-Checked -Command $venvPython -Arguments $cliArgs -WorkingDirectory $backendDir

