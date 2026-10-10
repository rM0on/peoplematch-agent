$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backend = Join-Path $repo "backend"
$databaseName = "peoplematch_task6_portfolio_20261009"
$databaseUrl = "postgresql+asyncpg://peoplematch:peoplematch_local@127.0.0.1:5432/$databaseName"
$created = $false
$exitCode = 1

try {
  Push-Location $repo
  docker compose exec -T postgres pg_isready -U peoplematch -d peoplematch | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "PostgreSQL unavailable" }
  $existing = (docker compose exec -T postgres psql -U peoplematch -d postgres -tAc "SELECT count(*) FROM pg_database WHERE datname = '$databaseName';" | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $existing -ne "0") { throw "Disposable portfolio database already exists or cannot be checked; refusing overwrite" }
  docker compose exec -T postgres createdb -U peoplematch $databaseName
  if ($LASTEXITCODE -ne 0) { throw "Disposable database creation failed" }
  $created = $true
  Pop-Location

  $env:DATABASE_URL = $databaseUrl
  $env:TEST_DATABASE_URL = $databaseUrl
  Push-Location $backend
  & ".\.venv\Scripts\python.exe" -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) { throw "Isolated migration failed" }
  & ".\.venv\Scripts\python.exe" "..\frontend\e2e\seed_phase10.py"
  if ($LASTEXITCODE -ne 0) { throw "Synthetic fixture seed failed" }
  Pop-Location

  Push-Location (Join-Path $repo "frontend")
  & npx.cmd playwright test --config=playwright.portfolio-review.config.ts
  $exitCode = $LASTEXITCODE
  Pop-Location
}
catch {
  Write-Error $_
  $exitCode = 1
}
finally {
  Set-Location $repo
  if ($created) {
    $stillExact = (docker compose exec -T postgres psql -U peoplematch -d postgres -tAc "SELECT count(*) FROM pg_database WHERE datname = '$databaseName';" | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $stillExact -eq "1") {
      docker compose exec -T postgres dropdb -U peoplematch $databaseName
      if ($LASTEXITCODE -ne 0) { Write-Warning "Disposable database cleanup failed"; $exitCode = 1 }
      else { Write-Output "Removed only disposable database: $databaseName" }
    } else { Write-Warning "Disposable database state unexpected; no deletion attempted"; $exitCode = 1 }
  }
}
exit $exitCode
