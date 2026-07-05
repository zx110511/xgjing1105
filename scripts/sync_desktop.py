"""
天机桌面启动文件自动同步脚本 v1.0
=================================
职责: 连接版本管理与桌面快捷方式，实现自动同步

触发机制:
  1. 每次运行审计脚本 → 自动检查桌面同步状态
  2. 手动运行  → python scripts/sync_desktop.py
  3. 手动运行  → python scripts/sync_desktop.py --check (仅检查)

设计原则:
  - 不重复造轮子，复用 launcher/desktop.py 的核心逻辑
  - 审计脚本失败时不阻塞，仅报告同步状态
  - 与 07-升级状态与下一程.md 联动
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from launcher.desktop import check_sync_needed, auto_sync


def main():
    import argparse
    parser = argparse.ArgumentParser(description="天机桌面同步检查器 v1.0")
    parser.add_argument("--check", action="store_true", help="仅检查不修复")
    parser.add_argument("--json", action="store_true", help="JSON格式输出(审计集成用)")
    args = parser.parse_args()

    needed = check_sync_needed()

    if args.json:
        import json
        result = {
            "sync_needed": needed,
            "status": "needs_update" if needed else "synced",
        }
        print(json.dumps(result, ensure_ascii=False))
        return 1 if needed else 0

    if args.check:
        if needed:
            print("[DESKTOP_SYNC] NEEDED — version mismatch detected")
            return 1
        else:
            print("[DESKTOP_SYNC] OK")
            return 0

    if needed:
        print("=" * 50)
        print(" 天机桌面同步 — 版本变更检测")
        print("=" * 50)
        ok = auto_sync()
        return 0 if ok else 1
    else:
        print("[DESKTOP_SYNC] Already synced, no action needed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
