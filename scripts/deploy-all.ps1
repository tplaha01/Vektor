param(
  [Parameter(Mandatory = $true)]
  [string]$AzureAppName,
  [string]$AzureResourceGroup = "vektor-rg",
  [string]$AzureLocation = "eastus",
  [ValidateSet("F1", "B1", "B2", "B3", "S1", "P1v3")]
  [string]$AzureSku = "F1",
  [string]$AzureSubscriptionId = "",
  [string]$FrontendApiKey = "dev-api-key"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot

Write-Output "Deploying backend to Azure..."
$backendOutput = & "$scriptRoot\deploy-azure-backend.ps1" `
  -AppName $AzureAppName `
  -ResourceGroup $AzureResourceGroup `
  -Location $AzureLocation `
  -Sku $AzureSku `
  -SubscriptionId $AzureSubscriptionId

$backendUrlLine = $backendOutput | Where-Object { $_ -like "BACKEND_URL=*" } | Select-Object -Last 1
if (-not $backendUrlLine) {
  throw "Backend deployment did not return BACKEND_URL."
}
$backendUrl = $backendUrlLine.Split("=", 2)[1]
Write-Output "Backend deployed: $backendUrl"

Write-Output "Deploying frontend to Vercel..."
$frontendOutput = & "$scriptRoot\deploy-vercel-frontend.ps1" `
  -BackendUrl $backendUrl `
  -FrontendApiKey $FrontendApiKey

$frontendUrlLine = $frontendOutput | Where-Object { $_ -like "FRONTEND_URL=*" } | Select-Object -Last 1
if (-not $frontendUrlLine) {
  throw "Frontend deployment did not return FRONTEND_URL."
}
$frontendUrl = $frontendUrlLine.Split("=", 2)[1]
Write-Output "Frontend deployed: $frontendUrl"

Write-Output "Updating backend CORS FRONTEND_URL to deployed frontend..."
& "$scriptRoot\deploy-azure-backend.ps1" `
  -AppName $AzureAppName `
  -ResourceGroup $AzureResourceGroup `
  -Location $AzureLocation `
  -Sku $AzureSku `
  -SubscriptionId $AzureSubscriptionId `
  -FrontendUrl $frontendUrl `
  -SkipDeployCode

Write-Output ""
Write-Output "Deployment complete."
Write-Output "BACKEND_URL=$backendUrl"
Write-Output "FRONTEND_URL=$frontendUrl"
