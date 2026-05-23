param(
    [string]$FeatureFile = "feature_list.json"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $FeatureFile)) {
    Write-Error "feature file not found: $FeatureFile"
    exit 1
}

try {
    $raw = Get-Content -Raw -Path $FeatureFile
    $json = $raw | ConvertFrom-Json
} catch {
    Write-Error "failed to parse $FeatureFile"
    exit 2
}

$pending = @($json | Where-Object { $_.passes -eq $false })
if ($pending.Count -eq 0) {
    Write-Output "ALL_FEATURES_COMPLETE"
    exit 0
}

$next = $pending[0]
$stepCount = @($next.steps).Count
Write-Output "category=$($next.category)"
Write-Output "description=$($next.description)"
Write-Output "step_count=$stepCount"
Write-Output "passes=$($next.passes)"

