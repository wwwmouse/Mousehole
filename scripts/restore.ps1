param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDir,
    [string]$ComposeFile = "",
    [string]$StorageDir = "storage",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $ComposeFile) { $ComposeFile = Join-Path $repoRoot "docker-compose.yml" }

$backupPath = (Resolve-Path $BackupDir).Path
$dumpPath = Join-Path $backupPath "database.sql"
if (-not (Test-Path $dumpPath)) { throw "Missing database.sql in $backupPath" }

$pgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "mousehole" }
$pgDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "mousehole" }

if (-not $Force) {
    Write-Warning "Restore overwrites the current database and storage files."
    $answer = Read-Host "Type YES to continue"
    if ($answer -ne "YES") { Write-Host "Cancelled."; exit 0 }
}

cmd /c ('docker compose -f "' + $ComposeFile + '" stop backend frontend >nul 2>&1')
cmd /c ('docker compose -f "' + $ComposeFile + '" up -d postgres >nul 2>&1')
if ($LASTEXITCODE -ne 0) { throw "Failed to start postgres." }

$resetCommand = 'docker compose -f "' + $ComposeFile + '" exec -T postgres psql -U ' + $pgUser + ' -d ' + $pgDb + ' -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >nul 2>&1'
cmd /c $resetCommand
if ($LASTEXITCODE -ne 0) { throw "Failed to reset schema." }

$restoreCommand = 'type "' + $dumpPath + '" | docker compose -f "' + $ComposeFile + '" exec -T postgres psql -U ' + $pgUser + ' -d ' + $pgDb + ' -v ON_ERROR_STOP=1'
cmd /c $restoreCommand
if ($LASTEXITCODE -ne 0) { throw "Database restore failed." }

$storageArchive = Join-Path $backupPath "storage.tar.gz"
if (Test-Path $storageArchive) {
    tar -xzf $storageArchive -C $repoRoot
    if ($LASTEXITCODE -ne 0) { throw "Storage restore failed." }
}

cmd /c ('docker compose -f "' + $ComposeFile + '" up -d >nul 2>&1')
$countsCommand = 'docker compose -f "' + $ComposeFile + '" exec -T postgres psql -U ' + $pgUser + ' -d ' + $pgDb + ' -t -A -c "SELECT ''tasks='' || count(*) FROM tasks;"'
cmd /c $countsCommand

Write-Host "Restore complete. Re-enter provider API keys in Settings."
