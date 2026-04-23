param(
  [string]$RunDirectory = "",
  [string]$OutputRoot = ".run\\soak",
  [int]$RecentEventCount = 12,
  [int]$RecentSnapshotCount = 3,
  [switch]$AsJson
)

$ErrorActionPreference = "Stop"

function Resolve-SoakDirectory {
  param(
    [string]$RunDirectory,
    [string]$OutputRoot
  )

  if ($RunDirectory) {
    if (-not (Test-Path $RunDirectory)) {
      throw "RunDirectory not found: $RunDirectory"
    }
    return (Resolve-Path $RunDirectory).Path
  }

  $resolvedRoot = Resolve-Path $OutputRoot -ErrorAction Stop
  $latest = Get-ChildItem $resolvedRoot.Path -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $latest) {
    throw "No soak runs found under $($resolvedRoot.Path)"
  }
  return $latest.FullName
}

function Read-JsonLines {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return @() }
  $rows = @()
  foreach ($line in Get-Content $Path) {
    if ([string]::IsNullOrWhiteSpace($line)) {
      $trimmed = ""
    } else {
      $trimmed = $line.Trim()
    }
    if (-not $trimmed) { continue }
    try {
      $rows += ($trimmed | ConvertFrom-Json)
    } catch {
      # Ignore malformed lines and continue; the soak run should not be invalidated by one bad row.
    }
  }
  return $rows
}

function Get-LatestProviderStates {
  param([object[]]$Snapshots)
  $latest = $Snapshots | Select-Object -Last 1
  if (-not $latest) { return @() }
  return @($latest.provider_states)
}

function Measure-ProviderThrottleEvents {
  param([object[]]$Snapshots)
  $count = 0
  foreach ($snapshot in $Snapshots) {
    foreach ($provider in @($snapshot.provider_states)) {
      if ($provider.quota_state -in @("throttled", "budget_window_exhausted", "error")) {
        $count += 1
      }
    }
  }
  return $count
}

function Get-MemoryPeak {
  param(
    [object[]]$Snapshots,
    [string]$Key
  )
  $peak = 0.0
  foreach ($snapshot in $Snapshots) {
    $rss = 0.0
    try { $rss = [double]$snapshot.processes.$Key.rss_mb } catch { $rss = 0.0 }
    if ($rss -gt $peak) { $peak = $rss }
  }
  return [math]::Round($peak, 2)
}

$runDir = Resolve-SoakDirectory -RunDirectory $RunDirectory -OutputRoot $OutputRoot
$snapshotsPath = Join-Path $runDir "snapshots.jsonl"
$summaryPath = Join-Path $runDir "summary.json"
$eventsPath = Join-Path $runDir "events.log"

$snapshots = @(Read-JsonLines -Path $snapshotsPath)
$latest = $snapshots | Select-Object -Last 1
$startedAt = $null
$endedAt = $null
if ($snapshots.Count -gt 0) {
  try { $startedAt = [datetime]$snapshots[0].timestamp } catch {}
  try { $endedAt = [datetime]$latest.timestamp } catch {}
}

$summary = if (Test-Path $summaryPath) {
  Get-Content $summaryPath -Raw | ConvertFrom-Json
} else {
  [pscustomobject]@{
    started_at = if ($startedAt) { $startedAt.ToString("o") } else { $null }
    ended_at = if ($endedAt) { $endedAt.ToString("o") } else { $null }
    duration_hours = if ($startedAt -and $endedAt) { [math]::Round((($endedAt - $startedAt).TotalHours), 3) } else { 0 }
    sample_count = $snapshots.Count
    probe_failures = @($snapshots | Where-Object { -not $_.backend_ok }).Count
    halt_observations = @($snapshots | Where-Object { $_.halted }).Count
    max_active_tasks = @($snapshots | ForEach-Object { [int]($_.active_task_count) } | Measure-Object -Maximum).Maximum
    max_pending_approvals = @($snapshots | ForEach-Object { [int]($_.pending_approval_count) } | Measure-Object -Maximum).Maximum
    max_signal_packs = @($snapshots | ForEach-Object { [int]($_.signal_pack_count) } | Measure-Object -Maximum).Maximum
    provider_throttle_events = Measure-ProviderThrottleEvents -Snapshots $snapshots
    last_digest_id = if ($latest) { $latest.last_digest_id } else { $null }
    memory_peaks_mb = @{
      backend = Get-MemoryPeak -Snapshots $snapshots -Key "backend"
      frontend = Get-MemoryPeak -Snapshots $snapshots -Key "frontend"
      blog = Get-MemoryPeak -Snapshots $snapshots -Key "blog"
    }
    output_dir = $runDir
  }
}

$recentEventLines = if (Test-Path $eventsPath) { Get-Content -Path $eventsPath -Tail $RecentEventCount } else { @() }
$recentSnapshotRows = @($snapshots | Select-Object -Last $RecentSnapshotCount | ForEach-Object {
  [ordered]@{
    timestamp = $_.timestamp
    backend_ok = $_.backend_ok
    halted = $_.halted
    active_tasks = $_.active_task_count
    signal_packs = $_.signal_pack_count
    pending_approvals = $_.pending_approval_count
    llm_agent_health = $_.llm_agent_health
    last_digest_id = $_.last_digest_id
  }
})

$payload = [ordered]@{
  run_directory = $runDir
  summary = $summary
  latest_snapshot = $latest
  provider_states = @(Get-LatestProviderStates -Snapshots $snapshots)
  recent_snapshots = $recentSnapshotRows
  recent_events = $recentEventLines
}

if ($AsJson) {
  $payload | ConvertTo-Json -Depth 10
  exit 0
}

Write-Host ""
Write-Host "Local Soak Progress" -ForegroundColor Cyan
Write-Host "Run directory: $runDir"
Write-Host "Samples: $($summary.sample_count)"
Write-Host "Duration hours: $($summary.duration_hours)"
Write-Host "Probe failures: $($summary.probe_failures)"
Write-Host "Halts observed: $($summary.halt_observations)"
Write-Host "Max active tasks: $($summary.max_active_tasks)"
Write-Host "Max pending approvals: $($summary.max_pending_approvals)"
Write-Host "Max signal packs: $($summary.max_signal_packs)"
Write-Host "Provider throttle events: $($summary.provider_throttle_events)"
Write-Host "Last digest id: $($summary.last_digest_id)"
Write-Host ""

if ($latest) {
  Write-Host "Latest snapshot" -ForegroundColor Yellow
  Write-Host "  timestamp: $($latest.timestamp)"
  Write-Host "  backend_ok: $($latest.backend_ok)"
  Write-Host "  halted: $($latest.halted)"
  Write-Host "  orchestration: $($latest.orchestration)"
  Write-Host "  execution_mode: $($latest.execution_mode)"
  Write-Host "  llm_agent_health: $($latest.llm_agent_health)"
  Write-Host "  active_tasks: $($latest.active_task_count)"
  Write-Host "  signal_packs: $($latest.signal_pack_count)"
  Write-Host "  pending_approvals: $($latest.pending_approval_count)"
  Write-Host ""
}

if (@($payload.provider_states).Count) {
  Write-Host "Providers" -ForegroundColor Yellow
  foreach ($provider in @($payload.provider_states)) {
    Write-Host ("  {0}: quota={1} in_flight={2} attempts={3} failures={4} cooldown={5}s" -f `
      $provider.name, `
      $provider.quota_state, `
      $provider.in_flight, `
      $provider.attempts, `
      $provider.failures, `
      ([math]::Round([double]$provider.cooldown_remaining_seconds, 1)))
  }
  Write-Host ""
}

if ($recentEventLines.Count) {
  Write-Host "Recent events" -ForegroundColor Yellow
  $recentEventLines | ForEach-Object { Write-Host "  $_" }
  Write-Host ""
}

Write-Host "Memory peaks (MB)" -ForegroundColor Yellow
Write-Host "  backend: $($summary.memory_peaks_mb.backend)"
Write-Host "  frontend: $($summary.memory_peaks_mb.frontend)"
Write-Host "  blog: $($summary.memory_peaks_mb.blog)"
