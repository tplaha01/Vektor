param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$TrackRecordRoot = "",
  [string]$BackupRoot = "",
  [int]$TrackRecordRetentionDays = 30,
  [int]$BackupRetentionDays = 14
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $TrackRecordRoot) {
  $TrackRecordRoot = Join-Path $RepoRoot ".artifacts\track-record\nightly"
}
if (-not $BackupRoot) {
  $BackupRoot = Join-Path $RepoRoot ".backups\nightly"
}

function Remove-OldDirectories {
  param(
    [Parameter(Mandatory = $true)][string]$Root,
    [Parameter(Mandatory = $true)][int]$RetentionDays
  )

  if (-not (Test-Path $Root)) {
    return 0
  }

  $cutoff = (Get-Date).AddDays(-1 * $RetentionDays)
  $deleted = 0
  Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
      Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop
      $deleted += 1
    }
  return $deleted
}

New-Item -ItemType Directory -Force -Path $TrackRecordRoot | Out-Null
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$trackDir = Join-Path $TrackRecordRoot $stamp

& (Join-Path $PSScriptRoot "export-track-record.ps1") -BaseUrl $BaseUrl -OutDir $trackDir | Out-Host
& (Join-Path $PSScriptRoot "local-backup.ps1") -BackupRoot $BackupRoot | Out-Host

$deletedTrackDirs = Remove-OldDirectories -Root $TrackRecordRoot -RetentionDays $TrackRecordRetentionDays
$deletedBackupDirs = Remove-OldDirectories -Root $BackupRoot -RetentionDays $BackupRetentionDays

Write-Host "Nightly maintenance complete"
Write-Host "Track record export: $trackDir"
Write-Host "Removed old track-record directories: $deletedTrackDirs"
Write-Host "Removed old backup directories: $deletedBackupDirs"
