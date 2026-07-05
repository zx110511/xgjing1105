#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""天机v9.1 发布包同步脚本 — 将最新源码同步到release目录"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="gbk", errors="replace")
        sys.stderr.reconfigure(encoding="gbk", errors="replace")
    except Exception:
        pass

SRC = Path(r"D:\元初系统\天机v9.1")
DST = SRC / "release" / "天机v9.1-全量发布包"

EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".pytest_cache", ".mypy_cache"}
EXCLUDE_EXTS = {".pyc", ".pyo", ".pdb", ".log"}


def sync_dir(src: Path, dst: Path):
    """使用robocopy镜像同步目录"""
    if not src.exists():
        print(f"  跳过(不存在): {src.name}")
        return
    print(f"  同步: {src.name} -> {dst.name}")
    dst.mkdir(parents=True, exist_ok=True)
    cmd = [
        "robocopy", str(src), str(dst), "/MIR",
        "/XD", "__pycache__", ".git", "node_modules", ".pytest_cache", ".mypy_cache",
        "/XF", "*.pyc", "*.pyo", "*.pdb", "*.log",
        "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
    ]
    subprocess.run(cmd, capture_output=True)


def sync_file(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  复制: {src.name}")


def main():
    print("=" * 50)
    print("  天机v9.1 发布包同步")
    print("=" * 50)

    # 1. 核心代码
    for d in ["core", "server", "indexing", "active_memory", "agents", "adapters"]:
        sync_dir(SRC / d, DST / d)

    # 2. Python运行时
    py_src = SRC / "python"
    py_dst = DST / "python"
    if py_src.exists():
        print("  同步: python运行时")
        py_dst.mkdir(parents=True, exist_ok=True)
        # python.exe和DLL
        for f in py_src.iterdir():
            if f.is_file() and f.suffix in (".exe", ".dll"):
                shutil.copy2(f, py_dst / f.name)
        # Lib
        sync_dir(py_src / "Lib", py_dst / "Lib")
        # DLLs
        if (py_src / "DLLs").exists():
            sync_dir(py_src / "DLLs", py_dst / "DLLs")
        # Scripts
        if (py_src / "Scripts").exists():
            sync_dir(py_src / "Scripts", py_dst / "Scripts")

    # 3. 数据
    sync_dir(SRC / "data", DST / "data")

    # 4. .trae配置
    sync_dir(SRC / ".trae", DST / ".trae")

    # 5. Web构建产物
    web_dst = DST / "web"
    dist_src = SRC / "web" / "dist"
    if dist_src.exists():
        sync_dir(dist_src, web_dst / "dist")
    tauri_exe = SRC / "web" / "src-tauri" / "target" / "release" / "tianji.exe"
    if tauri_exe.exists():
        web_dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tauri_exe, web_dst / "tianji.exe")
        print("  复制: tianji.exe")
    nsis_src = SRC / "web" / "src-tauri" / "target" / "release" / "bundle" / "nsis"
    if nsis_src.exists():
        sync_dir(nsis_src, web_dst / "bundle" / "nsis")

    # 6. 顶层文件
    for f in ["functional_audit.py", "requirements.txt", "mcp_servers.py", "tianji_mcp_server.py"]:
        sync_file(SRC / f, DST / f)

    # 7. 创建启动脚本
    launch_vbs = DST / "启动天机.vbs"
    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        'installDir = fso.GetParentFolderName(WScript.ScriptFullName)\n'
        'pythonExe = installDir & "\\python\\python.exe"\n'
        '\n'
        "WshShell.Environment(\"Process\").Item(\"AI_MEMORY_ROOT\") = installDir\n"
        "WshShell.Environment(\"Process\").Item(\"AI_MEMORY_PORT\") = \"8778\"\n"
        "WshShell.Environment(\"Process\").Item(\"PYTHONIOENCODING\") = \"gbk\"\n"
        '\n'
        "WshShell.Run \"\"\"\" & pythonExe & \"\"\" -m uvicorn server.main:app --host 127.0.0.1 --port 8778 --log-level warning\", 0, False\n"
        '\n'
        "WScript.Sleep 5000\n"
        '\n'
        'tauriExe = installDir & "\\web\\tianji.exe"\n'
        "If fso.FileExists(tauriExe) Then\n"
        "    WshShell.Run \"\"\"\" & tauriExe & \"\"\"\", 1, False\n"
        "Else\n"
        '    WshShell.Run "http://127.0.0.1:8778", 1, False\n'
        "End If\n"
    )
    launch_vbs.write_text(vbs_content, encoding="ascii", errors="replace")
    print("  创建: 启动天机.vbs")

    # 8. 创建安装说明
    install_txt = DST / "安装说明.txt"
    install_content = """天机v9.1 AI智能记忆平台 - 安装说明
========================================
版本: 9.1.0
系统要求: Windows 10/11 64位, 无需预装任何软件

[快速启动]
  1. 将整个文件夹复制到目标电脑 如 D:\\天机v9.1
  2. 双击 启动天机.vbs
  3. 等待5秒后浏览器自动打开 http://127.0.0.1:8778
  4. 如有桌面应用tianji.exe会自动启动

[端口说明]
  后端API服务: http://127.0.0.1:8778
  健康检查: http://127.0.0.1:8778/api/health
  API文档: http://127.0.0.1:8778/docs

[MCP接入]
  在Trae IDE或Cursor的MCP配置中添加:
  mcpServers.tianji-native.command = python/python.exe
  mcpServers.tianji-native.args = [mcp_servers.py]

[停止服务]
  任务管理器结束 python.exe 进程
  或访问 http://127.0.0.1:8778/api/shutdown

[目录结构]
  python/        - Python 3.12运行时
  core/          - 天机核心引擎
  server/        - FastAPI后端服务
  data/          - 记忆数据存储
  .trae/         - 配置和规则
  web/           - 前端和桌面应用
  indexing/      - 检索索引引擎
  active_memory/ - 主动记忆系统
  agents/        - 智能体定义
  adapters/      - AI平台适配器
"""
    install_txt.write_text(install_content, encoding="utf-8")
    print("  创建: 安装说明.txt")

    # 9. 统计
    total_files = sum(1 for _ in DST.rglob("*") if _.is_file())
    total_size = sum(f.stat().st_size for f in DST.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"\n=== 同步完成 ===")
    print(f"总文件数: {total_files}")
    print(f"总大小: {total_size:.1f}MB")


if __name__ == "__main__":
    main()
