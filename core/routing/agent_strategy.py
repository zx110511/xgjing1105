# -*- coding: utf-8-sig -*-
"""Agent 路由策略 AgentRoutingStrategy  [v10-ready]

将 core/orchestration/dispatcher.py 的 Agent 分配逻辑提取为独立的
ITaskRouter 策略插件，用于"任务 → 目标 Agent"的选择决策。

选择优先级:
  1. 任务显式指定 agent_id (经能力矩阵校验)
  2. 任务声明所需 capability (能力矩阵子串匹配)
  3. 任务 goal/keywords 关键词与 Agent 能力匹配
  4. 兜底返回总指挥 tianshu

本地实现 core.shared.protocols.ITaskRouter，携带 PLUGIN_INFO (category="route")。
不修改 dispatcher.py 对外接口，仅提取选择逻辑供策略化复用。

架构定位: core/routing/ 路由策略插件层
版本: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Any

from core.shared.plugin_interface import PluginInfo

try:  # pragma: no cover - 兼容直接执行
    from core.orchestration.registry import AGENT_CAPABILITY_MATRIX, CapabilityRegistry
except ImportError:  # pragma: no cover
    AGENT_CAPABILITY_MATRIX = {}  # type: ignore
    CapabilityRegistry = None  # type: ignore

logger = logging.getLogger("tianji.routing.agent")

#: 兜底总指挥 Agent
DEFAULT_AGENT = "tianshu"


class AgentRoutingStrategy:
    """Agent 路由策略  [v10-ready]

    本地实现: 基于能力矩阵的"任务→Agent"选择。
    实现协议: core.shared.protocols.ITaskRouter (route / get_routing_strategy)。
    """

    STRATEGY_NAME = "capability_based"

    def __init__(self, registry: Any = None) -> None:
        """初始化 Agent 路由策略。  [v10-ready]

        Args:
            registry: 能力矩阵注册中心 (CapabilityRegistry, 可选)。
                      未提供时使用全局 AGENT_CAPABILITY_MATRIX。
        """
        if registry is not None:
            self._registry = registry
        elif CapabilityRegistry is not None:
            self._registry = CapabilityRegistry()
        else:
            self._registry = None
        self._matrix = (
            getattr(self._registry, "matrix", None)
            if self._registry is not None
            else None
        ) or AGENT_CAPABILITY_MATRIX

    # ---- ITaskRouter 协议实现 ----

    def route(self, task: dict[str, Any]) -> str:
        """根据任务特征选择目标 Agent。  [v10-ready]

        ITaskRouter 协议入口。

        Args:
            task: 任务描述字典，支持字段:
                  - agent_id: 显式指定 Agent
                  - capability: 所需能力关键词
                  - goal/text/keywords: 任务文本 (用于能力匹配)

        Returns:
            目标 Agent 标识 (能力矩阵中的 key)。
        """
        # 1) 显式指定 agent_id
        agent_id = task.get("agent_id")
        if agent_id and self._exists(agent_id):
            return agent_id

        # 2) 声明所需 capability
        capability = task.get("capability")
        if capability:
            matched = self._find_by_capability(capability)
            if matched:
                return matched[0]

        # 3) goal/keywords 关键词匹配能力
        text = " ".join(
            str(task.get(k, ""))
            for k in ("goal", "text", "keywords", "content")
        ).strip()
        if text:
            best = self._match_by_text(text)
            if best:
                return best

        # 4) 兜底总指挥
        return DEFAULT_AGENT

    def get_routing_strategy(self) -> str:
        """获取当前路由策略名称。  [v10-ready]"""
        return self.STRATEGY_NAME

    # ---- 辅助查询 ----

    def get_available_agents(self) -> list[str]:
        """获取可路由的 Agent 列表。  [v10-ready]"""
        return list(self._matrix.keys())

    def _exists(self, agent_id: str) -> bool:
        """判断 Agent 是否存在于能力矩阵。  [v10-ready]"""
        return agent_id in self._matrix

    def _find_by_capability(self, capability: str) -> list[str]:
        """按能力子串匹配 Agent。  [v10-ready]"""
        if self._registry is not None and hasattr(self._registry, "find_by_capability"):
            return self._registry.find_by_capability(capability)
        return [
            aid
            for aid, info in self._matrix.items()
            if any(capability in c for c in info.get("capabilities", []))
        ]

    def _match_by_text(self, text: str) -> str | None:
        """以任务文本对各 Agent 能力做关键词计分，返回最高分 Agent。  [v10-ready]"""
        text_lower = text.lower()
        best_agent: str | None = None
        best_score = 0
        for aid, info in self._matrix.items():
            score = 0
            for cap in info.get("capabilities", []):
                if cap.lower() in text_lower:
                    score += 1
            if score > best_score:
                best_score = score
                best_agent = aid
        return best_agent if best_score > 0 else None


PLUGIN_INFO = PluginInfo(
    name="agent_routing",
    version="1.0.0",
    description="任务→Agent路由策略",
    category="route",
    protocols=["ITaskRouter"],
)
