$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$frontendRoot = Split-Path -Parent $PSScriptRoot
$repositoryRoot = Split-Path -Parent $frontendRoot
$backendRoot = Join-Path $repositoryRoot "backend"
$databaseName = "peoplematch_task6_e2e_20260829"
$databaseUrl = "postgresql+asyncpg://peoplematch:peoplematch_local@127.0.0.1:5432/$databaseName"
$exitCode = 1

if (-not $databaseName.StartsWith("peoplematch_task6_")) {
  throw "Refusing to use a non-disposable database"
}

function Invoke-Checked {
  param([scriptblock]$Command, [string]$Description)
  & $Command
  if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE" }
}

try {
  Push-Location $repositoryRoot
  Invoke-Checked { docker compose up -d postgres } "PostgreSQL startup"
  $healthy = $false
  for ($attempt = 0; $attempt -lt 30; $attempt += 1) {
    docker compose exec -T postgres pg_isready -U peoplematch -d peoplematch *> $null
    if ($LASTEXITCODE -eq 0) { $healthy = $true; break }
    Start-Sleep -Seconds 1
  }
  if (-not $healthy) { throw "PostgreSQL did not become healthy" }
  Invoke-Checked { docker compose exec -T postgres psql -U peoplematch -d postgres -tAc "SHOW server_version;" } "PostgreSQL version query"
  Invoke-Checked { docker compose exec -T postgres dropdb --if-exists -U peoplematch $databaseName } "Disposable database reset"
  Invoke-Checked { docker compose exec -T postgres createdb -U peoplematch $databaseName } "Disposable database creation"
  Pop-Location

  $env:DATABASE_URL = $databaseUrl
  $env:TEST_DATABASE_URL = $databaseUrl
  $env:TASK6_BACKEND_URL = "http://127.0.0.1:18000"
  $env:TASK6_FRONTEND_URL = "http://127.0.0.1:13000"
  $env:NEXT_PUBLIC_API_BASE_URL = $env:TASK6_BACKEND_URL

  Push-Location $backendRoot
  Invoke-Checked { & ".\.venv\Scripts\python.exe" -m alembic upgrade head } "Alembic upgrade"
  Invoke-Checked { & ".\.venv\Scripts\python.exe" -m alembic heads } "Alembic heads"
  Invoke-Checked { & ".\.venv\Scripts\python.exe" -m alembic current } "Alembic current"
  Invoke-Checked { & ".\.venv\Scripts\python.exe" -m alembic check } "Alembic drift check"
  Invoke-Checked { & ".\.venv\Scripts\python.exe" "..\frontend\e2e\seed_phase10.py" } "Synthetic historical fixture"
  Pop-Location

  Push-Location $frontendRoot
  & npx.cmd playwright test
  $exitCode = $LASTEXITCODE
  Pop-Location
}
catch {
  Write-Error $_
  $exitCode = 1
}
finally {
  Set-Location $repositoryRoot
  docker compose exec -T postgres dropdb --if-exists -U peoplematch $databaseName
  if ($LASTEXITCODE -ne 0) { Write-Warning "Disposable database cleanup failed"; $exitCode = 1 }
  $remaining = (docker compose exec -T postgres psql -U peoplematch -d postgres -tAc "SELECT count(*) FROM pg_database WHERE datname = '$databaseName';" | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $remaining -ne "0") { Write-Warning "Disposable database cleanup could not be verified"; $exitCode = 1 }
  else { Write-Output "Disposable database cleanup verified: $databaseName is absent" }
}

exit $exitCode
