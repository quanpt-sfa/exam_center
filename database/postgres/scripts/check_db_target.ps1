param([string]$EnvFile = "")

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "db_target.ps1")

$target = Get-DbTarget -EnvFile $EnvFile
Write-Host "[OK] DB target contract is valid."
Write-DbTargetSummary -Target $target
