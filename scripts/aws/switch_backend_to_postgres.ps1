param(
  [Parameter(Mandatory = $true)]
  [string]$VmHost,
  [string]$User = "ubuntu",
  [Parameter(Mandatory = $true)]
  [string]$KeyPath,
  [string]$RepoDir = "/home/ubuntu/Vektor",
  [Parameter(Mandatory = $true)]
  [string]$DatabaseUrl,
  [string]$SqlitePath = "trading_bot.db",
  [switch]$MigrateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$resolvedKeyPath = Resolve-Path -LiteralPath $KeyPath -ErrorAction Stop
$sshArgs = @(
  "-i", $resolvedKeyPath.Path,
  "-o", "StrictHostKeyChecking=accept-new",
  "-o", "ConnectTimeout=20"
)

$envFile = New-TemporaryFile
try {
  @(
    "DB_BACKEND=postgres"
    "DATABASE_URL=$DatabaseUrl"
  ) | Set-Content -LiteralPath $envFile.FullName -Encoding UTF8

  & ssh @sshArgs "$User@$VmHost" "mkdir -p '$RepoDir/backend/scripts' '$RepoDir/.run'"
  if ($LASTEXITCODE -ne 0) { throw "Unable to prepare remote directories." }

  & scp @sshArgs `
    "backend/app/storage/db.py" `
    "backend/app/config.py" `
    "backend/requirements.txt" `
    "backend/scripts/migrate_sqlite_to_postgres.py" `
    ("{0}@{1}:{2}/backend/scripts/" -f $User, $VmHost, $RepoDir)
  if ($LASTEXITCODE -ne 0) { throw "Failed to upload backend Postgres files." }

  & ssh @sshArgs "$User@$VmHost" "mv '$RepoDir/backend/scripts/db.py' '$RepoDir/backend/app/storage/db.py' && mv '$RepoDir/backend/scripts/config.py' '$RepoDir/backend/app/config.py' && mv '$RepoDir/backend/scripts/requirements.txt' '$RepoDir/backend/requirements.txt'"
  if ($LASTEXITCODE -ne 0) { throw "Failed to place backend Postgres files." }

  & scp @sshArgs $envFile.FullName ("{0}@{1}:{2}/.run/postgres.env" -f $User, $VmHost, $RepoDir)
  if ($LASTEXITCODE -ne 0) { throw "Failed to upload temporary Postgres env file." }

  $remote = @'
set -euo pipefail
cd __REPO_DIR__
if [ -d "backend/.venv" ]; then
  backend/.venv/bin/pip install -r backend/requirements.txt
else
  python3 -m pip install -r backend/requirements.txt
fi
ts="$(date -u +%Y%m%dT%H%M%SZ)"
if [ -f "backend/trading_bot.db" ]; then
  cp "backend/trading_bot.db" ".run/trading_bot.${ts}.sqlite.backup"
fi
DATABASE_URL="$(sed -n 's/^DATABASE_URL=//p' .run/postgres.env)"
backend/.venv/bin/python backend/scripts/migrate_sqlite_to_postgres.py \
  --sqlite-path "backend/trading_bot.db" \
  --database-url "$DATABASE_URL"
python3 - <<'PY'
from pathlib import Path

repo = Path.cwd()
env_path = repo / "backend" / ".env"
updates = {}
for line in (repo / ".run" / "postgres.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        key, value = line.split("=", 1)
        updates[key.strip()] = value.strip()
lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
for key, value in updates.items():
    entry = f"{key}={value}"
    if any(line.startswith(f"{key}=") for line in lines):
        lines = [entry if line.startswith(f"{key}=") else line for line in lines]
    else:
        lines.append(entry)
env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
PY
'@
  $remote = $remote.Replace('__REPO_DIR__', $RepoDir)
  $remote | & ssh @sshArgs "$User@$VmHost" "bash -s"
  if ($LASTEXITCODE -ne 0) { throw "Remote Postgres migration failed." }

  if (-not $MigrateOnly) {
    & ssh @sshArgs "$User@$VmHost" "sudo systemctl restart vektor-backend && sleep 8 && sudo systemctl is-active vektor-backend && curl -fsS http://127.0.0.1:8000/health | head -c 800"
    if ($LASTEXITCODE -ne 0) { throw "Backend restart or health check failed." }
  }
}
finally {
  Remove-Item -LiteralPath $envFile.FullName -Force -ErrorAction SilentlyContinue
}
