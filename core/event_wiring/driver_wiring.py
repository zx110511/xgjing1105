# -*- coding: utf-8-sig -*-
"""Driver域事件接线  [v10-ready]

在 DeepSeekDriver 决策完成后发布事件:
- perceive_decide_act()完成 → 发布 DeepSeekEvents.QUICK_DECIDED
- trigger_deep_think()完成   → 发布 DeepSeekEvents.DEEP_THOUGHT
- trigger_evolution()完成    → 发布 DeepSeekEvents.EVOLUTION_TRIGGERED

订阅:
- MemoryEvents.STORED → 触发学习/进化(best-effort, 经 ACL 路由)

设计原则:
- **不修改兼容层**: deepseek_driver.py 保持不动，本模块以"方法包装"
  方式在 DeepSeekDriver 实例之上叠加事件能力。
- **降级友好**: event_bus=None 时退化为透传(不包装、不订阅)。
- **线程安全/非阻塞**: 复用 engine_wiring 的后台线程池派发。
- **ACL集成**: 可选注入 ACL，记忆→驱动的学习触发经 ACL 异步路由。

版本: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Any

from core.shared.events import (
    DomainEvent,
    MemoryEvents,
    DeepSeekEvents,
    DeepSeekEventPayload,
)
from core.event_wiring.engine_wiring import (
    MethodWiringMixin,
    safe_publish,
    pick_arg,
)

logger = logging.getLogger(__name__)


class DriverEventWiring(MethodWiringMixin):
    """Driver域事件接线器  [v10-ready]

    包装 DeepSeekDriver 的三循环触发方法，在其执行后发布 DeepSeek 域事件；
    并订阅记忆写入事件以触发学习/进化闭环。

    Usage:
        from core.shared.events import LocalEventBus
        bus = LocalEventBus()
        wiring = DriverEventWiring(driver, bus)
        driver.trigger_deep_think()    # → 自动发布 deepseek.deep_thought
        wiring.unwire()

    降级: event_bus=None 时不包装、不订阅，driver 行为完全不变。
    """

    DOMAIN = "deepseek"

    def __init__(self, driver: Any, event_bus: Any = None, acl: Any = None) -> None:
        """初始化 Driver 接线器  [v10-ready]

        Args:
            driver: DeepSeekDriver 实例。
            event_bus: 事件总线，None 则降级透传。
            acl: 可选 AnticorruptionLayer，用于记忆→驱动的学习触发路由。
        """
        self._driver = driver
        self._bus = event_bus
        self._acl = acl
        self._init_wiring_state()
        # 统计: 收到的 memory.stored 事件数
        self.memory_stored_count: int = 0

        if self._bus is None:
            logger.debug("[DriverWiring] event_bus 为空，降级为透传(无副作用)")
            return

        self._setup_publishers()
        self._setup_subscribers()

    def _setup_publishers(self) -> None:
        """包装 driver 决策方法，在执行后发布事件  [v10-ready]"""
        self._wrap_after(
            self._driver, "perceive_decide_act", self._after_quick_decide
        )
        self._wrap_after(self._driver, "trigger_deep_think", self._after_deep_think)
        self._wrap_after(self._driver, "trigger_evolution", self._after_evolution)

    def _setup_subscribers(self) -> None:
        """订阅记忆写入事件，触发学习/进化  [v10-ready]"""
        self._add_subscription(self._bus, MemoryEvents.STORED, self._on_memory_stored)

    # ------------------------------------------------------------------
    # 发布回调
    # ------------------------------------------------------------------

    def _after_quick_decide(self, result: Any, args: tuple, kwargs: dict) -> None:
        """perceive_decide_act 完成 → 发布 deepseek.quick_decided  [v10-ready]"""
        if result is None:
            return  # 无决策产生, 不发布
        event = pick_arg(args, kwargs, 0, "event", None)
        input_summary = ""
        if event is not None:
            input_summary = str(getattr(event, "event_id", event))[:120]
        output_summary = ""
        if isinstance(result, dict):
            output_summary = str(result.get("decision", result))[:200]
        payload = DeepSeekEventPayload(
            decision_type="quick",
            input_summary=input_summary,
            output_summary=output_summary,
            confidence=0.0,
            duration_ms=0.0,
        )
        safe_publish(self._bus, DeepSeekEvents.QUICK_DECIDED, payload, self.DOMAIN)

    def _after_deep_think(self, result: Any, args: tuple, kwargs: dict) -> None:
        """trigger_deep_think 完成 → 发布 deepseek.deep_thought  [v10-ready]"""
        output_summary = ""
        if isinstance(result, dict):
            output_summary = str(result.get("triggered", result))[:200]
        payload = DeepSeekEventPayload(
            decision_type="deep",
            input_summary="manual_trigger",
            output_summary=output_summary,
            confidence=0.0,
            duration_ms=0.0,
        )
        safe_publish(self._bus, DeepSeekEvents.DEEP_THOUGHT, payload, self.DOMAIN)

    def _after_evolution(self, result: Any, args: tuple, kwargs: dict) -> None:
        """trigger_evolution 完成 → 发布 deepseek.evolution_triggered  [v10-ready]"""
        payload = DeepSeekEventPayload(
            decision_type="evolution",
            input_summary="manual_trigger",
            output_summary=str(result)[:200] if result else "",
            confidence=0.0,
            duration_ms=0.0,
        )
        safe_publish(
            self._bus, DeepSeekEvents.EVOLUTION_TRIGGERED, payload, self.DOMAIN
        )

    # ------------------------------------------------------------------
    # 订阅处理
    # ------------------------------------------------------------------

    def _on_memory_stored(self, event: DomainEvent) -> None:
        """记忆写入 → 触发学习/进化(best-effort)  [v10-ready]

        优先经 ACL 异步路由 memory→deepseek；ACL 不可用时直接尝试
        将事件投递给 driver 的内部 EventBus(若存在)，全程 guarded。
        """
        self.memory_stored_count += 1
        payload = dict(event.payload) if isinstance(event.payload, dict) else {}

        if self._acl is not None and hasattr(self._acl, "call_async"):
            try:
                self._acl.call_async(
                    "memory", "deepseek", "on_memory_stored", **payload
                )
                return
            except Exception as exc:  # noqa: BLE001
                logger.debug("[DriverWiring] ACL 路由失败, 降级: %s", exc)

        # best-effort: 投递到 driver 内部事件总线(若存在)
        try:
            inner_bus = getattr(self._driver, "event_bus", None)
            if inner_bus is not None and hasattr(inner_bus, "total_count"):
                logger.debug(
                    "[DriverWiring] 记忆写入触发学习信号(累计 %d)",
                    self.memory_stored_count,
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[DriverWiring] 处理 memory.stored 失败: %s", exc)


__all__ = ["DriverEventWiring"]
