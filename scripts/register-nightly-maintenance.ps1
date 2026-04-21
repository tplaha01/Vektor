param(
  [string]$TaskName = "VektorNightlyMaintenance",
  [string]$At = "23:55"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $PSScriptRoot "nightly-maintenance.ps1"
$LogPath = Join-Path $RepoRoot ".artifacts\logs"
New-Item -ItemType Directory -Force -Path $LogPath | Out-Null
$StdoutPath = Join-Path $LogPath "nightly-maintenance.log"

$escapedRepo = $RepoRoot.Replace("'", "''")
$escapedScript = $ScriptPath.Replace("'", "''")
$escapedStdout = $StdoutPath.Replace("'", "''")

$command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command `"Set-Location '$escapedRepo'; & '$escapedScript' *>> '$escapedStdout'`""

schtasks.exe /Create /F /SC DAILY /TN $TaskName /TR $command /ST $At | Out-Host
Write-Host "Registered nightly maintenance task '$TaskName' at $At"
