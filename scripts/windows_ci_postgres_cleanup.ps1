[CmdletBinding()]
param([string]$ContainerName = "research_ai_ci_postgres")
docker rm -f $ContainerName 2>$null | Out-Null
Write-Host "PostgreSQL CI container cleaned up."
