r"""
天机模块注册中心 (Tianji Module Registry) v1.1
===============================================
Phase 2 治理机制建设 — 核心里程碑

M20升级: EvolutionLoop闭环 + record_action喂入 + health() + 双注入
灵境道谱溯源: D6-2【生命周期煞】· 道六·容器体 · 四地煞之容之术
  - S0需求→S1架构→S2开发→S3测试→S4集成→S5运维 全生命周期管理
  - 源文件: core/module_registry.py → ModuleRegistry + ModuleLifecycleState

职责:
  1. 统一管理所有38个模块的定义、依赖、生命周期
  2. 提供模块发现、查询、健康检查接口
  3. 与EvolutionBus集成实现模块间联动进化

设计原则:
  - 单一职责: 仅负责模块注册与查询，不负责执行
  - 高内聚低耦合: 内部维护完整的模块图，对外暴露最小接口
  - 可执行架构: 模块定义即文档，可静态验证

参考:
  - Spring Modulith 模块化单体架构
  - 天机进化闭环协议 v1.0
  - 专业级模块化方案 (TMD-Spec v1.0)
"""

import time
import json
import threading
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List, Set, Tuple, Callable
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)

try:
    from ..processors.evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


class ModuleLifecycleState(str, Enum):
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    RETIRED = "retired"


class ModuleTier(str, Enum):
    CORE_ENGINE = "core_engine"
    BRAIN_INTELLIGENCE = "brain_intelligence"
    ENFORCEMENT_COMPLIANCE = "enforcement_compliance"
    SCHEDULING_ORCHESTRATION = "scheduling_orchestration"
    LEARNING_EVOLUTION = "learning_evolution"
    INFRASTRUCTURE_FOUNDATION = "infrastructure_foundation"
    ADAPTER_INDEXING_LLM = "adapter_indexing_llm"


class ModuleType(str, Enum):
    ENGINE = "engine"
    DRIVER = "driver"
    MANAGER = "manager"
    SCHEDULER = "scheduler"
    GATEWAY = "gateway"
    REGISTRY = "registry"
    HOOK = "hook"
    LOOP = "loop"
    PIPELINE = "pipeline"
    ORCHESTRATOR = "orchestrator"
    CAPTURE = "capture"
    QUALITY_GATE = "quality_gate"
    ADAPTER = "adapter"
    BRIDGE = "bridge"
    CLIENT = "client"
    SERVICE = "service"
    AGENT = "agent"
    INDEXER = "indexer"
    DAEMON = "daemon"
    CHECKER = "checker"


class DependencyType(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    RUNTIME = "runtime"
    WEAK = "weak"


class AuditStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"


@dataclass
class ModuleDependency:
    target_module: str
    dependency_type: DependencyType = DependencyType.REQUIRED
    version_constraint: str = "^1.0.0"
    description: str = ""
    interface_used: List[str] = field(default_factory=list)


@dataclass
class MethodSignature:
    name: str
    params: List[str] = field(default_factory=list)
    returns: str = "None"
    description: str = ""


@dataclass
class EventDef:
    name: str
    event_type: str = "custom"
    description: str = ""


@dataclass
class HealthMetricDef:
    metric_name: str
    unit: str = "%"
    warn_threshold: float = 0.7
    critical_threshold: float = 0.9
    is_inverse: bool = False


@dataclass
class AuditRecord:
    audit_id: str
    module_id: str
    check_type: str
    status: AuditStatus = AuditStatus.PENDING
    score: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    auditor: str = "system"


@dataclass
class TianjiModuleDefinition:
    module_id: str
    module_name: str
    display_name: str
    module_version: str = "1.0.0"
    tier: ModuleTier = ModuleTier.CORE_ENGINE
    module_type: ModuleType = ModuleType.ENGINE
    domain: str = ""
    subdomain: Optional[str] = None
    responsibility: str = ""
    capabilities: List[str] = field(default_factory=list)
    anti_responsibilities: List[str] = field(default_factory=list)
    dependencies: List[ModuleDependency] = field(default_factory=list)
    public_api: List[MethodSignature] = field(default_factory=list)
    events_published: List[EventDef] = field(default_factory=list)
    events_subscribed: List[EventDef] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    lifecycle_state: ModuleLifecycleState = ModuleLifecycleState.UNREGISTERED
    health_metrics: List[HealthMetricDef] = field(default_factory=list)
    health_status: str = "unknown"
    last_health_check: float = 0.0
    owner: str = "tianji_core_team"
    criticality: str = "medium"
    evolution_enabled: bool = True
    evolution_loop_ref: Optional[Any] = None
    instance_ref: Optional[Any] = None
    stats_fn: Optional[Callable] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    audit_records: List[AuditRecord] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "module_id": self.module_id,
            "module_name": self.module_name,
            "display_name": self.display_name,
            "module_version": self.module_version,
            "tier": self.tier.value,
            "module_type": self.module_type.value,
            "domain": self.domain,
            "subdomain": self.subdomain,
            "responsibility": self.responsibility,
            "capabilities": self.capabilities,
            "anti_responsibilities": self.anti_responsibilities,
            "dependencies": [
                {"target": d.target_module, "type": d.dependency_type.value,
                 "version": d.version_constraint, "description": d.description}
                for d in self.dependencies
            ],
            "public_api": [
                {"name": a.name, "params": a.params, "returns": a.returns, "description": a.description}
                for a in self.public_api
            ],
            "events_published": [{"name": e.name, "type": e.event_type} for e in self.events_published],
            "events_subscribed": [{"name": e.name, "type": e.event_type} for e in self.events_subscribed],
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "lifecycle_state": self.lifecycle_state.value,
            "health_status": self.health_status,
            "health_metrics": [
                {"name": h.metric_name, "unit": h.unit, "warn": h.warn_threshold, "critical": h.critical_threshold}
                for h in self.health_metrics
            ],
            "last_health_check": self.last_health_check,
            "owner": self.owner,
            "criticality": self.criticality,
            "evolution_enabled": self.evolution_enabled,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "audit_count": len(self.audit_records),
        }

    def add_audit_record(self, record: AuditRecord):
        self.audit_records.append(record)
        self.updated_at = time.time()


class ModuleRegistry:
    """
    天机模块注册中心 — 集中管理所有模块

    功能:
      1. 模块注册/注销/查询
      2. 依赖图构建与验证
      3. 生命周期状态管理
      4. 健康检查聚合
      5. 审计记录追踪
      6. 与EvolutionBus集成
    """

    def __init__(self, recorder: Optional[Any] = None,
                 learning_engine: Optional[Any] = None):
        self._modules: Dict[str, TianjiModuleDefinition] = {}
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()
        self._evolution_bus = None
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._stats = {
            "total_registered": 0,
            "total_active": 0,
            "total_degraded": 0,
            "total_errors": 0,
            "registrations": 0,
            "deregistrations": 0,
            "health_checks": 0,
            "start_time": time.time(),
        }

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="module_registry",
                    effectiveness_fn=self._calc_registry_effectiveness,
                    learn_fn=self._learn_from_registry,
                    evolve_fn=self._evolve_registry_config,
                    mutable_config={
                        "circular_dep_warn_threshold": 1,
                        "health_check_interval": 300.0,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception as e:
                logger.warning(f"ModuleRegistry EvolutionLoop init failed: {e}")

    def register(self, definition: TianjiModuleDefinition) -> bool:
        with self._lock:
            if definition.module_id in self._modules:
                logger.warning(f"模块 '{definition.module_id}' 已注册，执行更新")
                self._update_existing(definition)
                return True

            definition.lifecycle_state = ModuleLifecycleState.REGISTERED
            self._modules[definition.module_id] = definition
            self._build_dependency_edges(definition)
            self._stats["total_registered"] += 1
            self._stats["registrations"] += 1
            logger.info(f"[ModuleRegistry] 注册模块: {definition.module_id} ({definition.module_name})")

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="register_module",
                        state_before={"total_registered": self._stats["total_registered"] - 1},
                        state_after={"total_registered": self._stats["total_registered"],
                                     "module_id": definition.module_id,
                                     "module_type": definition.module_type.value},
                    )
                except Exception:
                    pass

            return True

    def unregister(self, module_id: str) -> bool:
        with self._lock:
            if module_id not in self._modules:
                return False
            definition = self._modules[module_id]
            self._remove_dependency_edges(definition)
            definition.lifecycle_state = ModuleLifecycleState.RETIRED
            self._stats["total_registered"] -= 1
            self._stats["deregistrations"] += 1
            logger.info(f"[ModuleRegistry] 注销模块: {module_id}")

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="unregister_module",
                        state_before={"total_registered": self._stats["total_registered"] + 1},
                        state_after={"total_registered": self._stats["total_registered"],
                                     "module_id": module_id},
                    )
                except Exception:
                    pass

            return True

    def get(self, module_id: str) -> Optional[TianjiModuleDefinition]:
        with self._lock:
            return self._modules.get(module_id)

    def get_definition(self, module_id: str) -> Optional[Dict[str, Any]]:
        m = self.get(module_id)
        if m is None:
            return None
        return m.to_dict()

    def get_all_definitions(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [m.to_dict() for m in self._modules.values()]

    def get_by_name(self, module_name: str) -> Optional[TianjiModuleDefinition]:
        with self._lock:
            for m in self._modules.values():
                if m.module_name == module_name:
                    return m
            return None

    def list_all(self) -> List[TianjiModuleDefinition]:
        with self._lock:
            return list(self._modules.values())

    def list_by_tier(self, tier: ModuleTier) -> List[TianjiModuleDefinition]:
        with self._lock:
            return [m for m in self._modules.values() if m.tier == tier]

    def list_by_type(self, module_type: ModuleType) -> List[TianjiModuleDefinition]:
        with self._lock:
            return [m for m in self._modules.values() if m.module_type == module_type]

    def list_by_state(self, state: ModuleLifecycleState) -> List[TianjiModuleDefinition]:
        with self._lock:
            return [m for m in self._modules.values() if m.lifecycle_state == state]

    def list_by_health(self, health: str) -> List[TianjiModuleDefinition]:
        with self._lock:
            return [m for m in self._modules.values() if m.health_status == health]

    def update_state(self, module_id: str, state: ModuleLifecycleState) -> bool:
        with self._lock:
            m = self._modules.get(module_id)
            if not m:
                return False
            m.lifecycle_state = state
            m.updated_at = time.time()
            self._refresh_stats()
            return True

    def update_health(self, module_id: str, status: str, metrics: Dict[str, float] = None) -> bool:
        with self._lock:
            m = self._modules.get(module_id)
            if not m:
                return False
            m.health_status = status
            m.last_health_check = time.time()
            m.updated_at = time.time()
            self._refresh_stats()
            return True

    def bind_instance(self, module_id: str, instance: Any, stats_fn: Callable = None) -> bool:
        with self._lock:
            m = self._modules.get(module_id)
            if not m:
                return False
            m.instance_ref = instance
            m.stats_fn = stats_fn
            m.lifecycle_state = ModuleLifecycleState.ACTIVE
            m.updated_at = time.time()
            self._refresh_stats()

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="bind_instance",
                        state_before={"total_active": self._stats["total_active"] - 1},
                        state_after={"total_active": self._stats["total_active"],
                                     "module_id": module_id},
                    )
                except Exception:
                    pass

            return True

    def get_dependencies(self, module_id: str) -> List[TianjiModuleDefinition]:
        with self._lock:
            deps = self._dependency_graph.get(module_id, set())
            return [self._modules[d] for d in deps if d in self._modules]

    def get_dependents(self, module_id: str) -> List[TianjiModuleDefinition]:
        with self._lock:
            deps = self._reverse_dependency_graph.get(module_id, set())
            return [self._modules[d] for d in deps if d in self._modules]

    def find_circular_dependencies(self) -> List[List[str]]:
        with self._lock:
            cycles = []
            visited = set()
            stack = []

            def dfs(node: str):
                if node in stack:
                    cycle_start = stack.index(node)
                    cycles.append(stack[cycle_start:] + [node])
                    return
                if node in visited:
                    return
                visited.add(node)
                stack.append(node)
                for neighbor in self._dependency_graph.get(node, set()):
                    dfs(neighbor)
                stack.pop()

            for node in self._dependency_graph:
                dfs(node)
            return cycles

    def get_module_graph(self) -> Dict[str, Any]:
        with self._lock:
            nodes = []
            edges = []
            for m in self._modules.values():
                nodes.append({
                    "id": m.module_id,
                    "name": m.module_name,
                    "tier": m.tier.value,
                    "type": m.module_type.value,
                    "state": m.lifecycle_state.value,
                    "health": m.health_status,
                })
            for src, targets in self._dependency_graph.items():
                for tgt in targets:
                    if src in self._modules and tgt in self._modules:
                        dep = next(
                            (d for d in self._modules[src].dependencies if d.target_module == tgt),
                            None
                        )
                        edges.append({
                            "source": src,
                            "target": tgt,
                            "type": dep.dependency_type.value if dep else "unknown",
                        })
            return {"nodes": nodes, "edges": edges, "total": len(nodes)}

    def get_stats(self) -> Dict:
        with self._lock:
            self._refresh_stats()
            tier_distribution = defaultdict(int)
            type_distribution = defaultdict(int)
            for m in self._modules.values():
                tier_distribution[m.tier.value] += 1
                type_distribution[m.module_type.value] += 1
            return {
                **self._stats,
                "tier_distribution": dict(tier_distribution),
                "type_distribution": dict(type_distribution),
                "circular_dependencies": len(self.find_circular_dependencies()),
                "total_modules": len(self._modules),
            }

    def get_unified_stats(self) -> Dict[str, Any]:
        r"""统一信封格式收集所有已注册模块的统计信息

        返回格式::
          {
            "schema_version": "1.0.0",
            "generated_at": <timestamp>,
            "summary": { "total_modules": N, "active": N, "degraded": N, "error": N },
            "modules": {
              "<module_id>": {
                "definition": { ... TianjiModuleDefinition.to_dict() ... },
                "stats": { ... 模块自身 get_stats() 返回值 ... },
                "lifecycle": { "state": "...", "health": "..." },
              }
            }
          }
        """
        with self._lock:
            self._refresh_stats()
            modules_data = {}
            for m in self._modules.values():
                raw_stats = {}
                if m.stats_fn:
                    try:
                        raw_stats = m.stats_fn()
                    except Exception:
                        raw_stats = {"_error": "stats_fn调用失败"}
                elif m.instance_ref and hasattr(m.instance_ref, 'get_stats'):
                    try:
                        raw_stats = m.instance_ref.get_stats()
                    except Exception:
                        raw_stats = {"_error": "instance.get_stats()调用失败"}

                modules_data[m.module_id] = {
                    "definition": m.to_dict(),
                    "stats": raw_stats,
                    "lifecycle": {
                        "state": m.lifecycle_state.value,
                        "health": m.health_status,
                        "last_health_check": m.last_health_check,
                    },
                }

            return {
                "schema_version": "1.0.0",
                "generated_at": time.time(),
                "summary": {
                    "total_modules": len(self._modules),
                    "active": self._stats["total_active"],
                    "degraded": self._stats["total_degraded"],
                    "errors": self._stats["total_errors"],
                },
                "modules": modules_data,
            }

    def set_evolution_bus(self, bus: Any):
        self._evolution_bus = bus

    def validate_dependencies(self) -> List[Dict[str, Any]]:
        with self._lock:
            issues = []
            for module_id, definition in self._modules.items():
                for dep in definition.dependencies:
                    if dep.target_module not in self._modules:
                        issues.append({
                            "module_id": module_id,
                            "target": dep.target_module,
                            "type": dep.dependency_type.value,
                            "issue": "missing",
                            "message": f"依赖模块 '{dep.target_module}' 未在注册中心注册",
                        })
                    else:
                        target_def = self._modules[dep.target_module]
                        if target_def.lifecycle_state in (ModuleLifecycleState.UNREGISTERED, ModuleLifecycleState.RETIRED):
                            issues.append({
                                "module_id": module_id,
                                "target": dep.target_module,
                                "type": dep.dependency_type.value,
                                "issue": "unavailable",
                                "message": f"依赖模块 '{dep.target_module}' 状态为 {target_def.lifecycle_state.value}",
                            })
            return issues

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            results = {}
            for module_id, definition in self._modules.items():
                results[module_id] = {
                    "state": definition.lifecycle_state.value,
                    "health": definition.health_status,
                    "last_check": definition.last_health_check,
                    "metrics": {h.metric_name: "unknown" for h in definition.health_metrics},
                }
            return results

    def export_module_manifest(self, output_path: str = None) -> Dict[str, Any]:
        with self._lock:
            manifest = {
                "schema_version": "1.0.0",
                "generated_at": time.time(),
                "summary": {
                    "total_registered": self._stats["total_registered"],
                    "total_active": self._stats["total_active"],
                    "total_degraded": self._stats["total_degraded"],
                    "total_errors": self._stats["total_errors"],
                },
                "modules": [m.to_dict() for m in self._modules.values()],
                "dependency_graph": self.get_module_graph(),
                "circular_dependencies": self.find_circular_dependencies(),
            }
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, ensure_ascii=False, indent=2, default=str)
            return manifest

    def _build_dependency_edges(self, definition: TianjiModuleDefinition):
        self._dependency_graph[definition.module_id] = set()
        for dep in definition.dependencies:
            self._dependency_graph[definition.module_id].add(dep.target_module)
            self._reverse_dependency_graph[dep.target_module].add(definition.module_id)

    def _remove_dependency_edges(self, definition: TianjiModuleDefinition):
        self._dependency_graph.pop(definition.module_id, None)
        for targets in self._reverse_dependency_graph.values():
            targets.discard(definition.module_id)

    def _update_existing(self, new_def: TianjiModuleDefinition):
        old_def = self._modules[new_def.module_id]
        self._remove_dependency_edges(old_def)
        new_def.lifecycle_state = old_def.lifecycle_state
        new_def.created_at = old_def.created_at
        new_def.audit_records = old_def.audit_records
        new_def.instance_ref = old_def.instance_ref
        new_def.stats_fn = old_def.stats_fn
        self._modules[new_def.module_id] = new_def
        self._build_dependency_edges(new_def)

    def health(self) -> Dict[str, Any]:
        with self._lock:
            self._refresh_stats()
            return {
                "status": "healthy" if self._stats["total_errors"] == 0 else "degraded",
                "version": "1.1",
                "total_modules": len(self._modules),
                "total_registered": self._stats["total_registered"],
                "total_active": self._stats["total_active"],
                "total_degraded": self._stats["total_degraded"],
                "total_errors": self._stats["total_errors"],
                "circular_dependencies": len(self.find_circular_dependencies()),
                "evo_loop_active": self._evo_loop is not None,
                "recorder_attached": self._recorder is not None,
                "evolution_bus_attached": self._evolution_bus is not None,
                "registrations": self._stats["registrations"],
                "deregistrations": self._stats["deregistrations"],
            }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_registry_effectiveness(self, action: str,
                                      state_before: Dict[str, Any],
                                      state_after: Dict[str, Any]) -> float:
        if action == "register_module":
            delta = state_after.get("total_registered", 0) - state_before.get("total_registered", 0)
            return min(0.6, delta * 0.3) if delta > 0 else 0.0
        elif action == "unregister_module":
            return 0.2
        elif action == "bind_instance":
            delta = state_after.get("total_active", 0) - state_before.get("total_active", 0)
            return min(0.5, delta * 0.25) if delta > 0 else 0.0
        return 0.0

    def _learn_from_registry(self, causal_pairs: List[Any],
                              effectiveness_summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "module_count": len(self._modules),
            "active_ratio": (
                self._stats["total_active"] / max(self._stats["total_registered"], 1)
            ),
        }

    def _evolve_registry_config(self, learn_result: Dict[str, Any],
                                 mutable_config: Dict[str, Any]) -> Dict[str, Any]:
        changes = {}
        avg_eff = learn_result.get("avg_effectiveness", 0.0)
        if avg_eff < -0.2:
            changes["health_check_interval"] = min(600,
                mutable_config.get("health_check_interval", 300) + 60)
        if avg_eff > 0.3 and mutable_config.get("health_check_interval", 300) > 120:
            changes["health_check_interval"] = max(120,
                mutable_config.get("health_check_interval", 300) - 60)
        return {"rules_modified": changes, "skills_created": []}

    def _refresh_stats(self):
        self._stats["total_registered"] = sum(
            1 for m in self._modules.values()
            if m.lifecycle_state not in (ModuleLifecycleState.UNREGISTERED, ModuleLifecycleState.RETIRED)
        )
        self._stats["total_active"] = sum(
            1 for m in self._modules.values() if m.lifecycle_state == ModuleLifecycleState.ACTIVE
        )
        self._stats["total_degraded"] = sum(
            1 for m in self._modules.values() if m.lifecycle_state == ModuleLifecycleState.DEGRADED
        )
        self._stats["total_errors"] = sum(
            1 for m in self._modules.values() if m.lifecycle_state == ModuleLifecycleState.ERROR
        )


DEFAULT_MODULE_REGISTRY = ModuleRegistry()


def get_module_registry() -> ModuleRegistry:
    return DEFAULT_MODULE_REGISTRY
