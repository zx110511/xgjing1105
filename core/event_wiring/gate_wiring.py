# -*- coding: utf-8-sig -*-
"""Gate域事件接线  [v10-ready]

在 QualityGate 检查完成后发布事件:
- check()判定 PASS      → 发布 GateEvents.PASSED
- check()判定 REJECT    → 发布 GateEvents.REJECTED
- check()判定 DOWNGRADE → 发布 GateEvents.DOWNGRADED

订阅:
- MemoryEvents.STORED → 异步质量审计(best-effort)

设计原则:
- **不修改兼容层**: quality_gate.py 保持不动，本模块以"方法包装"
  方式在 QualityGate 实例之上叠加事件能力。
- **降级友好**: event_bus=None 时退化为透传(不包装、不订阅)。
- **线程安全/非阻塞**: 复用 engine_wiring 的后台线程池派发。
- **ACL集成**: 可选注入 ACL，记忆→门禁的审计触发经 ACL 路由。

版本: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Any

from core.shared.events import (
    DomainEvent,
    MemoryEvents,
    GateEvents,
    GateEventPayload,
)
from core.event_wiring.engine_wiring import (
    MethodWiringMixin,
    safe_publish,
    pick_arg,
)

logger = logging.getLogger(__name__)

# GateVerdict 值 → GateEvents 事件类型映射  [v10-ready]
_VERDICT_EVENT_MAP: dict[str, str] = {
    "pass": GateEvents.PASSED,
    "reject": GateEvents.REJECTED,
    "downgrade": GateEvents.DOWNGRADED,
}


def _verdict_to_str(verdict: Any) -> str:
    """归一化 GateVerdict(枚举或字符串) 为小写值  [v10-ready]"""
    value = getattr(verdict, "value", verdict)
    return str(value).lower()


class GateEventWiring(MethodWiringMixin):
    """Gate域事件接线器  [v10-ready]

    包装 QualityGate.check，在其判定后按 verdict 发布门禁域事件；
    并订阅记忆写入事件以进行异步质量审计。

    Usage:
        from core.shared.events import LocalEventBus
        bus = LocalEventBus()
        wiring = GateEventWiring(gate, bus)
        gate.check("text", "working", [], "medium")  # → 自动发布 gate.*
        wiring.unwire()

    降级: event_bus=None 时不包装、不订阅，gate 行为完全不变。
    """

    DOMAIN = "gate"

    def __init__(self, gate: Any, event_bus: Any = None, acl: Any = None) -> None:
        """初始化 Gate 接线器  [v10-ready]

        Args:
            gate: QualityGate 实例。
            event_bus: 事件总线，None 则降级透传。
            acl: 可选 AnticorruptionLayer，用于记忆→门禁的审计触发路由。
        """
        self._gate = gate
        self._bus = event_bus
        self._acl = acl
        self._init_wiring_state()
        # 统计: 收到的 memory.stored 审计触发数
        self.audit_count: int = 0

        if self._bus is None:
            logger.debug("[GateWiring] event_bus 为空，降级为透传(无副作用)")
            return

        self._setup_publishers()
        self._setup_subscribers()

    def _setup_publishers(self) -> None:
        """包装 gate.check，在判定后发布事件  [v10-ready]"""
        self._wrap_after(self._gate, "check", self._after_check)

    def _setup_subscribers(self) -> None:
        """订阅记忆写入事件，触发异步质量审计  [v10-ready]"""
        self._add_subscription(self._bus, MemoryEvents.STORED, self._on_memory_stored)

    # ------------------------------------------------------------------
    # 发布回调
    # ------------------------------------------------------------------

    def _after_check(self, result: Any, args: tuple, kwargs: dict) -> None:
        """check 完成 → 按 verdict 发布对应门禁事件  [v10-ready]"""
        if result is None:
            return
        content = pick_arg(args, kwargs, 0, "content", "")
        verdict = _verdict_to_str(getattr(result, "verdict", ""))
        event_type = _VERDICT_EVENT_MAP.get(verdict)
        if event_type is None:
            return  # conflict / pending_upstream 等不发布标准事件

        dims = getattr(result, "quality_dimensions", {}) or {}
        confidence = 0.0
        if dims:
            try:
                confidence = sum(dims.values()) / len(dims)
            except Exception:  # noqa: BLE001
                confidence = 0.0
        payload = GateEventPayload(
            content=str(content)[:200],
            verdict=verdict,
            confidence=confidence,
            reason=str(getattr(result, "reason", ""))[:200],
        )
        safe_publish(self._bus, event_type, payload, self.DOMAIN)

    # ------------------------------------------------------------------
    # 订阅处理
    # ------------------------------------------------------------------

    def _on_memory_stored(self, event: DomainEvent) -> None:
        """记忆写入 → 异步质量审计(best-effort)  [v10-ready]

        优先经 ACL 异步路由 memory→gate；ACL 不可用时仅记录审计计数，
        不直接回调 gate.check 以免与发布回调形成递归。全程 guarded。
        """
        self.audit_count += 1
        payload = dict(event.payload) if isinstance(event.payload, dict) else {}

        if self._acl is not None and hasattr(self._acl, "call_async"):
            try:
                self._acl.call_async(
                    "memory", "gate", "audit", **payload
                )
                return
            except Exception as exc:  # noqa: BLE001
                logger.debug("[GateWiring] ACL 路由失败, 降级: %s", exc)

        logger.debug(
            "[GateWiring] 记忆写入触发质量审计(累计 %d)", self.audit_count
        )


__all__ = ["GateEventWiring"]
