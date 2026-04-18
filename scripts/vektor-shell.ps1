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

function Test-IsAdmin {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

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

function Get-ListenerPids([int]$port) {
    $rows = netstat -ano -p tcp | Where-Object { $_ -match "LISTENING" -and $_ -match ":$port(\s|$)" }
    if (-not $rows) {
        return @()
    }
    $pids = @()
    foreach ($row in $rows) {
        $text = ($row | Out-String).Trim()
        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }
        $parts = $text -split "\s+"
        if ($parts.Count -lt 5) {
            continue
        }
        if ($parts[3] -ne "LISTENING") {
            continue
        }
        $local = $parts[1]
        $pidText = $parts[4]
        if ($local -match ":(\d+)$" -and [int]$Matches[1] -eq $port) {
            $pidVal = 0
            if ([int]::TryParse($pidText, [ref]$pidVal) -and $pidVal -gt 0) {
                $pids += $pidVal
            }
        }
    }
    return @($pids | Sort-Object -Unique)
}

function Stop-PortListeners([int]$port, [int]$attempts = 3) {
    for ($i = 0; $i -lt $attempts; $i++) {
        $pids = Get-ListenerPids -port $port
        if (@($pids).Count -eq 0) {
            return @()
        }
        foreach ($procId in $pids) {
            try {
                Stop-Process -Id $procId -Force -ErrorAction Stop
            } catch {
                # Continue trying other PIDs; unresolved ones are returned to caller.
            }
        }
        Start-Sleep -Milliseconds 350
    }
    return Get-ListenerPids -port $port
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
    $stale = @()
    foreach ($p in $ports) {
        $remaining = Stop-PortListeners -port $p
        if (@($remaining).Count -gt 0) {
            $stale += @(
                [PSCustomObject]@{
                    Port = $p
                    PID = ($remaining -join ",")
                }
            )
        }
    }

    Save-Manifest -rows @()
    if ($stale.Count -gt 0) {
        Write-Warning "Some listeners could not be stopped. Run PowerShell as Administrator and terminate these PIDs:"
        if (-not (Test-IsAdmin)) {
            Write-Warning "Current shell is not elevated. Open 'Windows PowerShell (Administrator)' and retry."
        }
        $stale | Format-Table -AutoSize | Out-Host
    } else {
        Write-Host "Vektor services stopped."
    }
}

function Start-ServiceRow($svc) {
    $stdout = Join-Path $LogDir "$($svc.name).out.log"
    $stderr = Join-Path $LogDir "$($svc.name).err.log"
    if (-not (Test-Path $stdout)) { New-Item -ItemType File -Path $stdout | Out-Null }
    if (-not (Test-Path $stderr)) { New-Item -ItemType File -Path $stderr | Out-Null }

    $baselinePids = @(Get-ListenerPids -port $svc.port)
    $remaining = Stop-PortListeners -port $svc.port
    if (@($remaining).Count -gt 0) {
        if (-not (Test-IsAdmin)) {
            throw "Port $($svc.port) is still in use by PID(s): $($remaining -join ', '). Current shell is not elevated. Open PowerShell as Administrator, stop those processes, then retry."
        }
        throw "Port $($svc.port) is still in use by PID(s): $($remaining -join ', '). Start PowerShell as Administrator, stop those processes, then retry."
    }

    $proc = Start-Process `
        -FilePath $svc.file `
        -ArgumentList $svc.args `
        -WorkingDirectory $svc.cwd `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    $listenPid = 0
    for ($i = 0; $i -lt 20; $i++) {
        $currentPids = @(Get-ListenerPids -port $svc.port)
        $newPids = @($currentPids | Where-Object { $_ -notin $baselinePids })
        if ($newPids.Count -gt 0) {
            $listenPid = [int]$newPids[0]
            break
        }
        if ($currentPids -contains [int]$proc.Id) {
            $listenPid = [int]$proc.Id
            break
        }
        $stillRunning = $null -ne (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)
        if (-not $stillRunning) {
            break
        }
        Start-Sleep -Milliseconds 300
    }
    $listening = $listenPid -gt 0
    $actualPid = if ($listenPid -gt 0) { $listenPid } else { [int]$proc.Id }
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
        $listenerPids = @(Get-ListenerPids -port ([int]$row.port))
        $activePid = if ($listenerPids.Count -gt 0) { [int]$listenerPids[0] } else { $pidVal }
        $proc = $null
        if ($activePid -gt 0) {
            $proc = Get-Process -Id $activePid -ErrorAction SilentlyContinue
        }
        $listening = $listenerPids.Count -gt 0
        $rows += [PSCustomObject]@{
            Service = $row.name
            PID = if ($activePid -gt 0) { $activePid } else { "-" }
            Port = $row.port
            State = if ($listening) { "running" } elseif ($proc) { "process-only" } else { "stopped" }
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
