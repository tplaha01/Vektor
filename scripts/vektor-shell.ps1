param(
    [ValidateSet("up", "down", "status", "logs")]
    [string]$Action = "up",
    [switch]$IncludeLanding,
    [switch]$IncludeBlog,
    [ValidateSet("backend", "frontend", "landing", "blog")]
    [string]$Service = "backend",
    [switch]$Follow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunDir = Join-Path $RepoRoot ".run"
$LogDir = Join-Path $RunDir "logs"
$ManifestPath = Join-Path $RunDir "vektor-services.json"

function Ensure-Dirs {
    if (-not (Test-Path $RunDir)) {
        New-Item -ItemType Directory -Path $RunDir | Out-Null
    }
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir | Out-Null
    }
}

function Get-ServiceDefinitions {
    $defs = @(
        @{
            name = "backend"
            port = 8000
            cwd = Join-Path $RepoRoot "backend"
            file = "py"
            args = @("-3", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")
            url = "http://127.0.0.1:8000/health"
        },
        @{
            name = "frontend"
            port = 9000
            cwd = Join-Path $RepoRoot "frontend"
            file = "npm.cmd"
            args = @("run", "dev")
            url = "http://127.0.0.1:9000"
        }
    )

    if ($IncludeLanding) {
        $defs += @{
            name = "landing"
            port = 3000
            cwd = Join-Path $RepoRoot "landing-next"
            file = "npm.cmd"
            args = @("run", "dev")
            url = "http://127.0.0.1:3000"
        }
    }

    if ($IncludeBlog) {
        $defs += @{
            name = "blog"
            port = 3001
            cwd = Join-Path $RepoRoot "blog-next"
            file = "npm.cmd"
            args = @("run", "dev", "--", "--port", "3001")
            url = "http://127.0.0.1:3001"
        }
    }

    return $defs
}

function Load-Manifest {
    if (-not (Test-Path $ManifestPath)) {
        return @()
    }
    $raw = Get-Content $ManifestPath -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return @()
    }
    try {
        $json = $raw | ConvertFrom-Json
        if ($null -eq $json) {
            return @()
        }
        if ($json -is [System.Array]) {
            return @($json)
        }
        return @($json)
    } catch {
        return @()
    }
}

function Save-Manifest([array]$rows) {
    $rows | ConvertTo-Json -Depth 6 | Set-Content -Path $ManifestPath -Encoding UTF8
}

function Get-ListenersByPorts([int[]]$ports) {
    $list = @()
    foreach ($p in $ports) {
        $list += Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue
    }
    return $list
}

function Stop-VektorServices {
    $manifestRows = Load-Manifest
    foreach ($row in $manifestRows) {
        $pidVal = 0
        try {
            $pidVal = [int]$row.pid
        } catch {
            $pidVal = 0
        }
        if ($pidVal -gt 0) {
            Stop-Process -Id $pidVal -Force -ErrorAction SilentlyContinue
        }
    }

    $ports = @(8000, 9000, 3000, 3001, 5173, 5174)
    $listeners = Get-ListenersByPorts -ports $ports
    foreach ($conn in $listeners) {
        if ($conn.OwningProcess -gt 0) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }

    Save-Manifest -rows @()
    Write-Host "Vektor services stopped."
}

function Start-ServiceRow($svc) {
    $stdout = Join-Path $LogDir "$($svc.name).out.log"
    $stderr = Join-Path $LogDir "$($svc.name).err.log"
    if (-not (Test-Path $stdout)) { New-Item -ItemType File -Path $stdout | Out-Null }
    if (-not (Test-Path $stderr)) { New-Item -ItemType File -Path $stderr | Out-Null }

    $existing = Get-NetTCPConnection -State Listen -LocalPort $svc.port -ErrorAction SilentlyContinue
    if ($existing) {
        foreach ($conn in $existing) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 250
    }

    $proc = Start-Process `
        -FilePath $svc.file `
        -ArgumentList $svc.args `
        -WorkingDirectory $svc.cwd `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    $listenConn = $null
    for ($i = 0; $i -lt 20; $i++) {
        $candidate = Get-NetTCPConnection -State Listen -LocalPort $svc.port -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($candidate) {
            $listenConn = $candidate
            break
        }
        Start-Sleep -Milliseconds 300
    }
    $listening = $null -ne $listenConn
    $actualPid = if ($listenConn) { [int]$listenConn.OwningProcess } else { [int]$proc.Id }
    return @{
        name = $svc.name
        pid = $actualPid
        port = $svc.port
        cwd = $svc.cwd
        url = $svc.url
        state = if ($listening) { "listening" } else { "starting" }
        stdout = $stdout
        stderr = $stderr
        started_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    }
}

function Show-Status {
    $manifestRows = Load-Manifest
    if ($manifestRows.Count -eq 0) {
        Write-Host "No Vektor services recorded in manifest."
        return
    }

    $rows = @()
    foreach ($row in $manifestRows) {
        $pidVal = 0
        try { $pidVal = [int]$row.pid } catch { $pidVal = 0 }
        $listener = Get-NetTCPConnection -State Listen -LocalPort ([int]$row.port) -ErrorAction SilentlyContinue | Select-Object -First 1
        $activePid = if ($listener) { [int]$listener.OwningProcess } else { $pidVal }
        $proc = $null
        if ($activePid -gt 0) {
            $proc = Get-Process -Id $activePid -ErrorAction SilentlyContinue
        }
        $listening = [bool]$listener
        $rows += [PSCustomObject]@{
            Service = $row.name
            PID = if ($proc) { $activePid } else { "-" }
            Port = $row.port
            State = if ($proc -and $listening) { "running" } elseif ($proc) { "process-only" } else { "stopped" }
            URL = $row.url
            Stdout = $row.stdout
            Stderr = $row.stderr
        }
    }
    $rows | Format-Table -AutoSize
}

Ensure-Dirs

switch ($Action) {
    "down" {
        Stop-VektorServices
        break
    }
    "status" {
        Show-Status
        break
    }
    "logs" {
        $manifestRows = Load-Manifest
        $target = $manifestRows | Where-Object { $_.name -eq $Service } | Select-Object -First 1
        if (-not $target) {
            throw "Service '$Service' not found in manifest."
        }
        if ($Follow) {
            Get-Content $target.stdout -Tail 120 -Wait
        } else {
            Get-Content $target.stdout -Tail 120
        }
        break
    }
    "up" {
        Stop-VektorServices
        $defs = Get-ServiceDefinitions
        $rows = @()
        foreach ($svc in $defs) {
            $rows += Start-ServiceRow -svc $svc
        }
        Save-Manifest -rows $rows
        Write-Host ""
        Write-Host "Vektor local stack started."
        Show-Status
        Write-Host ""
        Write-Host "Open URLs:"
        foreach ($row in $rows) {
            Write-Host ("- {0}: {1}" -f $row.name, $row.url)
        }
        break
    }
}
