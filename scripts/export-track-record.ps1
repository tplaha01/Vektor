param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$OutDir = "",
  [int]$Limit = 5000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) {
  $OutDir = Join-Path $RepoRoot ".artifacts\track-record\$(Get-Date -Format 'yyyyMMdd-HHmmss')"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$summary = Invoke-RestMethod -Uri "$BaseUrl/fund/performance/summary" -TimeoutSec 15
$snapshots = Invoke-RestMethod -Uri "$BaseUrl/fund/performance/snapshots?limit=$Limit" -TimeoutSec 30
$decisions = Invoke-RestMethod -Uri "$BaseUrl/fund/decisions/pending" -TimeoutSec 15
$blocked = Invoke-RestMethod -Uri "$BaseUrl/fund/trades/blocked?limit=500" -TimeoutSec 15

$summary | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $OutDir "performance-summary.json")
$snapshots | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $OutDir "performance-snapshots.json")
$decisions | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $OutDir "pending-decisions.json")
$blocked | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $OutDir "blocked-trades.json")

$csvRows = @()
foreach ($row in @($snapshots)) {
  $primary = @($row.benchmarks)[0]
  $csvRows += [pscustomobject]@{
    snapshot_id = $row.snapshot_id
    snapshot_kind = $row.snapshot_kind
    recorded_at = $row.recorded_at
    equity = $row.equity
    cash = $row.cash
    market_value = $row.market_value
    realized_pnl = $row.realized_pnl
    unrealized_pnl = $row.unrealized_pnl
    total_pnl = $row.total_pnl
    total_trades = $row.total_trades
    win_rate = $row.win_rate
    max_drawdown = $row.max_drawdown
    primary_benchmark = if ($primary) { $primary.symbol } else { "" }
    primary_benchmark_return_pct = if ($primary) { $primary.return_pct } else { "" }
  }
}
$csvRows | Export-Csv -Path (Join-Path $OutDir "performance-snapshots.csv") -NoTypeInformation

Write-Host "Track record exported to $OutDir"
