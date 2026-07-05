# -*- coding: utf-8-sig -*-
r"""天机v9.1 项目Hooks — 基于全局框架的项目级钩子适配

包名: tianji_hooks (避免与全局hooks包名冲突)
全局框架: D:\元初系统\hooks (通过sys.path导入)

架构:
  tianji_hooks/
  ├── __init__.py              — 包入口+项目级API
  ├── project_registry.py      — 项目级注册中心
  ├── bridge.py                — 集成桥接
  └── project_builtin/         — 项目专用钩子
      ├── __init__.py
      ├── icme_layer_guard.py  — ICME层路由守卫
      ├── agent_permission.py  — Agent权限检查
      ├── file_operation.py    — 文件操作追踪
      ├── mcp_intercept.py     — MCP调用拦截
      └── consistency_check.py — 一致性检查

版本: 1.0.0 | 维护: @tianshu
"""

import sys
from pathlib import Path

# 将全局hooks框架加入sys.path
_GLOBAL_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _GLOBAL_HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _GLOBAL_HOOKS_ROOT)

from hooks.base import (
    HookPhase,
    HookPriority,
    HookResult,
    HookContext,
    BaseHook,
    SyncHook,
)
from hooks.registry import get_global_registry
from hooks.lifecycle import get_lifecycle_manager
from tianji_hooks.project_registry import (
    PROJECT_NAMESPACE,
    get_project_registry,
    init_project_hooks,
)

__all__ = [
    "HookPhase",
    "HookPriority",
    "HookResult",
    "HookContext",
    "BaseHook",
    "SyncHook",
    "PROJECT_NAMESPACE",
    "get_project_registry",
    "init_project_hooks",
]
