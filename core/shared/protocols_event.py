# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核Protocol事件域接口  [v10-ready]

定义3个事件相关Protocol接口：
- IEventBus: 事件总线接口
- IEventHandler: 事件处理器接口
- IEventFilter: 事件过滤接口

架构定位: core/shared/ Ω基点层 — 事件聚阵契约
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class IEventBus(Protocol):
    """事件总线接口  [v10-ready]

    本地实现: LocalEventBus (进程内同步/异步分发, 单进程默认)
    远程实现: RemoteEventBus (灵境消息队列跨进程分发)

    切换方式: 用于解耦记忆写入、晋升、图谱同步等协作，
    分布式模式下事件经消息中间件广播至各节点订阅者。
    """

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """发布事件。

        Args:
            event_type: 事件类型标识。
            payload: 事件负载数据。
        """
        ...

    def subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """订阅事件。

        Args:
            event_type: 事件类型标识。
            handler: 事件回调处理器。
        """
        ...

    def unsubscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """取消订阅。

        Args:
            event_type: 事件类型标识。
            handler: 先前注册的回调处理器。
        """
        ...


@runtime_checkable
class IEventHandler(Protocol):
    """事件处理器接口  [v10-ready]

    本地实现: LocalEventHandler (进程内回调处理)
    远程实现: RemoteEventHandler (灵境远程消费者代理)

    切换方式: 处理器注册到事件总线，
    分布式模式下可由远程工作节点消费并回执处理结果。
    """

    def handle(self, event_type: str, payload: dict[str, Any]) -> Any:
        """处理一个事件。

        Args:
            event_type: 事件类型标识。
            payload: 事件负载数据。

        Returns:
            处理结果 (可为 None)。
        """
        ...

    def can_handle(self, event_type: str) -> bool:
        """判定能否处理指定事件类型。

        Args:
            event_type: 事件类型标识。

        Returns:
            是否可处理。
        """
        ...


@runtime_checkable
class IEventFilter(Protocol):
    """事件过滤接口  [v10-ready]

    本地实现: LocalEventFilter (进程内规则过滤)
    远程实现: RemoteEventFilter (灵境集中式过滤策略)

    切换方式: 事件分发前经本接口判定是否放行，
    分布式模式下过滤规则可由中心服务统一下发。
    """

    def should_process(self, event_type: str, payload: dict[str, Any]) -> bool:
        """判定事件是否应被处理。

        Args:
            event_type: 事件类型标识。
            payload: 事件负载数据。

        Returns:
            是否放行处理。
        """
        ...


__all__ = [
    "IEventBus",
    "IEventHandler",
    "IEventFilter",
]
