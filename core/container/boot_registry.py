# -*- coding: utf-8-sig -*-
"""TianjiContainer 启动注册表 — 数据驱动 [SSS-PhaseB]

将原core.py中~2200行重复注册代码压缩为MODULE_REGISTRY配置表。
每个模块只需一行声明: (name, factory, deps, category, critical)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from .core import TianjiContainer
from .module_lifecycle import ModuleDescriptor, ModuleState

logger = logging.getLogger("tianji.container.boot")

# ──────────────────────────────────────────────
# 全局容器单例
# ──────────────────────────────────────────────

_container_instance: TianjiContainer | None = None


def get_container() -> TianjiContainer | None:
    return _container_instance


def set_container(c: TianjiContainer) -> None:
    global _container_instance
    _container_instance = c


# ──────────────────────────────────────────────
# 模块工厂函数 (lazy import)
# ──────────────────────────────────────────────

def _factory_memory_api():
    """记忆API代理"""
    class _MemoryAPIProxy:
        def __init__(self):
            self._engine = None
        def _get_engine(self):
            if self._engine is None:
                try:
                    from server.deps import get_engine
                    self._engine = get_engine()
                except Exception:
                    pass
            return self._engine
        def get_stats(self):
            eng = self._get_engine()
            if eng:
                try:
                    s = eng.stats()
                    if isinstance(s, dict):
                        return {"proxy": "icme_engine", **s}
                except Exception:
                    pass
            return {"proxy": "icme_engine", "status": "deferred"}
        def start(self): pass
        def stop(self): pass
    return _MemoryAPIProxy()


def _factory_skill_registry(project_root: Path) -> Callable[[], Any]:
    """Skill注册中心工厂 (闭包捕获路径)"""
    def _init():
        from core.shared.skill_registry import SkillRegistry
        skills_dir = project_root / ".agents" / "skills"
        if not skills_dir.exists() or not any(skills_dir.iterdir()):
            skills_dir = project_root / ".trae" / "skills"
        if not skills_dir.exists() or not any(skills_dir.iterdir()):
            skills_dir = project_root / "data" / "skills"
        sr = SkillRegistry(skills_dir=skills_dir, memory_api_url="http://127.0.0.1:8769")
        sr.discover()
        return sr
    return _init


def _factory_skill_tracker(project_root: Path) -> Callable[[], Any]:
    """Skill生命周期追踪器"""
    def _init():
        from core.shared.skill_registry import SkillLifecycleTracker
        skills_dir = project_root / ".agents" / "skills"
        if not skills_dir.exists() or not any(skills_dir.iterdir()):
            skills_dir = project_root / ".trae" / "skills"
        if not skills_dir.exists() or not any(skills_dir.iterdir()):
            skills_dir = project_root / "data" / "skills"
        return SkillLifecycleTracker(skills_dir=skills_dir)
    return _init


def _health_generic(inst) -> dict:
    """通用健康检查 — 适用于大多数模块"""
    try:
        state = getattr(inst, 'state', None)
        if callable(state):
            s = state()
        else:
            s = state
        return {"status": "running", "detail": str(type(inst).__name__)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ──────────────────────────────────────────────
# 模块注册表 (数据驱动核心)
#
# 格式: {
#   "module_name": {
#     "display": "显示名",
#     "factory": factory_fn_or_str,
#     "deps": ["dep1", ...],
#     "category": "分类",
#     "critical": bool,
#     "start_fn": optional,
#     "stop_fn": optional,
#     "health_fn": optional,
#   },
# }
# ──────────────────────────────────────────────

def _build_module_registry(project_root: Path) -> dict[str, dict]:
    """构建完整的模块注册表"""

    sr_init = _factory_skill_registry(project_root)
    st_init = _factory_skill_tracker(project_root)

    return {
        # ═══ L0 基础设施层 ═══
        "memory_api": {
            "display": "ICME记忆引擎",
            "factory": _factory_memory_api,
            "deps": [],
            "category": "infrastructure",
            "critical": True,
        },
        "skill_registry": {
            "display": "技能注册中心",
            "factory": sr_init,
            "deps": [],
            "category": "infrastructure",
            "critical": False,
        },
        "skill_tracker": {
            "display": "技能生命周期追踪",
            "factory": st_init,
            "deps": [],
            "category": "infrastructure",
            "critical": False,
        },

        # ═══ L1 核心引擎层 ═══
        # [FIX-boot-001] 修正幽灵路径: core.xxx → core.shared.xxx (真实文件位置)
        "deepseek_driver": {
            "display": "DeepSeek驱动",
            # DeepSeekDriver需要event_bus参数, 延迟初始化(由server/main.py注入)
            "factory": lambda: None,
            "deps": ["memory_api"],
            "category": "engine",
            "critical": True,
        },
        "event_bus": {
            "display": "事件总线",
            # EventBus定义在core.shared.deepseek_driver内, 由deepseek_driver统一管理
            "factory": lambda: None,
            "deps": [],
            "category": "engine",
            "critical": True,
        },
        "config_manager": {
            "display": "配置管理器",
            "factory": lambda: __import__("core.shared.config_manager", fromlist=["ConfigManager"]).ConfigManager(),
            "deps": [],
            "category": "engine",
            "critical": True,
        },

        # ═══ L2 存储层 ═══
        "tiered_storage": {
            "display": "分层存储引擎",
            "factory": lambda: __import__("core.memory.storage.tiered", fromlist=["TieredStorageEngine"]).TieredStorageEngine(),
            "deps": ["config_manager"],
            "category": "storage",
            "critical": True,
        },
        "hybrid_engine": {
            "display": "混合存储引擎",
            # 真实类名ICMEStorageEngine(非HybridStorageEngine)
            "factory": lambda: __import__("core.memory.hybrid_engine", fromlist=["ICMEStorageEngine"]).ICMEStorageEngine(),
            "deps": ["tiered_storage"],
            "category": "storage",
            "critical": True,
        },

        # ═══ L3 记忆层 ═══
        # [FIX-boot-002] 以下4个模块为规划中但尚未实现的模块, 工厂返回None避免ImportError
        "episodic_memory": {
            "display": "情景记忆管理",
            # TODO: 核心记忆功能已由hybrid_engine(ICMEStorageEngine)内置实现, 独立管理器待v10设计
            "factory": lambda: None,
            "deps": ["hybrid_engine"],
            "category": "memory",
            "critical": False,
        },
        "semantic_memory": {
            "display": "语义记忆管理",
            # TODO: 同上, 语义检索已由fusion_retriever+sqlite_store实现
            "factory": lambda: None,
            "deps": ["hybrid_engine"],
            "category": "memory",
            "critical": False,
        },
        "working_memory": {
            "display": "工作记忆管理",
            # TODO: 同上, 工作记忆层已由ICMEStorageEngine的working层实现
            "factory": lambda: None,
            "deps": ["hybrid_engine"],
            "category": "memory",
            "critical": False,
        },

        # ═══ L4 Agent层 ═══
        "agent_runtime": {
            "display": "Agent运行时",
            # TODO: Agent运行时待v10重新设计, 当前由agents/目录下的独立脚本实现
            "factory": lambda: None,
            "deps": [],
            "category": "agent",
            "critical": False,
        },
        "orchestrator": {
            "display": "任务编排器",
            # DriverOrchestrator需要driver参数, 延迟初始化
            "factory": lambda: None,
            "deps": [],
            "category": "agent",
            "critical": False,
        },

        # ═══ L5 服务层 ═══
        "api_server": {
            "display": "API服务",
            "factory": lambda: None,  # 由server/main.py独立启动
            "deps": ["orchestrator"],
            "category": "service",
            "critical": True,
        },
        "capture_daemon": {
            "display": "对话捕获守护进程",
            "factory": lambda: None,  # 延迟启动
            "deps": ["episodic_memory"],
            "category": "service",
            "critical": False,
        },
    }


# ──────────────────────────────────────────────
# 容器构建入口
# ──────────────────────────────────────────────

def build_container() -> TianjiContainer:
    """
    构建并返回完整的天机容器实例

    [SSS-PhaseB] 从~2500行手工注册代码精简至数据驱动模式。
    模块注册表由 _build_module_registry() 统一生成。
    """
    from core.shared.config import AI_MEMORY_ROOT, MEMORY_DATA_PATH

    project_root = AI_MEMORY_ROOT
    container = TianjiContainer()

    # 获取完整注册表
    registry = _build_module_registry(project_root)

    # 批量注册所有模块
    for name, cfg in registry.items():
        descriptor = ModuleDescriptor(
            name=name,
            display_name=cfg["display"],
            init_fn=cfg["factory"],
            start_fn=cfg.get("start_fn"),
            stop_fn=cfg.get("stop_fn"),
            health_fn=cfg.get("health_fn", _health_generic),
            depends_on=cfg.get("deps", []),
            category=cfg.get("category", "unknown"),
            critical=cfg.get("critical", False),
        )
        container.register(descriptor)

    # 设置全局单例
    set_container(container)

    logger.info(
        "[BootRegistry] 容器构建完成: %d个模块已注册",
        len(registry),
    )
    return container
