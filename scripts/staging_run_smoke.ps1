[CmdletBinding()]
param(
    [int]$ApiPort = 18000,
    [int]$WebPort = 13000
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$credentialsPath = Join-Path $root "deploy\staging\runtime\smoke-credentials.json"

if (-not (Test-Path $credentialsPath)) {
    throw "Smoke credentials file does not exist: $credentialsPath"
}

$credentials = Get-Content -Raw $credentialsPath | ConvertFrom-Json
$env:SMOKE_BASE_URL = "http://127.0.0.1:$ApiPort"
$env:SMOKE_WEB_BASE_URL = "http://127.0.0.1:$WebPort"
$env:SMOKE_AUTH_EMAIL = [string]$credentials.email
$env:SMOKE_AUTH_PASSWORD = [string]$credentials.password
$env:SMOKE_EXPECT_PROVIDER = "generation=openrouter;embedding=openrouter;translation=openrouter;detection=sapling;source_discovery=openalex"
$env:SMOKE_VERIFY_SAPLING = "true"
$env:SMOKE_VERIFY_OPENROUTER = "true"
$env:SMOKE_VERIFY_OPENALEX = "true"
$env:SMOKE_VERIFY_CROSSREF = "true"
$env:SMOKE_VERIFY_NCBI = "true"
$env:SMOKE_VERIFY_UNPAYWALL = "true"
$env:SAPLING_API_KEY = [Environment]::GetEnvironmentVariable("SAPLING_API_KEY")
$env:DETECTION_SAPLING_BASE_URL = "https://api.sapling.ai/api/v1"
$env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY")
$env:OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
$env:OPENALEX_API_KEY = [Environment]::GetEnvironmentVariable("OPENALEX_API_KEY")
$env:CROSSREF_MAILTO = [Environment]::GetEnvironmentVariable("CROSSREF_MAILTO")
$env:NCBI_API_KEY = [Environment]::GetEnvironmentVariable("NCBI_API_KEY")
$env:UNPAYWALL_EMAIL = [Environment]::GetEnvironmentVariable("UNPAYWALL_EMAIL")

Push-Location $root
try {
    python scripts\production_smoke.py
    if ($LASTEXITCODE -ne 0) {
        throw "Production smoke failed."
    }
} finally {
    Pop-Location
}
