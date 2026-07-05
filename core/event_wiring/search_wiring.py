# -*- coding: utf-8-sig -*-
"""Search域事件接线  [v10-ready]

在FusionRetriever(FusionRetrievalStrategy)检索完成后发布事件:
- retrieve()完成 → 发布 SearchEvents.FUSION_COMPLETED + RESULTS_RETURNED
- search()完成   → 发布 SearchEvents.RESULTS_RETURNED

订阅:
- MemoryEvents.STORED → 可选索引更新通知(标记索引脏位/计数)

设计原则(与Task #38核心域接线一致):
- 不修改 core/fusion_retriever.py / core/search/fusion_strategy.py
- 降级友好: event_bus=None 时为纯透传(不包装、不订阅)
- 线程安全: 包装/订阅/状态读写均由 RLock 保护
- 幂等: 重复 wire/unwire 安全
- 防腐: 可选注入 AnticorruptionLayer(预留跨域调用入口)

架构定位: core/event_wiring/ — 领域事件接线层(v10事件驱动过渡)
版本: 1.0.0
"""
from __future__ import annotations

import time
import logging
import functools
import threading
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from core.shared.events import (
    DomainEvent,
    SearchEvents,
    MemoryEvents,
    SearchEventPayload,
    get_event_priority,
)

logger = logging.getLogger("tianji.event_wiring.search")

_DOMAIN = "search"


def _publish_event(bus: Any, event_type: str, source: str, payload: Any) -> None:
    """安全发布领域事件(失败不影响主流程)  [v10-ready]"""
    if bus is None:
        return
    try:
        data = asdict(payload) if is_dataclass(payload) else dict(payload or {})
        event = DomainEvent(
            event_type=event_type,
            source=source,
            payload=data,
            priority=get_event_priority(event_type),
        )
        bus.publish(event)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[SearchWiring] 发布事件 %s 失败: %s", event_type, exc)


class SearchEventWiring:
    """Search域事件接线器  [v10-ready]

    在 FusionRetriever/FusionRetrievalStrategy 之上叠加事件能力，
    不侵入原实现。event_bus 为 None 时退化为透传。

    Usage:
        wiring = SearchEventWiring(retriever, bus, acl=acl)
        # ... retriever 正常使用 ...
        wiring.unwire()
    """

    def __init__(self, retriever: Any, event_bus: Any = None, acl: Any = None) -> None:
        """初始化接线器  [v10-ready]

        Args:
            retriever: FusionRetriever/FusionRetrievalStrategy 实例。
            event_bus: 事件总线(实现 publish/subscribe)；None 则透传。
            acl: 可选 AnticorruptionLayer。
        """
        self._retriever = retriever
        self._bus = event_bus
        self._acl = acl
        self._lock = threading.RLock()
        self._wired = False
        self._originals: dict[str, Callable[..., Any]] = {}
        self._subscriptions: list[tuple[str, Callable[..., Any]]] = []
        # 检索/索引状态
        self._search_state: dict[str, Any] = {
            "fusion_completed": 0,
            "results_returned": 0,
            "index_dirty": False,
            "memory_stored_seen": 0,
        }

        if self._bus is None:
            logger.debug("[SearchWiring] event_bus 为空，进入透传模式")
            return

        self._setup_publishers()
        self._setup_subscribers()
        self._wired = True

    # ------------------------------------------------------------------
    # 方法包装
    # ------------------------------------------------------------------
    def _wrap(
        self,
        method_name: str,
        after: Callable[[tuple, dict, Any, float], None] | None = None,
        on_error: Callable[[tuple, dict, BaseException, float], None] | None = None,
    ) -> bool:
        """在 retriever 实例方法外层叠加事件钩子  [v10-ready]"""
        target = self._retriever
        original = getattr(target, method_name, None)
        if not callable(original):
            return False

        with self._lock:
            self._originals[method_name] = original

        @functools.wraps(original)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = original(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                dur = (time.perf_counter() - start) * 1000.0
                if on_error is not None:
                    try:
                        on_error(args, kwargs, exc, dur)
                    except Exception:  # noqa: BLE001
                        pass
                raise
            dur = (time.perf_counter() - start) * 1000.0
            if after is not None:
                try:
                    after(args, kwargs, result, dur)
                except Exception:  # noqa: BLE001
                    pass
            return result

        setattr(target, method_name, wrapper)
        return True

    # ------------------------------------------------------------------
    # 发布端
    # ------------------------------------------------------------------
    def _setup_publishers(self) -> None:
        """包装 retriever 方法，执行后发布检索事件  [v10-ready]"""
        self._wrap("retrieve", after=self._after_retrieve)
        self._wrap("search", after=self._after_search)

    def _after_retrieve(
        self, args: tuple, kwargs: dict, result: Any, duration_ms: float
    ) -> None:
        """retrieve 完成 → FUSION_COMPLETED + RESULTS_RETURNED  [v10-ready]"""
        query = args[0] if args else kwargs.get("query", "")
        # result 期望为 FusionResult(query/results/channel_stats/total_time_ms)
        results = getattr(result, "results", None)
        count = len(results) if isinstance(results, (list, tuple)) else 0
        channel_stats = getattr(result, "channel_stats", {}) or {}
        channels = list(channel_stats.keys()) if isinstance(channel_stats, dict) else []
        elapsed = getattr(result, "total_time_ms", duration_ms)
        query_text = getattr(result, "query", query)

        payload = SearchEventPayload(
            query=str(query_text),
            results_count=count,
            channels_used=channels,
            duration_ms=float(elapsed),
        )
        _publish_event(self._bus, SearchEvents.FUSION_COMPLETED, _DOMAIN, payload)
        _publish_event(self._bus, SearchEvents.RESULTS_RETURNED, _DOMAIN, payload)

        with self._lock:
            self._search_state["fusion_completed"] += 1
            self._search_state["results_returned"] += 1

    def _after_search(
        self, args: tuple, kwargs: dict, result: Any, duration_ms: float
    ) -> None:
        """search 完成 → RESULTS_RETURNED  [v10-ready]"""
        query = args[0] if args else kwargs.get("query", "")
        count = len(result) if isinstance(result, (list, tuple)) else 0
        payload = SearchEventPayload(
            query=str(query),
            results_count=count,
            channels_used=[],
            duration_ms=duration_ms,
        )
        _publish_event(self._bus, SearchEvents.RESULTS_RETURNED, _DOMAIN, payload)
        with self._lock:
            self._search_state["results_returned"] += 1

    # ------------------------------------------------------------------
    # 订阅端
    # ------------------------------------------------------------------
    def _setup_subscribers(self) -> None:
        """订阅记忆写入事件以做索引更新通知  [v10-ready]"""
        self._subscribe(MemoryEvents.STORED, self._on_memory_stored)

    def _subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """登记订阅并记录句柄以便 unwire  [v10-ready]"""
        if self._bus is None or not hasattr(self._bus, "subscribe"):
            return
        self._bus.subscribe(event_type, handler)
        with self._lock:
            self._subscriptions.append((event_type, handler))

    def _on_memory_stored(self, event: DomainEvent) -> None:
        """MemoryEvents.STORED → 标记索引脏位(可选索引更新通知)  [v10-ready]"""
        with self._lock:
            self._search_state["memory_stored_seen"] += 1
            self._search_state["index_dirty"] = True

    # ------------------------------------------------------------------
    # 查询 / 清理
    # ------------------------------------------------------------------
    def get_search_state(self) -> dict[str, Any]:
        """返回检索/索引状态快照  [v10-ready]"""
        with self._lock:
            return dict(self._search_state)

    def clear_index_dirty(self) -> None:
        """清除索引脏位(索引刷新后调用)  [v10-ready]"""
        with self._lock:
            self._search_state["index_dirty"] = False

    @property
    def is_wired(self) -> bool:
        """是否已完成接线(非透传模式)  [v10-ready]"""
        return self._wired

    def unwire(self) -> None:
        """恢复原始方法并退订全部事件(幂等)  [v10-ready]"""
        with self._lock:
            for method_name, original in self._originals.items():
                try:
                    setattr(self._retriever, method_name, original)
                except Exception:  # noqa: BLE001
                    pass
            self._originals.clear()
            if self._bus is not None and hasattr(self._bus, "unsubscribe"):
                for event_type, handler in self._subscriptions:
                    try:
                        self._bus.unsubscribe(event_type, handler)
                    except Exception:  # noqa: BLE001
                        pass
            self._subscriptions.clear()
            self._wired = False


def wire_search(
    retriever: Any, event_bus: Any = None, acl: Any = None
) -> SearchEventWiring:
    """Search域一键接线工厂  [v10-ready]

    Args:
        retriever: FusionRetriever/FusionRetrievalStrategy 实例。
        event_bus: 事件总线；None 则返回透传接线器。
        acl: 可选 AnticorruptionLayer。

    Returns:
        SearchEventWiring 实例。
    """
    return SearchEventWiring(retriever, event_bus, acl=acl)


__all__ = ["SearchEventWiring", "wire_search"]
