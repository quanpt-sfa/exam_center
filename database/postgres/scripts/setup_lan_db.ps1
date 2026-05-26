param(
    [string]$EnvFile = "",
    [string]$PsqlPath = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

& (Join-Path $scriptDir "create_database.ps1") -EnvFile $EnvFile -PsqlPath $PsqlPath
& (Join-Path $scriptDir "run_all_migrations.ps1") -EnvFile $EnvFile -PsqlPath $PsqlPath
