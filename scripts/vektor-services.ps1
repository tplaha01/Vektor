param(
  [ValidateSet("up", "down", "restart", "status", "health", "watch")]
  [string]$Action = "status",
  [int]$WatchIntervalSeconds = 15
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $RepoRoot ".run"
if (-not (Test-Path $RunDir)) {
  New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
}

$BackendPidFile = Join-Path $RunDir "backend.pid"
$OllamaPidFile = Join-Path $RunDir "ollama.pid"
$OpenClawRuntimeConfigPath = Join-Path $RunDir "openclaw.runtime.json"

function Get-OpenClawConfigPath {
  $defaultPath = Join-Path (Join-Path $HOME ".openclaw") "openclaw.json"
  if (-not (Test-Path $defaultPath)) {
    return $null
  }

  try {
    $raw = Get-Content -Path $defaultPath -Raw -ErrorAction Stop
    if (-not $raw) {
      return $null
    }
    $config = $raw | ConvertFrom-Json -ErrorAction Stop
    if (@($config.PSObject.Properties.Name) -contains "mcpServers") {
      $sanitizedConfig = [ordered]@{}
      foreach ($prop in $config.PSObject.Properties) {
        if ($prop.Name -ne "mcpServers") {
          $sanitizedConfig[$prop.Name] = $prop.Value
        }
      }
      $sanitized = $sanitizedConfig | ConvertTo-Json -Depth 100
      Set-Content -Path $OpenClawRuntimeConfigPath -Value $sanitized -Encoding UTF8
      Write-Host "[openclaw] sanitized runtime config at $OpenClawRuntimeConfigPath (removed unsupported mcpServers)"
      return $OpenClawRuntimeConfigPath
    }
    return $defaultPath
  } catch {
    Write-Host "[openclaw] warning: failed to parse $defaultPath; using default OpenClaw profile fallback"
    return $null
  }
}

function Get-ListeningPids {
  param([int]$Port)
  [array]$rows = @(
    Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique
  )
  return $rows
}

function Test-Any {
  param([object]$Value)
  return (@($Value)).Length -gt 0
}

function Test-Endpoint {
  param(
    [string]$Url,
    [int]$TimeoutSec = 5
  )
  try {
    Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Invoke-OpenClaw {
  param(
    [string[]]$CliArgs,
    [switch]$Quiet
  )

  $resolvedConfigPath = Get-OpenClawConfigPath
  $priorConfigPath = $env:OPENCLAW_CONFIG_PATH
  $hasPriorConfigPath = [bool]$priorConfigPath
  if ($resolvedConfigPath) {
    $env:OPENCLAW_CONFIG_PATH = $resolvedConfigPath
  } else {
    Remove-Item Env:OPENCLAW_CONFIG_PATH -ErrorAction SilentlyContinue
  }

  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    if ($Quiet) {
      & openclaw @CliArgs 1>$null 2>$null
    } else {
      & openclaw @CliArgs | Out-Host
    }
    return $LASTEXITCODE
  } catch {
    return 1
  } finally {
    if ($hasPriorConfigPath) {
      $env:OPENCLAW_CONFIG_PATH = $priorConfigPath
    } else {
      Remove-Item Env:OPENCLAW_CONFIG_PATH -ErrorAction SilentlyContinue
    }
    $ErrorActionPreference = $prev
  }
}

function Test-OpenClawService {
  $pids = @(Get-ListeningPids -Port 18789)
  if (-not (Test-Any $pids)) {
    return $false
  }
  $statusCode = Invoke-OpenClaw -CliArgs @("gateway", "status", "--no-probe") -Quiet
  return $statusCode -eq 0
}

function Start-Backend {
  $pids = @(Get-ListeningPids -Port 8000)
  if (Test-Any $pids) {
    Write-Host "[backend] already listening on 8000 (pid: $($pids -join ','))"
    return
  }

  $venvPython = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
  $backendCwd = Join-Path $RepoRoot "backend"
  $args = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")

  if (Test-Path $venvPython) {
    $proc = Start-Process -FilePath $venvPython -ArgumentList $args -WorkingDirectory $backendCwd -PassThru -WindowStyle Hidden
  } else {
    $proc = Start-Process -FilePath "py" -ArgumentList @("-3") + $args -WorkingDirectory $backendCwd -PassThru -WindowStyle Hidden
  }
  Set-Content -Path $BackendPidFile -Value $proc.Id -NoNewline
  Write-Host "[backend] started pid=$($proc.Id)"
}

function Stop-Backend {
  if (Test-Path $BackendPidFile) {
    $backendPid = [int](Get-Content $BackendPidFile -ErrorAction SilentlyContinue)
    if ($backendPid -gt 0) {
      Stop-Process -Id $backendPid -Force -ErrorAction SilentlyContinue
      Write-Host "[backend] stopped pid=$backendPid"
    }
    Remove-Item $BackendPidFile -Force -ErrorAction SilentlyContinue
  }
}

function Start-Ollama {
  $pids = @(Get-ListeningPids -Port 11434)
  if (Test-Any $pids) {
    Write-Host "[ollama] already listening on 11434 (pid: $($pids -join ','))"
    return
  }
  $proc = Start-Process -FilePath "ollama" -ArgumentList @("serve") -PassThru -WindowStyle Hidden
  Set-Content -Path $OllamaPidFile -Value $proc.Id -NoNewline
  Write-Host "[ollama] started pid=$($proc.Id)"
}

function Stop-Ollama {
  if (Test-Path $OllamaPidFile) {
    $ollamaPid = [int](Get-Content $OllamaPidFile -ErrorAction SilentlyContinue)
    if ($ollamaPid -gt 0) {
      Stop-Process -Id $ollamaPid -Force -ErrorAction SilentlyContinue
      Write-Host "[ollama] stopped pid=$ollamaPid"
    }
    Remove-Item $OllamaPidFile -Force -ErrorAction SilentlyContinue
  }
}

function Start-OpenClaw {
  if (Test-OpenClawService) {
    Write-Host "[openclaw] gateway already healthy"
    return
  }

  $existingListener = Test-Any @(Get-ListeningPids -Port 18789)
  if ($existingListener) {
    Write-Host "[openclaw] listener exists but service probe is unhealthy; requesting restart"
    $restartCode = Invoke-OpenClaw -CliArgs @("gateway", "restart")
    if ($restartCode -ne 0) {
      throw "[openclaw] failed to restart gateway service"
    }
  } else {
    $startCode = Invoke-OpenClaw -CliArgs @("gateway", "start")
    if ($startCode -ne 0) {
      throw "[openclaw] failed to start gateway service"
    }
  }

  $deadline = (Get-Date).AddSeconds(60)
  while ((Get-Date) -lt $deadline) {
    if (Test-OpenClawService) {
      Write-Host "[openclaw] gateway start requested and is healthy"
      return
    }
    Start-Sleep -Seconds 2
  }
  throw "[openclaw] gateway start requested, but health probe still failing"
}

function Stop-OpenClaw {
  $stopCode = Invoke-OpenClaw -CliArgs @("gateway", "stop")
  if ($stopCode -eq 0) {
    Write-Host "[openclaw] gateway stop requested"
  }
}

function Get-ServiceHealth {
  # /health includes fund/runtime summaries and can exceed 5s during startup.
  # Use a wider timeout to avoid false "backend=down" status on healthy runs.
  $backendOk = Test-Endpoint -Url "http://127.0.0.1:8000/health" -TimeoutSec 12
  $ollamaOk = Test-Endpoint -Url "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
  $openclawOk = Test-OpenClawService

  return [pscustomobject]@{
    backend  = if ($backendOk) { "healthy" } else { "down" }
    ollama   = if ($ollamaOk) { "healthy" } else { "down" }
    openclaw = if ($openclawOk) { "healthy" } else { "down" }
  }
}

function Show-Status {
  $ports = @(8000, 11434, 18789)
  foreach ($port in $ports) {
    $pids = @(Get-ListeningPids -Port $port)
    if (Test-Any $pids) {
      Write-Host ("port {0}: LISTEN (pid: {1})" -f $port, ($pids -join ","))
    } else {
      Write-Host ("port {0}: NOT LISTENING" -f $port)
    }
  }
  $health = Get-ServiceHealth
  Write-Host ("health: backend={0} ollama={1} openclaw={2}" -f $health.backend, $health.ollama, $health.openclaw)
}

function Wait-Healthy {
  param([int]$TimeoutSec = 45)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    $h = Get-ServiceHealth
    if ($h.backend -eq "healthy" -and $h.ollama -eq "healthy" -and $h.openclaw -eq "healthy") {
      Write-Host "All services healthy."
      return
    }
    Start-Sleep -Seconds 2
  }
  throw "Timed out waiting for healthy backend/openclaw/ollama."
}

switch ($Action) {
  "up" {
    Start-Ollama
    Start-OpenClaw
    Start-Backend
    Wait-Healthy
    Show-Status
    break
  }
  "down" {
    Stop-Backend
    Stop-OpenClaw
    Stop-Ollama
    Show-Status
    break
  }
  "restart" {
    Stop-Backend
    Stop-OpenClaw
    Stop-Ollama
    Start-Sleep -Seconds 1
    Start-Ollama
    Start-OpenClaw
    Start-Backend
    Wait-Healthy
    Show-Status
    break
  }
  "status" {
    Show-Status
    break
  }
  "health" {
    $h = Get-ServiceHealth
    $line = ("backend={0} ollama={1} openclaw={2}" -f $h.backend, $h.ollama, $h.openclaw)
    Write-Host $line
    if ($h.backend -ne "healthy" -or $h.ollama -ne "healthy" -or $h.openclaw -ne "healthy") {
      exit 1
    }
    break
  }
  "watch" {
    while ($true) {
      try {
        $h = Get-ServiceHealth
        if ($h.ollama -ne "healthy") { Start-Ollama }
        if ($h.openclaw -ne "healthy") { Start-OpenClaw }
        if ($h.backend -ne "healthy") { Start-Backend }
      } catch {
        Write-Host ("[watch] " + $_.Exception.Message)
      }
      Start-Sleep -Seconds ([Math]::Max(5, $WatchIntervalSeconds))
    }
  }
}
