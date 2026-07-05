# -*- coding: utf-8-sig -*-
"""core/event_wiring 子包 — 领域事件接线层  [v10-ready]

在不修改既有领域实现的前提下，于其上层叠加 EventBus 事件发布/订阅能力，
将跨域直接耦合渐进式转换为事件驱动通信(v10 事件驱动过渡)。

包含两类接线:
- 核心域 (Task #38): engine / driver / gate
- 次要域 (Task #39): orchestration / scheduling / search

设计要点:
- 不侵入原模块，纯上层包装(instance method monkey-patch)
- 降级友好: event_bus=None 时各 Wiring 均为透传
- 线程安全 + 幂等 wire/unwire
- 防腐: 可选注入 AnticorruptionLayer

注: 核心域接线模块按可用性 **可选导入**，缺失时不影响次要域接线使用。

版本: 1.0.0
"""
from __future__ import annotations

from typing import Any

# ============================================================================
# 次要域接线 (Task #39) — orchestration / scheduling / search
# ============================================================================
from core.event_wiring.orchestration_wiring import (
    OrchestrationEventWiring,
    wire_orchestration,
)
from core.event_wiring.scheduling_wiring import (
    SchedulingEventWiring,
    wire_scheduling,
)
from core.event_wiring.search_wiring import (
    SearchEventWiring,
    wire_search,
)

__all__ = [
    # ---- 次要域 Wiring (Task #39) ----
    "OrchestrationEventWiring",
    "SchedulingEventWiring",
    "SearchEventWiring",
    "wire_orchestration",
    "wire_scheduling",
    "wire_search",
    "wire_secondary_domains",
    "wire_core_domains",
    "wire_all_domains",
]

# ============================================================================
# 记忆域接线 (v9.1新增) — writer / promoter / archiver / indexer
# 可选导入，缺失时静默降级
# ============================================================================
_MEMORY_WIRING_AVAILABLE = False
try:
    from core.event_wiring.memory_wiring import (  # noqa: F401
        MemoryEventWiring,
        wire_memory,
    )

    __all__.extend(["MemoryEventWiring", "wire_memory"])
    _MEMORY_WIRING_AVAILABLE = True
except Exception:  # noqa: BLE001 — 记忆域未就绪时不阻断其他域
    pass

# ============================================================================
# 核心域接线 (Task #38) — 可选导入，缺失时静默降级
# ============================================================================
_CORE_DOMAIN_READY = False
try:  # engine / driver 由 Task #38 提供
    from core.event_wiring.engine_wiring import (  # noqa: F401
        EngineEventWiring,
        MethodWiringMixin,
        safe_publish,
        pick_arg,
        get_dispatch_executor,
    )
    from core.event_wiring.driver_wiring import DriverEventWiring  # noqa: F401

    __all__.extend(
        [
            "EngineEventWiring",
            "DriverEventWiring",
            "MethodWiringMixin",
            "safe_publish",
            "pick_arg",
            "get_dispatch_executor",
        ]
    )
    _CORE_DOMAIN_READY = True
except Exception:  # noqa: BLE001 — 核心域尚未就绪时不阻断次要域
    pass

try:  # gate 接线 (若 Task #38 提供)
    from core.event_wiring.gate_wiring import GateEventWiring  # noqa: F401

    __all__.append("GateEventWiring")
except Exception:  # noqa: BLE001
    _CORE_DOMAIN_READY = False


# ============================================================================
# 次要域一键接线工厂 (Task #39)
# ============================================================================
def wire_secondary_domains(
    orchestrator: Any = None,
    scheduler: Any = None,
    retriever: Any = None,
    event_bus: Any = None,
    acl: Any = None,
) -> dict[str, Any]:
    """一键接线次要域(orchestration / scheduling / search)  [v10-ready]

    为传入的各域组件叠加事件接线。任一组件为 None 时跳过该域；
    event_bus 为 None 时各 Wiring 退化为透传(仍返回实例，便于统一管理)。

    Args:
        orchestrator: AgentScheduler/AgentOrchestrator 实例 (可选)。
        scheduler: TianjiIntelligentScheduler/IntelligentScheduler 实例 (可选)。
        retriever: FusionRetriever/FusionRetrievalStrategy 实例 (可选)。
        event_bus: 事件总线实例；None 则透传。
        acl: 可选 AnticorruptionLayer。

    Returns:
        dict: {"orchestration": ..., "scheduling": ..., "search": ...}
              仅包含成功接线的域(对应组件非 None)。
    """
    wirings: dict[str, Any] = {}
    if orchestrator is not None:
        wirings["orchestration"] = wire_orchestration(orchestrator, event_bus, acl=acl)
    if scheduler is not None:
        wirings["scheduling"] = wire_scheduling(scheduler, event_bus, acl=acl)
    if retriever is not None:
        wirings["search"] = wire_search(retriever, event_bus, acl=acl)
    return wirings


# ============================================================================
# 核心域一键接线工厂 (Task #38) — 降级友好重建
# ============================================================================
def wire_core_domains(
    engine: Any = None,
    driver: Any = None,
    gate: Any = None,
    event_bus: Any = None,
    acl: Any = None,
) -> dict[str, Any]:
    """一键接线核心域(engine / driver / gate)  [v10-ready]

    为传入的各核心域组件叠加事件接线。任一组件为 None 或对应接线类
    未就绪时跳过该域；event_bus 为 None 时各 Wiring 退化为透传。

    注: 本工厂为降级友好重建版 — 依赖 Task #38 的 Engine/Driver/Gate 接线类。
    若核心域模块未就绪则返回空字典。

    Args:
        engine: ICMEEngine 实例 (可选)。
        driver: DeepSeekDriver 实例 (可选)。
        gate: QualityGate 实例 (可选)。
        event_bus: 事件总线实例；None 则透传。
        acl: 可选 AnticorruptionLayer。

    Returns:
        dict: {"engine": ..., "driver": ..., "gate": ...}
              仅包含成功接线的域。
    """
    wirings: dict[str, Any] = {}
    if not _CORE_DOMAIN_READY:
        return wirings
    if engine is not None:
        wirings["engine"] = EngineEventWiring(engine, event_bus, acl=acl)
    if driver is not None:
        wirings["driver"] = DriverEventWiring(driver, event_bus, acl=acl)
    if gate is not None:
        wirings["gate"] = GateEventWiring(gate, event_bus, acl=acl)
    return wirings


# ============================================================================
# 全域一键接线工厂 (v9.1) — 核心域 + 次要域 + 记忆域
# ============================================================================
def wire_all_domains(
    engine: Any = None,
    driver: Any = None,
    gate: Any = None,
    event_bus: Any = None,
    acl: Any = None,
    # 次要域
    orchestrator: Any = None,
    scheduler: Any = None,
    retriever: Any = None,
    # v9.1: 记忆域
    memory_writer: Any = None,
    memory_promoter: Any = None,
    memory_archiver: Any = None,
    memory_indexer: Any = None,
) -> dict[str, Any]:
    """一键接线所有域(核心 + 次要 + 记忆)  [v10-ready]

    汇总核心域(engine/driver/gate)、次要域(orchestration/scheduling/search)
    与记忆域(writer/promoter/archiver/indexer)的事件接线。任一组件为 None
    时跳过该域；event_bus 为 None 时各 Wiring 退化为透传。

    Args:
        engine: ICMEEngine 实例 (可选)。
        driver: DeepSeekDriver 实例 (可选)。
        gate: QualityGate 实例 (可选)。
        event_bus: 事件总线实例；None 则透传。
        acl: 可选 AnticorruptionLayer。
        orchestrator: AgentScheduler/AgentOrchestrator 实例 (可选)。
        scheduler: IntelligentScheduler 实例 (可选)。
        retriever: FusionRetriever 实例 (可选)。
        memory_writer: MemoryWriter 实例 (可选)。
        memory_promoter: PromotionEngine 实例 (可选)。
        memory_archiver: ArchiveManager 实例 (可选)。
        memory_indexer: MemoryIndex 实例 (可选)。

    Returns:
        dict: 各域接线结果聚合，含 "memory" 子项(若记忆域可用)。
    """
    wirings: dict[str, Any] = {}
    wirings.update(wire_core_domains(engine, driver, gate, event_bus, acl) or {})
    wirings.update(
        wire_secondary_domains(orchestrator, scheduler, retriever, event_bus, acl) or {}
    )
    if _MEMORY_WIRING_AVAILABLE and event_bus is not None:
        wirings["memory"] = wire_memory(
            event_bus,
            memory_writer,
            memory_promoter,
            memory_archiver,
            memory_indexer,
            acl,
        )
    return wirings


# ============================================================================
# 进化/治理域接线 (Task #40) — evolution / governance
# ============================================================================
try:
    from core.event_wiring.evolution_wiring import (  # noqa: F401
        EvolutionEventWiring,
        GovernanceEventWiring,
        wire_evolution_domain,
    )

    __all__.extend(
        [
            "EvolutionEventWiring",
            "GovernanceEventWiring",
            "wire_evolution_domain",
        ]
    )
except Exception:  # noqa: BLE001 — 进化域未就绪时不阻断其他域
    pass
