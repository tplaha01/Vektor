param(
  [string]$BackupRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $BackupRoot) {
  $BackupRoot = Join-Path $RepoRoot ".backups"
}
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OutDir = Join-Path $BackupRoot $Stamp
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$targets = @(
  "backend\trading_bot.db",
  "backend\trading_bot.log",
  "Dev_Logs.md"
)

foreach ($target in $targets) {
  $src = Join-Path $RepoRoot $target
  if (Test-Path $src) {
    Copy-Item -LiteralPath $src -Destination $OutDir -Force
  }
}

$kgDir = Join-Path $RepoRoot "knowledge_graph"
if (Test-Path $kgDir) {
  Copy-Item -LiteralPath $kgDir -Destination (Join-Path $OutDir "knowledge_graph") -Recurse -Force
}

& (Join-Path $PSScriptRoot "export-track-record.ps1") -OutDir (Join-Path $OutDir "track-record") | Out-Host

Write-Host "Local backup created at $OutDir"
