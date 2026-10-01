[CmdletBinding()]
param(
    [int]$ApiPort = 18000,
    [int]$WebPort = 13000
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$compose = Join-Path $root "deploy\staging\docker-compose.yml"
$runtime = Join-Path $root "deploy\staging\runtime"
$envFile = Join-Path $runtime "staging.env"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required on the self-hosted runner."
}
$dockerVersion = docker version --format '{{.Server.Version}}'
if ($LASTEXITCODE -ne 0 -or -not $dockerVersion) {
    throw "Docker daemon is not available."
}

function Require-Env([string]$Name) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "$Name is required for staging deployment."
    }
    return $value
}

$emailFrom = Require-Env "EMAIL_FROM"
$crossrefMailto = Require-Env "CROSSREF_MAILTO"
$unpaywallEmail = Require-Env "UNPAYWALL_EMAIL"
foreach ($name in @("OPENROUTER_API_KEY","OPENALEX_API_KEY","NCBI_API_KEY","SAPLING_API_KEY","RESEND_API_KEY")) {
    Require-Env $name | Out-Null
}

New-Item -ItemType Directory -Force -Path $runtime | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtime "storage") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtime "backups") | Out-Null

$lines = @(
    "APP_ENV=staging",
    "DEBUG=false",
    "PROJECT_NAME=research-ai",
    "API_PREFIX=/api/v1",
    "LOG_LEVEL=INFO",
    "LOG_FORMAT=json",
    "DATABASE_URL=postgresql+psycopg://research_ai:staging-local-only@db:5432/research_ai",
    "JWT_SECRET_KEY=staging-local-only-replaced-by-runtime",
    "AUTH_REQUIRE_VERIFIED_EMAIL=false",
    "AUTH_MFA_REQUIRED=false",
    "CORS_ALLOWED_ORIGINS=http://127.0.0.1:$WebPort,http://localhost:$WebPort",
    "CORS_ALLOW_CREDENTIALS=true",
    "TRUSTED_HOSTS=*",
    "RATE_LIMIT_ENABLED=true",
    "FILE_STORAGE_BACKEND=local",
    "FILE_STORAGE_LOCAL_ROOT=/app/storage/files",
    "METRICS_ENABLED=true",
    "TRACING_ENABLED=false",
    "BACKUP_DIRECTORY=/app/backups",
    "GENERATION_PROVIDER=openrouter",
    "EMBEDDING_PROVIDER=openrouter",
    "TRANSLATION_PROVIDER=openrouter",
    "SOURCE_DISCOVERY_PROVIDER=openalex",
    "DETECTION_PROVIDER=sapling",
    "PROVIDER_FALLBACKS=generation=openrouter;embedding=openrouter;translation=openrouter;detection=sapling;source_discovery=openalex",
    "OPENROUTER_API_KEY=$($env:OPENROUTER_API_KEY)",
    "OPENROUTER_BASE_URL=https://openrouter.ai/api/v1",
    "OPENALEX_API_KEY=$($env:OPENALEX_API_KEY)",
    "NCBI_API_KEY=$($env:NCBI_API_KEY)",
    "CROSSREF_MAILTO=$crossrefMailto",
    "UNPAYWALL_EMAIL=$unpaywallEmail",
    "SAPLING_API_KEY=$($env:SAPLING_API_KEY)",
    "DETECTION_SAPLING_BASE_URL=https://api.sapling.ai/api/v1",
    "DETECTION_SAPLING_MODEL=20260820",
    "EMAIL_PROVIDER=resend",
    "RESEND_API_KEY=$($env:RESEND_API_KEY)",
    "EMAIL_FROM=$emailFrom",
    "WEB_APP_BASE_URL=http://127.0.0.1:$WebPort",
    "BILLING_PROVIDER=none"
)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($envFile, ($lines -join [Environment]::NewLine), $utf8NoBom)

$env:STAGING_API_PORT = [string]$ApiPort
$env:STAGING_WEB_PORT = [string]$WebPort

docker compose -p research-ai-staging -f $compose up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed."
}

function Wait-Http([string]$Url, [int]$ExpectedStatus = 200, [int]$Attempts = 90) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -eq $ExpectedStatus) {
                return
            }
        } catch {
        }
        Start-Sleep -Seconds 2
    }
    throw "Timed out waiting for $Url"
}

Wait-Http "http://127.0.0.1:$ApiPort/api/v1/health/live"
Wait-Http "http://127.0.0.1:$ApiPort/api/v1/health/ready"
Wait-Http "http://127.0.0.1:$WebPort/login"

Write-Host "Staging deployment: PASS"
Write-Host "API=http://127.0.0.1:$ApiPort"
Write-Host "WEB=http://127.0.0.1:$WebPort"
