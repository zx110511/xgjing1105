# -*- coding: utf-8-sig -*-
"""Orchestration域事件接线  [v10-ready]

在AgentOrchestrator(AgentScheduler)操作完成后发布事件:
- dispatch_parallel()完成   → 发布 AgentEvents.DISPATCHED + COMPLETED/FAILED
- execute_dag()完成         → 发布 AgentEvents.COMPLETED / FAILED
- plan_and_execute()完成    → 发布 AgentEvents.COMPLETED / FAILED

订阅:
- AgentEvents.COMPLETED → 更新内部任务追踪器(计数/最近完成)

设计原则(与Task #38核心域接线一致):
- 不修改 core/agent_orchestrator.py — 在实例方法上层叠加包装实现事件能力
- 降级友好: event_bus=None 时为纯透传(不包装、不订阅)
- 线程安全: 包装/订阅/状态读写均由 RLock 保护
- 幂等: 重复 wire/unwire 安全
- 防腐: 可选注入 AnticorruptionLayer，跨域后续动作经 ACL 异步派发

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

logger = logging.getLogger("tianji.event_wiring.orchestration")

# 本接线器所属源域标识(用于事件 source 与 ACL 调用)
_DOMAIN = "orchestration"


def _publish_event(bus: Any, event_type: str, source: str, payload: Any) -> None:
    """安全发布领域事件(失败不影响主流程)  [v10-ready]

    Args:
        bus: 事件总线(实现 publish)。为 None 时静默返回。
        event_type: 事件类型标识。
        source: 事件来源域。
        payload: dataclass 或 dict 形式的事件载荷。
    """
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
    except Exception as exc:  # noqa: BLE001 — 发布失败必须吞掉，保证主链路
        logger.warning("[OrchestrationWiring] 发布事件 %s 失败: %s", event_type, exc)


class OrchestrationEventWiring:
    """Orchestration域事件接线器  [v10-ready]

    在 AgentScheduler/AgentOrchestrator 之上叠加事件发布与订阅能力，
    不侵入原实现。event_bus 为 None 时退化为无操作透传。

    Usage:
        wiring = OrchestrationEventWiring(orchestrator, bus, acl=acl)
        # ... orchestrator 正常使用，事件自动发布 ...
        wiring.unwire()  # 需要时恢复原始方法
    """

    def __init__(self, orchestrator: Any, event_bus: Any = None, acl: Any = None) -> None:
        """初始化接线器  [v10-ready]

        Args:
            orchestrator: AgentScheduler/AgentOrchestrator 实例。
            event_bus: 事件总线实例(实现 publish/subscribe)；None 则透传。
            acl: 可选 AnticorruptionLayer，用于订阅回调中的跨域后续动作。
        """
        self._orchestrator = orchestrator
        self._bus = event_bus
        self._acl = acl
        self._lock = threading.RLock()
        self._wired = False
        # method_name -> 原始可调用，用于 unwire 恢复
        self._originals: dict[str, Callable[..., Any]] = {}
        # 订阅句柄 (event_type, handler)，用于 unwire 退订
        self._subscriptions: list[tuple[str, Callable[..., Any]]] = []
        # 任务追踪器状态
        self._tracker_state: dict[str, Any] = {
            "dispatched": 0,
            "completed": 0,
            "failed": 0,
            "last_completed_task": None,
        }

        # 降级友好: 无事件总线时不做任何包装/订阅
        if self._bus is None:
            logger.debug("[OrchestrationWiring] event_bus 为空，进入透传模式")
            return

        self._setup_publishers()
        self._setup_subscribers()
        self._wired = True

    # ------------------------------------------------------------------
    # 方法包装基础设施
    # ------------------------------------------------------------------
    def _wrap(
        self,
        method_name: str,
        after: Callable[[tuple, dict, Any, float], None] | None = None,
        on_error: Callable[[tuple, dict, BaseException, float], None] | None = None,
    ) -> bool:
        """在 orchestrator 实例方法外层叠加事件钩子  [v10-ready]

        Args:
            method_name: 目标方法名(不存在则跳过，返回 False)。
            after: 成功回调 (args, kwargs, result, duration_ms)。
            on_error: 异常回调 (args, kwargs, exc, duration_ms)；回调后原异常照常抛出。

        Returns:
            是否成功包装。
        """
        target = self._orchestrator
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
            except Exception as exc:  # noqa: BLE001 — 仅旁路发布事件，不吞主异常
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
        """包装 orchestrator 方法，执行后发布事件  [v10-ready]"""
        self._wrap(
            "dispatch_parallel",
            after=self._after_dispatch_parallel,
            on_error=self._on_dispatch_error,
        )
        self._wrap(
            "execute_dag",
            after=self._after_execute,
            on_error=self._on_dispatch_error,
        )
        self._wrap(
            "plan_and_execute",
            after=self._after_execute,
            on_error=self._on_dispatch_error,
        )

    def _after_dispatch_parallel(
        self, args: tuple, kwargs: dict, result: Any, duration_ms: float
    ) -> None:
        """dispatch_parallel 完成 → DISPATCHED + COMPLETED  [v10-ready]"""
        tasks = args[0] if args else kwargs.get("tasks", [])
        count = len(tasks) if isinstance(tasks, (list, tuple)) else 0
        task_type = "parallel_dispatch"
        _publish_event(
            self._bus,
            AgentEvents.DISPATCHED,
            _DOMAIN,
            AgentEventPayload(
                agent_id="orchestrator",
                task_type=task_type,
                status="dispatched",
                duration_ms=duration_ms,
            ),
        )
        # 依据结果推断成功/失败
        success = self._results_succeeded(result)
        event_type = AgentEvents.COMPLETED if success else AgentEvents.FAILED
        _publish_event(
            self._bus,
            event_type,
            _DOMAIN,
            AgentEventPayload(
                agent_id="orchestrator",
                task_type=task_type,
                status="completed" if success else "failed",
                duration_ms=duration_ms,
            ),
        )

    def _after_execute(
        self, args: tuple, kwargs: dict, result: Any, duration_ms: float
    ) -> None:
        """execute_dag / plan_and_execute 完成 → DISPATCHED + COMPLETED/FAILED  [v10-ready]"""
        pipeline_id = ""
        success = True
        if isinstance(result, dict):
            success = bool(result.get("success", True))
            pipeline_id = str(result.get("pipeline_id", ""))
        _publish_event(
            self._bus,
            AgentEvents.DISPATCHED,
            _DOMAIN,
            AgentEventPayload(
                agent_id="orchestrator",
                task_id=pipeline_id,
                task_type="dag_execute",
                status="dispatched",
                duration_ms=duration_ms,
            ),
        )
        event_type = AgentEvents.COMPLETED if success else AgentEvents.FAILED
        _publish_event(
            self._bus,
            event_type,
            _DOMAIN,
            AgentEventPayload(
                agent_id="orchestrator",
                task_id=pipeline_id,
                task_type="dag_execute",
                status="completed" if success else "failed",
                duration_ms=duration_ms,
            ),
        )

    def _on_dispatch_error(
        self, args: tuple, kwargs: dict, exc: BaseException, duration_ms: float
    ) -> None:
        """调度方法异常 → FAILED  [v10-ready]"""
        _publish_event(
            self._bus,
            AgentEvents.FAILED,
            _DOMAIN,
            AgentEventPayload(
                agent_id="orchestrator",
                task_type="dispatch",
                status=f"error:{type(exc).__name__}",
                duration_ms=duration_ms,
            ),
        )

    @staticmethod
    def _results_succeeded(result: Any) -> bool:
        """从 dispatch_parallel 结果推断整体是否成功  [v10-ready]"""
        if not isinstance(result, (list, tuple)) or not result:
            return True
        ok = 0
        for item in result:
            if isinstance(item, dict):
                status = str(item.get("status", "")).lower()
                if item.get("success") is True or "complete" in status or "success" in status:
                    ok += 1
            else:
                status = str(getattr(item, "status", "")).lower()
                if "complete" in status or "success" in status:
                    ok += 1
        return ok > 0

    # ------------------------------------------------------------------
    # 订阅端
    # ------------------------------------------------------------------
    def _setup_subscribers(self) -> None:
        """订阅相关事件  [v10-ready]"""
        self._subscribe(AgentEvents.COMPLETED, self._on_agent_completed)

    def _subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """登记订阅并记录句柄以便 unwire  [v10-ready]"""
        if self._bus is None or not hasattr(self._bus, "subscribe"):
            return
        self._bus.subscribe(event_type, handler)
        with self._lock:
            self._subscriptions.append((event_type, handler))

    def _on_agent_completed(self, event: DomainEvent) -> None:
        """AgentEvents.COMPLETED → 更新任务追踪器  [v10-ready]"""
        payload = getattr(event, "payload", {}) or {}
        with self._lock:
            self._tracker_state["completed"] += 1
            self._tracker_state["last_completed_task"] = payload.get("task_id") or payload.get(
                "task_type"
            )

    # ------------------------------------------------------------------
    # 查询 / 清理
    # ------------------------------------------------------------------
    def get_tracker_state(self) -> dict[str, Any]:
        """返回任务追踪器当前状态快照  [v10-ready]"""
        with self._lock:
            return dict(self._tracker_state)

    @property
    def is_wired(self) -> bool:
        """是否已完成接线(非透传模式)  [v10-ready]"""
        return self._wired

    def unwire(self) -> None:
        """恢复原始方法并退订全部事件(幂等)  [v10-ready]"""
        with self._lock:
            for method_name, original in self._originals.items():
                try:
                    setattr(self._orchestrator, method_name, original)
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


def wire_orchestration(
    orchestrator: Any, event_bus: Any = None, acl: Any = None
) -> OrchestrationEventWiring:
    """Orchestration域一键接线工厂  [v10-ready]

    Args:
        orchestrator: AgentScheduler/AgentOrchestrator 实例。
        event_bus: 事件总线；None 则返回透传接线器。
        acl: 可选 AnticorruptionLayer。

    Returns:
        OrchestrationEventWiring 实例。
    """
    return OrchestrationEventWiring(orchestrator, event_bus, acl=acl)


__all__ = ["OrchestrationEventWiring", "wire_orchestration"]
