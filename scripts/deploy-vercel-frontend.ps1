param(
  [Parameter(Mandatory = $true)]
  [string]$BackendUrl,
  [string]$FrontendApiKey = "dev-api-key",
  [string]$FrontendDir = "frontend"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command vercel -ErrorAction SilentlyContinue)) {
  throw "Vercel CLI not found. Install with: npm i -g vercel"
}

vercel whoami *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Not logged into Vercel. Run: vercel login"
}

if (-not $BackendUrl.StartsWith("https://")) {
  throw "BackendUrl must be an https URL (example: https://vektor-backend.azurewebsites.net)."
}

Push-Location $FrontendDir
try {
  $deployOutput = & vercel deploy `
    --prod `
    --yes `
    --build-env "VITE_BACKEND_URL=$BackendUrl" `
    --build-env "VITE_API_KEY=$FrontendApiKey" 2>&1
  if ($LASTEXITCODE -ne 0) {
    $deployOutput | Write-Output
    throw "Vercel deploy failed."
  }

  $deployText = ($deployOutput -join "`n")
  $match = [regex]::Matches($deployText, "https://[a-zA-Z0-9\-\.]+\.vercel\.app")
  if ($match.Count -eq 0) {
    $deployOutput | Write-Output
    throw "Could not parse deployment URL from Vercel output."
  }

  $frontendUrl = $match[$match.Count - 1].Value
  Write-Output "FRONTEND_URL=$frontendUrl"
}
finally {
  Pop-Location
}
