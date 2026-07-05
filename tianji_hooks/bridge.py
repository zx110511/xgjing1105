# -*- coding: utf-8-sig -*-
"""天机v9.1 Hooks集成桥接 — 新Hooks框架 ↔ 现有enforcement_hook

统一入口, 同时触发全局钩子和项目钩子。

版本: 1.0.0
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 确保全局hooks在path中
_GLOBAL_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _GLOBAL_HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _GLOBAL_HOOKS_ROOT)

from hooks.base import HookPhase, HookContext
from hooks.registry import get_global_registry
from hooks.lifecycle import HookLifecycleManager, get_lifecycle_manager, HookExecutionSummary
from tianji_hooks.project_registry import PROJECT_NAMESPACE, init_project_hooks

logger = logging.getLogger("tianji.hooks.bridge")


class HooksBridge:
    """Hooks集成桥接 — 统一入口"""

    def __init__(self, project_root: str = ""):
        self._lifecycle = get_lifecycle_manager()
        self._registry = get_global_registry()
        self._project_root = project_root or str(Path(__file__).resolve().parent.parent)
        self._initialized = False

    def initialize(self) -> Dict[str, Any]:
        if self._initialized:
            return {"status": "already_initialized"}
        try:
            project_hooks = init_project_hooks()
            self._initialized = True
            stats = self._registry.get_stats()
            logger.info(f"Hooks系统初始化完成: total_hooks={stats['total_hooks']} | namespaces={stats['namespaces']}")
            return {"status": "initialized", "project_hooks": len(project_hooks), "registry_stats": stats}
        except Exception as e:
            logger.error(f"Hooks系统初始化失败: {e}")
            return {"status": "error", "error": str(e)}

    def pre_check(self, operation: str, session_id: str = "", agent_id: str = "", target_agent: str = "", payload: Optional[Dict[str, Any]] = None, user_input: str = "") -> HookExecutionSummary:
        context = HookContext(operation=operation, phase=HookPhase.PRE, session_id=session_id, agent_id=agent_id, target_agent=target_agent, project_root=self._project_root, payload=payload or {}, user_input=user_input)
        return self._lifecycle.trigger(context, namespace=PROJECT_NAMESPACE)

    def post_check(self, operation: str, session_id: str = "", agent_id: str = "", payload: Optional[Dict[str, Any]] = None) -> HookExecutionSummary:
        context = HookContext(operation=operation, phase=HookPhase.POST, session_id=session_id, agent_id=agent_id, project_root=self._project_root, payload=payload or {})
        return self._lifecycle.trigger(context, namespace=PROJECT_NAMESPACE)

    def on_error(self, operation: str, error: str = "", session_id: str = "", agent_id: str = "", payload: Optional[Dict[str, Any]] = None) -> HookExecutionSummary:
        context = HookContext(operation=operation, phase=HookPhase.ON_ERROR, session_id=session_id, agent_id=agent_id, project_root=self._project_root, payload={**(payload or {}), "error": error})
        return self._lifecycle.trigger(context, namespace=PROJECT_NAMESPACE)

    def get_stats(self) -> Dict[str, Any]:
        return {"initialized": self._initialized, "lifecycle": self._lifecycle.get_stats(), "registry": self._registry.get_stats()}

    def get_audit_log(self, limit: int = 50) -> list:
        return self._lifecycle.get_audit_log(limit)

    def list_hooks(self) -> Dict[str, list]:
        return self._registry.list_hooks()


_bridge: Optional[HooksBridge] = None


def get_hooks_bridge() -> HooksBridge:
    global _bridge
    if _bridge is None:
        _bridge = HooksBridge()
    return _bridge
