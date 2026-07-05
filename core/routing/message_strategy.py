# -*- coding: utf-8-sig -*-
"""消息路由策略 MessageRoutingStrategy  [v10-ready]

将"消息 → 处理器"的路由逻辑实现为独立的 ITaskRouter 策略插件。
基于消息类型 (remember/recall/consolidate 等) 路由到对应处理器标识。

支持的消息类型映射 (MESSAGE_HANDLER_MAP):
  - remember/store/write       → memory_remember_handler
  - recall/search/query/read   → memory_recall_handler
  - consolidate/promote        → consolidation_handler
  - forget/delete              → memory_forget_handler
  - stats/capacity/health      → stats_handler
  - reflect/evolve             → reflective_handler

本地实现 core.shared.protocols.ITaskRouter，携带 PLUGIN_INFO (category="route")。

架构定位: core/routing/ 路由策略插件层
版本: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Any

from core.shared.plugin_interface import PluginInfo

logger = logging.getLogger("tianji.routing.message")

#: 兜底处理器
DEFAULT_HANDLER = "default_handler"

#: 消息类型 → 处理器标识映射
MESSAGE_HANDLER_MAP: dict[str, str] = {
    # 写入类
    "remember": "memory_remember_handler",
    "store": "memory_remember_handler",
    "write": "memory_remember_handler",
    "save": "memory_remember_handler",
    # 检索类
    "recall": "memory_recall_handler",
    "search": "memory_recall_handler",
    "query": "memory_recall_handler",
    "read": "memory_recall_handler",
    "get": "memory_recall_handler",
    # 固结晋升类
    "consolidate": "consolidation_handler",
    "promote": "consolidation_handler",
    "promotion": "consolidation_handler",
    # 删除类
    "forget": "memory_forget_handler",
    "delete": "memory_forget_handler",
    "remove": "memory_forget_handler",
    # 统计/健康类
    "stats": "stats_handler",
    "capacity": "stats_handler",
    "health": "stats_handler",
    "status": "stats_handler",
    # 反思/进化类
    "reflect": "reflective_handler",
    "reflective": "reflective_handler",
    "evolve": "reflective_handler",
    "digest": "reflective_handler",
}


class MessageRoutingStrategy:
    """消息路由策略  [v10-ready]

    本地实现: 基于消息类型的"消息→处理器"路由。
    实现协议: core.shared.protocols.ITaskRouter (route / get_routing_strategy)。
    """

    STRATEGY_NAME = "message_type_based"

    def __init__(self, handler_map: dict[str, str] | None = None) -> None:
        """初始化消息路由策略。  [v10-ready]

        Args:
            handler_map: 可选自定义"消息类型→处理器"映射，覆盖默认表。
        """
        self._handler_map = dict(MESSAGE_HANDLER_MAP)
        if handler_map:
            self._handler_map.update(handler_map)

    # ---- ITaskRouter 协议实现 ----

    def route(self, task: dict[str, Any]) -> str:
        """根据消息类型选择目标处理器。  [v10-ready]

        ITaskRouter 协议入口。

        Args:
            task: 消息任务字典，支持 type/op/action/message_type 字段承载类型。

        Returns:
            目标处理器标识。
        """
        msg_type = (
            task.get("type")
            or task.get("op")
            or task.get("action")
            or task.get("message_type")
            or ""
        )
        key = str(msg_type).strip().lower()
        return self._handler_map.get(key, DEFAULT_HANDLER)

    def get_routing_strategy(self) -> str:
        """获取当前路由策略名称。  [v10-ready]"""
        return self.STRATEGY_NAME

    # ---- 辅助查询 ----

    def register_handler(self, msg_type: str, handler: str) -> None:
        """注册/覆盖一个消息类型到处理器的映射。  [v10-ready]"""
        self._handler_map[msg_type.strip().lower()] = handler

    def get_handlers(self) -> dict[str, str]:
        """获取当前消息→处理器映射快照。  [v10-ready]"""
        return dict(self._handler_map)


PLUGIN_INFO = PluginInfo(
    name="message_routing",
    version="1.0.0",
    description="消息→处理器路由策略",
    category="route",
    protocols=["ITaskRouter"],
)
