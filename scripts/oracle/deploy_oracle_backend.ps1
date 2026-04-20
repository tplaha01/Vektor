param(
  [Parameter(Mandatory = $true)]
  [string]$VmHost,
  [string]$User = "ubuntu",
  [Parameter(Mandatory = $true)]
  [string]$KeyPath,
  [string]$RepoDir = "~/Vektor",
  [string]$Branch = "main",
  [string]$BackupDir = "~/vektor-backups",
  [string]$LocalEnvPath = "backend/.env",
  [switch]$UploadEnv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command not found on PATH: $Name"
  }
}

function Invoke-RemoteScript {
  param([string]$ScriptText)
  $ScriptText | & ssh @script:sshArgs "$User@$VmHost" "bash -s"
  if ($LASTEXITCODE -ne 0) {
    throw "Remote command failed."
  }
}

Require-Command "ssh"
Require-Command "scp"

$resolvedKeyPath = Resolve-Path -LiteralPath $KeyPath -ErrorAction Stop
$script:sshArgs = @(
  "-i", $resolvedKeyPath.Path,
  "-o", "StrictHostKeyChecking=accept-new",
  "-o", "ConnectTimeout=20"
)

Write-Host "[oracle] Verifying SSH connectivity to $User@$VmHost ..."
& ssh @sshArgs "$User@$VmHost" "echo connected"
if ($LASTEXITCODE -ne 0) {
  throw "Unable to connect to $User@$VmHost over SSH."
}

$bootstrapScript = @"
set -euo pipefail
REPO_DIR='$RepoDir'
BRANCH='$Branch'
BACKUP_DIR='$BackupDir'
if [ ! -d "\$REPO_DIR/.git" ]; then
  git clone https://github.com/tplaha01/Vektor.git "\$REPO_DIR"
fi
cd "\$REPO_DIR"
git fetch --all --prune
git checkout "\$BRANCH"
git pull --ff-only origin "\$BRANCH"
chmod +x scripts/oracle/setup_oracle_backend.sh scripts/oracle/backup_backend.sh
./scripts/oracle/setup_oracle_backend.sh "\$REPO_DIR" "\$(whoami)" "\$BACKUP_DIR"
"@

Write-Host "[oracle] Bootstrapping backend on remote VM ..."
Invoke-RemoteScript -ScriptText $bootstrapScript

if ($UploadEnv) {
  $resolvedEnvPath = Resolve-Path -LiteralPath $LocalEnvPath -ErrorAction Stop
  Write-Host "[oracle] Uploading backend env file: $($resolvedEnvPath.Path)"
  & scp @sshArgs $resolvedEnvPath.Path ("{0}@{1}:{2}/backend/.env" -f $User, $VmHost, $RepoDir)
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload env file to remote VM."
  }
}

$restartScript = @'
set -euo pipefail
if ! sudo -n true 2>/dev/null; then
  echo "sudo passwordless is required for non-interactive deploy script." >&2
  exit 1
fi
sudo -n systemctl restart vektor-backend
sudo -n systemctl --no-pager --full status vektor-backend | sed -n "1,20p"
curl -fsS http://127.0.0.1:8000/health | head -c 800
echo
'@

Write-Host "[oracle] Restarting service and checking health ..."
Invoke-RemoteScript -ScriptText $restartScript

Write-Host ""
Write-Host ("[oracle] Deployment complete. Health endpoint: http://{0}:8000/health" -f $VmHost)
