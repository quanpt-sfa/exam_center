param(
    [string]$EnvFile = "",
    [string]$PsqlPath = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$legacyScript = Join-Path $scriptDir "run_phase1_migrations.ps1"

if (-not (Test-Path -LiteralPath $legacyScript)) {
    throw "Legacy migration runner not found: $legacyScript"
}

Write-Host "[INFO] Running ALL migrations in db/postgres/01_migrations (deterministic filename order)."
Write-Host "[INFO] Using preferred alias run_all_migrations.ps1."
Write-Host "[INFO] Delegating execution to legacy implementation run_phase1_migrations.ps1 for compatibility."

& $legacyScript `
    -EnvFile $EnvFile `
    -PsqlPath $PsqlPath

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "[OK] All migrations completed via run_all_migrations.ps1."
