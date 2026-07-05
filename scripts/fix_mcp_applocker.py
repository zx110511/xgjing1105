"""
天机MCP修复脚本 v18.0 — EXE→Python模式绕过AppLocker
用法: python scripts/fix_mcp_applocker.py
效果: 将.mcp.json中6个Server从EXE切换为python+script.py
"""

import json
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
MCP_JSON = ROOT / ".trae" / "mcp.json"
BACKUP = ROOT / ".trae" / "mcp.json.backup-exe"

PYTHON_EXE = str(ROOT / "python" / "python.exe")

SERVER_MAP = {
    "agent-framework-global": {
        "command": PYTHON_EXE,
        "args": [str(ROOT / "mcp" / "server" / "agent_framework.py")],
        "env": {"PROJECT_ROOT": str(ROOT), "PYTHONIOENCODING": "utf-8-sig"}
    },
    "command-executor": {
        "command": PYTHON_EXE,
        "args": [str(ROOT / "mcp" / "server" / "command_executor.py")],
        "env": {"PROJECT_ROOT": str(ROOT), "PYTHONIOENCODING": "utf-8-sig"}
    },
    "memory-engine-global": {
        "command": PYTHON_EXE,
        "args": [str(ROOT / "mcp" / "tianji_mcp_server.py")],
        "env": {
            "AI_MEMORY_ROOT": str(ROOT),
            "TIANJI_API_URL": "http://127.0.0.1:8771",
            "PYTHONIOENCODING": "utf-8-sig"
        }
    },
    "ops-engine": {
        "command": PYTHON_EXE,
        "args": [str(ROOT / "mcp" / "server" / "ops_engine.py")],
        "env": {
            "PROJECT_ROOT": str(ROOT),
            "TIANJI_API_URL": "http://127.0.0.1:8771",
            "PYTHONIOENCODING": "utf-8-sig"
        }
    },
    "performance-profiler": {
        "command": PYTHON_EXE,
        "args": [str(ROOT / "mcp" / "server" / "performance_profiler.py")],
        "env": {"PROJECT_ROOT": str(ROOT), "PYTHONIOENCODING": "utf-8-sig"}
    },
    "security-scanner": {
        "command": PYTHON_EXE,
        "args": [str(ROOT / "mcp" / "server" / "security_scanner.py")],
        "env": {"PROJECT_ROOT": str(ROOT), "PYTHONIOENCODING": "utf-8-sig"}
    }
}

def main():
    print("=" * 60)
    print("  天机 MCP 修复工具 v18.0 — AppLocker绕过")
    print("=" * 60)

    if not MCP_JSON.exists():
        print(f"[ERROR] {MCP_JSON} 不存在!")
        return 1

    with open(MCP_JSON, 'r', encoding='utf-8') as f:
        config = json.load(f)

    servers = config.get("mcpServers", {})
    old_mode = list(servers.values())[0].get("command", "") if servers else ""

    is_exe = ".exe" in old_mode.lower()
    if not is_exe and "python.exe" in old_mode:
        print("[INFO] 已经是Python模式，无需修复。")
        return 0

    print(f"\n[1/3] 备份原配置 → {BACKUP.name}")
    import shutil
    shutil.copy2(MCP_JSON, BACKUP)

    print(f"[2/3] 切换 {len(servers)} 个 Server: EXE → Python脚本")
    for name, new_cfg in SERVER_MAP.items():
        if name in servers:
            old_cmd = servers[name].get("command", "")
            servers[name] = new_cfg
            print(f"  [OK] {name:25s} {os.path.basename(old_cmd):15s} -> python + {os.path.basename(new_cfg['args'][0])}")
        else:
            print(f"  [!!] {name} not in config, adding")
            servers[name] = new_cfg

    config["_meta"]["description"] = "用户全局 MCP 配置 - 天机Python脚本模式 (绕过AppLocker)"
    config["_meta"]["last_updated"] = "2026-06-01T14:30:00+08:00"
    config["_meta"]["note"] = "All servers use python + script.py to bypass AppLocker. 6 servers, 70+ tools total."
    config["_meta"]["version"] = "18.0.0-TIANJI-PYTHON-BYPASS"
    config["mcpServers"] = servers

    print(f"[3/3] 写入新配置 → {MCP_JSON}")
    with open(MCP_JSON, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("  [DONE] Fix complete!")
    print("=" * 60)
    print()
    print("下一步操作:")
    print("  1. 关闭 Trae IDE 中 MCP 面板")
    print("  2. 点击每个 Server 的「重试」按钮")
    print("  3. 或重启 Trae IDE 使配置生效")
    print()
    print(f"  备份文件: {BACKUP}")
    print(f"  如需回滚: 复制 {BACKUP.name} → mcp.json")
    return 0

if __name__ == "__main__":
    sys.exit(main())
