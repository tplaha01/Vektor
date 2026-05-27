param(
    [string]$WorkDir = ".",
    [switch]$Strict,
    [switch]$CountRemaining,
    [string]$CanonicalBranch = "codex/main",
    [string]$CanonicalRemote = "origin/codex/main"
)

$ErrorActionPreference = "Stop"

$resolved = Resolve-Path -LiteralPath $WorkDir
Set-Location -LiteralPath $resolved

Write-Output "=== SESSION BOOTSTRAP ==="
Write-Output "[1/8] pwd"
Get-Location

Write-Output "[2/8] ls -la"
Get-ChildItem -Force

Write-Output "[3/8] app_spec.txt"
if (Test-Path -LiteralPath "app_spec.txt") {
    Get-Content -Path "app_spec.txt"
} else {
    Write-Warning "app_spec.txt missing"
    if ($Strict) { exit 2 }
}

Write-Output "[4/8] feature_list.json (head)"
if (Test-Path -LiteralPath "feature_list.json") {
    Get-Content -Path "feature_list.json" -TotalCount 50
} else {
    Write-Warning "feature_list.json missing"
    if ($Strict) { exit 3 }
}

Write-Output "[5/8] codex-progress.txt"
if (Test-Path -LiteralPath "codex-progress.txt") {
    Get-Content -Path "codex-progress.txt"
} else {
    Write-Warning "codex-progress.txt missing"
    if ($Strict) { exit 4 }
}

Write-Output "[6/8] git log --oneline -20"
git log --oneline -20

Write-Output "[7/8] branch and handoff status"
$currentBranch = (& git branch --show-current).Trim()
$currentHead = (& git rev-parse --short HEAD).Trim()
$statusLines = @(& git status --short)
$worktreeDirty = $statusLines.Count -gt 0

Write-Output "current_branch=$currentBranch"
Write-Output "current_head=$currentHead"
Write-Output "canonical_local_branch=$CanonicalBranch"
Write-Output "canonical_remote_branch=$CanonicalRemote"
Write-Output "worktree_dirty=$worktreeDirty"

if ($worktreeDirty) {
    Write-Warning "Dirty worktree detected. Previous session handoff is incomplete until the tree is clean again."
    $statusLines | Select-Object -First 20 | ForEach-Object { Write-Output $_ }
}

$remoteMainExists = $false
& git show-ref --verify --quiet "refs/remotes/$CanonicalRemote"
if ($LASTEXITCODE -eq 0) {
    $remoteMainExists = $true
    $remoteHead = (& git rev-parse --short $CanonicalRemote).Trim()
    $ahead = [int]((& git rev-list --count "$CanonicalRemote..HEAD").Trim())
    $behind = [int]((& git rev-list --count "HEAD..$CanonicalRemote").Trim())
    Write-Output "remote_head=$remoteHead"
    Write-Output "ahead_of_$($CanonicalRemote.Replace('/','_'))=$ahead"
    Write-Output "behind_$($CanonicalRemote.Replace('/','_'))=$behind"

    if ($behind -gt 0) {
        Write-Warning "$CanonicalBranch is behind $CanonicalRemote. Sync before starting the next coding session."
        if ($Strict) { exit 8 }
    }
} else {
    Write-Warning "$CanonicalRemote is not available in local refs yet."
}

if ($currentBranch -ne $CanonicalBranch) {
    Write-Warning "Long-running sessions must end on $CanonicalBranch. Current branch is $currentBranch."
    if ($Strict) { exit 6 }
}

if ($worktreeDirty -and $Strict) {
    exit 7
}

Write-Output "handoff_script=scripts/session-handoff.ps1"

Write-Output "[8/8] remaining tests"
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
