# Tianji v9.1 verification helper (pure ASCII)
$Port = 8778
Write-Host "---PROCESS (PID file)---"
$PidFile = "D:\" + [char]0x5143 + [char]0x521D + [char]0x7CFB + [char]0x7EDF + "\" + [char]0x5929 + [char]0x673A + "v9.1\.daemon\tianji.pid"
if (Test-Path $PidFile) {
    $procId = Get-Content $PidFile | Select-Object -First 1
    Write-Host "PID file value: $procId"
    $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($p) { Write-Host "Process ALIVE: $($p.Id) $($p.ProcessName)" } else { Write-Host "Process NOT running" }
}
else {
    Write-Host "PID file missing"
}

Write-Host "---PORT $Port---"
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conn) { $conn | Select-Object LocalAddress, LocalPort, State, OwningProcess | Format-Table | Out-String | Write-Host } else { Write-Host "No listener on $Port" }

Write-Host "---HEALTH---"
try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 5
    Write-Host "status        = $($r.status)"
    Write-Host "version       = $($r.version)"
    Write-Host "protocol_mode = $($r.protocol_mode)"
    Write-Host "event_wiring  = $($r.event_wiring)"
    Write-Host "uptime_sec    = $($r.uptime_seconds)"
}
catch {
    Write-Host ("HEALTH ERROR: " + $_.Exception.Message)
}
