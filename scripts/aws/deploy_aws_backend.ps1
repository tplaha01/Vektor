param(
  [Parameter(Mandatory = $true)]
  [string]$VmHost,
  [string]$User = "ubuntu",
  [Parameter(Mandatory = $true)]
  [string]$KeyPath,
  [string]$RepoUrl = "https://github.com/tplaha01/Vektor.git",
  [string]$RepoDir = "/home/ubuntu/Vektor",
  [string]$Branch = "main",
  [string]$ApiHost = "",
  [switch]$UseSslipHost,
  [string]$LocalEnvPath = "backend/.env",
  [switch]$UploadEnv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$resolvedKeyPath = Resolve-Path -LiteralPath $KeyPath -ErrorAction Stop
if ($UseSslipHost) {
  if ($ApiHost) { throw "Use either -ApiHost or -UseSslipHost, not both." }
  if ($VmHost -notmatch '^\d{1,3}(\.\d{1,3}){3}$') { throw "-UseSslipHost requires an IPv4 -VmHost." }
  $ApiHost = "$VmHost.sslip.io"
}

$sshArgs = @(
  "-i", $resolvedKeyPath.Path,
  "-o", "StrictHostKeyChecking=accept-new",
  "-o", "ConnectTimeout=20"
)

& ssh @sshArgs "$User@$VmHost" "echo connected"
if ($LASTEXITCODE -ne 0) { throw "Unable to connect to $User@$VmHost." }

$bootstrap = @"
set -euo pipefail
REPO_DIR='$RepoDir'
REPO_URL='$RepoUrl'
BRANCH='$Branch'
API_HOST='$ApiHost'
if [ ! -d "`$REPO_DIR/.git" ]; then
  git clone "`$REPO_URL" "`$REPO_DIR"
fi
cd "`$REPO_DIR"
git fetch --all --prune
git checkout "`$BRANCH"
git pull --ff-only origin "`$BRANCH"
chmod +x scripts/aws/setup_aws_backend.sh
./scripts/aws/setup_aws_backend.sh "`$REPO_DIR" "`$(whoami)" "`$API_HOST"
"@

$bootstrap | & ssh @sshArgs "$User@$VmHost" "bash -s"
if ($LASTEXITCODE -ne 0) { throw "Remote bootstrap failed." }

if ($UploadEnv) {
  $resolvedEnvPath = Resolve-Path -LiteralPath $LocalEnvPath -ErrorAction Stop
  & scp @sshArgs $resolvedEnvPath.Path ("{0}@{1}:{2}/backend/.env" -f $User, $VmHost, $RepoDir)
  if ($LASTEXITCODE -ne 0) { throw "Failed to upload env file." }
}

& ssh @sshArgs "$User@$VmHost" "sudo systemctl restart vektor-backend && sleep 8 && sudo systemctl is-active vektor-backend && curl -fsS http://127.0.0.1:8000/health | head -c 1200"
if ($LASTEXITCODE -ne 0) { throw "Backend restart or health check failed." }

if ($ApiHost) {
  Write-Host "Public backend: https://$ApiHost"
} else {
  Write-Host "Public backend: http://$VmHost"
}
