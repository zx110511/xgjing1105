"""
注册对话钩子模块到registry.json
"""

import json
import time
from pathlib import Path

registry_path = Path(r"d:\元初系统\天机v9.1\modules\registry.json")

# 读取现有registry
with open(registry_path, "r", encoding="utf-8") as f:
    registry = json.load(f)

# 添加conversation_hook模块
registry["modules"]["conversation_hook"] = {
    "module_id": "conversation_hook",
    "display_name": "对话结束钩子系统",
    "version": "1.0.0",
    "description": "实现对话结束时的自动触发机制，确保每次对话都自动录入天机记忆系统",
    "author": "tianji_core",
    "category": "core",
    "tier": "core_engine",
    "module_type": "engine",
    "import_path": "active_memory.conversation_hook.ConversationHookManager",
    "init_args": {},
    "depends_on": [],
    "provides": [],
    "tags": ["hook", "auto-capture", "conversation"],
    "min_platform_version": "9.1.0",
    "max_platform_version": "",
    "checksum": "",
    "install_state": "activated",
    "installed_at": time.time(),
    "activated_at": time.time(),
    "source_dir": "builtin",
    "config_schema": {},
    "health_check_interval": 30.0,
}

# 更新时间戳
registry["updated_at"] = time.time()

# 写回registry
with open(registry_path, "w", encoding="utf-8") as f:
    json.dump(registry, f, indent=2, ensure_ascii=False)

print("✅ conversation_hook模块已注册到registry.json")
print(f"   模块总数: {len(registry['modules'])}")
