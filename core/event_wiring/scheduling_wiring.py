# -*- coding: utf-8-sig -*-
"""Scheduling域事件接线  [v10-ready]

在IntelligentScheduler(TianjiIntelligentScheduler)操作完成后发布事件:
- delegate()完成   → 发布 AgentEvents.DISPATCHED (附带调度上下文)
- schedule()完成   → 发布 AgentEvents.DISPATCHED (cron 调度上下文)

订阅:
- AgentEvents.DISPATCHED → 记录调度决策(计数)
- AgentEvents.COMPLETED  → 容量释放 + 触发后续调度评估(经 ACL 异步派发)

设计原则(与Task #38核心域接线一致):
- 不修改 core/intelligent_scheduler.py — 在实例方法上层叠加包装
- 降级友好: event_bus=None 时为纯透传(不包装、不订阅)
- 线程安全: 包装/订阅/状态读写均由 RLock 保护
- 幂等: 重复 wire/unwire 安全
- 防腐: 可选注入 AnticorruptionLayer，COMPLETED 后续动作经 ACL 异步派发

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
    AgentEvents,
    AgentEventPayload,
    get_event_priority,
)

logger = logging.getLogger("tianji.event_wiring.scheduling")

_DOMAIN = "scheduling"


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
        logger.warning("[SchedulingWiring] 发布事件 %s 失败: %s", event_type, exc)


class SchedulingEventWiring:
    """Scheduling域事件接线器  [v10-ready]

    在 TianjiIntelligentScheduler/IntelligentScheduler 之上叠加事件能力，
    不侵入原实现。event_bus 为 None 时退化为透传。

    Usage:
        wiring = SchedulingEventWiring(scheduler, bus, acl=acl)
        # ... scheduler 正常使用 ...
        wiring.unwire()
    """

    def __init__(self, scheduler: Any, event_bus: Any = None, acl: Any = None) -> None:
        """初始化接线器  [v10-ready]

        Args:
            scheduler: TianjiIntelligentScheduler/IntelligentScheduler 实例。
            event_bus: 事件总线(实现 publish/subscribe)；None 则透传。
            acl: 可选 AnticorruptionLayer，用于 COMPLETED 后的容量释放/后续调度。
        """
        self._scheduler = scheduler
        self._bus = event_bus
        self._acl = acl
        self._lock = threading.RLock()
        self._wired = False
        self._originals: dict[str, Callable[..., Any]] = {}
        self._subscriptions: list[tuple[str, Callable[..., Any]]] = []
        # 调度决策记录状态
        self._schedule_state: dict[str, Any] = {
            "decisions_recorded": 0,
            "capacity_released": 0,
            "followups_triggered": 0,
        }

        if self._bus is None:
            logger.debug("[SchedulingWiring] event_bus 为空，进入透传模式")
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
        """在 scheduler 实例方法外层叠加事件钩子  [v10-ready]"""
        target = self._scheduler
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
        """包装 scheduler 方法，执行后发布调度事件  [v10-ready]"""
        self._wrap("delegate", after=self._after_delegate, on_error=self._on_error)
        self._wrap("schedule", after=self._after_schedule, on_error=self._on_error)

    def _after_delegate(
        self, args: tuple, kwargs: dict, result: Any, duration_ms: float
    ) -> None:
        """delegate 完成 → AgentEvents.DISPATCHED (调度上下文)  [v10-ready]"""
        task_desc = args[0] if args else kwargs.get("task_description", "")
        spawned = len(result) if isinstance(result, (list, tuple)) else 0
        _publish_event(
            self._bus,
            AgentEvents.DISPATCHED,
            _DOMAIN,
            AgentEventPayload(
                agent_id="scheduler",
                task_type="delegation",
                status=f"delegated:{spawned}",
                duration_ms=duration_ms,
            ),
        )

    def _after_schedule(
        self, args: tuple, kwargs: dict, result: Any, duration_ms: float
    ) -> None:
        """schedule 完成 → AgentEvents.DISPATCHED (cron 上下文)  [v10-ready]"""
        cron_id = str(result) if result is not None else ""
        _publish_event(
            self._bus,
            AgentEvents.DISPATCHED,
            _DOMAIN,
            AgentEventPayload(
                agent_id="scheduler",
                task_id=cron_id,
                task_type="cron_schedule",
                status="scheduled",
                duration_ms=duration_ms,
            ),
        )

    def _on_error(
        self, args: tuple, kwargs: dict, exc: BaseException, duration_ms: float
    ) -> None:
        """调度方法异常 → AgentEvents.FAILED  [v10-ready]"""
        _publish_event(
            self._bus,
            AgentEvents.FAILED,
            _DOMAIN,
            AgentEventPayload(
                agent_id="scheduler",
                task_type="schedule",
                status=f"error:{type(exc).__name__}",
                duration_ms=duration_ms,
            ),
        )

    # ------------------------------------------------------------------
    # 订阅端
    # ------------------------------------------------------------------
    def _setup_subscribers(self) -> None:
        """订阅调度相关事件  [v10-ready]"""
        self._subscribe(AgentEvents.DISPATCHED, self._on_dispatched)
        self._subscribe(AgentEvents.COMPLETED, self._on_completed)

    def _subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """登记订阅并记录句柄以便 unwire  [v10-ready]"""
        if self._bus is None or not hasattr(self._bus, "subscribe"):
            return
        self._bus.subscribe(event_type, handler)
        with self._lock:
            self._subscriptions.append((event_type, handler))

    def _on_dispatched(self, event: DomainEvent) -> None:
        """AgentEvents.DISPATCHED → 记录调度决策  [v10-ready]"""
        with self._lock:
            self._schedule_state["decisions_recorded"] += 1

    def _on_completed(self, event: DomainEvent) -> None:
        """AgentEvents.COMPLETED → 容量释放 + 后续调度评估  [v10-ready]

        容量释放在本域内计数；后续调度动作(若有 ACL)经 ACL 异步派发，
        避免与调度器形成直接耦合。
        """
        with self._lock:
            self._schedule_state["capacity_released"] += 1

        if self._acl is not None:
            payload = getattr(event, "payload", {}) or {}
            try:
                self._acl.call_async(
                    _DOMAIN,
                    "orchestration",
                    "evaluate_followup",
                    task_id=payload.get("task_id", ""),
                )
                with self._lock:
                    self._schedule_state["followups_triggered"] += 1
            except Exception as exc:  # noqa: BLE001 — 后续调度尽力而为
                logger.debug("[SchedulingWiring] 后续调度派发失败: %s", exc)

    # ------------------------------------------------------------------
    # 查询 / 清理
    # ------------------------------------------------------------------
    def get_schedule_state(self) -> dict[str, Any]:
        """返回调度决策记录状态快照  [v10-ready]"""
        with self._lock:
            return dict(self._schedule_state)

    @property
    def is_wired(self) -> bool:
        """是否已完成接线(非透传模式)  [v10-ready]"""
        return self._wired

    def unwire(self) -> None:
        """恢复原始方法并退订全部事件(幂等)  [v10-ready]"""
        with self._lock:
            for method_name, original in self._originals.items():
                try:
                    setattr(self._scheduler, method_name, original)
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


def wire_scheduling(
    scheduler: Any, event_bus: Any = None, acl: Any = None
) -> SchedulingEventWiring:
    """Scheduling域一键接线工厂  [v10-ready]

    Args:
        scheduler: TianjiIntelligentScheduler/IntelligentScheduler 实例。
        event_bus: 事件总线；None 则返回透传接线器。
        acl: 可选 AnticorruptionLayer。

    Returns:
        SchedulingEventWiring 实例。
    """
    return SchedulingEventWiring(scheduler, event_bus, acl=acl)


__all__ = ["SchedulingEventWiring", "wire_scheduling"]
