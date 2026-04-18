param(
  [Parameter(Mandatory = $true)]
  [string]$AppName,
  [string]$ResourceGroup = "vektor-rg",
  [string]$Location = "eastus",
  [ValidateSet("F1", "B1", "B2", "B3", "S1", "P1v3")]
  [string]$Sku = "F1",
  [string]$SubscriptionId = "",
  [string]$EnvFile = "backend/.env",
  [string]$FrontendUrl = "",
  [switch]$SkipDeployCode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Initialize-AzureConfigDir {
  if ($env:AZURE_CONFIG_DIR) {
    return
  }

  $repoRoot = Split-Path -Parent $PSScriptRoot
  $localConfigDir = Join-Path $repoRoot ".azcfg"
  if (Test-Path $localConfigDir) {
    $env:AZURE_CONFIG_DIR = $localConfigDir
  }
}

function Ensure-AzCli {
  if (Get-Command az -ErrorAction SilentlyContinue) {
    return
  }

  $azScriptDir = Join-Path $env:APPDATA "Python\Python314\Scripts"
  $azBat = Join-Path $azScriptDir "az.bat"
  if (-not (Test-Path $azBat)) {
    throw "Azure CLI not found. Install it first (py -3 -m pip install --user azure-cli)."
  }

  $shimDir = Join-Path (Get-Location) ".tmpbin"
  New-Item -ItemType Directory -Force -Path $shimDir | Out-Null
  @'
@echo off
py -3 %*
'@ | Set-Content -Path (Join-Path $shimDir "python.cmd") -NoNewline

  $env:PATH = "$shimDir;$azScriptDir;$env:PATH"

  if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI found on disk but unavailable on PATH."
  }
}

function Assert-AzLogin {
  $null = az account show --output none 2>$null
  if ($LASTEXITCODE -ne 0) {
    throw "Not logged into Azure. Run: az login --use-device-code"
  }
}

function Parse-EnvFile {
  param([string]$Path)
  $result = @{}
  if (-not (Test-Path $Path)) {
    return $result
  }

  Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $key = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()
    if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    $result[$key] = $value
  }

  return $result
}

Initialize-AzureConfigDir
Ensure-AzCli
Assert-AzLogin

if ($SubscriptionId) {
  az account set --subscription $SubscriptionId
}

az group create --name $ResourceGroup --location $Location --output none

if (-not $SkipDeployCode) {
  Push-Location backend
  try {
    az webapp up `
      --name $AppName `
      --resource-group $ResourceGroup `
      --location $Location `
      --runtime "PYTHON:3.11" `
      --sku $Sku `
      --output none
  }
  finally {
    Pop-Location
  }
}

az webapp config set `
  --resource-group $ResourceGroup `
  --name $AppName `
  --startup-file "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000" `
  --output none

$envMap = Parse-EnvFile -Path $EnvFile

$allowedKeys = @(
  "APP_NAME",
  "ENV",
  "BROKER",
  "DATA_MODE",
  "REAL_DATA_STRICT_MODE",
  "TECH_WEIGHT",
  "FUND_WEIGHT",
  "SENT_WEIGHT",
  "ML_WEIGHT",
  "WEBSOCKET_BROADCAST_INTERVAL",
  "AUTO_TRADING_ENABLED",
  "AGENT_RUNTIME_ENABLED",
  "AGENT_RUNTIME_POLL_INTERVAL_SECONDS",
  "AGENT_RUNTIME_AUTOPILOT_ENABLED",
  "AGENT_RUNTIME_AUTOPILOT_INTERVAL_SECONDS",
  "AGENT_RUNTIME_AUTOPILOT_SYMBOLS",
  "AGENT_RUNTIME_AUTOPILOT_DEFAULT_SIDE",
  "AGENT_RUNTIME_AUTOPILOT_DEFAULT_QUANTITY",
  "AGENT_RUNTIME_AUTOPILOT_SLEEVE",
  "FUND_DEFAULT_CAPITAL_USD",
  "FUND_DEFAULT_RESERVE_CASH_USD",
  "FUND_DEFAULT_SLEEVE_WEIGHTS",
  "SECRET_KEY",
  "API_KEY",
  "OPENCLAW_INGEST_TOKEN",
  "OPENCLAW_COMMANDS_ENABLED",
  "OPENCLAW_COMMAND_TOKEN",
  "OPENCLAW_COMMAND_DEFAULT_AGENT_ID",
  "OPENCLAW_COMMAND_CHANNEL_ALLOWLIST",
  "OPENCLAW_COMMAND_SENDER_ALLOWLIST",
  "OPENCLAW_COMMAND_ROLE_ALLOWLIST",
  "OPENCLAW_COMMAND_CHANNEL_ROLE_POLICIES",
  "OPENCLAW_COMMAND_MAX_TEXT_LENGTH",
  "OPENCLAW_FUND_MANAGER_MODE",
  "OPENCLAW_FUND_MANAGER_AGENT_ID",
  "OPENCLAW_FUND_MANAGER_ASSIGNED_ROLES",
  "KNOWLEDGE_GRAPH_ENABLED",
  "KNOWLEDGE_GRAPH_MAX_EVENTS",
  "KNOWLEDGE_GRAPH_PERSIST",
  "GRAPHIFY_SYNC_ENABLED",
  "GRAPHIFY_SYNC_MIN_INTERVAL_SECONDS",
  "GRAPHIFY_UPDATE_COMMAND",
  "AI_ROLE_ADAPTER_ENABLED",
  "AI_ROLE_PROVIDER",
  "AI_ROLE_API_BASE_URL",
  "AI_ROLE_API_KEY",
  "AI_ROLE_TIMEOUT_SECONDS",
  "AI_ROLE_TEMPERATURE",
  "AI_ROLE_MAX_TOKENS",
  "AI_ROLE_MODEL_DEFAULT",
  "AI_ROLE_MODEL_TECHNICAL",
  "AI_ROLE_MODEL_FUNDAMENTAL",
  "AI_ROLE_MODEL_SENTIMENT",
  "AI_ROLE_MODEL_ML",
  "AI_ROLE_MODEL_INSIGHT",
  "AI_ROLE_MODEL_HEDGE_FUND",
  "AI_ROLE_REQUIRE_SUCCESS",
  "NEWSAPI_KEY",
  "FMP_KEY",
  "FINNHUB_KEY",
  "ALPACA_API_KEY",
  "ALPACA_SECRET_KEY",
  "ALPACA_BASE_URL",
  "ALPACA_FEED",
  "BUY_THRESHOLD",
  "SELL_THRESHOLD",
  "ATR_PERIOD",
  "VOL_THRESHOLD",
  "FRONTEND_URL"
)

$settingsList = New-Object System.Collections.Generic.List[string]

foreach ($key in $allowedKeys) {
  if ($envMap.ContainsKey($key)) {
    $value = [string]$envMap[$key]
    if ($value) {
      $settingsList.Add("$key=$value")
    }
  }
}

# Safety overrides for cloud deployment posture.
$settingsList.Add("ENV=prod")
$settingsList.Add("BROKER=paper")
$settingsList.Add("AUTO_TRADING_ENABLED=false")
$settingsList.Add("WEBSITES_PORT=8000")

if ($FrontendUrl) {
  $settingsList.Add("FRONTEND_URL=$FrontendUrl")
}

if ($settingsList.Count -gt 0) {
  az webapp config appsettings set `
    --resource-group $ResourceGroup `
    --name $AppName `
    --settings $settingsList `
    --output none
}

az webapp restart --resource-group $ResourceGroup --name $AppName --output none

$backendUrl = "https://$AppName.azurewebsites.net"
Write-Output "BACKEND_URL=$backendUrl"
Write-Output "HEALTH_URL=$backendUrl/health"
Write-Output "DEPLOY_SKU=$Sku"
