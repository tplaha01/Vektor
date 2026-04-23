param(
  [double]$DurationHours = 24,
  [int]$IntervalSeconds = 30,
  [string]$BackendUrl = "http://127.0.0.1:8000",
  [string]$OutputRoot = ".run\\soak"
)

$ErrorActionPreference = "Stop"

if ($IntervalSeconds -lt 10) {
  throw "IntervalSeconds must be at least 10."
}

$startTime = Get-Date
$runStamp = $startTime.ToString("yyyyMMdd-HHmmss")
$outputDir = Join-Path (Resolve-Path ".") "$OutputRoot\\$runStamp"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$jsonlPath = Join-Path $outputDir "snapshots.jsonl"
$summaryPath = Join-Path $outputDir "summary.json"
$eventLogPath = Join-Path $outputDir "events.log"

function Write-EventLine {
  param([string]$Message)
  $line = "[{0}] {1}" -f ((Get-Date).ToUniversalTime().ToString("o")), $Message
  Add-Content -Path $eventLogPath -Value $line
  Write-Host $line
}

function Invoke-SafeJson {
  param([string]$Uri)
  try {
    return @{
      ok = $true
      payload = Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 15
      error = $null
    }
  } catch {
    return @{
      ok = $false
      payload = $null
      error = $_.Exception.Message
    }
  }
}

function Get-PortProcess {
  param([int]$Port)
  try {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop | Select-Object -First 1
    if (-not $conn) { return $null }
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction Stop
    return @{
      pid = $proc.Id
      name = $proc.ProcessName
      rss_mb = [math]::Round($proc.WorkingSet64 / 1MB, 2)
      cpu_seconds = [math]::Round($proc.CPU, 2)
    }
  } catch {
    return $null
  }
}

$deadline = $startTime.AddHours($DurationHours)
$sampleCount = 0
$failureCount = 0
$haltCount = 0
$maxActiveTasks = 0
$maxPendingApprovals = 0
$maxSignalPacks = 0
$providerThrottleEvents = 0
$lastDigestId = $null
$memoryPeaks = @{
  backend = 0.0
  frontend = 0.0
  blog = 0.0
}

Write-EventLine "Starting local soak run at $runStamp for $DurationHours hours with $IntervalSeconds second intervals."

while ((Get-Date) -lt $deadline) {
  $health = Invoke-SafeJson -Uri "$BackendUrl/health"
  $workers = Invoke-SafeJson -Uri "$BackendUrl/fund/agents/workers/status"
  $status = Invoke-SafeJson -Uri "$BackendUrl/api/admin/system/status-badges"
  $digest = Invoke-SafeJson -Uri "$BackendUrl/api/admin/ceo/digest"
  $approvals = Invoke-SafeJson -Uri "$BackendUrl/api/admin/ceo/approvals/pending?limit=100"

  $backendProc = Get-PortProcess -Port 8000
  $frontendProc = Get-PortProcess -Port 9000
  $blogProc = Get-PortProcess -Port 3001

  $providerStates = @()
  if ($workers.ok -and $workers.payload.ai_role_adapter.providers) {
    $providerStates = @($workers.payload.ai_role_adapter.providers.PSObject.Properties | ForEach-Object {
      [ordered]@{
        name = $_.Name
        quota_state = $_.Value.quota_state
        attempts = $_.Value.attempts
        failures = $_.Value.failures
        failovers = $_.Value.failovers
        in_flight = $_.Value.in_flight
        cooldown_remaining_seconds = $_.Value.cooldown_remaining_seconds
        window_remaining_seconds = $_.Value.window_remaining_seconds
        requests_in_window = $_.Value.requests_in_window
        requests_per_window = $_.Value.requests_per_window
      }
    })
  }

  $snapshot = [ordered]@{
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    backend_ok = $health.ok
    health = $health.payload
    workers_ok = $workers.ok
    halted = [bool]$status.payload.halt.halted
    orchestration = $status.payload.orchestration.status
    data_source = $status.payload.data_source.status
    execution_mode = $status.payload.execution_mode.status
    llm_agent_health = $status.payload.llm_agent_health.status
    active_task_count = @($workers.payload.active_contexts).Count
    signal_pack_count = @($workers.payload.signal_packs).Count
    pending_decision_count = @($workers.payload.pending_decisions).Count
    pending_approval_count = @($approvals.payload.approvals).Count
    risk_alert_count = @($digest.payload.risk_alerts).Count
    last_digest_id = $workers.payload.ceo_digest.last_digest_id
    ceo_digest_running = [bool]$workers.payload.ceo_digest.running
    provider_states = $providerStates
    processes = @{
      backend = $backendProc
      frontend = $frontendProc
      blog = $blogProc
    }
    errors = @(
      $health.error,
      $workers.error,
      $status.error,
      $digest.error,
      $approvals.error
    ) | Where-Object { $_ }
  }

  ($snapshot | ConvertTo-Json -Depth 10 -Compress) | Add-Content -Path $jsonlPath
  $sampleCount += 1

  if (-not $snapshot.backend_ok -or -not $snapshot.workers_ok) {
    $failureCount += 1
    Write-EventLine "Probe failure detected."
  }
  if ($snapshot.halted) {
    $haltCount += 1
    Write-EventLine "Runtime halt observed."
  }

  $maxActiveTasks = [math]::Max($maxActiveTasks, [int]$snapshot.active_task_count)
  $maxPendingApprovals = [math]::Max($maxPendingApprovals, [int]$snapshot.pending_approval_count)
  $maxSignalPacks = [math]::Max($maxSignalPacks, [int]$snapshot.signal_pack_count)
  $lastDigestId = $snapshot.last_digest_id

  foreach ($provider in $providerStates) {
    if ($provider.quota_state -in @("throttled", "budget_window_exhausted", "error")) {
      $providerThrottleEvents += 1
    }
  }

  foreach ($entry in @(
    @{ key = "backend"; value = $backendProc },
    @{ key = "frontend"; value = $frontendProc },
    @{ key = "blog"; value = $blogProc }
  )) {
    if ($entry.value) {
      $memoryPeaks[$entry.key] = [math]::Max([double]$memoryPeaks[$entry.key], [double]$entry.value.rss_mb)
    }
  }

  Start-Sleep -Seconds $IntervalSeconds
}

$summary = [ordered]@{
  started_at = $startTime.ToUniversalTime().ToString("o")
  ended_at = (Get-Date).ToUniversalTime().ToString("o")
  duration_hours = $DurationHours
  interval_seconds = $IntervalSeconds
  sample_count = $sampleCount
  probe_failures = $failureCount
  halt_observations = $haltCount
  max_active_tasks = $maxActiveTasks
  max_pending_approvals = $maxPendingApprovals
  max_signal_packs = $maxSignalPacks
  provider_throttle_events = $providerThrottleEvents
  last_digest_id = $lastDigestId
  memory_peaks_mb = $memoryPeaks
  output_dir = $outputDir
}

$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryPath
Write-EventLine "Local soak completed. Summary written to $summaryPath"
$summary | ConvertTo-Json -Depth 8
