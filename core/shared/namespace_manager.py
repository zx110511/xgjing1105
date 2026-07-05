"""
Agent命名空间管理 v1.1 - 集成自nexus-memory

M23升级: EvolutionLoop闭环 + record_action喂入 + health() + 双注入
灵境道谱溯源: D8-3【认知流水煞】· 道八·认知体道 · 四地煞之识之术
  - 20个Agent命名空间生命周期流水线管理
  - 源文件: core/namespace_manager.py → NamespaceManager

功能:
- 管理Agent命名空间的创建/查询/统计
- 隔离各Agent的记忆存储空间
- 与ICME引擎集成，为remember调用分配命名空间

对应Rust: nexus-storage/src/models.rs (AgentNamespaceRow)
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

try:
    from ..processors.evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


@dataclass
class AgentNamespace:
    id: str
    name: str
    description: str = ""
    agent_type: str = "general"
    created_at: float = field(default_factory=time.time)
    updated_at: Optional[float] = None
    memory_count: int = 0
    is_active: bool = True
    metadata: Dict = field(default_factory=dict)


@dataclass
class PerspectiveKey:
    observer: str = ""
    subject: str = ""
    session_key: Optional[str] = None


class NamespaceManager:
    def __init__(self, recorder: Optional[Any] = None,
                 learning_engine: Optional[Any] = None):
        self._namespaces: Dict[str, AgentNamespace] = {}
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._errors = 0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="namespace_manager",
                    effectiveness_fn=self._calc_ns_effectiveness,
                    learn_fn=self._learn_from_ns,
                    evolve_fn=self._evolve_ns_config,
                    mutable_config={
                        "default_agent_type": "general",
                        "max_namespaces": 100,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception:
                pass

        self._init_default_namespaces()

    def _init_default_namespaces(self):
        defaults = [
            ("general", "通用记忆空间", "general"),
            ("orchestrator", "编排器记忆空间", "orchestrator"),
            ("writer", "写手记忆空间", "writer"),
            ("reviewer", "审校记忆空间", "reviewer"),
            ("planner", "规划师记忆空间", "planner"),
            ("analyzer", "分析师记忆空间", "analyzer"),
            ("memory-architect", "记忆架构师记忆空间", "memory-architect"),
            ("corpus-miner", "语料矿工记忆空间", "corpus-miner"),
            ("test-verifier", "测试验证器记忆空间", "test-verifier"),
            ("version-keeper", "版本守卫记忆空间", "version-keeper"),
            ("editor", "主编记忆空间", "editor"),
            ("monitor", "监控器记忆空间", "monitor"),
            ("novel-formatter", "格式化器记忆空间", "novel-formatter"),
            ("context-extractor", "上下文提取器记忆空间", "context-extractor"),
            ("skill-invoker", "技能调度器记忆空间", "skill-invoker"),
            ("rule-evaluator", "规则评估器记忆空间", "rule-evaluator"),
            ("security-auditor", "安全审计师记忆空间", "security-auditor"),
            ("devops-engineer", "DevOps工程师记忆空间", "devops-engineer"),
            ("performance-optimizer", "性能优化师记忆空间", "performance-optimizer"),
            ("conversation-monitor", "对话监控器记忆空间", "conversation-monitor"),
        ]
        for name, desc, agent_type in defaults:
            self._namespaces[name] = AgentNamespace(
                id=str(uuid.uuid4())[:16],
                name=name,
                description=desc,
                agent_type=agent_type,
            )

    def get_or_create(self, name: str, agent_type: str = "general") -> AgentNamespace:
        is_new = name not in self._namespaces
        if is_new:
            self._namespaces[name] = AgentNamespace(
                id=str(uuid.uuid4())[:16],
                name=name,
                agent_type=agent_type,
            )
        ns = self._namespaces[name]
        ns.memory_count += 1
        ns.updated_at = time.time()

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="get_or_create",
                    state_before={"ns_count": len(self._namespaces) - (1 if is_new else 0)},
                    state_after={"ns_count": len(self._namespaces),
                                 "ns_name": name,
                                 "is_new": is_new,
                                 "agent_type": agent_type},
                )
            except Exception:
                pass

        return ns

    def get(self, name: str) -> Optional[AgentNamespace]:
        return self._namespaces.get(name)

    def list_all(self) -> List[AgentNamespace]:
        return list(self._namespaces.values())

    def list_active(self) -> List[AgentNamespace]:
        return [ns for ns in self._namespaces.values() if ns.is_active]

    def deactivate(self, name: str) -> bool:
        ns = self._namespaces.get(name)
        if ns:
            ns.is_active = False
            ns.updated_at = time.time()

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="deactivate",
                        state_before={"ns_name": name, "is_active": True},
                        state_after={"ns_name": name, "is_active": False,
                                     "memory_count": ns.memory_count},
                    )
                except Exception:
                    pass

            return True
        return False

    def activate(self, name: str) -> bool:
        ns = self._namespaces.get(name)
        if ns:
            ns.is_active = True
            ns.updated_at = time.time()

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="activate",
                        state_before={"ns_name": name, "is_active": False},
                        state_after={"ns_name": name, "is_active": True,
                                     "memory_count": ns.memory_count},
                    )
                except Exception:
                    pass

            return True
        return False

    def increment_memory(self, name: str) -> bool:
        ns = self._namespaces.get(name)
        if ns:
            before = ns.memory_count
            ns.memory_count += 1
            ns.updated_at = time.time()

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="increment_memory",
                        state_before={"ns_name": name, "memory_count": before},
                        state_after={"ns_name": name, "memory_count": ns.memory_count},
                    )
                except Exception:
                    pass

            return True
        return False

    def stats(self) -> dict:
        return {
            "total_namespaces": len(self._namespaces),
            "active_namespaces": len([ns for ns in self._namespaces.values() if ns.is_active]),
            "total_memories": sum(ns.memory_count for ns in self._namespaces.values()),
            "namespaces": {
                name: {
                    "agent_type": ns.agent_type,
                    "memory_count": ns.memory_count,
                    "is_active": ns.is_active,
                    "description": ns.description,
                    "created_at": ns.created_at,
                }
                for name, ns in self._namespaces.items()
            },
        }

    def get_namespace_for_agent(self, agent_type: str) -> AgentNamespace:
        for ns in self._namespaces.values():
            if ns.agent_type == agent_type and ns.is_active:
                return ns
        return self.get_or_create(agent_type, agent_type)

    def health(self) -> Dict[str, Any]:
        active = len([ns for ns in self._namespaces.values() if ns.is_active])
        return {
            "status": "ready",
            "version": "1.1",
            "total_namespaces": len(self._namespaces),
            "active_namespaces": active,
            "total_memories": sum(ns.memory_count for ns in self._namespaces.values()),
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
        }

    def get_stats(self) -> Dict[str, Any]:
        evo_stats = {}
        if self._evo_loop is not None:
            try:
                evo_stats = self._evo_loop.get_stats()
            except Exception:
                evo_stats = {"error": "evo_loop_stats_failed"}
        return {
            "version": "1.1",
            "ns_stats": self.stats(),
            "health": self.health(),
            "evo_loop": evo_stats,
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_ns_effectiveness(self, action: str,
                                state_before: Dict[str, Any],
                                state_after: Dict[str, Any]) -> float:
        if action == "get_or_create":
            return 0.7 if state_after.get("is_new", False) else 0.4
        elif action == "deactivate":
            return 0.5 if not state_after.get("is_active", True) else -0.1
        elif action == "activate":
            return 0.5 if state_after.get("is_active", False) else -0.1
        elif action == "increment_memory":
            growth = state_after.get("memory_count", 0) - state_before.get("memory_count", 0)
            return 0.3 if growth > 0 else 0.0
        return 0.0

    def _learn_from_ns(self, causal_pairs: List[Any],
                        effectiveness_summary: Dict[str, Any]) -> Dict[str, Any]:
        active = len([ns for ns in self._namespaces.values() if ns.is_active])
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "total_namespaces": len(self._namespaces),
            "active_namespaces": active,
            "total_memories": sum(ns.memory_count for ns in self._namespaces.values()),
        }

    def _evolve_ns_config(self, learn_result: Dict[str, Any],
                           mutable_config: Dict[str, Any]) -> Dict[str, Any]:
        changes = {}
        total_ns = learn_result.get("total_namespaces", 0)
        if total_ns > 50:
            changes["max_namespaces"] = min(200,
                mutable_config.get("max_namespaces", 100) + 50)
        active = learn_result.get("active_namespaces", 0)
        if active < total_ns * 0.3 and total_ns > 20:
            changes["default_agent_type"] = "general"
        return {"rules_modified": changes, "skills_created": []}
