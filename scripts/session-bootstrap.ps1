param(
    [string]$WorkDir = ".",
    [switch]$Strict,
    [switch]$CountRemaining
)

$ErrorActionPreference = "Stop"

$resolved = Resolve-Path -LiteralPath $WorkDir
Set-Location -LiteralPath $resolved

Write-Output "=== SESSION BOOTSTRAP ==="
Write-Output "[1/7] pwd"
Get-Location

Write-Output "[2/7] ls -la"
Get-ChildItem -Force

Write-Output "[3/7] app_spec.txt"
if (Test-Path -LiteralPath "app_spec.txt") {
    Get-Content -Path "app_spec.txt"
} else {
    Write-Warning "app_spec.txt missing"
    if ($Strict) { exit 2 }
}

Write-Output "[4/7] feature_list.json (head)"
if (Test-Path -LiteralPath "feature_list.json") {
    Get-Content -Path "feature_list.json" -TotalCount 50
} else {
    Write-Warning "feature_list.json missing"
    if ($Strict) { exit 3 }
}

Write-Output "[5/7] codex-progress.txt"
if (Test-Path -LiteralPath "codex-progress.txt") {
    Get-Content -Path "codex-progress.txt"
} else {
    Write-Warning "codex-progress.txt missing"
    if ($Strict) { exit 4 }
}

Write-Output "[6/7] git log --oneline -20"
git log --oneline -20

Write-Output "[7/7] remaining tests"
if ($CountRemaining -and (Test-Path -LiteralPath "feature_list.json")) {
    try {
        $raw = Get-Content -Raw -Path "feature_list.json"
        $json = $raw | ConvertFrom-Json
        $remaining = @($json | Where-Object { $_.passes -eq $false }).Count
        Write-Output "remaining_false=$remaining"
    } catch {
        Write-Warning "could not parse feature_list.json for remaining tests"
    }
} elseif (Test-Path -LiteralPath "feature_list.json") {
    $remaining = (Select-String -Path "feature_list.json" -Pattern '"passes"\s*:\s*false' -AllMatches).Matches.Count
    Write-Output "remaining_false_approx=$remaining"
} else {
    Write-Warning "feature_list.json missing"
    if ($Strict) { exit 5 }
}

Write-Output "=== BOOTSTRAP COMPLETE ==="
if (-not (Test-Path -LiteralPath "app_spec.txt") -or -not (Test-Path -LiteralPath "feature_list.json") -or -not (Test-Path -LiteralPath "codex-progress.txt")) {
    Write-Output "MISSING_REQUIRED_FILES=true"
} else {
    Write-Output "MISSING_REQUIRED_FILES=false"
}
