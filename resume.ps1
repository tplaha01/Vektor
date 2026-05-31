param(
    [int]$MaxRetries = 3,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root ".orchestrator\resume.ps1") -RepoRoot $root -MaxRetries $MaxRetries -Once:$Once
