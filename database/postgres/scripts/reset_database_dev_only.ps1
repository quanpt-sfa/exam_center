param(
    [string]$EnvFile = "",
    [string]$PsqlPath = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "db_target.ps1")

function Get-PsqlPath {
    param([string]$RequestedPath = "")

    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        if (-not (Test-Path -LiteralPath $RequestedPath)) {
            throw "psql executable not found at requested path: $RequestedPath"
        }
        return $RequestedPath
    }

    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { Join-Path $_ "PostgreSQL" }
    foreach ($root in $roots) {
        if (Test-Path $root) {
            $found = Get-ChildItem -Path $root -Filter "psql.exe" -Recurse -ErrorAction SilentlyContinue |
                Select-Object -First 1 -ExpandProperty FullName
            if ($found) {
                return $found
            }
        }
    }

    throw "psql was not found. Install PostgreSQL client tools or add psql to PATH."
}

$target = Get-DbTarget -EnvFile $EnvFile
$psql = Get-PsqlPath -RequestedPath $PsqlPath
$env:PGPASSWORD = $target.Password

if (-not $Force) {
    throw "DEVELOPMENT ONLY: This script drops and recreates '$($target.Name)'. Re-run with -Force to continue."
}

Write-DbTargetSummary -Target $target
Write-Host "[WARN] DEVELOPMENT ONLY: Dropping database '$($target.Name)'..."

& $psql -h $target.Host -p $target.Port -U $target.User -d $target.MaintenanceDatabase -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$($target.Name)' AND pid <> pg_backend_pid();"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to terminate active sessions for '$($target.Name)'."
}

& $psql -h $target.Host -p $target.Port -U $target.User -d $target.MaintenanceDatabase -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS `"$($target.Name)`";"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to drop database '$($target.Name)'."
}

& $psql -h $target.Host -p $target.Port -U $target.User -d $target.MaintenanceDatabase -v ON_ERROR_STOP=1 -c "CREATE DATABASE `"$($target.Name)`";"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to recreate database '$($target.Name)'."
}

Write-Host "[OK] DEVELOPMENT ONLY reset complete for '$($target.Name)'."
