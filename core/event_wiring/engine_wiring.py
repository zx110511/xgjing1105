# -*- coding: utf-8-sig -*-
"""Engine域事件接线  [v10-ready]

在 ICMEEngine 操作完成后发布对应事件:
- remember()完成          → 发布 MemoryEvents.STORED
- recall()完成            → 发布 MemoryEvents.RETRIEVED
- consolidate_batch()完成 → 发布 MemoryEvents.CONSOLIDATED

同时订阅来自其他域的事件:
- DeepSeekEvents.QUICK_DECIDED → 可选择性消费决策结果

设计原则:
- **不修改兼容层**: engine.py 保持不动，本模块以"方法包装"方式在
  ICMEEngine 实例之上叠加事件发布能力。
- **降级友好**: event_bus=None 时，接线器退化为透传(不包装方法、不发布)。
- **线程安全/非阻塞**: 事件发布经后台线程池异步派发，不阻塞主业务流。
- **ACL集成**: 可选注入 AnticorruptionLayer，跨域消费经 ACL 路由。

本文件同时提供本子包共享的派发工具 (safe_publish / 方法包装 /
参数提取)，供 driver_wiring 与 gate_wiring 复用，避免重复实现。

版本: 1.0.0
"""
from __future__ import annotations

import time
import logging
import threading
from dataclasses import asdict
from typing import Any, Callable
from concurrent.futures import ThreadPoolExecutor

from core.shared.events import (
    DomainEvent,
    MemoryEvents,
    DeepSeekEvents,
    MemoryEventPayload,
    get_event_priority,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 共享派发工具 (子包内复用)  [v10-ready]
# ============================================================================

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def get_dispatch_executor() -> ThreadPoolExecutor:
    """获取事件派发线程池(惰性单例)  [v10-ready]

    用于将事件发布从主业务线程剥离，保证发布动作不阻塞主流程。

    Returns:
        进程内共享的 ThreadPoolExecutor。
    """
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=2, thread_name_prefix="tianji-event"
                )
    return _executor


def safe_publish(
    bus: Any,
    event_type: str,
    payload_obj: Any,
    source: str,
    async_dispatch: bool = True,
) -> None:
    """安全发布事件(全程 guarded, 默认异步非阻塞)  [v10-ready]

    Args:
        bus: 事件总线实例(实现 publish)，为 None 时直接返回(降级)。
        event_type: 事件类型标识。
        payload_obj: 事件载荷(dataclass 实例或 dict)。
        source: 事件来源标识。
        async_dispatch: True 经后台线程池派发(不阻塞)；False 同步派发。
    """
    if bus is None or not hasattr(bus, "publish"):
        return

    if hasattr(payload_obj, "__dataclass_fields__"):
        payload = asdict(payload_obj)
    elif isinstance(payload_obj, dict):
        payload = payload_obj
    else:
        payload = {"raw": payload_obj}

    event = DomainEvent(
        event_type=event_type,
        source=source,
        payload=payload,
        priority=get_event_priority(event_type),
    )

    def _do_publish() -> None:
        try:
            bus.publish(event)
        except Exception as exc:  # noqa: BLE001 — 发布失败绝不影响主业务
            logger.debug("[EventWiring] 发布事件 %s 失败: %s", event_type, exc)

    if async_dispatch:
        try:
            get_dispatch_executor().submit(_do_publish)
        except Exception as exc:  # noqa: BLE001 — 线程池异常降级为同步
            logger.debug("[EventWiring] 异步派发降级为同步: %s", exc)
            _do_publish()
    else:
        _do_publish()


def pick_arg(
    args: tuple,
    kwargs: dict,
    index: int,
    name: str,
    default: Any = None,
) -> Any:
    """按位置或名称从调用参数中提取实参  [v10-ready]

    包装后的原方法为绑定方法(不含 self)，故 index 从 0 计起对应第一个业务参数。

    Args:
        args: 位置参数元组。
        kwargs: 关键字参数字典。
        index: 位置参数下标。
        name: 关键字参数名。
        default: 缺省值。

    Returns:
        提取到的实参或缺省值。
    """
    if index < len(args):
        return args[index]
    return kwargs.get(name, default)


class MethodWiringMixin:
    """方法包装混入  [v10-ready]

    为子类提供"在目标实例方法执行后发布事件"的包装/还原能力。
    所有子类共享 _wrapped 记录，支持 unwire() 完整还原。
    """

    def _init_wiring_state(self) -> None:
        """初始化包装状态(子类 __init__ 调用)  [v10-ready]"""
        # 记录: [(obj, method_name, original_callable), ...]
        self._wrapped: list[tuple[Any, str, Callable[..., Any]]] = []
        # 记录订阅: [(event_type, handler), ...]
        self._subscriptions: list[tuple[str, Callable[..., Any]]] = []

    def _wrap_after(
        self,
        obj: Any,
        method_name: str,
        after: Callable[[Any, tuple, dict], None],
    ) -> bool:
        """包装实例方法，在原方法返回后调用 after 回调  [v10-ready]

        Args:
            obj: 目标实例。
            method_name: 待包装方法名。
            after: 回调 (result, args, kwargs) -> None，负责发布事件。

        Returns:
            是否成功包装。
        """
        original = getattr(obj, method_name, None)
        if original is None or not callable(original):
            logger.debug("[EventWiring] 跳过不存在的方法: %s", method_name)
            return False
        if getattr(original, "_tianji_wired", False):
            return False  # 幂等: 已包装

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = original(*args, **kwargs)
            try:
                after(result, args, kwargs)
            except Exception as exc:  # noqa: BLE001 — 接线绝不破坏业务
                logger.debug(
                    "[EventWiring] 方法 %s 事件回调失败: %s", method_name, exc
                )
            return result

        wrapper._tianji_wired = True  # type: ignore[attr-defined]
        wrapper._tianji_original = original  # type: ignore[attr-defined]
        setattr(obj, method_name, wrapper)
        self._wrapped.append((obj, method_name, original))
        return True

    def _add_subscription(
        self, bus: Any, event_type: str, handler: Callable[..., Any]
    ) -> None:
        """登记并执行一次事件订阅  [v10-ready]"""
        if bus is None or not hasattr(bus, "subscribe"):
            return
        bus.subscribe(event_type, handler)
        self._subscriptions.append((event_type, handler))

    def unwire(self) -> None:
        """还原全部方法包装并取消订阅  [v10-ready]"""
        for obj, method_name, original in self._wrapped:
            try:
                setattr(obj, method_name, original)
            except Exception as exc:  # noqa: BLE001
                logger.debug("[EventWiring] 还原 %s 失败: %s", method_name, exc)
        self._wrapped.clear()

        bus = getattr(self, "_bus", None)
        if bus is not None and hasattr(bus, "unsubscribe"):
            for event_type, handler in self._subscriptions:
                try:
                    bus.unsubscribe(event_type, handler)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("[EventWiring] 取消订阅 %s 失败: %s", event_type, exc)
        self._subscriptions.clear()


# ============================================================================
# Engine域事件接线器
# ============================================================================

class EngineEventWiring(MethodWiringMixin):
    """Engine域事件接线器  [v10-ready]

    包装 ICMEEngine 的 remember/recall/consolidate_batch，在其执行后
    发布对应记忆域事件；并订阅 DeepSeek 决策事件以选择性消费。

    Usage:
        from core.shared.events import LocalEventBus
        bus = LocalEventBus()
        wiring = EngineEventWiring(engine, bus)
        engine.remember("text")        # → 自动发布 memory.stored
        wiring.unwire()                # 还原

    降级: event_bus=None 时不包装方法、不订阅，engine 行为完全不变。
    """

    DOMAIN = "engine"

    def __init__(self, engine: Any, event_bus: Any = None, acl: Any = None) -> None:
        """初始化 Engine 接线器  [v10-ready]

        Args:
            engine: ICMEEngine 实例。
            event_bus: 事件总线(实现 publish/subscribe)，None 则降级透传。
            acl: 可选 AnticorruptionLayer，用于跨域消费路由。
        """
        self._engine = engine
        self._bus = event_bus
        self._acl = acl
        self._init_wiring_state()
        # 接收到的 DeepSeek 决策(供选择性消费)
        self.last_deepseek_decision: dict[str, Any] | None = None

        if self._bus is None:
            logger.debug("[EngineWiring] event_bus 为空，降级为透传(无副作用)")
            return

        self._setup_publishers()
        self._setup_subscribers()

    def _setup_publishers(self) -> None:
        """包装 engine 方法，在执行后发布事件  [v10-ready]"""
        self._wrap_after(self._engine, "remember", self._after_remember)
        self._wrap_after(self._engine, "remember_guarded", self._after_remember)
        self._wrap_after(self._engine, "recall", self._after_recall)
        self._wrap_after(self._engine, "consolidate_batch", self._after_consolidate)

    def _setup_subscribers(self) -> None:
        """订阅来自其他域的事件  [v10-ready]"""
        self._add_subscription(
            self._bus, DeepSeekEvents.QUICK_DECIDED, self._on_deepseek_decided
        )

    # ------------------------------------------------------------------
    # 发布回调
    # ------------------------------------------------------------------

    def _after_remember(self, result: Any, args: tuple, kwargs: dict) -> None:
        """remember 完成 → 发布 memory.stored  [v10-ready]"""
        content = pick_arg(args, kwargs, 0, "content", "")
        layer = pick_arg(args, kwargs, 1, "layer", "working")
        tags = pick_arg(args, kwargs, 2, "tags", None) or []
        entry_id = ""
        actual_layer = layer
        if isinstance(result, dict):
            entry_id = str(result.get("id", "") or result.get("entry_id", ""))
            actual_layer = result.get("actual_layer", layer)
        payload = MemoryEventPayload(
            entry_id=entry_id,
            content=str(content)[:200],
            layer=str(actual_layer),
            tags=list(tags),
            timestamp=time.time(),
        )
        safe_publish(self._bus, MemoryEvents.STORED, payload, self.DOMAIN)

    def _after_recall(self, result: Any, args: tuple, kwargs: dict) -> None:
        """recall 完成 → 发布 memory.retrieved  [v10-ready]"""
        query = pick_arg(args, kwargs, 0, "query", "") or ""
        layers = pick_arg(args, kwargs, 1, "layers", None) or []
        payload = MemoryEventPayload(
            entry_id="",
            content=str(query)[:200],
            layer=",".join(str(x) for x in layers),
            tags=[],
            timestamp=time.time(),
        )
        safe_publish(self._bus, MemoryEvents.RETRIEVED, payload, self.DOMAIN)

    def _after_consolidate(self, result: Any, args: tuple, kwargs: dict) -> None:
        """consolidate_batch 完成 → 发布 memory.consolidated  [v10-ready]"""
        from_layer = pick_arg(args, kwargs, 0, "from_layer", "")
        to_layer = pick_arg(args, kwargs, 1, "to_layer", "") or ""
        payload = MemoryEventPayload(
            entry_id="",
            content=f"{from_layer}->{to_layer}",
            layer=str(to_layer),
            tags=[],
            timestamp=time.time(),
        )
        safe_publish(self._bus, MemoryEvents.CONSOLIDATED, payload, self.DOMAIN)

    # ------------------------------------------------------------------
    # 订阅处理
    # ------------------------------------------------------------------

    def _on_deepseek_decided(self, event: DomainEvent) -> None:
        """消费 DeepSeek 快速决策结果(选择性)  [v10-ready]"""
        try:
            self.last_deepseek_decision = dict(event.payload)
            logger.debug(
                "[EngineWiring] 收到 DeepSeek 决策: %s",
                event.payload.get("decision_type", ""),
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[EngineWiring] 处理 DeepSeek 决策失败: %s", exc)


__all__ = [
    "EngineEventWiring",
    "MethodWiringMixin",
    "safe_publish",
    "pick_arg",
    "get_dispatch_executor",
]
