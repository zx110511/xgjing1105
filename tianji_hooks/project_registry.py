# -*- coding: utf-8-sig -*-
"""天机v9.1 项目级注册中心

项目级钩子注册到全局注册中心的 "project:tianji-v91" 命名空间,
执行时自动合并全局钩子。

版本: 1.0.0
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import List

# 确保全局hooks在path中
_GLOBAL_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _GLOBAL_HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _GLOBAL_HOOKS_ROOT)

from hooks.registry import HookRegistry, get_global_registry
from hooks.base import BaseHook

logger = logging.getLogger("tianji.hooks.project_registry")

PROJECT_NAMESPACE = "project:tianji-v91"


def get_project_registry() -> HookRegistry:
    """获取全局注册中心(项目级钩子使用PROJECT_NAMESPACE)"""
    return get_global_registry()


def register_project_hook(hook: BaseHook, override: bool = False) -> bool:
    """注册项目级钩子"""
    registry = get_global_registry()
    return registry.register(hook, namespace=PROJECT_NAMESPACE, override=override)


def unregister_project_hook(name: str) -> bool:
    """注销项目级钩子"""
    registry = get_global_registry()
    return registry.unregister(name, namespace=PROJECT_NAMESPACE)


def init_project_hooks() -> List[BaseHook]:
    """初始化天机v9.1项目级钩子

    同时注册全局内置钩子 + 项目专用钩子。
    返回所有已注册的项目级钩子列表。
    """
    # 先注册全局钩子
    try:
        from hooks.builtin import register_all_global_hooks
        global_hooks = register_all_global_hooks()
        logger.info(f"全局钩子注册完成: {len(global_hooks)} 个")
    except Exception as e:
        logger.warning(f"全局钩子注册失败(降级): {e}")

    # 注册项目级钩子
    from tianji_hooks.project_builtin import register_all_project_hooks
    project_hooks = register_all_project_hooks()
    logger.info(f"项目钩子注册完成: {len(project_hooks)} 个")

    return project_hooks


def get_project_stats() -> dict:
    """获取项目钩子统计"""
    registry = get_global_registry()
    return {
        "project": registry.list_hooks(PROJECT_NAMESPACE),
        "global": registry.list_hooks("global"),
        "registry_stats": registry.get_stats(),
    }
