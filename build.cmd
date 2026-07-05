@echo off
chcp 65001 > nul
set CARGO_PATH=C:\Users\Administrator\.rustup\toolchains\stable-x86_64-pc-windows-gnu\bin\cargo.exe
set TAURI_DIR=C:\tianji-build\web\src-tauri

echo [INFO] Building Tauri with GNU toolchain...
echo [INFO] Cargo: %CARGO_PATH%
echo [INFO] Dir: %TAURI_DIR%

if exist "%TAURI_DIR%\target" rmdir /s /q "%TAURI_DIR%\target"

cd /d "%TAURI_DIR%"
"%CARGO_PATH%" build --release

if %ERRORLEVEL% equ 0 (
    echo [OK] Build successful!
    if exist "%TAURI_DIR%\target\release\tianji.exe" (
        echo [OK] Output: tianji.exe
    )
) else (
    echo [ERROR] Build failed with code %ERRORLEVEL%
)
