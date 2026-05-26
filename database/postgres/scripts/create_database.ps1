param(
    [string]$EnvFile = "",
    [string]$PsqlPath = ""
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
$env:PGPASSWORD = $target.Password
$psql = Get-PsqlPath -RequestedPath $PsqlPath

Write-DbTargetSummary -Target $target
Write-Host "[INFO] Checking PostgreSQL connectivity at $($target.Host):$($target.Port) as $($target.User)..."
& $psql -h $target.Host -p $target.Port -U $target.User -d $target.MaintenanceDatabase -v ON_ERROR_STOP=1 -c "SELECT 1;" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to connect to PostgreSQL using provided connection settings."
}

Write-Host "[INFO] Checking whether database '$($target.Name)' exists..."
$exists = & $psql -h $target.Host -p $target.Port -U $target.User -d $target.MaintenanceDatabase -tAc "SELECT 1 FROM pg_database WHERE datname = '$($target.Name)';"
if ($LASTEXITCODE -ne 0) {
    throw "Failed while checking whether database '$($target.Name)' exists."
}
$existsValue = if ($null -eq $exists) { "" } else { ($exists | Out-String).Trim() }

if ($existsValue -eq "1") {
    Write-Host "[INFO] Database '$($target.Name)' already exists."
    return
}

Write-Host "[INFO] Creating database '$($target.Name)'..."
& $psql -h $target.Host -p $target.Port -U $target.User -d $target.MaintenanceDatabase -v ON_ERROR_STOP=1 -c "CREATE DATABASE `"$($target.Name)`";"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create database '$($target.Name)'."
}

Write-Host "[OK] Database '$($target.Name)' created."
