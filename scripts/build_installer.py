#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
天机v9.1 安装包生成器
=====================
使用7-Zip创建自解压.exe安装程序
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# 强制GBK输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="gbk", errors="replace")
        sys.stderr.reconfigure(encoding="gbk", errors="replace")
    except Exception:
        pass

SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"
RELEASE_DIR = Path(r"D:\元初系统\天机v9.1\release\天机v9.1-全量发布包")
OUTPUT_DIR = Path(r"D:\元初系统\天机v9.1\天机v9.1-发布仓库\一键安装包")
SCRIPTS_DIR = Path(r"D:\元初系统\天机v9.1\scripts")
TEMP_DIR = Path(r"D:\元初系统\天机v9.1\release\_sfx_temp")


def main():
    print("=" * 50)
    print("  天机v9.1 安装包生成器")
    print("=" * 50)

    # 1. 检查7-Zip
    if not Path(SEVEN_ZIP).exists():
        print("[ERROR] 7-Zip未安装!")
        sys.exit(1)
    print(f"[OK] 7-Zip: {SEVEN_ZIP}")

    # 2. 检查发布包
    if not RELEASE_DIR.exists():
        print(f"[ERROR] 发布包目录不存在: {RELEASE_DIR}")
        sys.exit(1)
    print(f"[OK] 发布包: {RELEASE_DIR}")

    # 3. 创建临时目录
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    payload_dir = TEMP_DIR / "payload"
    payload_dir.mkdir()

    # 4. 复制安装脚本
    installer_bat = SCRIPTS_DIR / "installer.bat"
    if installer_bat.exists():
        shutil.copy2(str(installer_bat), str(TEMP_DIR / "installer.bat"))
        print("[OK] 安装脚本已复制")

    # 5. 复制发布包到payload
    print("[INFO] 复制发布包...")
    result = subprocess.run([
        "robocopy",
        str(RELEASE_DIR), str(payload_dir),
        "/MIR", "/XD", "__pycache__", ".git",
        "/XF", "*.log",
        "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
    ], capture_output=True, text=True)
    print(f"[OK] 发布包已复制")

    # 6. 创建7z压缩包
    archive_path = TEMP_DIR / "archive.7z"
    print("[INFO] 压缩文件(这可能需要几分钟)...")
    result = subprocess.run([
        SEVEN_ZIP, "a", "-t7z", "-mx=5",
        str(archive_path),
        str(payload_dir),
        str(TEMP_DIR / "installer.bat"),
        "-y"
    ], capture_output=True, text=True)
    if result.returncode not in (0, 1):
        print(f"[ERROR] 压缩失败: {result.stderr}")
        sys.exit(1)

    archive_size = archive_path.stat().st_size / (1024 * 1024)
    print(f"[OK] 压缩包: {archive_size:.1f}MB")

    # 7. 检查SFX模块
    sfx_module = None
    for candidate in [
        r"C:\Program Files\7-Zip\7z.sfx",
        r"C:\Program Files\7-Zip\7zCon.sfx",
    ]:
        if Path(candidate).exists():
            sfx_module = candidate
            break

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if sfx_module:
        # 创建SFX配置
        config_content = """;!@Install@!UTF-8!
Title=天机v9.1 安装程序
BeginPrompt=即将安装 天机v9.1 AI智能记忆平台\\n\\n点击确定开始安装
RunProgram="cmd.exe /c installer.bat"
;!@InstallEnd@!
"""
        config_path = TEMP_DIR / "config.txt"
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)

        # 合并: SFX模块 + 配置 + 压缩包 = 自解压EXE
        exe_output = OUTPUT_DIR / "天机v9.1_安装程序.exe"
        print("[INFO] 生成自解压EXE...")

        with open(sfx_module, "rb") as sf:
            sfx_bytes = sf.read()
        with open(config_path, "rb") as cf:
            config_bytes = cf.read()
        with open(archive_path, "rb") as af:
            archive_bytes = af.read()

        with open(exe_output, "wb") as out:
            out.write(sfx_bytes)
            out.write(config_bytes)
            out.write(archive_bytes)

        exe_size = exe_output.stat().st_size / (1024 * 1024)
        print(f"[OK] 自解压EXE: {exe_output} ({exe_size:.1f}MB)")
    else:
        # 没有SFX模块, 创建7z压缩包+安装脚本
        print("[WARN] 未找到7z.sfx, 创建7z压缩包+安装脚本")
        final_7z = OUTPUT_DIR / "天机v9.1_安装包.7z"
        shutil.copy2(str(archive_path), str(final_7z))

        # 复制安装脚本
        shutil.copy2(str(TEMP_DIR / "installer.bat"), str(OUTPUT_DIR / "安装.bat"))

        size_mb = final_7z.stat().st_size / (1024 * 1024)
        print(f"[OK] 7z压缩包: {final_7z} ({size_mb:.1f}MB)")

    # 8. 清理
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    print()
    print("=" * 50)
    print("  安装包生成完成!")
    print("=" * 50)
    print(f"  输出目录: {OUTPUT_DIR}")
    for f in OUTPUT_DIR.iterdir():
        size = f.stat().st_size / (1024 * 1024)
        print(f"  - {f.name} ({size:.1f}MB)")


if __name__ == "__main__":
    main()
