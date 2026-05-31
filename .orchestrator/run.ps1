param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$StartSession = "",
    [int]$MaxRetries = 3,
    [switch]$Once
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "orchestrator-lib.ps1")

$orchestratorRoot = $PSScriptRoot
$queuePath = Join-Path $orchestratorRoot "queue.json"
$statePath = Join-Path $orchestratorRoot "state.json"
$promptsDir = Join-Path $orchestratorRoot "prompts"
$handoffsDir = Join-Path $orchestratorRoot "handoffs"
$logsDir = Join-Path $orchestratorRoot "logs"
$sessionsDir = Join-Path $orchestratorRoot "sessions"

foreach ($dir in @($promptsDir, $handoffsDir, $logsDir, $sessionsDir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

if (-not (Test-Path -LiteralPath $queuePath) -or -not (Test-Path -LiteralPath $promptsDir)) {
    & (Join-Path $orchestratorRoot "generate-prompts.ps1") -OrchestratorRoot $orchestratorRoot
}

Initialize-OrchestratorState -StatePath $statePath

$queueIds = Get-OrchestratorQueueIds -QueuePath $queuePath
$codexExe = Resolve-CodexExecutable

function Add-BestEffortLogLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [AllowNull()]
        [string]$Value,
        [int]$MaxAttempts = 5
    )

    $line = if ($null -eq $Value) { "" } else { $Value }
    $lastError = ""

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt += 1) {
        try {
            Add-Content -LiteralPath $Path -Value $line -Encoding UTF8 -ErrorAction Stop
            return $true
        } catch {
            $lastError = $_.Exception.Message
            Start-Sleep -Milliseconds (75 * $attempt)
        }
    }

    Write-Warning "Skipped aggregate log write after $MaxAttempts attempts: $Path ($lastError)"
    return $false
}

function Add-BestEffortLogLines {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string[]]$Lines
    )

    foreach ($line in $Lines) {
        [void](Add-BestEffortLogLine -Path $Path -Value $line)
    }
}

function Update-State {
    param(
        [string]$CurrentSession,
        [string]$LastCompleted,
        [string]$Status,
        [int]$RetryCount,
        [string]$StartedAt = $null
    )

    $existing = Read-OrchestratorJson -Path $statePath
    $state = [ordered]@{
        current_session = if ($PSBoundParameters.ContainsKey("CurrentSession")) { $CurrentSession } else { [string]$existing.current_session }
        last_completed = if ($PSBoundParameters.ContainsKey("LastCompleted")) { $LastCompleted } else { [string]$existing.last_completed }
        status = if ($PSBoundParameters.ContainsKey("Status")) { $Status } else { [string]$existing.status }
        started_at = if ($StartedAt) { $StartedAt } else { [string]$existing.started_at }
        updated_at = Get-OrchestratorTimestamp
        retry_count = if ($PSBoundParameters.ContainsKey("RetryCount")) { $RetryCount } else { [int]$existing.retry_count }
    }

    Write-OrchestratorJson -Path $statePath -Value $state
    return [pscustomobject]$state
}

function Invoke-CodexSession {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SessionId,
        [Parameter(Mandatory = $true)]
        [int]$RetryCount
    )

    $promptPath = Join-Path $promptsDir "$SessionId.txt"
    if (-not (Test-Path -LiteralPath $promptPath)) {
        throw "Prompt file not found for session ${SessionId}: $promptPath"
    }

    $attempt = $RetryCount + 1
    $start = Get-Date
    $stamp = $start.ToString("yyyyMMdd-HHmmss")
    $rawLogPath = Join-Path $logsDir "$SessionId.log"
    $attemptLogPath = Join-Path $sessionsDir "$SessionId-attempt-$attempt-$stamp.log"
    $lastMessagePath = Join-Path $sessionsDir "$SessionId-attempt-$attempt-$stamp-last-message.txt"

    $header = @(
        "timestamp=$($start.ToString("o"))",
        "session_id=$SessionId",
        "retry_count=$RetryCount",
        "attempt=$attempt",
        "codex=$codexExe",
        "repo_root=$RepoRoot",
        "approval_policy=never",
        "sandbox_mode=danger-full-access",
        ""
    )
    $header | Set-Content -LiteralPath $attemptLogPath -Encoding UTF8
    Add-BestEffortLogLines -Path $rawLogPath -Lines $header

    $promptText = Get-Content -Raw -LiteralPath $promptPath
    $arguments = @(
        "-a", "never",
        "-s", "danger-full-access",
        "exec",
        "-C", $RepoRoot,
        "--output-last-message", $lastMessagePath,
        "--json",
        "-"
    )
    Write-Host "Launching Codex:"
    Write-Host "$codexExe $($arguments -join ' ')"

    $capturedLines = @()

    try {
    $promptText | & $codexExe @arguments 2>&1 | ForEach-Object {
    $line = $_.ToString()

        $capturedLines += $line

        Add-Content -LiteralPath $attemptLogPath -Value $line -Encoding UTF8
        [void](Add-BestEffortLogLine -Path $rawLogPath -Value $line)

        Write-Host $line
    }

    $exitCode = $LASTEXITCODE

    }
    catch {
    $capturedLines += $_.ToString()

    Add-Content -LiteralPath $attemptLogPath -Value $_.ToString() -Encoding UTF8
    [void](Add-BestEffortLogLine -Path $rawLogPath -Value $_.ToString())

    $exitCode = 1
    
    }


    $end = Get-Date
    $duration = [Math]::Round(($end - $start).TotalSeconds, 2)
    $lastMessage = if (Test-Path -LiteralPath $lastMessagePath) { Get-Content -Raw -LiteralPath $lastMessagePath } else { "" }
    $attemptLog = if (Test-Path -LiteralPath $attemptLogPath) { Get-Content -Raw -LiteralPath $attemptLogPath } else { "" }
    $combined = ($attemptLog + "`n" + $lastMessage)
    $handoff = Parse-HandoffPackage -Text $combined -FallbackSession $SessionId

    $handoffPath = Join-Path $handoffsDir "$SessionId.json"
    Write-OrchestratorJson -Path $handoffPath -Value $handoff

    $footer = @(
        "",
        "duration_seconds=$duration",
        "exit_code=$exitCode",
        "parsed_status=$($handoff.status)",
        "handoff_path=$handoffPath",
        "completed_at=$($end.ToString("o"))",
        ""
    )
    $footer | Add-Content -LiteralPath $attemptLogPath -Encoding UTF8
    Add-BestEffortLogLines -Path $rawLogPath -Lines $footer

    return [pscustomobject]@{
        session = $SessionId
        retry_count = $RetryCount
        exit_code = $exitCode
        duration_seconds = $duration
        log_path = $rawLogPath
        attempt_log_path = $attemptLogPath
        last_message_path = $lastMessagePath
        handoff_path = $handoffPath
        handoff = $handoff
    }
}

$state = Read-OrchestratorJson -Path $statePath
$current = if ($StartSession) {
    if ($StartSession -notin $queueIds) {
        throw "StartSession '$StartSession' is not in queue.json"
    }
    $StartSession
} else {
    Get-NextSessionId -QueueIds $queueIds -LastCompleted ([string]$state.last_completed) -CurrentSession ([string]$state.current_session) -Status ([string]$state.status)
}

if (-not $current) {
    Update-State -CurrentSession "" -LastCompleted ([string]$state.last_completed) -Status "complete" -RetryCount 0 | Out-Null
    Write-Output "All orchestrator sessions are already complete."
    exit 0
}

while ($current) {
    $state = Read-OrchestratorJson -Path $statePath
    $retry = if ([string]$state.current_session -eq $current) { [int]$state.retry_count } else { 0 }
    $startedAt = if ([string]$state.started_at) { [string]$state.started_at } else { Get-OrchestratorTimestamp }
    Update-State -CurrentSession $current -LastCompleted ([string]$state.last_completed) -Status "running" -RetryCount $retry -StartedAt $startedAt | Out-Null

    Write-Output "=== ORCHESTRATOR SESSION $current retry=$retry ==="
    $result = Invoke-CodexSession -SessionId $current -RetryCount $retry
    if ($result -is [System.Array]) {
        $result = $result | Where-Object { $_ -is [psobject] -and $_.PSObject.Properties["handoff"] } | Select-Object -Last 1
    }
    $handoff = $result.handoff
    $attemptLogText = if (Test-Path -LiteralPath $result.attempt_log_path) {
    Get-Content -Raw -LiteralPath $result.attempt_log_path
    } else {
    ""
    }

    $pass =
    $handoff.has_handoff_package`
    -and ($handoff.status -eq "PASS")

    $streamDisconnected =
    (-not $pass) `
    -and (
        $attemptLogText -match "stream disconnected before response.completed" `
        -or $attemptLogText -match "Reconnecting... 5/5"
    )

    if ($streamDisconnected) {
    Write-Output "Transient stream disconnect detected for $current."

    $retry += 1

    if ($retry -lt $MaxRetries) {
        Update-State `
            -CurrentSession $current `
            -LastCompleted ([string](Read-OrchestratorJson -Path $statePath).last_completed) `
            -Status "stream_retry" `
            -RetryCount $retry `
            -StartedAt $startedAt | Out-Null

        continue
    }

    }

    if ($pass) {
        $candidateNext = [string]$handoff.next_session
        if ($candidateNext -and $candidateNext -notin $queueIds) {
            throw "Handoff for $current points to unknown next session '$candidateNext'."
        }

        if (-not $candidateNext) {
            $candidateNext = Get-NextSessionId -QueueIds $queueIds -LastCompleted $current -CurrentSession "" -Status "passed"
        }

        if ($candidateNext) {
            Update-State -CurrentSession $candidateNext -LastCompleted $current -Status "queued" -RetryCount 0 -StartedAt $startedAt | Out-Null
        } else {
            Update-State -CurrentSession "" -LastCompleted $current -Status "complete" -RetryCount 0 -StartedAt $startedAt | Out-Null
            Write-Output "All orchestrator sessions complete. last_completed=$current"
            exit 0
        }

        if ($Once) {
            Write-Output "Once mode complete. next_session=$candidateNext"
            exit 0
        }

        $current = $candidateNext
        continue
    }

    $retry += 1
    if ($retry -lt $MaxRetries) {
        Update-State -CurrentSession $current -LastCompleted ([string](Read-OrchestratorJson -Path $statePath).last_completed) -Status "failed_retryable" -RetryCount $retry -StartedAt $startedAt | Out-Null
        Write-Output "Session $current failed; retrying automatically ($retry/$MaxRetries)."
        continue
    }

    $failurePath = Join-Path $logsDir "$current.failure.json"
    Save-FailureReport -Path $failurePath -SessionId $current -RetryCount $retry -ExitCode $result.exit_code -Reason "Session failed or did not emit PASS handoff after max retries." -LogPath $result.log_path -Handoff $handoff
    Update-State -CurrentSession $current -LastCompleted ([string](Read-OrchestratorJson -Path $statePath).last_completed) -Status "failed" -RetryCount $retry -StartedAt $startedAt | Out-Null
    Write-Error "Stopping orchestration after $retry failed attempts for $current. Failure report: $failurePath"
}
