<#
.SYNOPSIS
    Tianji v9.1 Windows native background launcher (robust edition)
.DESCRIPTION
    Pure-ASCII script (PowerShell 5.1 ANSI-reads .ps1). Chinese text is built via [char] code points.
    Flow: check python -> free port -> set env -> start uvicorn hidden -> wait health -> report.
    Top-level try/catch guarantees any error is logged and the script exits without hanging.
#>

# ============ Pure-ASCII Chinese fragments (char code points) ============
$S_TIANJI = [char]0x5929 + [char]0x673A                                  # Tianji
$S_HEALTH = [char]0x5065 + [char]0x5EB7 + [char]0x7AEF + [char]0x70B9    # health endpoint
$S_START = [char]0x542F + [char]0x52A8                                  # start
$S_SUCCESS = [char]0x6210 + [char]0x529F                                  # success
$S_FAIL = [char]0x5931 + [char]0x8D25                                  # fail
$S_PORT = [char]0x7AEF + [char]0x53E3                                  # port
$S_LOGW = [char]0x65E5 + [char]0x5FD7                                  # log
$S_ERRW = [char]0x9519 + [char]0x8BEF                                  # error
$S_PROC = [char]0x8FDB + [char]0x7A0B                                  # process
$S_SVC = [char]0x670D + [char]0x52A1                                  # service

# ============ Paths and port ============
$Root = "D:\" + [char]0x5143 + [char]0x521D + [char]0x7CFB + [char]0x7EDF + "\" + [char]0x5929 + [char]0x673A + "v9.1"
$Python = Join-Path $Root "python\python.exe"
$LogDir = Join-Path $Root "logs"
$DaemonDir = Join-Path $Root ".daemon"
$LogFile = Join-Path $LogDir "tianji-server.log"
$ErrFile = Join-Path $LogDir "tianji-server.err.log"
$LaunchLog = Join-Path $LogDir "tianji-launcher.log"
$ErrorLog = Join-Path $LogDir "tianji-launcher.err.log"
$PidFile = Join-Path $DaemonDir "tianji.pid"
$Port = 8771
$HealthUrl = "http://localhost:$Port/api/health"

# Ensure log dir exists early so Log-Message can write
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

# ============ Unified output function ============
function Log-Message {
    param([string]$Level, [string]$Message)
    $ts = Get-Date -Format "HH:mm:ss"
    $prefix = "[$ts][$Level]"
    switch ($Level) {
        "ERROR" { Write-Host "$prefix $Message" -ForegroundColor Red }
        "WARN" { Write-Host "$prefix $Message" -ForegroundColor Yellow }
        "OK" { Write-Host "$prefix $Message" -ForegroundColor Green }
        default { Write-Host "$prefix $Message" }
    }
    Add-Content -Path $LaunchLog -Value "$prefix $Message" -ErrorAction SilentlyContinue
}

# ============ Main logic wrapped in top-level try/catch ============
try {
    $ErrorActionPreference = "Stop"

    Log-Message "INFO" "=================================================="
    Log-Message "INFO" ($S_TIANJI + " v9.1 native background " + $S_START + " (" + $S_PORT + " $Port)")
    Log-Message "INFO" "=================================================="

    # ---- Step 1/6: check embedded Python ----
    Log-Message "INFO" "[1/6] Checking embedded Python ..."
    if (-not (Test-Path $Python)) {
        throw "Embedded Python not found: $Python"
    }
    if (-not (Test-Path $DaemonDir)) { New-Item -ItemType Directory -Path $DaemonDir -Force | Out-Null }
    Log-Message "OK" "    Python OK: $Python"

    # ---- Step 2/6: free the port ----
    Log-Message "INFO" ("[2/6] Checking " + $S_PORT + " $Port ...")
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($conns) {
            $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($p in $pids) {
                Log-Message "WARN" ("    " + $S_PORT + " busy, killing " + $S_PROC + " PID=$p")
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Seconds 1
        }
        else {
            Log-Message "OK" ("    " + $S_PORT + " is free")
        }
    }
    catch {
        Log-Message "WARN" ("    " + $S_PORT + " check skipped: $($_.Exception.Message)")
    }

    # Stop old instance from PID file if still alive
    if (Test-Path $PidFile) {
        $oldPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
            Log-Message "WARN" ("    Cleaning old instance " + $S_PROC + " PID=$oldPid")
            Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }

    # ---- Step 3/6: set environment variables ----
    Log-Message "INFO" "[3/6] Setting environment variables ..."
    $env:AI_MEMORY_PORT = "$Port"
    $env:AI_MEMORY_ROOT = $Root
    $env:AI_MEMORY_DB = Join-Path $Root "data\icme.db"
    $env:TIANJI_V91_PROTOCOL_MODE = "true"
    $env:TIANJI_V91_EVENT_WIRING = "true"
    $env:PYTHONPATH = $Root
    $env:PYTHONIOENCODING = "utf-8"
    Log-Message "OK" "    Environment variables set"

    # ---- Step 4/6: start uvicorn in background ----
    Log-Message "INFO" ("[4/6] " + $S_START + " uvicorn (server.main:app) ...")
    $uvArgs = @(
        "-X", "utf8",
        "-m", "uvicorn",
        "server.main:app",
        "--host", "0.0.0.0",
        "--port", "$Port",
        "--workers", "1"
    )

    $proc = Start-Process -FilePath $Python `
        -ArgumentList $uvArgs `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError $ErrFile `
        -PassThru

    if (-not $proc) { throw "Failed to start uvicorn process" }
    $proc.Id | Out-File -FilePath $PidFile -Encoding ascii -Force
    Log-Message "OK" ("    " + $S_START + " " + $S_SUCCESS + ", " + $S_PROC + " PID=$($proc.Id), PID file: $PidFile")

    # ---- Step 5/6: wait and verify health (max 120s, retry every 5s) ----
    Log-Message "INFO" "[5/6] Waiting for health check (cold start may take ~98s, max 120s) ..."
    $healthy = $false
    $resp = $null
    for ($i = 1; $i -le 24; $i++) {
        Start-Sleep -Seconds 5
        if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
            Log-Message "ERROR" ("    " + $S_PROC + " exited unexpectedly, see " + $S_ERRW + " " + $S_LOGW + ": $ErrFile")
            break
        }
        try {
            $resp = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 4 -ErrorAction Stop
            if ($resp.status -eq "healthy") {
                $healthy = $true
                break
            }
        }
        catch {
            Log-Message "INFO" "    waiting... ($i/24)"
        }
    }

    # ---- Step 6/6: report result ----
    Log-Message "INFO" "[6/6] Reporting result ..."
    Log-Message "INFO" "=================================================="
    if ($healthy) {
        Log-Message "OK" ($S_TIANJI + " v9.1 " + $S_START + " " + $S_SUCCESS + " (" + $S_PROC + " PID=$($proc.Id))")
        Log-Message "OK" ("    status        = " + $resp.status)
        Log-Message "OK" ("    version       = " + $resp.version)
        Log-Message "OK" ("    protocol_mode = " + $resp.protocol_mode)
        Log-Message "OK" ("    event_wiring  = " + $resp.event_wiring)
        Log-Message "OK" ($S_HEALTH + ": " + $HealthUrl)
        Log-Message "OK" (($S_SVC) + " " + $S_LOGW + ": $LogFile")
        Log-Message "INFO" "=================================================="
        exit 0
    }
    else {
        Log-Message "ERROR" ($S_TIANJI + " v9.1 " + $S_START + " " + $S_FAIL + " (health check not passed)")
        Log-Message "ERROR" ($S_HEALTH + ": " + $HealthUrl)
        Log-Message "ERROR" ($S_SVC + " " + $S_ERRW + " " + $S_LOGW + ": $ErrFile")
        Log-Message "ERROR" ("launcher " + $S_LOGW + ": $LaunchLog")
        Log-Message "INFO" "=================================================="
        exit 1
    }
}
catch {
    # Top-level catch: log to console + launcher log + dedicated error log, then exit(1) without hanging
    $msg = $_.Exception.Message
    try { Log-Message "ERROR" ("FATAL: " + $msg) } catch { Write-Host "[ERROR] FATAL: $msg" -ForegroundColor Red }
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$stamp] FATAL: $msg" | Out-File -Append -FilePath $ErrorLog -Encoding utf8 -ErrorAction SilentlyContinue
    $_ | Out-File -Append -FilePath $ErrorLog -Encoding utf8 -ErrorAction SilentlyContinue
    exit 1
}
