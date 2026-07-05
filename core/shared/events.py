# -*- coding: utf-8-sig -*-
"""天机v10.0.1 事件总线  [v10-ready]

提供DomainEvent基类和LocalEventBus实现:
- DomainEvent: 领域事件基类，含类型/时间戳/来源/载荷
- EventPriority: 事件优先级枚举
- LocalEventBus: 进程内事件总线（默认实现）
  - 同步发布: publish()
  - 异步发布: publish_async()
  - 订阅/取消: subscribe()/unsubscribe()
  - 通配符: subscribe("*", handler) 接收所有事件

架构定位: core/shared/ Ω基点 — 合体间通信基础设施
本地实现: LocalEventBus (进程内, 同步/异步双模式)
远程实现: RemoteEventBus (灵境gRPC, stub预留)

Protocol兼容: 实现 core/shared/protocols.py 中的 IEventBus。
    协议声明 publish(event_type: str, payload: dict) 双参数形式；
    本实现的 publish/publish_async 同时兼容:
        - publish(DomainEvent)            领域事件对象 (推荐)
        - publish(event_type, payload)    协议双参数形式
        - publish(任意对象)               自动包装为通用事件
版本: 1.0.0
"""
from __future__ import annotations

import time
import asyncio
import logging
from typing import Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """事件优先级  [v10-ready]"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class DomainEvent:
    """领域事件基类  [v10-ready]

    所有天机领域事件的统一基类。9域每域定义3-5个具体事件类。

    Attributes:
        event_type: 事件类型标识 (如 "memory.stored", "gate.rejected")
        timestamp: 事件发生时间戳
        source: 事件来源模块/Agent
        payload: 事件载荷（任意数据）
        priority: 事件优先级
        event_id: 唯一事件ID
    """
    event_type: str
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: f"evt_{int(time.time() * 1000)}")


# === 9域预定义事件类型 ===  [v10-ready]

class MemoryEvents:
    """D1守道域事件"""
    STORED = "memory.stored"
    RETRIEVED = "memory.retrieved"
    CONSOLIDATED = "memory.consolidated"
    DELETED = "memory.deleted"


class GateEvents:
    """D1守道域-门禁事件"""
    PASSED = "gate.passed"
    REJECTED = "gate.rejected"
    DOWNGRADED = "gate.downgraded"


class SearchEvents:
    """D2寻道域事件"""
    QUERY_STARTED = "search.query_started"
    RESULTS_RETURNED = "search.results_returned"
    FUSION_COMPLETED = "search.fusion_completed"


class GraphEvents:
    """D2寻道域-图谱事件"""
    NODE_ADDED = "graph.node_added"
    EDGE_ADDED = "graph.edge_added"
    SYNCED = "graph.synced"


class DeepSeekEvents:
    """D3识道域事件"""
    QUICK_DECIDED = "deepseek.quick_decided"
    DEEP_THOUGHT = "deepseek.deep_thought"
    EVOLUTION_TRIGGERED = "deepseek.evolution_triggered"


class EvolutionEvents:
    """D4悟道域事件"""
    PARAM_TUNED = "evolution.param_tuned"
    RULE_ADDED = "evolution.rule_added"
    ARCH_EVOLVED = "evolution.arch_evolved"


class GovernanceEvents:
    """D5御道域事件"""
    PLAN_CREATED = "governance.plan_created"
    AUDIT_COMPLETED = "governance.audit_completed"
    APPROVED = "governance.approved"


class AgentEvents:
    """D6使道域事件"""
    DISPATCHED = "agent.dispatched"
    COMPLETED = "agent.completed"
    FAILED = "agent.failed"


class InfraEvents:
    """D7载道域事件"""
    MODULE_LOADED = "infra.module_loaded"
    HEALTH_CHECKED = "infra.health_checked"
    DEGRADED = "infra.degraded"


def _coerce_event(event: Any, payload: dict[str, Any] | None = None) -> DomainEvent:
    """将多种入参形式统一归一为 DomainEvent  [v10-ready]

    支持三种调用形式:
        - DomainEvent 对象          直接返回
        - (event_type: str, payload) 协议双参数形式 -> 包装
        - 任意其它对象              包装为通用事件
    """
    if isinstance(event, DomainEvent):
        return event
    if isinstance(event, str):
        # Protocol风格: publish(event_type, payload)
        return DomainEvent(event_type=event, payload=payload or {})
    # 兜底: 包装任意对象
    return DomainEvent(event_type=str(type(event).__name__), payload={"raw": event})


class LocalEventBus:
    """进程内事件总线  [v10-ready]

    实现IEventBus Protocol。同步发布，FIFO顺序处理。
    支持通配符订阅("*")和事件类型前缀匹配。

    本地实现: 进程内dict + list，零外部依赖
    远程扩展: 替换为RemoteEventBus(灵境gRPC)时，接口不变

    Usage:
        bus = LocalEventBus()
        bus.subscribe("memory.stored", my_handler)
        bus.publish(DomainEvent(event_type="memory.stored", payload={"id": "123"}))
        # 或协议双参数形式:
        bus.publish("memory.stored", {"id": "123"})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._event_count: int = 0
        self._error_count: int = 0

    def _collect_handlers(self, event_type: str) -> list[Callable[..., Any]]:
        """收集匹配某事件类型的全部handler（精确+通配符+前缀）"""
        handlers = list(self._handlers.get(event_type, []))
        # 通配符匹配
        handlers.extend(self._handlers.get("*", []))
        # 前缀匹配 (如订阅"memory.*"匹配所有memory.xxx事件)
        if "." in event_type:
            prefix = event_type.split(".")[0] + ".*"
            handlers.extend(self._handlers.get(prefix, []))
        return handlers

    def publish(self, event: Any, payload: dict[str, Any] | None = None) -> None:
        """同步发布事件  [v10-ready]

        按订阅顺序逐一调用handler。单个handler异常不影响其他handler。

        Args:
            event: DomainEvent对象，或事件类型字符串(协议双参数形式)，或任意对象
            payload: 当event为字符串时作为事件载荷(协议双参数形式)
        """
        domain_event = _coerce_event(event, payload)
        self._event_count += 1
        event_type = domain_event.event_type

        for handler in self._collect_handlers(event_type):
            try:
                handler(domain_event)
            except Exception as e:
                self._error_count += 1
                name = getattr(handler, "__name__", repr(handler))
                logger.warning(f"[EventBus] Handler {name} failed for {event_type}: {e}")

    async def publish_async(self, event: Any, payload: dict[str, Any] | None = None) -> None:
        """异步发布事件  [v10-ready]

        协程handler以await调用，普通handler直接调用。
        """
        domain_event = _coerce_event(event, payload)
        self._event_count += 1
        event_type = domain_event.event_type

        for handler in self._collect_handlers(event_type):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(domain_event)
                else:
                    handler(domain_event)
            except Exception as e:
                self._error_count += 1
                name = getattr(handler, "__name__", repr(handler))
                logger.warning(f"[EventBus] Async handler {name} failed for {event_type}: {e}")

    def subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """订阅事件  [v10-ready]

        Args:
            event_type: 事件类型或通配符("*"=全部, "memory.*"=memory域全部)
            handler: 事件处理函数, 签名: (event: DomainEvent) -> None
        """
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """取消订阅  [v10-ready]"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    def get_stats(self) -> dict[str, Any]:
        """获取事件总线统计  [v10-ready]"""
        return {
            "total_events": self._event_count,
            "total_errors": self._error_count,
            "subscriptions": {k: len(v) for k, v in self._handlers.items() if v},
            "handler_count": sum(len(v) for v in self._handlers.values()),
        }

    def reset(self) -> None:
        """重置事件总线（测试用）"""
        self._handlers.clear()
        self._event_count = 0
        self._error_count = 0


# === 远程实现预留 ===  [v10-ready]

class RemoteEventBus:
    """灵境分布式事件总线 (stub预留)  [v10-ready]

    v10.0分布式模式下经灵境gRPC/消息队列跨进程广播事件。
    当前为占位stub，接口与LocalEventBus一致，尚未实现。
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError(
            "RemoteEventBus 为 v10.0 灵境分布式预留实现，当前请使用 LocalEventBus"
        )


# === 模块级默认实例 ===  [v10-ready]

_default_bus: LocalEventBus | None = None


def get_event_bus() -> LocalEventBus:
    """获取默认事件总线实例（单例）"""
    global _default_bus
    if _default_bus is None:
        _default_bus = LocalEventBus()
    return _default_bus


# === 9域事件载荷Schema ===  [v10-ready]
#
# 为每个领域定义标准化的事件载荷数据类，作为 DomainEvent.payload 的
# 结构化约定。各域发布事件时可用 dataclasses.asdict() 转为 dict 装入
# payload，订阅方据此 Schema 解析，降低跨域耦合的隐式约定成本。

@dataclass
class MemoryEventPayload:
    """记忆域事件载荷  [v10-ready]"""
    entry_id: str = ""
    content: str = ""
    layer: str = ""
    tags: list[str] = field(default_factory=list)
    timestamp: float = 0.0


@dataclass
class GateEventPayload:
    """门禁域事件载荷  [v10-ready]"""
    content: str = ""
    verdict: str = ""
    confidence: float = 0.0
    reason: str = ""


@dataclass
class SearchEventPayload:
    """搜索域事件载荷  [v10-ready]"""
    query: str = ""
    results_count: int = 0
    channels_used: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class GraphEventPayload:
    """图谱域事件载荷  [v10-ready]"""
    node_id: str = ""
    node_type: str = ""
    edge_type: str = ""
    source_id: str = ""
    target_id: str = ""


@dataclass
class DeepSeekEventPayload:
    """DeepSeek域事件载荷  [v10-ready]"""
    decision_type: str = ""
    input_summary: str = ""
    output_summary: str = ""
    confidence: float = 0.0
    duration_ms: float = 0.0


@dataclass
class EvolutionEventPayload:
    """进化域事件载荷  [v10-ready]"""
    param_name: str = ""
    old_value: Any = None
    new_value: Any = None
    trigger: str = ""


@dataclass
class GovernanceEventPayload:
    """治理域事件载荷  [v10-ready]"""
    plan_id: str = ""
    audit_type: str = ""
    result: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class AgentEventPayload:
    """Agent域事件载荷  [v10-ready]"""
    agent_id: str = ""
    task_id: str = ""
    task_type: str = ""
    status: str = ""
    duration_ms: float = 0.0


@dataclass
class InfraEventPayload:
    """基础设施域事件载荷  [v10-ready]"""
    module_name: str = ""
    component: str = ""
    status: str = ""
    message: str = ""


# === 事件优先级分配规则 ===  [v10-ready]
#
# 显式声明关键事件的优先级；未列出的事件默认按 EventPriority.NORMAL 处理。
# 通过 get_event_priority() 查询，发布方据此设置 DomainEvent.priority。

EVENT_PRIORITY_MAP: dict[str, EventPriority] = {
    # CRITICAL - 系统关键决策
    GateEvents.REJECTED: EventPriority.CRITICAL,
    EvolutionEvents.ARCH_EVOLVED: EventPriority.CRITICAL,
    InfraEvents.DEGRADED: EventPriority.CRITICAL,
    # HIGH - 核心业务流
    MemoryEvents.STORED: EventPriority.HIGH,
    MemoryEvents.CONSOLIDATED: EventPriority.HIGH,
    DeepSeekEvents.QUICK_DECIDED: EventPriority.HIGH,
    DeepSeekEvents.DEEP_THOUGHT: EventPriority.HIGH,
    GovernanceEvents.APPROVED: EventPriority.HIGH,
    AgentEvents.FAILED: EventPriority.HIGH,
    # NORMAL - 其他
    # (默认所有未列出事件为 EventPriority.NORMAL)
}


def get_event_priority(event_type: str) -> EventPriority:
    """查询事件类型的优先级  [v10-ready]

    未在 EVENT_PRIORITY_MAP 中显式声明的事件统一返回 NORMAL。

    Args:
        event_type: 事件类型标识 (如 "gate.rejected")

    Returns:
        对应的 EventPriority，缺省为 EventPriority.NORMAL
    """
    return EVENT_PRIORITY_MAP.get(event_type, EventPriority.NORMAL)


# === 事件契约 ===  [v10-ready]

@dataclass
class EventContract:
    """事件契约文档  [v10-ready]

    定义事件的publisher域、subscriber域、payload类型，
    用于文档化和运行时验证事件通信契约。

    Attributes:
        event_type: 事件类型标识
        publisher_domain: 发布方所属域
        subscriber_domains: 订阅方域列表
        payload_type: 载荷数据类类型
        description: 契约说明
        priority: 事件优先级
    """
    event_type: str
    publisher_domain: str
    subscriber_domains: list[str]
    payload_type: type
    description: str = ""
    priority: EventPriority = EventPriority.NORMAL


# === 契约注册表 ===  [v10-ready]
#
# 集中登记核心跨域事件的通信契约，供文档生成与运行时校验使用。

EVENT_CONTRACTS: list[EventContract] = [
    EventContract(
        event_type=MemoryEvents.STORED,
        publisher_domain="memory",
        subscriber_domains=["gate", "search", "graph", "deepseek"],
        payload_type=MemoryEventPayload,
        description="记忆条目写入完成",
        priority=EventPriority.HIGH,
    ),
    EventContract(
        event_type=MemoryEvents.CONSOLIDATED,
        publisher_domain="memory",
        subscriber_domains=["search", "graph"],
        payload_type=MemoryEventPayload,
        description="记忆层级固结晋升完成",
        priority=EventPriority.HIGH,
    ),
    EventContract(
        event_type=GateEvents.REJECTED,
        publisher_domain="gate",
        subscriber_domains=["memory", "governance", "deepseek"],
        payload_type=GateEventPayload,
        description="写入门禁判决拒绝",
        priority=EventPriority.CRITICAL,
    ),
    EventContract(
        event_type=GateEvents.PASSED,
        publisher_domain="gate",
        subscriber_domains=["memory"],
        payload_type=GateEventPayload,
        description="写入门禁判决通过",
        priority=EventPriority.NORMAL,
    ),
    EventContract(
        event_type=SearchEvents.RESULTS_RETURNED,
        publisher_domain="search",
        subscriber_domains=["deepseek", "agent"],
        payload_type=SearchEventPayload,
        description="语义搜索返回结果",
        priority=EventPriority.NORMAL,
    ),
    EventContract(
        event_type=GraphEvents.NODE_ADDED,
        publisher_domain="graph",
        subscriber_domains=["search"],
        payload_type=GraphEventPayload,
        description="知识图谱新增节点",
        priority=EventPriority.NORMAL,
    ),
    EventContract(
        event_type=DeepSeekEvents.QUICK_DECIDED,
        publisher_domain="deepseek",
        subscriber_domains=["agent", "governance"],
        payload_type=DeepSeekEventPayload,
        description="DeepSeek快速反应环决策完成",
        priority=EventPriority.HIGH,
    ),
    EventContract(
        event_type=DeepSeekEvents.DEEP_THOUGHT,
        publisher_domain="deepseek",
        subscriber_domains=["agent", "governance", "evolution"],
        payload_type=DeepSeekEventPayload,
        description="DeepSeek深度思考环决策完成",
        priority=EventPriority.HIGH,
    ),
    EventContract(
        event_type=EvolutionEvents.ARCH_EVOLVED,
        publisher_domain="evolution",
        subscriber_domains=["governance", "infra"],
        payload_type=EvolutionEventPayload,
        description="架构级自演化完成",
        priority=EventPriority.CRITICAL,
    ),
    EventContract(
        event_type=GovernanceEvents.APPROVED,
        publisher_domain="governance",
        subscriber_domains=["evolution", "agent"],
        payload_type=GovernanceEventPayload,
        description="治理流水线审批通过",
        priority=EventPriority.HIGH,
    ),
    EventContract(
        event_type=AgentEvents.DISPATCHED,
        publisher_domain="agent",
        subscriber_domains=["governance"],
        payload_type=AgentEventPayload,
        description="Agent任务派发",
        priority=EventPriority.NORMAL,
    ),
    EventContract(
        event_type=AgentEvents.FAILED,
        publisher_domain="agent",
        subscriber_domains=["governance", "infra"],
        payload_type=AgentEventPayload,
        description="Agent任务执行失败",
        priority=EventPriority.HIGH,
    ),
    EventContract(
        event_type=InfraEvents.DEGRADED,
        publisher_domain="infra",
        subscriber_domains=["governance", "agent", "deepseek"],
        payload_type=InfraEventPayload,
        description="基础设施进入降级状态",
        priority=EventPriority.CRITICAL,
    ),
]


__all__ = [
    "EventPriority",
    "DomainEvent",
    "LocalEventBus",
    "RemoteEventBus",
    "get_event_bus",
    "MemoryEvents",
    "GateEvents",
    "SearchEvents",
    "GraphEvents",
    "DeepSeekEvents",
    "EvolutionEvents",
    "GovernanceEvents",
    "AgentEvents",
    "InfraEvents",
    # === Payload Schema  [v10-ready] ===
    "MemoryEventPayload",
    "GateEventPayload",
    "SearchEventPayload",
    "GraphEventPayload",
    "DeepSeekEventPayload",
    "EvolutionEventPayload",
    "GovernanceEventPayload",
    "AgentEventPayload",
    "InfraEventPayload",
    # === 优先级 + 契约  [v10-ready] ===
    "EVENT_PRIORITY_MAP",
    "get_event_priority",
    "EventContract",
    "EVENT_CONTRACTS",
]
