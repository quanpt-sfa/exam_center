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

function Invoke-PsqlFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PsqlPath,

        [Parameter(Mandatory = $true)]
        [string]$HostName,

        [Parameter(Mandatory = $true)]
        [string]$Port,

        [Parameter(Mandatory = $true)]
        [string]$UserName,

        [Parameter(Mandatory = $true)]
        [string]$DatabaseName,

        [Parameter(Mandatory = $true)]
        [string]$SqlFile
    )

    $stdoutFile = New-TemporaryFile
    $stderrFile = New-TemporaryFile

    try {
        $arguments = @(
            "-h `"$HostName`"",
            "-p `"$Port`"",
            "-U `"$UserName`"",
            "-d `"$DatabaseName`"",
            "-v ON_ERROR_STOP=1",
            "-f `"$SqlFile`""
        ) -join " "

        $proc = Start-Process `
            -FilePath $PsqlPath `
            -ArgumentList $arguments `
            -Wait `
            -PassThru `
            -NoNewWindow `
            -RedirectStandardOutput $stdoutFile.FullName `
            -RedirectStandardError $stderrFile.FullName

        if (Test-Path $stdoutFile.FullName) {
            $stdout = Get-Content $stdoutFile.FullName -Raw
            if ($stdout) {
                Write-Host $stdout
            }
        }

        if (Test-Path $stderrFile.FullName) {
            $stderr = Get-Content $stderrFile.FullName -Raw
            if ($stderr) {
                # psql writes NOTICE/WARNING to stderr.
                # Print it, but do not fail unless ExitCode != 0.
                Write-Host $stderr
            }
        }

        return $proc.ExitCode
    }
    finally {
        Remove-Item $stdoutFile.FullName -Force -ErrorAction SilentlyContinue
        Remove-Item $stderrFile.FullName -Force -ErrorAction SilentlyContinue
    }
}

$rootDir = Resolve-Path (Join-Path $scriptDir "..")
$migrationsDir = Join-Path $rootDir "01_migrations"

Write-DbTargetSummary -Target $target
$exists = & $psql -h $target.Host -p $target.Port -U $target.User -d $target.MaintenanceDatabase -tAc "SELECT 1 FROM pg_database WHERE datname = '$($target.Name)';"
if ($LASTEXITCODE -ne 0) {
    throw "Failed while checking whether database '$($target.Name)' exists."
}
if ((($exists | Out-String).Trim()) -ne "1") {
    throw "Target database '$($target.Name)' does not exist. Run the DB create command first, or run the LAN setup command."
}

$migrationFiles = Get-ChildItem -Path $migrationsDir -Filter "*.sql" | Sort-Object Name

if (-not $migrationFiles) {
    throw "No migration files found in $migrationsDir"
}

Write-Host "[INFO] Running Phase 1 migrations against '$($target.Name)'..."
foreach ($migration in $migrationFiles) {
    Write-Host "[INFO] Applying $($migration.Name)"
    $exitCode = Invoke-PsqlFile `
        -PsqlPath $psql `
        -HostName $target.Host `
        -Port $target.Port `
        -UserName $target.User `
        -DatabaseName $target.Name `
        -SqlFile $migration.FullName

    if ($exitCode -ne 0) {
        throw "Migration failed: $($migration.Name)"
    }
}

Write-Host "[OK] Phase 1 migrations completed."
