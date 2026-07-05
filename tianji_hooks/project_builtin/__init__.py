# -*- coding: utf-8-sig -*-
"""天机v9.1 项目专用钩子包

包名: tianji_hooks.project_builtin (避免与全局hooks.builtin冲突)

钩子清单:
  - ICMELayerGuardHook:  ICME层路由守卫 (P1, PRE)
  - AgentPermissionHook: Agent权限检查 (P0, PRE)
  - FileOperationHook:   文件操作追踪 (P2, PRE+POST)
  - MCPInterceptHook:    MCP调用拦截 (P2, PRE+POST)
  - ConsistencyCheckHook:一致性检查 (P1, POST)
"""

import sys
from pathlib import Path

_GLOBAL_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _GLOBAL_HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _GLOBAL_HOOKS_ROOT)

from tianji_hooks.project_builtin.icme_layer_guard import ICMELayerGuardHook
from tianji_hooks.project_builtin.agent_permission import AgentPermissionHook
from tianji_hooks.project_builtin.file_operation import FileOperationHook
from tianji_hooks.project_builtin.mcp_intercept import MCPInterceptHook
from tianji_hooks.project_builtin.consistency_check import ConsistencyCheckHook

__all__ = [
    "ICMELayerGuardHook",
    "AgentPermissionHook",
    "FileOperationHook",
    "MCPInterceptHook",
    "ConsistencyCheckHook",
]


def register_all_project_hooks() -> list:
    """注册所有项目级钩子"""
    from tianji_hooks.project_registry import register_project_hook

    hooks = [
        ICMELayerGuardHook(),
        AgentPermissionHook(),
        FileOperationHook(),
        MCPInterceptHook(),
        ConsistencyCheckHook(),
    ]

    registered = []
    for hook in hooks:
        if register_project_hook(hook):
            registered.append(hook)

    return registered
