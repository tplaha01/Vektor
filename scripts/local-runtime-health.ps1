param(
  [string]$BackendUrl = "http://127.0.0.1:8000",
  [string]$FrontendUrl = "http://127.0.0.1:9000/admin",
  [string]$BlogUrl = "http://127.0.0.1:3001",
  [switch]$AsJson
)

$ErrorActionPreference = "Stop"

function Invoke-SafeJson {
  param(
    [Parameter(Mandatory = $true)][string]$Uri
  )
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
  param(
    [Parameter(Mandatory = $true)][int]$Port
  )
  try {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop | Select-Object -First 1
    if (-not $connection) { return $null }
    $process = Get-Process -Id $connection.OwningProcess -ErrorAction Stop
    return @{
      pid = $process.Id
      name = $process.ProcessName
      rss_mb = [math]::Round($process.WorkingSet64 / 1MB, 2)
      cpu_seconds = [math]::Round($process.CPU, 2)
    }
  } catch {
    return $null
  }
}

$health = Invoke-SafeJson -Uri "$BackendUrl/health"
$workers = Invoke-SafeJson -Uri "$BackendUrl/fund/agents/workers/status"
$statusBadges = Invoke-SafeJson -Uri "$BackendUrl/api/admin/system/status-badges"
$ceoDigest = Invoke-SafeJson -Uri "$BackendUrl/api/admin/ceo/digest"
$approvals = Invoke-SafeJson -Uri "$BackendUrl/api/admin/ceo/approvals/pending?limit=100"

$snapshot = [ordered]@{
  timestamp = (Get-Date).ToUniversalTime().ToString("o")
  backend = @{
    url = $BackendUrl
    ok = $health.ok
    health = $health.payload
    error = $health.error
  }
  workers = @{
    ok = $workers.ok
    active_tasks = @($workers.payload.active_contexts).Count
    signal_packs = @($workers.payload.signal_packs).Count
    pending_decisions = @($workers.payload.pending_decisions).Count
    ceo_digest = $workers.payload.ceo_digest
    ai_role_adapter = $workers.payload.ai_role_adapter
    error = $workers.error
  }
  status_badges = @{
    ok = $statusBadges.ok
    halted = [bool]$statusBadges.payload.halt.halted
    orchestration = $statusBadges.payload.orchestration.status
    data_source = $statusBadges.payload.data_source.status
    execution_mode = $statusBadges.payload.execution_mode.status
    llm_agent_health = $statusBadges.payload.llm_agent_health.status
    error = $statusBadges.error
  }
  ceo = @{
    digest_ok = $ceoDigest.ok
    approvals_ok = $approvals.ok
    positions = $ceoDigest.payload.summary.positions_count
    pending_approvals = @($approvals.payload.approvals).Count
    risk_alerts = @($ceoDigest.payload.risk_alerts).Count
    error = @($ceoDigest.error, $approvals.error) -ne $null
  }
  processes = @{
    backend = Get-PortProcess -Port 8000
    frontend = Get-PortProcess -Port 9000
    blog = Get-PortProcess -Port 3001
  }
  surfaces = @{
    frontend = $FrontendUrl
    blog = $BlogUrl
  }
}

if ($AsJson) {
  $snapshot | ConvertTo-Json -Depth 8
} else {
  Write-Host ""
  Write-Host "Local Runtime Health" -ForegroundColor Cyan
  Write-Host "Timestamp: $($snapshot.timestamp)"
  Write-Host "Backend health: $($snapshot.backend.ok)"
  Write-Host "Orchestration: $($snapshot.status_badges.orchestration)"
  Write-Host "Data source: $($snapshot.status_badges.data_source)"
  Write-Host "Execution mode: $($snapshot.status_badges.execution_mode)"
  Write-Host "LLM health: $($snapshot.status_badges.llm_agent_health)"
  Write-Host "Halted: $($snapshot.status_badges.halted)"
  Write-Host "Active tasks: $($snapshot.workers.active_tasks)"
  Write-Host "Signal packs: $($snapshot.workers.signal_packs)"
  Write-Host "Pending decisions: $($snapshot.workers.pending_decisions)"
  Write-Host "Pending approvals: $($snapshot.ceo.pending_approvals)"
  Write-Host "Risk alerts: $($snapshot.ceo.risk_alerts)"
  Write-Host ""
  $snapshot.processes.GetEnumerator() | ForEach-Object {
    $proc = $_.Value
    if ($null -eq $proc) {
      Write-Host "$($_.Key): not listening"
    } else {
      Write-Host "$($_.Key): pid=$($proc.pid) rss=$($proc.rss_mb)MB cpu=$($proc.cpu_seconds)s"
    }
  }
}
