@echo off
:: [ENCODING:UTF-8-CRLF-DO-NOT-CONVERT] Tianji v9.1 Launcher (Optimized v2.0)
:: 唯一启动入口 - 服务+托盘+watchdog 三合一
:: 优化点: 静默启动 + 静态ICO + 科学右键 + 注册表对齐
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "D:\元初系统\天机v9.1" 2>nul
if errorlevel 1 (
    powershell -Command "$wshell = New-Object -ComObject WScript.Shell; $wshell.Popup('天机v9.1目录不存在，请检查安装路径',10,'天机v9.1 启动失败',0x10)"
    exit /b 1
)

:: Tianji v9.1 Launcher - 唯一启动入口
:: Single process exclusive mode: service + tray + watchdog
:: 快捷方式优化: IconLocation=assets\icon.ico, WindowStyle=7(最小化)

:: [FIX-DOUBLE-CLICK] PID文件检查：如果PID文件存在且进程存活，直接退出
if exist ".daemon\tianji.pid" (
    powershell -Command "$pid_content = Get-Content '.daemon\tianji.pid' -ErrorAction SilentlyContinue; if($pid_content) { $proc = Get-Process -Id $pid_content -ErrorAction SilentlyContinue; if($proc) { exit 0 } else { exit 1 } } else { exit 1 }" >nul 2>&1
    if !errorlevel! == 0 (
        powershell -Command "$wshell = New-Object -ComObject WScript.Shell; $wshell.Popup('Tianji v9.1 is already starting...',3,'Tianji v9.1',0x40)" >nul 2>&1
        exit /b 0
    )
)

:: Exclusive check: service already running -> exit 0; not running -> exit 1
powershell -Command "$r = $null; try { $r=Invoke-RestMethod 'http://127.0.0.1:8771/api/health' -TimeoutSec 3 } catch { }; if($r -and $r.engine_ready) { $wshell = New-Object -ComObject WScript.Shell; $wshell.Popup('Tianji v9.1 is already running',5,'Tianji v9.1',0x40); exit 0 } else { exit 1 }" >nul 2>&1
if %errorlevel% == 0 exit /b 0

:: Start pythonw tray mode (静默启动 - 不弹出控制台窗口)
start "" /B "python\pythonw.exe" -X utf8 -m launcher.tianji_v91_launcher --tray

:: Notify user after 4 seconds (静默通知 - 不弹窗，仅托盘提示)
powershell -Command "Start-Sleep -Seconds 4; $r = $null; try { $r=Invoke-RestMethod 'http://127.0.0.1:8771/api/health' -TimeoutSec 5 } catch { }; if(-not $r -or -not $r.engine_ready) { $wshell = New-Object -ComObject WScript.Shell; $wshell.Popup('Tianji v9.1 is starting, please wait...',5,'Tianji v9.1',0x40) }" >nul 2>&1
:: 启动后自动退出 (托盘独立运行)
exit /b 0
