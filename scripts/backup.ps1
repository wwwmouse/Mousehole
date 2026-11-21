param(
    [string]$OutputRoot = "",
    [string]$ComposeFile = "",
    [string]$StorageDir = "storage"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputRoot) { $OutputRoot = Join-Path $repoRoot "backups" }
if (-not $ComposeFile) { $ComposeFile = Join-Path $repoRoot "docker-compose.yml" }

$pgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "mousehole" }
$pgDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "mousehole" }

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $OutputRoot $timestamp
New-Item -ItemType Directory -Force -Path $target | Out-Null

Write-Host "mousehole backup -> $target"

$statusCommand = 'docker compose -f "' + $ComposeFile + '" ps --status running postgres >nul 2>&1'
cmd /c $statusCommand
if ($LASTEXITCODE -ne 0) { throw "docker compose is not available." }

$dumpPath = Join-Path $target "database.sql"
$dumpCommand = 'docker compose -f "' + $ComposeFile + '" exec -T postgres pg_dump -U ' + $pgUser + ' -d ' + $pgDb + ' --no-owner --no-privileges > "' + $dumpPath + '"'
cmd /c $dumpCommand
if (-not (Test-Path $dumpPath) -or (Get-Item $dumpPath).Length -eq 0) {
    throw "Database backup failed: database.sql is empty."
}
if (-not (Select-String -Path $dumpPath -Pattern "PostgreSQL database dump" -Quiet)) {
    throw "Database backup validation failed."
}

$storagePath = Join-Path $repoRoot $StorageDir
$storageArchive = Join-Path $target "storage.tar.gz"
if (Test-Path $storagePath) {
    tar -czf $storageArchive -C $repoRoot $StorageDir
    if ($LASTEXITCODE -ne 0) { throw "Storage archive failed." }
} else {
    Write-Warning "Storage directory not found: $storagePath"
}

$manifest = [ordered]@{
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    database = "database.sql"
    storage = if (Test-Path $storageArchive) { "storage.tar.gz" } else { $null }
    pg_user = $pgUser
    pg_database = $pgDb
    secrets_included = $false
}
$manifest | ConvertTo-Json -Depth 4 | Out-File -FilePath (Join-Path $target "manifest.json") -Encoding utf8

Write-Host "Backup complete: database.sql, manifest.json"
if (Test-Path $storageArchive) { Write-Host "Storage archive: storage.tar.gz" }
Write-Host "Secrets are NOT included. Re-enter provider API keys after restore."
