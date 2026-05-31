param(
    [string]$StartSession = "",
    [int]$MaxRetries = 3,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root ".orchestrator\run.ps1"

if ($StartSession) {
    & $runner -RepoRoot $root -StartSession $StartSession -MaxRetries $MaxRetries -Once:$Once
} else {
    & $runner -RepoRoot $root -MaxRetries $MaxRetries -Once:$Once
}
