# -*- coding: utf-8-sig -*-
"""天机v10.0.1 路由策略子包 core.routing  [v10-ready]

将原 core/layer_router.py (596行) 与 core/orchestration/dispatcher.py 的路由
逻辑插件化拆分为统一的 ITaskRouter 策略:

    - LayerRoutingStrategy   : 内容 → 记忆层级路由 (ITaskRouter)
    - AgentRoutingStrategy   : 任务 → Agent 选择路由 (ITaskRouter)
    - MessageRoutingStrategy : 消息 → 处理器路由 (ITaskRouter)
    - RemoteRoutingStrategy  : 灵境分布式远程策略 (gRPC stub)

所有本地策略实现 core.shared.protocols.ITaskRouter，
并携带 PLUGIN_INFO (category="route") 供 PluginManager 注册。

v9.1 单进程默认装配本地策略；v10.0 分布式可平滑切换 Remote。

架构定位: core/routing/ 路由策略子包入口
版本: 1.0.0
"""

from __future__ import annotations

try:
    from ..shared.plugin_interface import PluginInfo
except ImportError:  # pragma: no cover - 兼容直接执行
    from core.shared.plugin_interface import PluginInfo  # type: ignore

from .agent_strategy import DEFAULT_AGENT, AgentRoutingStrategy
from .layer_strategy import (
    KEYWORD_PATTERNS,
    LAYER_INDEX_FIELD,
    LAYER_MAX_SIZE,
    LAYER_PRIORITY_ORDER,
    LAYER_PROMOTION_THRESHOLD,
    MULTI_TURN_THRESHOLD,
    LayerName,
    LayerRoutingStrategy,
    LayerTarget,
    PromotionGate,
)
from .message_strategy import (
    DEFAULT_HANDLER,
    MESSAGE_HANDLER_MAP,
    MessageRoutingStrategy,
)
from .remote_stub import RemoteRoutingStrategy

#: 插件管理器注册元信息 (PluginManager 通过 category="route" 发现)
PLUGIN_INFO = PluginInfo(
    name="layer_routing",
    version="1.0.0",
    description="记忆层级路由策略",
    category="route",
    protocols=["ITaskRouter"],
)

__all__ = [
    # 本地策略
    "LayerRoutingStrategy",
    "AgentRoutingStrategy",
    "MessageRoutingStrategy",
    # 远程策略 (stub)
    "RemoteRoutingStrategy",
    # 层级类型与常量
    "LayerName",
    "LayerTarget",
    "PromotionGate",
    "LAYER_PRIORITY_ORDER",
    "LAYER_MAX_SIZE",
    "LAYER_PROMOTION_THRESHOLD",
    "LAYER_INDEX_FIELD",
    "KEYWORD_PATTERNS",
    "MULTI_TURN_THRESHOLD",
    # Agent/消息常量
    "DEFAULT_AGENT",
    "MESSAGE_HANDLER_MAP",
    "DEFAULT_HANDLER",
    # 插件元信息
    "PLUGIN_INFO",
]
