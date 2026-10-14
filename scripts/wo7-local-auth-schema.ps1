param(
  [string]$SourceArchivePath
)

$ErrorActionPreference = "Stop"

throw "WO-7 is blocked: the previously verified EDB binaries archive lacks initdb.exe and pg_ctl.exe, and the PostgreSQL 17.11 Windows installer candidate has not passed Authenticode verification. Do not execute an unverified installer. No installer was executed, no PostgreSQL binaries were extracted, and no database checks were run."

function Invoke-CheckedCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Command,
    [Parameter(Mandatory = $true)][string[]]$Arguments
  )

  & $Command @Arguments *> $null
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $([System.IO.Path]::GetFileName($Command)) (exit $LASTEXITCODE)."
  }
}

function Invoke-ScopedCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Command,
    [Parameter(Mandatory = $true)][string[]]$Arguments,
    [Parameter(Mandatory = $true)][hashtable]$Variables
  )

  $previous = @{}
  foreach ($name in $Variables.Keys) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    [Environment]::SetEnvironmentVariable($name, [string]$Variables[$name], "Process")
  }
  try {
    Invoke-CheckedCommand $Command $Arguments
  } finally {
    foreach ($name in $Variables.Keys) {
      [Environment]::SetEnvironmentVariable($name, $previous[$name], "Process")
    }
  }
}

function Invoke-ScopedQuery {
  param(
    [Parameter(Mandatory = $true)][string]$Command,
    [Parameter(Mandatory = $true)][string[]]$Arguments,
    [Parameter(Mandatory = $true)][hashtable]$Variables
  )

  $previous = @{}
  foreach ($name in $Variables.Keys) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    [Environment]::SetEnvironmentVariable($name, [string]$Variables[$name], "Process")
  }
  try {
    $output = & $Command @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
      throw "Query command failed: $([System.IO.Path]::GetFileName($Command)) (exit $exitCode)."
    }
    return ($output -join [Environment]::NewLine)
  } finally {
    foreach ($name in $Variables.Keys) {
      [Environment]::SetEnvironmentVariable($name, $previous[$name], "Process")
    }
  }
}

function Get-AvailablePort {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  try {
    $listener.Start()
    return $listener.LocalEndpoint.Port
  } finally {
    $listener.Stop()
  }
}

function Assert-PublicBetterAuthSql {
  param([Parameter(Mandatory = $true)][string]$Sql)

  if ($Sql -match "(?i)\b(?:CREATE|DROP)\s+SCHEMA\b|\bALTER\s+TABLE\b[\s\S]{0,100}\bSET\s+SCHEMA\b") {
    throw "Generated SQL contains schema-level DDL outside the public-only contract."
  }

  $tableNames = [regex]::Matches($Sql, '(?i)\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:"?([\w]+)"?\.)?"?([\w]+)"?')
  $tables = @($tableNames | ForEach-Object { $_.Groups[2].Value.ToLowerInvariant() } | Sort-Object -Unique)
  $expectedTables = @("account", "session", "user", "verification")
  if (($tables -join ",") -ne ($expectedTables -join ",")) {
    throw "Generated SQL does not define exactly the expected Better Auth tables."
  }

  $qualifiedNames = [regex]::Matches($Sql, '(?i)\b(?:CREATE\s+(?:UNIQUE\s+)?INDEX|CREATE\s+TABLE|REFERENCES)\s+(?:"?([\w]+)"?\.)"?([\w]+)"?')
  foreach ($match in $qualifiedNames) {
    if ($match.Groups[1].Value.ToLowerInvariant() -ne "public") {
      throw "Generated SQL targets a schema other than public."
    }
  }

  foreach ($field in @('"role"', '"banned"', '"banReason"', '"banExpires"', '"impersonatedBy"')) {
    if ($Sql -notmatch [regex]::Escape($field)) {
      throw "Generated SQL is missing an expected Better Auth Admin field."
    }
  }

  if ([regex]::Matches($Sql, '(?i)\bREFERENCES\s+').Count -lt 2) {
    throw "Generated SQL is missing expected foreign-key relationships."
  }
  if ([regex]::Matches($Sql, '(?i)\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+').Count -lt 2) {
    throw "Generated SQL is missing expected indexes."
  }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontRoot = Join-Path $repoRoot "front"
$tempBase = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
$runRoot = [System.IO.Path]::GetFullPath((Join-Path $tempBase ("casa-lopez-wo7-auth-" + [guid]::NewGuid().ToString("N"))))
$tempPrefix = $tempBase + [System.IO.Path]::DirectorySeparatorChar
if (-not $runRoot.StartsWith($tempPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Resolved temporary path is outside TEMP."
}
if (Test-Path -LiteralPath $runRoot) {
  throw "The unique temporary run directory already exists."
}

$freeBytes = [System.IO.DriveInfo]::new((Get-Item $tempBase).PSDrive.Root).AvailableFreeSpace
if ($freeBytes -lt 2000000000) {
  throw "At least 2 GB of free temporary disk space is required."
}

$archiveUrl = "https://get.enterprisedb.com/postgresql/postgresql-17.11-5-windows-x64-binaries.zip"
$expectedSha256 = "80379b2c04d51c30225532e0ae04509899141e9957ed096fe749d7fd9df8f82f"

$serverStarted = $false
$safeToRemove = $true
New-Item -ItemType Directory -Path $runRoot | Out-Null
try {
  $archivePath = Join-Path $runRoot "postgresql.zip"
  if ($SourceArchivePath) {
    Copy-Item -LiteralPath $SourceArchivePath -Destination $archivePath
  } else {
    Invoke-WebRequest -Uri $archiveUrl -OutFile $archivePath
  }
  $actualSha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualSha256 -ne $expectedSha256) {
    throw "Downloaded PostgreSQL archive SHA-256 did not match the pinned checksum."
  }

  $extractRoot = Join-Path $runRoot "postgresql"
  Expand-Archive -LiteralPath $archivePath -DestinationPath $extractRoot
  $binRoot = Join-Path $extractRoot "pgsql\bin"
  $initdb = Join-Path $binRoot "initdb.exe"
  $pgCtl = Join-Path $binRoot "pg_ctl.exe"
  $psql = Join-Path $binRoot "psql.exe"
  foreach ($binary in @($initdb, $pgCtl, $psql)) {
    if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) {
      throw "The verified PostgreSQL archive does not contain the expected portable binaries."
    }
  }

  $dataDir = Join-Path $runRoot "data"
  $passwordPath = Join-Path $runRoot "bootstrap-password.txt"
  $logPath = Join-Path $runRoot "postgres.log"
  $passwordBytes = [byte[]]::new(48)
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($passwordBytes)
  } finally {
    $rng.Dispose()
  }
  $databasePassword = [Convert]::ToBase64String($passwordBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
  [System.IO.File]::WriteAllText($passwordPath, $databasePassword + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
  $secretBytes = [byte[]]::new(48)
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($secretBytes)
  } finally {
    $rng.Dispose()
  }
  $authSecret = [Convert]::ToBase64String($secretBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
  [Array]::Clear($passwordBytes, 0, $passwordBytes.Length)
  [Array]::Clear($secretBytes, 0, $secretBytes.Length)

  Invoke-CheckedCommand $initdb @("--username=postgres", "--auth-local=scram-sha-256", "--auth-host=scram-sha-256", "--pwfile=$passwordPath", "--pgdata=$dataDir", "--encoding=UTF8", "--locale=C", "--no-instructions")
  $port = Get-AvailablePort
  Invoke-CheckedCommand $pgCtl @("-D", $dataDir, "-l", $logPath, "-o", "--listen_addresses=127.0.0.1 --port=$port --password_encryption=scram-sha-256", "-w", "start")
  $serverStarted = $true

  $postgresEnvironment = @{
    PGHOST = "127.0.0.1"
    PGPORT = "$port"
    PGUSER = "postgres"
    PGDATABASE = "postgres"
    PGPASSWORD = $databasePassword
    PGOPTIONS = "-c search_path=public"
  }
  Invoke-ScopedCommand $psql @("-X", "-v", "ON_ERROR_STOP=1", "-c", "CREATE DATABASE wo7_auth_stage3") $postgresEnvironment
  $authDatabaseUrl = "postgresql://postgres:$([uri]::EscapeDataString($databasePassword))@127.0.0.1:$port/wo7_auth_stage3"
  $authEnvironment = @{
    AUTH_DATABASE_URL = $authDatabaseUrl
    BETTER_AUTH_URL = "http://127.0.0.1:3000"
    BETTER_AUTH_SECRET = $authSecret
  }
  $applicationDatabaseEnvironment = @{} + $postgresEnvironment
  $applicationDatabaseEnvironment.PGDATABASE = "wo7_auth_stage3"

  $generatedPath = Join-Path $runRoot "better-auth-public.sql"
  Push-Location $frontRoot
  try {
    Invoke-ScopedCommand "corepack" @("pnpm", "exec", "auth", "generate", "--config", "./lib/auth.cli.ts", "--output", $generatedPath, "--yes") $authEnvironment
  } finally {
    Pop-Location
  }

  $generatedSql = [System.IO.File]::ReadAllText($generatedPath)
  if ($generatedSql.Contains($databasePassword) -or $generatedSql.Contains($authSecret) -or $generatedSql.Contains($authDatabaseUrl)) {
    throw "Generated SQL unexpectedly contains a temporary credential."
  }
  Assert-PublicBetterAuthSql $generatedSql

  $versionedSqlPath = Join-Path $frontRoot "db\better-auth-public.sql"
  New-Item -ItemType Directory -Path (Split-Path -Parent $versionedSqlPath) -Force | Out-Null
  [System.IO.File]::WriteAllText($versionedSqlPath, $generatedSql, [System.Text.UTF8Encoding]::new($false))

  Invoke-ScopedCommand $psql @("-X", "-v", "ON_ERROR_STOP=1", "-q", "--file", $versionedSqlPath) $applicationDatabaseEnvironment
  $connectionAddress = Invoke-ScopedQuery $psql @("-X", "-v", "ON_ERROR_STOP=1", "-A", "-t", "-c", "SELECT inet_server_addr()::text") $applicationDatabaseEnvironment
  if ($connectionAddress.Trim() -ne "127.0.0.1") {
    throw "The disposable PostgreSQL connection did not resolve to 127.0.0.1."
  }

  $catalogJson = Invoke-ScopedQuery $psql @("-X", "-v", "ON_ERROR_STOP=1", "-A", "-t", "-c", "SELECT json_build_object('tables', (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'), 'indexes', (SELECT count(*) FROM pg_indexes WHERE schemaname='public'), 'foreignKeys', (SELECT count(*) FROM information_schema.table_constraints WHERE table_schema='public' AND constraint_type='FOREIGN KEY'), 'adminUserFields', (SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='user' AND column_name IN ('role','banned','banReason','banExpires')), 'adminSessionFields', (SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='session' AND column_name='impersonatedBy'))::text") $applicationDatabaseEnvironment
  $catalog = $catalogJson.Trim() | ConvertFrom-Json
  if ($catalog.tables -ne 4 -or $catalog.indexes -lt 2 -or $catalog.foreignKeys -lt 2 -or $catalog.adminUserFields -ne 4 -or $catalog.adminSessionFields -ne 1) {
    throw "The live public schema did not satisfy the expected Better Auth table, index, foreign-key, or Admin-field checks."
  }

  Push-Location $frontRoot
  try {
    Invoke-ScopedCommand "corepack" @("pnpm", "exec", "auth", "check", "schema", "--config", "./lib/auth.cli.ts") $authEnvironment
  } finally {
    Pop-Location
  }

  Write-Output "Better Auth 1.7.7 schema generated, applied, and checked against disposable PostgreSQL on 127.0.0.1."
  Write-Output "Verified: 4 public tables, indexes, foreign keys, Admin fields, and CLI schema check."
} finally {
  if ($serverStarted) {
    & $pgCtl -D (Join-Path $runRoot "data") -m fast -w stop *> $null
    if ($LASTEXITCODE -ne 0) {
      $safeToRemove = $false
      Write-Warning "PostgreSQL did not confirm shutdown; preserve the temporary run directory for recovery: $runRoot"
    }
  }
  if ($safeToRemove -and (Test-Path -LiteralPath $runRoot)) {
    $resolvedRunRoot = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $runRoot).Path)
    if (-not $resolvedRunRoot.StartsWith($tempPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Resolved cleanup path escaped TEMP; preserving files."
    }
    Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force
  }
}
