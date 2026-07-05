<#
.SYNOPSIS
    Tianji v9.1 stop script (robust edition)
.DESCRIPTION
    Pure-ASCII script (PowerShell 5.1 ANSI-reads .ps1). Chinese text is built via [char] code points.
    Flow: read PID file -> stop process -> clean PID file -> free residual port listeners -> confirm port released.
    Top-level try/catch guarantees any error is logged and the script exits without hanging.
#>

# ============ Pure-ASCII Chinese fragments (char code points) ============
$S_TIANJI = [char]0x5929 + [char]0x673A                  # Tianji
$S_STOP = [char]0x505C + [char]0x6B62                  # stop
$S_SUCCESS = [char]0x6210 + [char]0x529F                  # success
$S_FAIL = [char]0x5931 + [char]0x8D25                  # fail
$S_PORT = [char]0x7AEF + [char]0x53E3                  # port
$S_LOGW = [char]0x65E5 + [char]0x5FD7                  # log
$S_ERRW = [char]0x9519 + [char]0x8BEF                  # error
$S_PROC = [char]0x8FDB + [char]0x7A0B                  # process

# ============ Paths and port ============
$Root = "D:\" + [char]0x5143 + [char]0x521D + [char]0x7CFB + [char]0x7EDF + "\" + [char]0x5929 + [char]0x673A + "v9.1"
$LogDir = Join-Path $Root "logs"
$DaemonDir = Join-Path $Root ".daemon"
$PidFile = Join-Path $DaemonDir "tianji.pid"
$LaunchLog = Join-Path $LogDir "tianji-launcher.log"
$ErrorLog = Join-Path $LogDir "tianji-launcher.err.log"
$Port = 8778

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
    Log-Message "INFO" "=================================================="
    Log-Message "INFO" ($S_TIANJI + " v9.1 " + $S_STOP)
    Log-Message "INFO" "=================================================="

    $stopped = $false

    # ---- Stop by PID file ----
    if (Test-Path $PidFile) {
        $procId = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($procId) {
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($p) {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Log-Message "OK" ($S_STOP + " " + $S_PROC + " PID=$procId")
                $stopped = $true
            }
            else {
                Log-Message "WARN" ($S_PROC + " PID=$procId not found")
            }
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Log-Message "INFO" "PID file cleaned"
    }
    else {
        Log-Message "WARN" "PID file not found: $PidFile"
    }

    # ---- Fallback: free residual port listeners ----
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pid2 in $pids) {
            Stop-Process -Id $pid2 -Force -ErrorAction SilentlyContinue
            Log-Message "OK" ("Freed residual " + $S_PORT + " $Port " + $S_PROC + " PID=$pid2")
            $stopped = $true
        }
        Start-Sleep -Seconds 1
    }

    # ---- Confirm port released ----
    $still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($still) {
        Log-Message "ERROR" ($S_PORT + " $Port still in use after " + $S_STOP)
        Log-Message "INFO" "=================================================="
        exit 1
    }
    else {
        Log-Message "OK" ($S_PORT + " $Port released")
    }

    Log-Message "INFO" "=================================================="
    if ($stopped) {
        Log-Message "OK" ($S_TIANJI + " v9.1 " + $S_STOP + " " + $S_SUCCESS)
    }
    else {
        Log-Message "WARN" ("No running " + $S_TIANJI + " v9.1 instance found")
    }
    Log-Message "INFO" "=================================================="
    exit 0
}
catch {
    $msg = $_.Exception.Message
    try { Log-Message "ERROR" ("FATAL: " + $msg) } catch { Write-Host "[ERROR] FATAL: $msg" -ForegroundColor Red }
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$stamp] FATAL: $msg" | Out-File -Append -FilePath $ErrorLog -Encoding utf8 -ErrorAction SilentlyContinue
    $_ | Out-File -Append -FilePath $ErrorLog -Encoding utf8 -ErrorAction SilentlyContinue
    exit 1
}
