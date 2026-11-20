[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python Launcher (py) is required on the self-hosted runner." }
& py -3.11 --version
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 is required on the self-hosted runner." }

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 20+ is required on the self-hosted runner." }
$nodeMajor = [int]((node --version) -replace '^v','').Split('.')[0]
if ($nodeMajor -lt 20) { throw "Node.js 20+ is required; found $nodeMajor." }
npm --version | Out-Null

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker is required on the self-hosted runner." }
docker version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker daemon is unavailable." }

$venv = Join-Path $env:GITHUB_WORKSPACE ".ci-venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
  & py -3.11 -m venv $venv
  if ($LASTEXITCODE -ne 0) { throw "Failed to create CI virtualenv." }
}
$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to bootstrap pip." }
Add-Content -Path $env:GITHUB_ENV -Value "CI_PYTHON=$python"
Write-Host "CI Python: $python"
Write-Host "Node: $(node --version)"
Write-Host "Docker: $(docker version --format '{{.Server.Version}}')"
