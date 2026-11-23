<#
.SYNOPSIS
    Run the mousehole backend test suites.

.DESCRIPTION
    Default: run the fast SQLite (in-memory) suite. PostgreSQL integration
    tests are marked `postgres` and are deselected; they are also auto-skipped
    when TEST_DATABASE_URL is not set.

    -Postgres: run ONLY the PostgreSQL integration suite (marker `postgres`)
    against a disposable test database. TEST_DATABASE_URL must be set to a
    dedicated test database; the suite runs `alembic upgrade head` itself and
    refuses to touch the application database configured in .env.

.EXAMPLE
    .\scripts\test.ps1

.EXAMPLE
    # One-time: create a dedicated test database in the running dev container
    docker exec mousehole-postgres createdb -U mousehole mousehole_test
    $env:TEST_DATABASE_URL = "postgresql+pg8000://mousehole:mousehole@localhost:5433/mousehole_test"
    .\scripts\test.ps1 -Postgres
#>
param(
    [switch]$Postgres
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendDir = Join-Path $repoRoot "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

Push-Location $backendDir
$exitCode = 0
try {
    Write-Host "mousehole backend tests" -ForegroundColor Cyan
    Write-Host "  python: $python"

    if ($Postgres) {
        if (-not $env:TEST_DATABASE_URL) {
            Write-Host ""
            Write-Host "ERROR: -Postgres requires the TEST_DATABASE_URL environment variable." -ForegroundColor Red
            Write-Host "It must point to a DISPOSABLE test database (never the dev database). Example:"
            Write-Host "  docker exec mousehole-postgres createdb -U mousehole mousehole_test"
            Write-Host '  $env:TEST_DATABASE_URL = "postgresql+pg8000://mousehole:mousehole@localhost:5433/mousehole_test"'
            Write-Host "  .\scripts\test.ps1 -Postgres"
            $exitCode = 2
        } else {
            Write-Host "  suite:  PostgreSQL integration (pytest -m postgres)"
            Write-Host "  target: $env:TEST_DATABASE_URL"
            Write-Host ""

            & $python -m pytest -q -m postgres
            $exitCode = $LASTEXITCODE
        }
    } else {
        Write-Host "  suite:  SQLite fast suite (pytest -m `"not postgres`")"
        Write-Host ""

        & $python -m pytest -q -m "not postgres"
        $exitCode = $LASTEXITCODE
    }
} finally {
    Pop-Location
}

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "TESTS PASSED" -ForegroundColor Green
} else {
    Write-Host "TESTS FAILED (exit code $exitCode)" -ForegroundColor Red
}
exit $exitCode
