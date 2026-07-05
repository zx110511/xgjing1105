#!/usr/bin/env python3
"""
激活所有核心模块 — 修复 trae_conversation_capture captured=0
"""
import json
import time
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_FILE = PROJECT_ROOT / "modules" / "registry.json"

# 需要激活的核心模块列表
CORE_MODULES_TO_ACTIVATE = [
    "trae_conversation_capture",  # Trae对话捕获 (P0)
    "enforcement_hook",           # 强制记录钩子 (P1)
    "tvp_bridge",                 # TVP协议桥接 (P1)
    "deepseek_driver",            # DeepSeek大脑 (P1)
    "workflow_engine",            # 工作流引擎 (P2)
    "message_gateway",            # 消息网关 (P2)
    "evolution_engine",           # 进化引擎 (P2)
    "evolution_loop",             # 进化循环 (P2)
    "event_bus",                  # 事件总线 (P2)
    "quality_gate",               # 质量门禁 (P2)
    "llm_bridge",                 # LLM桥接器 (P2)
    "evolution_bus",              # 进化信号总线 (P2)
    "causal_recorder",            # 因果对记录器 (P2)
    "hybrid_engine",              # 混合检索引擎 (P2)
    "dynamic_data_injector",      # 动态数据注入器 (P2)
    "memory_router",              # 记忆路由器 (P2)
    "skill_tracker",              # Skill生命周期追踪 (P2)
    "namespace_manager",          # 命名空间管理器 (P2)
]

def activate_modules():
    """激活所有核心模块"""

    print("=" * 60)
    print("天机v9.1 核心模块激活工具")
    print("=" * 60)

    # 读取 registry.json
    print(f"\n[1] 读取注册表: {REGISTRY_FILE}")
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f)

    modules = registry.get("modules", {})
    print(f"    当前模块数: {len(modules)}")

    # 激活模块
    print(f"\n[2] 激活核心模块...")
    activated_count = 0
    current_time = time.time()

    for module_id in CORE_MODULES_TO_ACTIVATE:
        if module_id in modules:
            module = modules[module_id]
            old_state = module.get("install_state", "unknown")
            old_activated_at = module.get("activated_at", 0.0)

            # 检查是否需要激活
            if old_state != "activated" or old_activated_at == 0.0:
                # 激活模块
                module["install_state"] = "activated"
                module["activated_at"] = current_time + activated_count

                activated_count += 1
                print(f"    ✓ {module_id:30s} {old_state:12s} → activated")
            else:
                print(f"    - {module_id:30s} 已激活")
        else:
            print(f"    ✗ {module_id:30s} 不存在")

    # 更新 registry
    registry["updated_at"] = current_time

    # 保存 registry.json
    print(f"\n[3] 保存注册表...")
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"    ✓ 已保存")
    print(f"    ✓ 激活模块数: {activated_count}")

    # 验证
    print(f"\n[4] 验证激活状态...")
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry_verify = json.load(f)

    modules_verify = registry_verify.get("modules", {})
    verified_count = 0

    for module_id in CORE_MODULES_TO_ACTIVATE:
        if module_id in modules_verify:
            module = modules_verify[module_id]
            if module.get("install_state") == "activated" and module.get("activated_at", 0.0) > 0:
                verified_count += 1
                print(f"    ✓ {module_id:30s} 验证通过")
            else:
                print(f"    ✗ {module_id:30s} 验证失败")

    print(f"\n{'=' * 60}")
    print(f"激活完成: {verified_count}/{len(CORE_MODULES_TO_ACTIVATE)}")
    print(f"{'=' * 60}")

    if verified_count == len(CORE_MODULES_TO_ACTIVATE):
        print("\n✅ 所有核心模块已激活")
        print("\n下一步:")
        print("1. 重启天机服务: python tianji_service.py restart")
        print("2. 验证捕获功能: 发起对话，检查 L0 Sensory 层")
        return 0
    else:
        print("\n⚠️ 部分模块激活失败")
        return 1

if __name__ == "__main__":
    exit(activate_modules())
