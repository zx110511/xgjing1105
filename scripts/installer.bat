@echo off
chcp 65001 >nul 2>&1
title 天机v9.1 安装程序
color 1F

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     天机v9.1 · AI智能记忆平台           ║
echo  ║          一键安装程序                    ║
echo  ╚══════════════════════════════════════════╝
echo.

:: 检查管理员权限(用于创建快捷方式)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [提示] 正在请求管理员权限...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: 设置安装目录
set "INSTALL_DIR=D:\天机v9.1"
if exist "%~dp0payload" (
    :: 从SFX解压模式运行
    set "SOURCE_DIR=%~dp0payload"
) else if exist "%~dp0天机v9.1-独立运行包" (
    set "SOURCE_DIR=%~dp0天机v9.1-独立运行包"
) else (
    echo  [错误] 未找到安装数据!
    pause
    exit /b 1
)

echo  安装目录: %INSTALL_DIR%
echo  数据来源: %SOURCE_DIR%
echo.

:: 确认安装
set /p CONFIRM="  确认安装到 %INSTALL_DIR%? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    set /p INSTALL_DIR="  请输入安装目录: "
    if "%INSTALL_DIR%"=="" (
        echo  [错误] 安装目录不能为空!
        pause
        exit /b 1
    )
)

echo.
echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  正在安装, 请稍候...
echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

:: 创建安装目录
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: 使用robocopy复制文件(自带进度)
robocopy "%SOURCE_DIR%" "%INSTALL_DIR%" /MIR /XD __pycache__ .git /XF *.log /NFL /NDL /NJH /NJS /NP

echo.
echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  创建桌面快捷方式...
echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:: 用PowerShell创建快捷方式(兼容性最好)
powershell -NoProfile -Command ^
    "$desktop = [Environment]::GetFolderPath('Desktop');" ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$lnk = $ws.CreateShortcut(\"$desktop\天机v9.1.lnk\");" ^
    "$lnk.TargetPath = '%INSTALL_DIR%\启动天机.vbs';" ^
    "$lnk.WorkingDirectory = '%INSTALL_DIR%';" ^
    "if (Test-Path '%INSTALL_DIR%\web\tianji.exe') { $lnk.IconLocation = '%INSTALL_DIR%\web\tianji.exe,0' };" ^
    "$lnk.Description = '天机v9.1 AI智能记忆平台';" ^
    "$lnk.Save();" ^
    "$lnk2 = $ws.CreateShortcut(\"$desktop\停止天机.lnk\");" ^
    "$lnk2.TargetPath = '%INSTALL_DIR%\停止天机.vbs';" ^
    "$lnk2.WorkingDirectory = '%INSTALL_DIR%';" ^
    "if (Test-Path '%INSTALL_DIR%\web\tianji.exe') { $lnk2.IconLocation = '%INSTALL_DIR%\web\tianji.exe,0' };" ^
    "$lnk2.Description = '停止天机服务';" ^
    "$lnk2.Save();"

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║        天机v9.1 安装完成!               ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  安装目录: %INSTALL_DIR%
echo  桌面图标: 天机v9.1 / 停止天机
echo.
echo  使用方法: 双击桌面"天机v9.1"图标即可启动
echo.

set /p LAUNCH="  是否立即启动天机? (Y/N): "
if /i "%LAUNCH%"=="Y" (
    cscript //nologo "%INSTALL_DIR%\启动天机.vbs"
)

exit /b 0
