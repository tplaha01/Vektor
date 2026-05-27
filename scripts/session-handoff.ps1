param(
    [Parameter(Mandatory = $true)]
    [string]$CommitMessage,
    [string]$WorkDir = ".",
    [string]$CanonicalBranch = "codex/main",
    [string]$RemoteName = "origin",
    [string]$RemoteBranch = "codex/main",
    [switch]$AllowEmptyCommit,
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$resolved = Resolve-Path -LiteralPath $WorkDir
Set-Location -LiteralPath $resolved

$repoRoot = (& git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
    throw "session-handoff.ps1 must run inside a git repository."
}

$currentBranch = (& git branch --show-current).Trim()
if ($currentBranch -ne $CanonicalBranch) {
    throw "Handoff must run from $CanonicalBranch. Current branch is $currentBranch."
}

Write-Output "=== SESSION HANDOFF ==="
Write-Output "repo_root=$repoRoot"
Write-Output "current_branch=$currentBranch"

& git add -A

& git diff --cached --quiet
$hasStagedChanges = $LASTEXITCODE -ne 0

if (-not $hasStagedChanges -and -not $AllowEmptyCommit) {
    throw "No staged changes found. Either make repo changes before handoff or rerun with -AllowEmptyCommit."
}

if ($AllowEmptyCommit) {
    & git commit --allow-empty -m $CommitMessage
} else {
    & git commit -m $CommitMessage
}

if ($LASTEXITCODE -ne 0) {
    throw "git commit failed."
}

$localHead = (& git rev-parse HEAD).Trim()
$shortHead = (& git rev-parse --short HEAD).Trim()
Write-Output "local_head=$localHead"
Write-Output "local_head_short=$shortHead"

if (-not $SkipPush) {
    & git push $RemoteName "HEAD:$RemoteBranch"
    if ($LASTEXITCODE -ne 0) {
        throw "git push to $RemoteName/$RemoteBranch failed."
    }

    & git branch --set-upstream-to "$RemoteName/$RemoteBranch" $CanonicalBranch *> $null

    $remoteLines = @(& git ls-remote $RemoteName "refs/heads/$RemoteBranch")
    if ($remoteLines.Count -eq 0) {
        throw "Could not read remote head for $RemoteName/$RemoteBranch."
    }

    $remoteHead = ($remoteLines[0] -split "\s+")[0].Trim()
    Write-Output "remote_head=$remoteHead"
    if ($remoteHead -ne $localHead) {
        throw "Remote head mismatch. local=$localHead remote=$remoteHead"
    }
}

$remainingStatus = @(& git status --short)
if ($remainingStatus.Count -gt 0) {
    $remainingStatus | ForEach-Object { Write-Output $_ }
    throw "Handoff incomplete: worktree is still dirty after commit/push."
}

Write-Output "HANDOFF_READY=true"
Write-Output "NEXT_AGENT_REF=$CanonicalBranch@$shortHead"
Write-Output "REMOTE_REF=$RemoteName/$RemoteBranch"
