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
$testsDir = Join-Path $rootDir "05_tests"

$testFiles = Get-ChildItem -Path $testsDir -Filter "*.sql" | Sort-Object Name

if (-not $testFiles) {
    throw "No smoke test files found in $testsDir"
}

$passed = 0
Write-DbTargetSummary -Target $target

foreach ($testFile in $testFiles) {
    Write-Host "[INFO] Running smoke test $($testFile.Name)..."

    $exitCode = Invoke-PsqlFile `
        -PsqlPath $psql `
        -HostName $target.Host `
        -Port $target.Port `
        -UserName $target.User `
        -DatabaseName $target.Name `
        -SqlFile $testFile.FullName

    if ($exitCode -ne 0) {
        throw "[FAIL] Smoke test failed: $($testFile.Name)"
    }

    $passed += 1
    Write-Host "[PASS] $($testFile.Name)"
}

Write-Host "[OK] Smoke tests completed: $passed passed, 0 failed."
