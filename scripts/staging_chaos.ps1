[CmdletBinding()]
param(
    [int]$ApiPort = 18000
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$compose = Join-Path $root "deploy\staging\docker-compose.yml"

function Wait-Ready([int]$Attempts = 60) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$ApiPort/api/v1/health/ready" -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                return
            }
        } catch {
        }
        Start-Sleep -Seconds 2
    }
    throw "Staging API readiness did not recover."
}

function Expect-NotReady {
    for ($i = 0; $i -lt 20; $i++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$ApiPort/api/v1/health/ready" -TimeoutSec 3
            if ($response.StatusCode -ne 200) {
                return
            }
        } catch {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "Fault injection did not make readiness fail."
}

Write-Host "F18 live chaos: API interruption"
docker compose -p research-ai-staging -f $compose stop api
if ($LASTEXITCODE -ne 0) { throw "Failed to stop API." }
Expect-NotReady
docker compose -p research-ai-staging -f $compose start api
if ($LASTEXITCODE -ne 0) { throw "Failed to start API." }
Wait-Ready

Write-Host "F18 live chaos: PostgreSQL interruption"
docker compose -p research-ai-staging -f $compose stop db
if ($LASTEXITCODE -ne 0) { throw "Failed to stop PostgreSQL." }
Expect-NotReady
docker compose -p research-ai-staging -f $compose start db
if ($LASTEXITCODE -ne 0) { throw "Failed to start PostgreSQL." }
Wait-Ready

Write-Host "F18 live chaos/recovery: PASS"
