[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$compose = Join-Path $root "deploy\staging\docker-compose.yml"
$backupRoot = Join-Path $env:TEMP "research-ai-staging-backups"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$hostDump = Join-Path $backupRoot "staging-$timestamp.dump"

docker compose -p research-ai-staging -f $compose exec -T db pg_dump -U research_ai -d research_ai -Fc -f /tmp/staging.dump
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed." }

docker cp "research-ai-staging-db-1:/tmp/staging.dump" $hostDump
if ($LASTEXITCODE -ne 0) { throw "docker cp backup failed." }

docker compose -p research-ai-staging -f $compose exec -T db bash -lc "dropdb -U postgres --if-exists research_ai_restore_check && createdb -U postgres research_ai_restore_check && pg_restore -U postgres --no-owner --no-acl -d research_ai_restore_check /tmp/staging.dump && psql -U postgres -d research_ai_restore_check -Atc 'select count(*) from alembic_version;'"
if ($LASTEXITCODE -ne 0) { throw "Restore verification failed." }

docker compose -p research-ai-staging -f $compose exec -T db rm -f /tmp/staging.dump | Out-Null
docker compose -p research-ai-staging -f $compose exec -T db psql -U postgres -d postgres -c "drop database if exists research_ai_restore_check;" | Out-Null

Write-Host "Backup file: $hostDump"
Write-Host "Backup/restore live evidence: PASS"
