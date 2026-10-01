[CmdletBinding()]
param([int]$HostPort = 55432, [string]$ContainerName = "research_ai_ci_postgres")

$ErrorActionPreference = "Stop"
docker rm -f $ContainerName 2>$null | Out-Null
docker run -d --name $ContainerName -e POSTGRES_USER=research -e POSTGRES_PASSWORD=research_test_password -e POSTGRES_DB=research_test -p "${HostPort}:5432" --health-cmd "pg_isready -U research -d research_test" --health-interval 5s --health-timeout 5s --health-retries 20 pgvector/pgvector:pg16 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to start PostgreSQL CI container." }
for ($i = 0; $i -lt 40; $i++) {
  $status = docker inspect --format '{{.State.Health.Status}}' $ContainerName 2>$null
  if ($status -eq "healthy") {
    Add-Content -Path $env:GITHUB_ENV -Value "DATABASE_URL=postgresql+psycopg://research:research_test_password@127.0.0.1:$HostPort/research_test"
    Add-Content -Path $env:GITHUB_ENV -Value "TEST_DATABASE_URL=postgresql+psycopg://research:research_test_password@127.0.0.1:$HostPort/research_test"
    Write-Host "PostgreSQL is healthy."
    exit 0
  }
  Start-Sleep -Seconds 2
}
docker logs $ContainerName
throw "PostgreSQL did not become healthy."
