# Deploy Viktor (Vercel + Azure)

This deploys:
- `frontend/` -> Vercel (production)
- `backend/` -> Azure App Service (Linux, Python 3.11)

## 1) Prerequisites

From repo root:

```powershell
npm i -g vercel
py -3 -m pip install --user azure-cli
```

If `az` is not on PATH (Windows), restart terminal.  
If still missing, add:

`C:\Users\<you>\AppData\Roaming\Python\Python314\Scripts`

## 2) Login

```powershell
vercel login
az login --use-device-code
```

If `az` is not on PATH on Windows, use:

```powershell
py -3 -m azure.cli login --use-device-code
```

Optional (if you have multiple Azure subscriptions):

```powershell
az account set --subscription "<SUBSCRIPTION_ID>"
```

## 3) One-command deploy

```powershell
.\scripts\deploy-all.ps1 -AzureAppName "<globally-unique-app-name>" -AzureSku F1
```

Example:

```powershell
.\scripts\deploy-all.ps1 -AzureAppName "vektor-backend-prod-001" -AzureSku F1
```

This prints:
- `BACKEND_URL=...`
- `FRONTEND_URL=...`

The script also updates backend `FRONTEND_URL` app setting for CORS after frontend deploy.

## 4) Individual deploys

Backend only:

```powershell
.\scripts\deploy-azure-backend.ps1 -AppName "<globally-unique-app-name>" -Sku F1
```

Frontend only:

```powershell
.\scripts\deploy-vercel-frontend.ps1 -BackendUrl "https://<app>.azurewebsites.net"
```

## 5) Post-deploy checks

```powershell
# Backend
Invoke-RestMethod https://<app>.azurewebsites.net/health

# Frontend
# Open FRONTEND_URL in browser and verify Admin page can load backend
```

## Notes

- Backend deploy reads keys from `backend/.env` and pushes allowed settings to Azure App Service.
- Safety defaults are enforced on cloud deploy:
  - `BROKER=paper`
  - `AUTO_TRADING_ENABLED=false`
  - `ENV=prod`

## Azure login troubleshooting (`{tenantid}` / `ConnectionResetError(10054)`)

If Azure CLI login fails with:
- `Unable to get authority configuration ... /{tenantid}/...`
- or intermittent `ConnectionResetError(10054)`

Run a clean Azure CLI session (PowerShell):

```powershell
# In the same terminal where you will deploy:
$env:AZURE_CONFIG_DIR = "$PWD\\.azcfg"
New-Item -ItemType Directory -Force -Path $env:AZURE_CONFIG_DIR | Out-Null

# Clear bad tenant env vars if present
Remove-Item Env:AZURE_TENANT_ID -ErrorAction SilentlyContinue
Remove-Item Env:AZURE_TENANT -ErrorAction SilentlyContinue
Remove-Item Env:ARM_TENANT_ID -ErrorAction SilentlyContinue
Remove-Item Env:AZURE_DEFAULTS_TENANT -ErrorAction SilentlyContinue

# Ensure public cloud
py -3 -m azure.cli cloud set -n AzureCloud

# IMPORTANT:
# Do not use pseudo tenants like "common" or "organizations" with Azure CLI 2.85 on this setup.
# They can resolve to issuer ".../{tenantid}/..." and fail.
# Use either:
# 1) no --tenant at all, or
# 2) your real tenant GUID.
py -3 -m azure.cli login --use-device-code --allow-no-subscriptions
py -3 -m azure.cli account list --all -o table
```

If this works, run deploy commands in the same terminal so they reuse the clean config dir.

If it still tries `/{tenantid}/...`, check VS Code PowerShell profile scripts for hardcoded tenant placeholders:

```powershell
$profiles = @($PROFILE.CurrentUserCurrentHost, $PROFILE.CurrentUserAllHosts) | Where-Object { Test-Path $_ }
if ($profiles.Count -gt 0) {
  Select-String -Path $profiles -Pattern "tenantid|AZURE_TENANT|ARM_TENANT|az login" -SimpleMatch
}
```
