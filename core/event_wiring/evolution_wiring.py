# -*- coding: utf-8-sig -*-
"""Evolution域事件接线  [v10-ready]

将EvolutionLoop的进化行为事件化:
- 参数调优 → 发布 EvolutionEvents.PARAM_TUNED
- 规则新增 → 发布 EvolutionEvents.RULE_ADDED
- 架构演化 → 发布 EvolutionEvents.ARCH_EVOLVED

将因果对记录事件化:
- CausalPair记录(record_action) → 发布 EvolutionEvents.PARAM_TUNED (with causal context)

将治理流水线事件化:
- 审计完成(audit)   → 发布 GovernanceEvents.AUDIT_COMPLETED
- 计划创建(plan)    → 发布 GovernanceEvents.PLAN_CREATED
- 批准通过(approve) → 发布 GovernanceEvents.APPROVED

订阅(触发进化评估/沉淀):
- DeepSeekEvents.DEEP_THOUGHT / EVOLUTION_TRIGGERED → 触发 evolution_loop.tick() 进化评估
- MemoryEvents.CONSOLIDATED                         → 触发 evolution_loop.tick() 沉淀

设计原则(与 Task #38/#39 一致):
- **不修改原文件**: evolution_loop.py / governance_pipeline.py 保持不动，
  本模块以"方法包装"方式在实例之上叠加事件能力。
- **降级友好**: event_bus=None(或目标实例为 None)时退化为透传(不包装、不订阅)。
- **线程安全/非阻塞**: 复用 engine_wiring 的后台线程池派发，订阅触发的 tick
  亦经线程池异步执行，绝不阻塞主业务流。
- **ACL集成**: 可选注入 ACL，跨域触发优先经 ACL 异步路由。
- **与 driver_wiring 协作**: driver_wiring 已接线 perceive_decide_act / trigger_deep_think /
  trigger_evolution(决策触发层面)，本模块聚焦 evolution_loop 的进化/治理层面。

版本: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Any

from core.shared.events import (
    DomainEvent,
    MemoryEvents,
    DeepSeekEvents,
    EvolutionEvents,
    GovernanceEvents,
    EvolutionEventPayload,
    GovernanceEventPayload,
)
from core.event_wiring.engine_wiring import (
    MethodWiringMixin,
    safe_publish,
    pick_arg,
    get_dispatch_executor,
)

logger = logging.getLogger("tianji.event_wiring.evolution")


class EvolutionEventWiring(MethodWiringMixin):
    """Evolution域事件接线器  [v10-ready]

    包装 EvolutionLoop 的 record_action / tick，在其执行后发布进化域事件；
    并订阅 DeepSeek 决策事件与记忆固结事件以触发进化评估/沉淀。

    Usage:
        from core.shared.events import LocalEventBus
        bus = LocalEventBus()
        wiring = EvolutionEventWiring(evolution_loop, bus)
        evolution_loop.record_action(...)   # → 自动发布 evolution.param_tuned
        wiring.unwire()

    降级: event_bus=None(或 evolution_loop=None)时不包装、不订阅，行为完全不变。
    """

    DOMAIN = "evolution"

    def __init__(self, evolution_loop: Any, event_bus: Any = None, acl: Any = None) -> None:
        """初始化 Evolution 接线器  [v10-ready]

        Args:
            evolution_loop: EvolutionLoop 实例(需具备 record_action/tick)。
            event_bus: 事件总线(实现 publish/subscribe)，None 则降级透传。
            acl: 可选 AnticorruptionLayer，用于跨域触发的异步路由。
        """
        self._loop = evolution_loop
        self._bus = event_bus
        self._acl = acl
        self._init_wiring_state()
        # 统计
        self.deepseek_trigger_count: int = 0
        self.consolidated_trigger_count: int = 0
        self.evolution_events_published: int = 0

        if self._loop is None or self._bus is None:
            logger.debug("[EvolutionWiring] loop/bus 为空，降级为透传(无副作用)")
            return

        self._setup_publishers()
        self._setup_subscribers()

    def _setup_publishers(self) -> None:
        """包装 evolution_loop 方法，执行后发布事件  [v10-ready]"""
        self._wrap_after(self._loop, "record_action", self._after_record_action)
        self._wrap_after(self._loop, "tick", self._after_tick)

    def _setup_subscribers(self) -> None:
        """订阅触发进化的事件  [v10-ready]"""
        self._add_subscription(
            self._bus, DeepSeekEvents.DEEP_THOUGHT, self._on_deepseek
        )
        self._add_subscription(
            self._bus, DeepSeekEvents.EVOLUTION_TRIGGERED, self._on_deepseek
        )
        self._add_subscription(
            self._bus, MemoryEvents.CONSOLIDATED, self._on_consolidated
        )

    # ------------------------------------------------------------------
    # 发布回调
    # ------------------------------------------------------------------

    def _after_record_action(self, result: Any, args: tuple, kwargs: dict) -> None:
        """record_action 完成 → 发布 evolution.param_tuned(含因果上下文)  [v10-ready]"""
        pair = result
        action = getattr(pair, "action", None) or pick_arg(args, kwargs, 0, "action", "")
        state_before = getattr(pair, "state_before", None)
        if state_before is None:
            state_before = pick_arg(args, kwargs, 1, "state_before", {})
        state_after = getattr(pair, "state_after", None)
        if state_after is None:
            state_after = pick_arg(args, kwargs, 2, "state_after", {})
        module_name = getattr(pair, "module_name", "")
        try:
            effectiveness = round(float(getattr(pair, "effectiveness", 0.0)), 4)
        except (TypeError, ValueError):
            effectiveness = 0.0

        payload = EvolutionEventPayload(
            param_name=str(action),
            old_value=state_before,
            new_value=state_after,
            trigger=f"causal_pair:{module_name}:eff={effectiveness}",
        )
        safe_publish(self._bus, EvolutionEvents.PARAM_TUNED, payload, self.DOMAIN)
        self.evolution_events_published += 1

    def _after_tick(self, result: Any, args: tuple, kwargs: dict) -> None:
        """tick 完成 → 按进化结果发布 param_tuned/rule_added/arch_evolved  [v10-ready]"""
        if not result:
            return
        try:
            results = list(result)
        except TypeError:
            return
        for evo_result in results:
            self._publish_evolution_result(evo_result)

    def _publish_evolution_result(self, evo_result: Any) -> None:
        """将单个 EvolutionResult 的变更项映射为进化域事件  [v10-ready]"""
        module_name = getattr(evo_result, "module_name", "")
        summary = getattr(evo_result, "summary", "")
        changes = (
            getattr(evo_result, "changes_made", None)
            or getattr(evo_result, "rules_modified", None)
            or []
        )
        if not changes:
            return
        for change in changes:
            if not isinstance(change, dict):
                continue
            event_type = self._classify_change(change)
            payload = EvolutionEventPayload(
                param_name=str(change.get("rule", change.get("name", ""))),
                old_value=change.get("old_value"),
                new_value=change.get("new_value"),
                trigger=f"evolve:{module_name}:{str(summary)[:120]}",
            )
            safe_publish(self._bus, event_type, payload, self.DOMAIN)
            self.evolution_events_published += 1

    @staticmethod
    def _classify_change(change: dict) -> str:
        """将变更项分类为具体进化事件类型  [v10-ready]

        启发式:
        - 架构级(arch / architecture)       → ARCH_EVOLVED
        - 新增规则(is_new / add / rule_added) → RULE_ADDED
        - 其余参数调优                        → PARAM_TUNED
        """
        ctype = str(change.get("type", "")).lower()
        name = str(change.get("rule", change.get("name", ""))).lower()
        level = str(change.get("level", "")).lower()
        if "arch" in ctype or "arch" in name or level in ("architecture", "arch"):
            return EvolutionEvents.ARCH_EVOLVED
        if (
            change.get("is_new")
            or change.get("new_rule")
            or "add" in ctype
            or ctype == "rule_added"
        ):
            return EvolutionEvents.RULE_ADDED
        return EvolutionEvents.PARAM_TUNED

    # ------------------------------------------------------------------
    # 订阅处理
    # ------------------------------------------------------------------

    def _on_deepseek(self, event: DomainEvent) -> None:
        """DeepSeek 决策事件 → 触发进化评估(best-effort, 非阻塞)  [v10-ready]"""
        self.deepseek_trigger_count += 1
        self._trigger_loop_tick(
            src="deepseek", reason=getattr(event, "event_type", "deepseek")
        )

    def _on_consolidated(self, event: DomainEvent) -> None:
        """记忆固结事件 → 触发沉淀(best-effort, 非阻塞)  [v10-ready]"""
        self.consolidated_trigger_count += 1
        self._trigger_loop_tick(src="memory", reason="memory.consolidated")

    def _trigger_loop_tick(self, src: str = "", reason: str = "") -> None:
        """触发 evolution_loop.tick()(优先经 ACL 路由, 否则线程池异步)  [v10-ready]

        注: tick 已被包装，其内部产生的进化变更会经 _after_tick 自动发布事件；
        本触发不会回环到本模块订阅的 DeepSeek/Memory 事件，故无递归风险。
        """
        if self._acl is not None and hasattr(self._acl, "call_async"):
            try:
                self._acl.call_async(src or "deepseek", "evolution", "tick", reason=reason)
                return
            except Exception as exc:  # noqa: BLE001 — ACL 失败降级为直接 tick
                logger.debug("[EvolutionWiring] ACL 路由失败, 降级: %s", exc)

        loop = self._loop
        if loop is None or not hasattr(loop, "tick"):
            return

        def _do() -> None:
            try:
                loop.tick()
            except Exception as exc:  # noqa: BLE001 — 触发绝不影响主业务
                logger.debug("[EvolutionWiring] 触发 tick 失败(%s): %s", reason, exc)

        try:
            get_dispatch_executor().submit(_do)
        except Exception as exc:  # noqa: BLE001 — 线程池异常降级为同步
            logger.debug("[EvolutionWiring] 异步 tick 降级为同步: %s", exc)
            _do()


class GovernanceEventWiring(MethodWiringMixin):
    """Governance域事件接线器  [v10-ready]

    包装 GovernancePipeline 的 plan / audit / approve，在其执行后发布治理域事件；
    并订阅架构演化事件以观测进化对治理的影响。

    Usage:
        from core.shared.events import LocalEventBus
        bus = LocalEventBus()
        wiring = GovernanceEventWiring(pipeline, bus)
        pipeline.audit(module_def)   # → 自动发布 governance.audit_completed
        wiring.unwire()

    降级: event_bus=None(或 governance=None)时不包装、不订阅，行为完全不变。
    """

    DOMAIN = "governance"

    def __init__(self, governance: Any = None, event_bus: Any = None, acl: Any = None) -> None:
        """初始化 Governance 接线器  [v10-ready]

        Args:
            governance: GovernancePipeline 实例(需具备 plan/audit/approve)。
            event_bus: 事件总线(实现 publish/subscribe)，None 则降级透传。
            acl: 可选 AnticorruptionLayer。
        """
        self._gov = governance
        self._bus = event_bus
        self._acl = acl
        self._init_wiring_state()
        # 统计
        self.arch_evolved_count: int = 0

        if self._gov is None or self._bus is None:
            logger.debug("[GovernanceWiring] governance/bus 为空，降级为透传(无副作用)")
            return

        self._setup_publishers()
        self._setup_subscribers()

    def _setup_publishers(self) -> None:
        """包装 governance 方法，执行后发布事件  [v10-ready]"""
        self._wrap_after(self._gov, "plan", self._after_plan)
        self._wrap_after(self._gov, "audit", self._after_audit)
        self._wrap_after(self._gov, "approve", self._after_approve)

    def _setup_subscribers(self) -> None:
        """订阅进化域事件以观测治理影响  [v10-ready]"""
        self._add_subscription(
            self._bus, EvolutionEvents.ARCH_EVOLVED, self._on_arch_evolved
        )

    # ------------------------------------------------------------------
    # 发布回调
    # ------------------------------------------------------------------

    def _after_plan(self, result: Any, args: tuple, kwargs: dict) -> None:
        """plan 完成 → 发布 governance.plan_created  [v10-ready]"""
        plan_id = str(
            getattr(result, "pipeline_id", "") or getattr(result, "record_id", "")
        )
        status = getattr(result, "overall_status", "")
        status = getattr(status, "value", status)
        payload = GovernanceEventPayload(
            plan_id=plan_id,
            audit_type="plan",
            result=str(status),
            details={"module_id": str(getattr(result, "module_id", ""))},
        )
        safe_publish(self._bus, GovernanceEvents.PLAN_CREATED, payload, self.DOMAIN)

    def _after_audit(self, result: Any, args: tuple, kwargs: dict) -> None:
        """audit 完成 → 发布 governance.audit_completed  [v10-ready]"""
        verdict = getattr(result, "verdict", "")
        verdict = getattr(verdict, "value", verdict)
        payload = GovernanceEventPayload(
            plan_id=str(getattr(result, "report_id", "")),
            audit_type="module_audit",
            result=str(verdict),
            details={
                "module_id": str(getattr(result, "module_id", "")),
                "summary": getattr(result, "summary", {}) or {},
            },
        )
        safe_publish(self._bus, GovernanceEvents.AUDIT_COMPLETED, payload, self.DOMAIN)

    def _after_approve(self, result: Any, args: tuple, kwargs: dict) -> None:
        """approve 完成 → 发布 governance.approved  [v10-ready]"""
        if isinstance(result, dict):
            approved = bool(result.get("approved"))
            details = dict(result)
        else:
            approved = bool(result)
            details = {"raw": str(result)}
        payload = GovernanceEventPayload(
            plan_id=str(details.get("record_id", "")),
            audit_type="approval",
            result="approved" if approved else "rejected",
            details=details,
        )
        safe_publish(self._bus, GovernanceEvents.APPROVED, payload, self.DOMAIN)

    # ------------------------------------------------------------------
    # 订阅处理
    # ------------------------------------------------------------------

    def _on_arch_evolved(self, event: DomainEvent) -> None:
        """架构演化事件 → 观测计数(供治理后续审计参考)  [v10-ready]"""
        self.arch_evolved_count += 1
        logger.debug(
            "[GovernanceWiring] 收到架构演化事件(累计 %d)", self.arch_evolved_count
        )


# ============================================================================
# 一键接线工厂  [v10-ready]
# ============================================================================
def wire_evolution_domain(
    evolution_loop: Any = None,
    governance: Any = None,
    event_bus: Any = None,
    acl: Any = None,
) -> dict[str, Any]:
    """进化/治理域一键接线工厂  [v10-ready]

    为传入的 evolution_loop / governance 叠加事件接线。任一组件为 None 时
    跳过该域；event_bus 为 None 时各 Wiring 退化为透传(仍返回实例，便于统一管理)。

    Args:
        evolution_loop: EvolutionLoop 实例 (可选)。
        governance: GovernancePipeline 实例 (可选)。
        event_bus: 事件总线实例；None 则透传。
        acl: 可选 AnticorruptionLayer。

    Returns:
        dict: {"evolution": ..., "governance": ...} 仅含成功接线的域。
    """
    wirings: dict[str, Any] = {}
    if evolution_loop is not None:
        wirings["evolution"] = EvolutionEventWiring(evolution_loop, event_bus, acl=acl)
    if governance is not None:
        wirings["governance"] = GovernanceEventWiring(governance, event_bus, acl=acl)
    return wirings


__all__ = [
    "EvolutionEventWiring",
    "GovernanceEventWiring",
    "wire_evolution_domain",
]
