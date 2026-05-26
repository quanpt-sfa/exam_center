Set-StrictMode -Version Latest

function Get-DbTargetRepoRoot {
    param([string]$StartPath = $PSScriptRoot)

    $current = Resolve-Path -LiteralPath $StartPath
    while ($null -ne $current) {
        $candidate = Join-Path $current.Path ".git"
        if (Test-Path -LiteralPath $candidate) {
            return $current.Path
        }

        $parent = Split-Path -Parent $current.Path
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $current.Path) {
            break
        }
        $current = Resolve-Path -LiteralPath $parent
    }

    throw "Could not resolve repository root from $StartPath."
}

function Resolve-DbTargetEnvFile {
    param(
        [string]$RepoRoot,
        [string]$EnvFile
    )

    $requested = $EnvFile
    if ([string]::IsNullOrWhiteSpace($requested)) {
        $requested = [Environment]::GetEnvironmentVariable("ENV_FILE", "Process")
    }
    if ([string]::IsNullOrWhiteSpace($requested)) {
        return (Join-Path $RepoRoot ".env.lan")
    }
    if ([System.IO.Path]::IsPathRooted($requested)) {
        return $requested
    }
    return (Join-Path $RepoRoot $requested)
}

function Read-DbTargetEnvFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "DB target env file not found: $Path"
    }

    $map = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }

        $idx = $trimmed.IndexOf("=")
        if ($idx -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $idx).Trim()
        $value = $trimmed.Substring($idx + 1).Trim().Trim([char[]]@([char]34, [char]39))
        if ($key) {
            $map[$key] = $value
        }
    }

    return $map
}

function Get-DbTargetRequiredValue {
    param(
        [hashtable]$Map,
        [string]$Name
    )

    if (-not $Map.ContainsKey($Name) -or [string]::IsNullOrWhiteSpace([string]$Map[$Name])) {
        throw "Missing required DB target variable $Name in .env.lan"
    }

    $value = [string]$Map[$Name]
    if ($value -match '^\s*(<[^>]+>|changeme|change-me|placeholder|todo|set-locally)\s*$') {
        throw "DB target variable $Name is still a placeholder"
    }

    return $value
}

function Get-DbNameFromDatabaseUrl {
    param([string]$DatabaseUrl)

    if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
        return ""
    }

    $uri = [System.Uri]$DatabaseUrl
    if ($uri.Scheme -notin @("postgres", "postgresql")) {
        throw "DATABASE_URL must use postgres:// or postgresql:// when present"
    }

    return [System.Uri]::UnescapeDataString($uri.AbsolutePath.TrimStart("/"))
}

function Get-DbTarget {
    param([string]$EnvFile = "")

    $repoRoot = Get-DbTargetRepoRoot
    $resolvedEnvFile = Resolve-DbTargetEnvFile -RepoRoot $repoRoot -EnvFile $EnvFile
    $map = Read-DbTargetEnvFile -Path $resolvedEnvFile

    $dbName = Get-DbTargetRequiredValue -Map $map -Name "DB_NAME"
    if ($dbName -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
        throw "DB_NAME must match ^[A-Za-z_][A-Za-z0-9_]*$"
    }
    if (@("postgres", "template0", "template1") -contains $dbName.ToLowerInvariant()) {
        throw "DB_NAME must not be a maintenance database ($dbName)"
    }

    foreach ($alias in @("POSTGRES_DB", "PGDATABASE")) {
        if ($map.ContainsKey($alias) -and -not [string]::IsNullOrWhiteSpace([string]$map[$alias]) -and [string]$map[$alias] -ne $dbName) {
            throw "$alias must match DB_NAME in $resolvedEnvFile"
        }
    }

    if ($map.ContainsKey("DATABASE_URL") -and -not [string]::IsNullOrWhiteSpace([string]$map["DATABASE_URL"])) {
        $urlDbName = Get-DbNameFromDatabaseUrl -DatabaseUrl ([string]$map["DATABASE_URL"])
        if ($urlDbName -ne $dbName) {
            throw "DATABASE_URL database name must match DB_NAME"
        }
    }

    $maintenanceDatabase = if ($map.ContainsKey("DB_MAINTENANCE_DATABASE") -and -not [string]::IsNullOrWhiteSpace([string]$map["DB_MAINTENANCE_DATABASE"])) {
        [string]$map["DB_MAINTENANCE_DATABASE"]
    } else {
        "postgres"
    }
    if (@("postgres", "template0", "template1") -notcontains $maintenanceDatabase.ToLowerInvariant()) {
        throw "DB_MAINTENANCE_DATABASE must be postgres, template0, or template1"
    }

    return [pscustomobject]@{
        Host = Get-DbTargetRequiredValue -Map $map -Name "DB_HOST"
        Port = Get-DbTargetRequiredValue -Map $map -Name "DB_PORT"
        User = Get-DbTargetRequiredValue -Map $map -Name "DB_USER"
        Password = Get-DbTargetRequiredValue -Map $map -Name "DB_PASSWORD"
        Name = $dbName
        SslMode = if ($map.ContainsKey("DB_SSLMODE") -and -not [string]::IsNullOrWhiteSpace([string]$map["DB_SSLMODE"])) { [string]$map["DB_SSLMODE"] } elseif ($map.ContainsKey("POSTGRES_SSLMODE")) { [string]$map["POSTGRES_SSLMODE"] } else { "prefer" }
        MaintenanceDatabase = $maintenanceDatabase
        EnvFile = $resolvedEnvFile
    }
}

function Write-DbTargetSummary {
    param([Parameter(Mandatory = $true)]$Target)

    Write-Host "[INFO] DB target source: $($Target.EnvFile)"
    Write-Host "[INFO] DB target: host=$($Target.Host) port=$($Target.Port) user=$($Target.User) db=$($Target.Name)"
    Write-Host "[INFO] Maintenance database: $($Target.MaintenanceDatabase)"
}
