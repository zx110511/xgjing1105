@echo off
chcp 65001 >nul
cd /d "D:\元初系统\天机v9.1"

echo === 测试bat排他性检查逻辑 ===
echo.

echo [测试1] 服务未运行时:
powershell -Command "$r = $null; try { $r=Invoke-RestMethod 'http://127.0.0.1:8771/api/health' -TimeoutSec 3 } catch { }; if($r -and $r.engine_ready) { exit 0 } else { exit 1 }" >nul 2>&1
echo PowerShell 退出码: %errorlevel%
if %errorlevel% == 0 (
    echo 结果: 会执行 exit /b 0 → 不启动服务 ❌
) else (
    echo 结果: 会继续执行启动命令 → 正常 ✅
)

echo.
echo [测试2] 模拟服务已运行时:
powershell -Command "exit 0" >nul 2>&1
echo PowerShell 退出码: %errorlevel%
if %errorlevel% == 0 (
    echo 结果: 会执行 exit /b 0 → 不启动服务 (正确，因为服务已在运行)
) else (
    echo 结果: 异常
)

echo.
echo === 当前bat文件的问题 ===
echo 当前bat第12行: if %%errorlevel%% == 0 exit /b 0
echo 但powershell正常结束(即使没检测到服务)的退出码也是0
echo 所以需要让powershell在"未检测到服务"时返回非0退出码
echo.
pause
