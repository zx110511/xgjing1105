# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核Protocol主动记忆域+插件域+调度域接口  [v10-ready]

定义8个Protocol接口：
主动记忆域 (3个):
- IActiveMemory: 主动记忆接口
- IInterceptLayer: 拦截层接口
- IIntentExtractor: 意图提取接口

插件域 (2个):
- IPlugin: 插件协议接口
- IPluginManager: 插件管理接口

调度域 (3个):
- IAgentDispatcher: Agent分发接口
- ITaskRouter: 任务路由接口
- ISchedulerStrategy: 调度策略接口

架构定位: core/shared/ Ω基点层 — 主动记忆+插件+调度聚阵契约
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .protocols_base import PluginInfo


# ============================================================================
# 主动记忆域 (3个) — IActiveMemory / IInterceptLayer / IIntentExtractor
# ============================================================================


@runtime_checkable
class IActiveMemory(Protocol):
    """主动记忆接口  [v10-ready]

    本地实现: LocalActiveMemory (进程内拦截 + 本地意图识别, 单进程默认)
    远程实现: RemoteActiveMemory (灵境远程意图决策服务)

    切换方式: 在输入与响应端双向拦截实现记忆优先决策，
    分布式模式下意图决策交由远程服务完成。
    """

    def intercept_input(self, content: str, session_id: str) -> dict[str, Any]:
        """拦截用户输入。

        Args:
            content: 用户输入文本。
            session_id: 会话标识。

        Returns:
            增强后的输入上下文字典。
        """
        ...

    def intercept_response(self, response: str, session_id: str) -> dict[str, Any]:
        """拦截 AI 响应。

        Args:
            response: AI 响应文本。
            session_id: 会话标识。

        Returns:
            记忆捕获结果字典。
        """
        ...


@runtime_checkable
class IInterceptLayer(Protocol):
    """拦截层接口  [v10-ready]

    本地实现: LocalInterceptLayer (进程内双端捕获)
    远程实现: RemoteInterceptLayer (灵境网关拦截代理)

    切换方式: 负责原始输入/输出的捕获与缓冲，
    分布式模式下捕获事件经网关转发至中心记忆服务。
    """

    def capture_user_input(self, content: str, session_id: str) -> str:
        """捕获用户输入。

        Args:
            content: 用户输入文本。
            session_id: 会话标识。

        Returns:
            捕获记录的 capture_id。
        """
        ...

    def capture_ai_response(self, response: str, session_id: str) -> str:
        """捕获 AI 响应。

        Args:
            response: AI 响应文本。
            session_id: 会话标识。

        Returns:
            捕获记录的 capture_id。
        """
        ...


@runtime_checkable
class IIntentExtractor(Protocol):
    """意图提取接口  [v10-ready]

    本地实现: LocalIntentExtractor (规则/轻量模型意图识别)
    远程实现: RemoteIntentExtractor (灵境 LLM 意图服务)

    切换方式: 从文本提取用户意图与分类，
    分布式模式下意图识别交由远程大模型。
    """

    def extract_intent(self, content: str) -> dict[str, Any]:
        """提取意图。

        Args:
            content: 输入文本。

        Returns:
            意图描述字典 (含类型/置信度/槽位等)。
        """
        ...

    def classify(self, content: str) -> str:
        """分类输入。

        Args:
            content: 输入文本。

        Returns:
            分类标签字符串。
        """
        ...


# ============================================================================
# 插件域 (2个) — IPlugin / IPluginManager
# ============================================================================


@runtime_checkable
class IPlugin(Protocol):
    """插件协议接口  [v10-ready]

    本地实现: LocalPlugin (进程内加载的插件实例)
    远程实现: RemotePlugin (灵境远程插件代理, sandbox 隔离)

    切换方式: 插件生命周期由插件管理器统一调度，
    分布式模式下远程插件在独立进程/节点中运行。
    """

    def activate(self) -> bool:
        """激活插件。

        Returns:
            激活是否成功。
        """
        ...

    def deactivate(self) -> bool:
        """停用插件。

        Returns:
            停用是否成功。
        """
        ...

    def get_info(self) -> PluginInfo:
        """获取插件元信息。

        Returns:
            插件元信息 PluginInfo。
        """
        ...


@runtime_checkable
class IPluginManager(Protocol):
    """插件管理接口  [v10-ready]

    本地实现: LocalPluginManager (进程内插件注册表)
    远程实现: RemotePluginManager (灵境插件编排服务)

    切换方式: 负责插件加载/卸载/查询，
    分布式模式下可跨节点管理远程插件生命周期。
    """

    def load(self, name: str, *, config: dict[str, Any] | None = None) -> bool:
        """加载插件。

        Args:
            name: 插件名称。
            config: 可选插件配置。

        Returns:
            加载是否成功。
        """
        ...

    def unload(self, name: str) -> bool:
        """卸载插件。

        Args:
            name: 插件名称。

        Returns:
            卸载是否成功。
        """
        ...

    def list(self) -> list[PluginInfo]:
        """列出已加载插件。

        Returns:
            插件元信息列表。
        """
        ...

    def get(self, name: str) -> IPlugin | None:
        """获取指定插件实例。

        Args:
            name: 插件名称。

        Returns:
            插件实例；不存在时返回 None。
        """
        ...


# ============================================================================
# 调度域 (3个) — IAgentDispatcher / ITaskRouter / ISchedulerStrategy
# ============================================================================


@runtime_checkable
class IAgentDispatcher(Protocol):
    """Agent 分发接口  [v10-ready]

    本地实现: LocalAgentDispatcher (进程内 Agent 调度)
    远程实现: RemoteAgentDispatcher (灵境分布式 Agent 调度网关)

    切换方式: 将任务分发至合适的 Agent 执行，
    分布式模式下 Agent 可跨节点远程调度。
    """

    def dispatch(
        self, task: dict[str, Any], *, agent: str | None = None
    ) -> dict[str, Any]:
        """分发任务。

        Args:
            task: 任务描述字典。
            agent: 可选指定目标 Agent 名称。

        Returns:
            调度结果字典。
        """
        ...

    def get_available_agents(self) -> list[str]:
        """获取可用 Agent 列表。

        Returns:
            可用 Agent 名称列表。
        """
        ...


@runtime_checkable
class ITaskRouter(Protocol):
    """任务路由接口  [v10-ready]

    本地实现: LocalTaskRouter (进程内规则路由)
    远程实现: RemoteTaskRouter (灵境集中式路由决策服务)

    切换方式: 根据任务特征选择路由目标与策略，
    分布式模式下路由策略由中心服务统一下发。
    """

    def route(self, task: dict[str, Any]) -> str:
        """为任务选择路由目标。

        Args:
            task: 任务描述字典。

        Returns:
            目标 Agent/节点标识。
        """
        ...

    def get_routing_strategy(self) -> str:
        """获取当前路由策略。

        Returns:
            路由策略标识 (如 round_robin/capability_based)。
        """
        ...


@runtime_checkable
class ISchedulerStrategy(Protocol):
    """调度策略接口  [v10-ready]

    本地实现: PriorityBasedScheduler (优先级调度, 单进程默认)
    远程实现: RemoteSchedulerStrategy (灵境分布式任务调度)

    切换方式: 统一调度接口，分布式模式下切换为远程调度中心。
    """

    def decide(self, task: dict[str, Any], agents: list[str]) -> str:
        """决定任务分配给哪个Agent"""
        ...

    def schedule(self, task: dict[str, Any], trigger: str) -> str:
        """调度任务，返回任务ID"""
        ...

    def evaluate_capacity(self, agent: str) -> float:
        """评估Agent当前负载容量 (0.0~1.0)"""
        ...


__all__ = [
    # 主动记忆域
    "IActiveMemory",
    "IInterceptLayer",
    "IIntentExtractor",
    # 插件域
    "IPlugin",
    "IPluginManager",
    # 调度域
    "IAgentDispatcher",
    "ITaskRouter",
    "ISchedulerStrategy",
]
