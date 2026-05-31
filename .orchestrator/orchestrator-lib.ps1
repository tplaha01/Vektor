$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-OrchestratorTimestamp {
    return [DateTimeOffset]::Now.ToString("o")
}

function Read-OrchestratorJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required JSON file not found: $Path"
    }

    $raw = Get-Content -Raw -LiteralPath $Path
    if ([string]::IsNullOrWhiteSpace($raw)) {
        throw "JSON file is empty: $Path"
    }

    return $raw | ConvertFrom-Json
}

function Write-OrchestratorJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [object]$Value,
        [int]$Depth = 12
    )

    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    $Value | ConvertTo-Json -Depth $Depth | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Initialize-OrchestratorState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StatePath
    )

    if (Test-Path -LiteralPath $StatePath) {
        return
    }

    $state = [ordered]@{
        current_session = ""
        last_completed = ""
        status = ""
        started_at = ""
        updated_at = ""
        retry_count = 0
    }

    Write-OrchestratorJson -Path $StatePath -Value $state
}

function Get-OrchestratorQueueIds {
    param(
        [Parameter(Mandatory = $true)]
        [string]$QueuePath
    )

    $queue = Read-OrchestratorJson -Path $QueuePath
    $sessions = @($queue.sessions)
    if ($sessions.Count -eq 0) {
        throw "Queue contains no sessions: $QueuePath"
    }

    return @($sessions | ForEach-Object { [string]$_.id })
}

function Get-NextSessionId {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$QueueIds,
        [string]$LastCompleted,
        [string]$CurrentSession,
        [string]$Status
    )

    if ($CurrentSession -and $Status -in @("running", "retrying", "failed_retryable", "stream_retry")) {
        return $CurrentSession
    }

    if (-not $LastCompleted) {
        return $QueueIds[0]
    }

    $index = [Array]::IndexOf($QueueIds, $LastCompleted)
    if ($index -lt 0) {
        throw "last_completed '$LastCompleted' is not present in queue.json"
    }

    if ($index + 1 -ge $QueueIds.Count) {
        return $null
    }

    return $QueueIds[$index + 1]
}

function Resolve-CodexExecutable {
    $cmd = Get-Command "codex.cmd" -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $cmd = Get-Command "codex" -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    throw "Codex CLI was not found on PATH."
}

function Get-RegexField {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [Parameter(Mandatory = $true)]
        [string]$Pattern
    )

    $match = [regex]::Match($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Multiline)
    if ($match.Success) {
        return $match.Groups["value"].Value.Trim()
    }

    return ""
}

function Parse-HandoffPackage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [Parameter(Mandatory = $true)]
        [string]$FallbackSession
    )

    $normalized = $Text -replace "`r`n", "`n"
    $handoffStart = $normalized.LastIndexOf("HANDOFF PACKAGE", [System.StringComparison]::OrdinalIgnoreCase)
    $handoffText = if ($handoffStart -ge 0) { $normalized.Substring($handoffStart) } else { $normalized }

    $session = Get-RegexField -Text $handoffText -Pattern "^\s*Session\s*:\s*(?<value>[A-Za-z0-9_-]+)\s*$"
    $status = Get-RegexField -Text $handoffText -Pattern "^\s*Status\s*:\s*(?<value>[A-Za-z0-9_-]+)\s*$"
    $nextSession = Get-RegexField -Text $handoffText -Pattern "^\s*Next\s+Session\s*:\s*(?<value>[A-Za-z0-9_-]+|NONE|END|COMPLETE)\s*$"
    $validation = Get-RegexField -Text $handoffText -Pattern "^\s*Validation(?:\s+Status)?\s*:\s*(?<value>.+?)\s*$"
    $commitHash = Get-RegexField -Text $handoffText -Pattern "^\s*Commit(?:\s+Hash)?\s*:\s*(?<value>[A-Fa-f0-9]{7,40}|none|n/a|pending)\s*$"

    if (-not $session) {
        $session = $FallbackSession
    }

    if (-not $status) {
        $status = "FAIL"
    }

    $status = $status.ToUpperInvariant()
    if ($nextSession -match "^(NONE|END|COMPLETE)$") {
        $nextSession = ""
    }

    $lines = @($handoffText -split "`n")
    $excerpt = ($lines | Select-Object -First 120) -join "`n"

    return [pscustomobject]@{
        session = $session
        status = $status
        next_session = $nextSession
        validation_status = $validation
        commit_hash = $commitHash
        has_handoff_package = ($handoffStart -ge 0)
        parsed_at = Get-OrchestratorTimestamp
        excerpt = $excerpt
    }
}

function Save-FailureReport {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$SessionId,
        [Parameter(Mandatory = $true)]
        [int]$RetryCount,
        [Parameter(Mandatory = $true)]
        [int]$ExitCode,
        [Parameter(Mandatory = $true)]
        [string]$Reason,
        [string]$LogPath = "",
        [object]$Handoff = $null
    )

    $report = [ordered]@{
        session = $SessionId
        status = "FAILED_MAX_RETRIES"
        retry_count = $RetryCount
        exit_code = $ExitCode
        reason = $Reason
        log_path = $LogPath
        handoff = $Handoff
        created_at = Get-OrchestratorTimestamp
    }

    Write-OrchestratorJson -Path $Path -Value $report
}
