$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$frontendRoot = Split-Path -Parent $PSScriptRoot
$repositoryRoot = Split-Path -Parent $frontendRoot
$backendRoot = Join-Path $repositoryRoot "backend"
$databaseName = "peoplematch_phase15_e2e_provider"
$databaseUrl = "postgresql+asyncpg://peoplematch:peoplematch_local@127.0.0.1:5432/$databaseName"
$candidateCollection = "peoplematch_phase15_e2e_candidates"
$jobCollection = "peoplematch_phase15_e2e_jobs"
$nodeExecutable = if ($env:PHASE15_NODE_EXE) { $env:PHASE15_NODE_EXE } else { "node" }
$playwrightCli = Join-Path $frontendRoot "node_modules\@playwright\test\cli.js"
$exitCode = 1

if (-not $databaseName.StartsWith("peoplematch_phase15_e2e_")) { throw "Refusing to use a non-disposable database" }
function Invoke-Checked { param([scriptblock]$Command, [string]$Description) & $Command; if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE" } }

try {
  Push-Location $repositoryRoot
  Invoke-Checked { docker compose up -d postgres redis qdrant } "Disposable infrastructure startup"
  $healthy = $false
  for ($attempt = 0; $attempt -lt 45; $attempt += 1) { docker compose exec -T postgres pg_isready -U peoplematch -d peoplematch *> $null; if ($LASTEXITCODE -eq 0) { $healthy = $true; break }; Start-Sleep -Seconds 1 }
  if (-not $healthy) { throw "PostgreSQL did not become healthy" }
  Invoke-Checked { docker compose exec -T postgres dropdb --if-exists -U peoplematch $databaseName } "Disposable database reset"
  Invoke-Checked { docker compose exec -T postgres createdb -U peoplematch $databaseName } "Disposable database creation"
  Pop-Location

  $env:DATABASE_URL = $databaseUrl; $env:TEST_DATABASE_URL = $databaseUrl
  $env:PHASE15_BACKEND_URL = "http://127.0.0.1:18150"; $env:PHASE15_FRONTEND_URL = "http://127.0.0.1:13150"
  $env:NEXT_PUBLIC_API_BASE_URL = $env:PHASE15_BACKEND_URL
  $env:QDRANT_URL = "http://127.0.0.1:6333"; $env:RETRIEVAL_CANDIDATE_COLLECTION = $candidateCollection; $env:RETRIEVAL_JOB_COLLECTION = $jobCollection
  $env:EXTRACTION_PROVIDER = "openai_compatible"; $env:EXPLANATION_PROVIDER = "openai_compatible"
  $env:LLM_BASE_URL = "https://phase15-provider.invalid/v1"; $env:LLM_MODEL = "phase15-test-model"; $env:LLM_API_KEY = "phase15-private-test-key"
  $env:HF_HUB_OFFLINE = "1"; $env:TRANSFORMERS_OFFLINE = "1"
  Push-Location $backendRoot
  Invoke-Checked { & ".\.venv\Scripts\python.exe" -m alembic upgrade head } "Alembic upgrade"
  Pop-Location
  Push-Location $repositoryRoot
  Invoke-Checked { & ".\backend\.venv\Scripts\python.exe" scripts\seed_database.py } "Synthetic database seed"
  Pop-Location
  Push-Location $frontendRoot
  Invoke-Checked { & $nodeExecutable $playwrightCli test --config playwright.phase15.config.ts } "OpenAI-compatible browser workflow"
  $env:EXTRACTION_PROVIDER = "mock"; $env:EXPLANATION_PROVIDER = "mock"
  Remove-Item Env:LLM_BASE_URL, Env:LLM_MODEL, Env:LLM_API_KEY -ErrorAction SilentlyContinue
  Invoke-Checked { & $nodeExecutable $playwrightCli test --config playwright.phase15.mock.config.ts } "Deterministic mock browser workflow"
  $exitCode = 0
  Pop-Location
} catch { Write-Error $_; $exitCode = 1 }
finally {
  Set-Location $repositoryRoot
  try { Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:6333/collections/$candidateCollection" | Out-Null } catch { Write-Warning "Candidate collection cleanup was not confirmed"; $exitCode = 1 }
  try { Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:6333/collections/$jobCollection" | Out-Null } catch { Write-Warning "Job collection cleanup was not confirmed"; $exitCode = 1 }
  docker compose exec -T postgres dropdb --if-exists -U peoplematch $databaseName
  if ($LASTEXITCODE -ne 0) { Write-Warning "Disposable database cleanup failed"; $exitCode = 1 }
}
exit $exitCode
