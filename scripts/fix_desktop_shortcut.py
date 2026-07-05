# -*- coding: utf-8-sig -*-
"""
天机v9.1 桌面快捷方式修复工具 (PowerShell版)
============================================
功能:
  1. 检查桌面快捷方式是否存在
  2. 读取快捷方式的目标路径和工作目录
  3. 验证目标路径是否指向正确的启动入口
  4. 如果快捷方式不存在或目标错误，自动创建或修复
  5. 设置正确的工作目录为项目根目录

支持的启动入口:
  - start_tianji.bat
  - tianji_v91_launcher.py

技术: 通过subprocess调用PowerShell处理.lnk文件，稳定可靠
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# 项目配置
TIANJI_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_DIR = TIANJI_ROOT / "launcher"
VALID_TARGETS = [
    str(LAUNCHER_DIR / "start_tianji.bat"),
    str(LAUNCHER_DIR / "tianji_v91_launcher.py"),
]
DESKTOP_SHORTCUT_PATH = (
    Path(os.environ.get("USERPROFILE", "C:\\Users\\Administrator"))
    / "Desktop"
    / "天机v9.1.lnk"
)


def _run_powershell(script: str) -> str:
    """执行PowerShell脚本并返回输出"""
    try:
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True,
            text=True,
            encoding="gbk",
            errors="replace",
            timeout=30,
        )
        if result.returncode != 0 and result.stderr:
            print(f"[DEBUG] PowerShell错误: {result.stderr.strip()}")
        return result.stdout.strip()
    except Exception as e:
        print(f"[ERROR] PowerShell执行失败: {e}")
        return ""


def read_shortcut(lnk_path: Path) -> dict | None:
    """读取快捷方式信息"""
    if not lnk_path.exists():
        return None

    script = f"""
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut('{lnk_path}')
    $result = @{{
        Target = $shortcut.TargetPath
        WorkingDir = $shortcut.WorkingDirectory
        Arguments = $shortcut.Arguments
        Description = $shortcut.Description
        IconLocation = $shortcut.IconLocation
    }}
    $result | ConvertTo-Json
    """

    output = _run_powershell(script)
    if not output:
        return None

    try:
        data = json.loads(output)
        return {
            "target": data.get("Target", ""),
            "working_dir": data.get("WorkingDir", ""),
            "arguments": data.get("Arguments", ""),
            "description": data.get("Description", ""),
        }
    except json.JSONDecodeError:
        return None


def create_or_fix_shortcut(lnk_path: Path, target_path: str, working_dir: str):
    """创建或修复快捷方式"""
    python_exe = TIANJI_ROOT / "python" / "pythonw.exe"
    icon_path = str(python_exe) if python_exe.exists() else target_path

    script = f"""
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut('{lnk_path}')
    $shortcut.TargetPath = '{target_path}'
    $shortcut.WorkingDirectory = '{working_dir}'
    $shortcut.Arguments = ''
    $shortcut.Description = '天机v9.1 统一启动器'
    $shortcut.IconLocation = '{icon_path}'
    $shortcut.Save()
    Write-Output 'OK'
    """

    output = _run_powershell(script)
    if output.strip() == "OK":
        print(f"[OK] 快捷方式已保存: {lnk_path}")
    else:
        raise RuntimeError(f"快捷方式创建失败: {output}")


def is_valid_target(target: str) -> bool:
    """检查目标路径是否为有效的启动入口"""
    if not target:
        return False
    target_lower = target.lower()
    return any(t.lower() == target_lower for t in VALID_TARGETS)


def find_best_target() -> str | None:
    """查找最佳启动入口"""
    for target in VALID_TARGETS:
        if os.path.exists(target):
            return target
    return None


def main():
    """主入口"""
    print("=" * 60)
    print("天机v9.1 桌面快捷方式修复工具 (PowerShell版)")
    print("=" * 60)

    print(f"\n[INFO] 快捷方式路径: {DESKTOP_SHORTCUT_PATH}")
    print(f"[INFO] 项目根目录: {TIANJI_ROOT}")

    shortcut_info = read_shortcut(DESKTOP_SHORTCUT_PATH)

    if shortcut_info:
        print("\n[INFO] 快捷方式已存在")
        print(f"[INFO] 目标路径: {shortcut_info['target']}")
        print(f"[INFO] 工作目录: {shortcut_info['working_dir']}")
        print(f"[INFO] 参数: {shortcut_info['arguments']}")
        print(f"[INFO] 描述: {shortcut_info['description']}")

        target_ok = is_valid_target(shortcut_info["target"])
        working_dir_ok = (
            shortcut_info["working_dir"].lower() == str(TIANJI_ROOT).lower()
        )

        if target_ok and working_dir_ok:
            print("\n[OK] 快捷方式配置正确，无需修复")
            return

        print("\n[WARN] 快捷方式配置不正确，需要修复")
        if not target_ok:
            print(f"[WARN] 目标路径错误: {shortcut_info['target']}")
        if not working_dir_ok:
            print(f"[WARN] 工作目录错误: {shortcut_info['working_dir']}")
    else:
        print("\n[WARN] 快捷方式不存在，需要创建")

    best_target = find_best_target()
    if not best_target:
        print("[ERROR] 未找到有效的启动入口:")
        for t in VALID_TARGETS:
            print(f"  - {t} ({'存在' if os.path.exists(t) else '不存在'})")
        sys.exit(1)

    print(f"\n[INFO] 选择启动入口: {best_target}")
    print(f"[INFO] 设置工作目录: {TIANJI_ROOT}")

    create_or_fix_shortcut(DESKTOP_SHORTCUT_PATH, best_target, str(TIANJI_ROOT))

    print("\n[INFO] 验证修复结果...")
    shortcut_info = read_shortcut(DESKTOP_SHORTCUT_PATH)

    if shortcut_info:
        print(f"[INFO] 目标路径: {shortcut_info['target']}")
        print(f"[INFO] 工作目录: {shortcut_info['working_dir']}")

        target_ok = is_valid_target(shortcut_info["target"])
        working_dir_ok = (
            shortcut_info["working_dir"].lower() == str(TIANJI_ROOT).lower()
        )

        if target_ok and working_dir_ok:
            print("\n[OK] 快捷方式修复成功！")
        else:
            print("\n[ERROR] 快捷方式修复失败")
            sys.exit(1)
    else:
        print("\n[ERROR] 无法读取修复后的快捷方式")
        sys.exit(1)


if __name__ == "__main__":
    main()
