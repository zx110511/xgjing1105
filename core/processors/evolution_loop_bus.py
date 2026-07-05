# -*- coding: utf-8-sig -*-
"""进化闭环 — 进化总线+因果图存储 (EvolutionBus + CausalGraphStore)

从 evolution_loop.py 拆分:
- EvolutionBus: 进化信号总线，模块间进化联动
- CausalGraphStore: 因果图持久化存储
"""
from __future__ import annotations


from typing import Any, Dict, List, Optional, TYPE_CHECKING
from .evolution_loop_models import EvolutionSignal, EvolutionSignalType, ModuleCausalPair
from .evolution_loop_recorder import CausalPairRecorder

if TYPE_CHECKING:
    from .evolution_loop import EvolutionLoop

class EvolutionBus:
    """
    进化信号总线 — 模块间进化联动的核心

    当一个模块的进化信号需要传播到其他模块时，
    通过EvolutionBus进行广播和路由。

    联动规则:
      quality_gate误判 → learning_loop调整知识提取策略
      skill_registry低利用 → enforcement_hook调整拦截策略
      ICMEEngine容量压力 → quality_gate收紧阈值
      agent_orchestrator调度失败 → intelligent_scheduler调整委派策略
      workflow_engine瓶颈 → agent_orchestrator调整流水线
    """

    ROUTING_TABLE = {
        EvolutionSignalType.GATE_MISJUDGMENT: ["learning_loop", "enforcement_hook"],
        EvolutionSignalType.SKILL_UNDERUSE: ["enforcement_hook", "skill_registry"],
        EvolutionSignalType.CAPACITY_PRESSURE: ["quality_gate", "engine"],
        EvolutionSignalType.SCHEDULE_SUBOPTIMAL: ["intelligent_scheduler"],
        EvolutionSignalType.ROUTE_INEFFICIENCY: [
            "message_gateway",
            "agent_orchestrator",
        ],
        EvolutionSignalType.QUALITY_DEGRADATION: ["quality_gate", "learning_loop"],
        EvolutionSignalType.WORKFLOW_BOTTLENECK: [
            "agent_orchestrator",
            "workflow_engine",
        ],
        EvolutionSignalType.DELEGATION_FAILURE: [
            "intelligent_scheduler",
            "agent_orchestrator",
        ],
        EvolutionSignalType.ENFORCEMENT_OVERBLOCK: ["enforcement_hook", "quality_gate"],
    }

    def __init__(
        self,
        global_recorder: Optional[CausalPairRecorder] = None,
        recorder: Optional[Any] = None,
        learning_engine: Optional[Any] = None,
    ):
        self._loops: Dict[str, EvolutionLoop] = {}
        self._signal_history: List[EvolutionSignal] = []
        self._lock = threading.Lock()
        self._global_recorder = global_recorder or CausalPairRecorder()
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._errors = 0
        self._signal_route_count = 0
        self._module_register_count = 0
        self._stats = {
            "signals_routed": 0,
            "signals_dropped": 0,
            "cross_module_triggers": 0,
        }

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="evolution_bus",
                    effectiveness_fn=self._calc_bus_effectiveness,
                    learn_fn=self._learn_from_bus,
                    evolve_fn=self._evolve_bus_routing,
                    mutable_config={
                        "max_signal_history": 500,
                        "route_cooldown_ms": 0,
                    },
                    recorder=recorder,
                )
            except Exception:
                pass

    def register_loop(self, loop: EvolutionLoop):
        self._loops[loop._module_name] = loop
        loop.subscribe_signals(self._route_signal)
        self._module_register_count += 1

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="register_loop",
                    state_before={},
                    state_after={
                        "module": loop._module_name,
                        "total_modules": len(self._loops),
                        "register_count": self._module_register_count,
                    },
                )
            except Exception:
                pass

    def _route_signal(self, signal: EvolutionSignal):
        with self._lock:
            self._signal_history.append(signal)
            if len(self._signal_history) > 500:
                self._signal_history = self._signal_history[-250:]

        target_modules = self.ROUTING_TABLE.get(signal.signal_type, [])
        routes_succeeded = 0

        for module_name in target_modules:
            if module_name in self._loops and module_name != signal.source_module:
                try:
                    self._loops[module_name].receive_signal(signal)
                    self._stats["signals_routed"] += 1
                    self._stats["cross_module_triggers"] += 1
                    routes_succeeded += 1
                except Exception as e:
                    logger.debug(f"EvolutionBus route error: {e}")
                    self._stats["signals_dropped"] += 1

        self._signal_route_count += 1

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="route_signal",
                    state_before={"signal_type": signal.signal_type.value},
                    state_after={
                        "signal_type": signal.signal_type.value,
                        "source": signal.source_module,
                        "targets": target_modules,
                        "routes_succeeded": routes_succeeded,
                        "severity": signal.severity,
                        "total_routes": self._signal_route_count,
                    },
                )
            except Exception:
                pass

    def get_stats(self) -> Dict:
        with self._lock:
            return {
                **self._stats,
                "registered_modules": list(self._loops.keys()),
                "signal_history_size": len(self._signal_history),
            }

    @property
    def global_recorder(self) -> CausalPairRecorder:
        return self._global_recorder

    def get_signal_history(self, limit: int = 20) -> List[Dict]:
        with self._lock:
            recent = self._signal_history[-limit:]
            return [
                {
                    "signal_id": s.signal_id,
                    "source": s.source_module,
                    "type": s.signal_type.value,
                    "severity": s.severity,
                    "description": s.description,
                    "timestamp": s.timestamp,
                }
                for s in recent
            ]

    def health(self) -> Dict[str, Any]:
        return {
            "status": "active",
            "version": "9.1.0",
            "registered_modules": len(self._loops),
            "signal_history_size": len(self._signal_history),
            "signals_routed": self._stats.get("signals_routed", 0),
            "signals_dropped": self._stats.get("signals_dropped", 0),
            "cross_module_triggers": self._stats.get("cross_module_triggers", 0),
            "module_register_count": self._module_register_count,
            "signal_route_count": self._signal_route_count,
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
        }

    def get_full_stats(self) -> Dict:
        return {
            "health": self.health(),
            "version": "9.1.0",
            "routing_table_size": len(self.ROUTING_TABLE),
            "signal_types": [t.value for t in self.ROUTING_TABLE],
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_bus_effectiveness(
        self, action: str, state_before: Dict[str, Any], state_after: Dict[str, Any]
    ) -> float:
        if action == "register_loop":
            if state_after.get("module", ""):
                return 0.7
            return 0.2
        elif action == "route_signal":
            targets = state_after.get("targets", [])
            succeeded = state_after.get("routes_succeeded", 0)
            if targets and succeeded > 0:
                ratio = succeeded / len(targets) if targets else 0
                return 0.5 + 0.4 * ratio
            return 0.1
        return 0.0

    def _learn_from_bus(
        self, causal_pairs: List[Any], effectiveness_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        signal_types_used = set()
        for _, v in self._stats.items():
            pass
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "registered_modules": len(self._loops),
            "signal_route_count": self._signal_route_count,
            "signals_routed": self._stats.get("signals_routed", 0),
            "signals_dropped": self._stats.get("signals_dropped", 0),
            "drop_rate": (
                self._stats.get("signals_dropped", 0) / max(self._signal_route_count, 1)
            ),
        }

    def _evolve_bus_routing(
        self, learn_result: Dict[str, Any], mutable_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        changes = {}
        drop_rate = learn_result.get("drop_rate", 0.0)
        if drop_rate > 0.1:
            changes["max_signal_history"] = min(
                1000, mutable_config.get("max_signal_history", 500) + 100
            )
            changes["route_cooldown_ms"] = 50
        elif drop_rate < 0.02:
            changes["max_signal_history"] = 500
            changes["route_cooldown_ms"] = 0
        return {"rules_modified": changes, "skills_created": []}


class CausalGraphStore:
    """
    因果图持久化存储 — 将进化循环的因果对持久化到磁盘

    功能:
      - 因果对JSON持久化 (per-module partitioning)
      - 因果链可视化 (DOT/JSON format)
      - 进化历史追溯 (action→effect timeline)
      - 统计摘要导出
    """

    def __init__(self, store_dir: Optional[Path] = None):
        if store_dir is None:
            store_dir = _DATA_DIR / "causal_graph"
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._pairs_file = self._store_dir / "causal_pairs.jsonl"
        self._graph_file = self._store_dir / "causal_graph.json"
        self._summary_file = self._store_dir / "summary.json"
        self._lock = threading.Lock()

    def append_pair(self, pair: ModuleCausalPair) -> str:
        pair_id = hashlib.md5(
            f"{pair.module_name}:{pair.action}:{pair.timestamp}".encode()
        ).hexdigest()[:12]

        record = {
            "pair_id": pair_id,
            "module": pair.module_name,
            "action": pair.action,
            "state_before": pair.state_before,
            "state_after": pair.state_after,
            "effectiveness": pair.effectiveness,
            "timestamp": pair.timestamp,
            "metadata": pair.metadata,
        }

        with self._lock:
            with open(self._pairs_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return pair_id

    def load_all_pairs(self, limit: int = 1000) -> List[Dict[str, Any]]:
        pairs = []
        if not self._pairs_file.exists():
            return pairs
        with self._lock:
            with open(self._pairs_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            start = max(0, len(lines) - limit)
            for line in lines[start:]:
                try:
                    pairs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return pairs

    def load_by_module(
        self, module_name: str, limit: int = 200
    ) -> List[Dict[str, Any]]:
        pairs = self.load_all_pairs(limit * 5)
        return [p for p in pairs if p.get("module") == module_name][-limit:]

    def load_by_action(self, action: str, limit: int = 200) -> List[Dict[str, Any]]:
        pairs = self.load_all_pairs(limit * 5)
        return [p for p in pairs if p.get("action") == action][-limit:]

    def build_causal_graph(self) -> Dict[str, Any]:
        pairs = self.load_all_pairs(5000)
        nodes: Dict[str, Dict] = {}
        edges: List[Dict] = []

        for p in pairs:
            module = p.get("module", "unknown")
            action = p.get("action", "unknown")
            eff = p.get("effectiveness", 0.0)

            node_key = f"{module}::{action}"
            if node_key not in nodes:
                nodes[node_key] = {
                    "id": node_key,
                    "module": module,
                    "action": action,
                    "count": 0,
                    "total_effect": 0.0,
                    "positive_count": 0,
                    "negative_count": 0,
                }
            nodes[node_key]["count"] += 1
            nodes[node_key]["total_effect"] += eff
            if eff > 0.05:
                nodes[node_key]["positive_count"] += 1
            elif eff < -0.05:
                nodes[node_key]["negative_count"] += 1

            state_before = p.get("state_before", {})
            state_after = p.get("state_after", {})
            for key in set(list(state_before.keys()) + list(state_after.keys())):
                target_key = f"{module}::state::{key}"
                if target_key not in nodes:
                    nodes[target_key] = {
                        "id": target_key,
                        "module": module,
                        "action": f"state::{key}",
                        "count": 0,
                        "total_effect": 0.0,
                        "positive_count": 0,
                        "negative_count": 0,
                    }
                edges.append(
                    {
                        "from": node_key,
                        "to": target_key,
                        "effectiveness": eff,
                        "pair_id": p.get("pair_id", ""),
                    }
                )

        for n in nodes.values():
            cnt = max(n["count"], 1)
            n["avg_effectiveness"] = round(n["total_effect"] / cnt, 4)
            n["positive_rate"] = round(n["positive_count"] / cnt, 4)

        graph = {
            "nodes": list(nodes.values()),
            "edges": edges,
            "total_pairs": len(pairs),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "built_at": time.time(),
        }

        with self._lock:
            self._graph_file.write_text(
                json.dumps(graph, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return graph

    def get_summary(self) -> Dict[str, Any]:
        pairs = self.load_all_pairs(10000)
        if not pairs:
            return {"total": 0, "avg_effectiveness": 0.0}

        effs = [p["effectiveness"] for p in pairs]
        modules = {}
        actions = {}

        for p in pairs:
            mod = p.get("module", "unknown")
            act = p.get("action", "unknown")
            eff = p["effectiveness"]

            if mod not in modules:
                modules[mod] = {
                    "count": 0,
                    "total_effect": 0.0,
                    "positive": 0,
                    "negative": 0,
                }
            modules[mod]["count"] += 1
            modules[mod]["total_effect"] += eff
            if eff > 0.05:
                modules[mod]["positive"] += 1
            elif eff < -0.05:
                modules[mod]["negative"] += 1

            if act not in actions:
                actions[act] = {
                    "count": 0,
                    "total_effect": 0.0,
                    "positive": 0,
                    "negative": 0,
                }
            actions[act]["count"] += 1
            actions[act]["total_effect"] += eff
            if eff > 0.05:
                actions[act]["positive"] += 1
            elif eff < -0.05:
                actions[act]["negative"] += 1

        summary = {
            "total": len(pairs),
            "avg_effectiveness": round(sum(effs) / len(effs), 4),
            "min_effectiveness": round(min(effs), 4),
            "max_effectiveness": round(max(effs), 4),
            "positive_ratio": round(sum(1 for e in effs if e > 0.05) / len(effs), 4),
            "negative_ratio": round(sum(1 for e in effs if e < -0.05) / len(effs), 4),
            "modules": {
                mod: {
                    "count": v["count"],
                    "avg_effect": round(v["total_effect"] / v["count"], 4),
                    "positive_rate": round(v["positive"] / v["count"], 4),
                }
                for mod, v in sorted(
                    modules.items(), key=lambda x: x[1]["count"], reverse=True
                )[:10]
            },
            "top_actions": {
                act: {
                    "count": v["count"],
                    "avg_effect": round(v["total_effect"] / v["count"], 4),
                    "positive_rate": round(v["positive"] / v["count"], 4),
                }
                for act, v in sorted(
                    actions.items(), key=lambda x: x[1]["count"], reverse=True
                )[:10]
            },
        }

        with self._lock:
            self._summary_file.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return summary

    def visualize_causal_chain(self, action: str, module: str = None) -> Dict[str, Any]:
        pairs = self.load_all_pairs(2000)

        if module:
            pairs = [p for p in pairs if p.get("module") == module]
        pairs = [p for p in pairs if p.get("action") == action]

        timeline = sorted(pairs, key=lambda x: x["timestamp"])
        if not timeline:
            return {"action": action, "chain_length": 0, "timeline": []}

        chain = {
            "action": action,
            "module": module or "all",
            "chain_length": len(timeline),
            "time_span": {
                "start": timeline[0]["timestamp"],
                "end": timeline[-1]["timestamp"],
                "duration_s": round(
                    timeline[-1]["timestamp"] - timeline[0]["timestamp"], 2
                ),
            },
            "effectiveness_trend": [p["effectiveness"] for p in timeline],
            "avg_effectiveness": round(
                sum(p["effectiveness"] for p in timeline) / len(timeline), 4
            ),
            "trend_direction": "improving"
            if (
                sum(p["effectiveness"] for p in timeline[-3:])
                / max(len(timeline[-3:]), 1)
                > sum(p["effectiveness"] for p in timeline[:3])
                / max(len(timeline[:3]), 1)
            )
            else "declining"
            if (
                sum(p["effectiveness"] for p in timeline[-3:])
                / max(len(timeline[-3:]), 1)
                < sum(p["effectiveness"] for p in timeline[:3])
                / max(len(timeline[:3]), 1)
            )
            else "stable",
            "state_changes": [
                {
                    "pair_id": p.get("pair_id", ""),
                    "timestamp": p["timestamp"],
                    "effectiveness": p["effectiveness"],
                    "state_delta": {
                        k: p.get("state_after", {}).get(k, "N/A")
                        for k in set(
                            list(p.get("state_before", {}).keys())
                            + list(p.get("state_after", {}).keys())
                        )
                    },
                }
                for p in timeline
            ],
        }

        return chain

    def export_dot(self, output_path: Optional[Path] = None) -> str:
        graph = self.build_causal_graph()
        lines = ["digraph TianjiCausalGraph {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box, style=rounded];")

        for node in graph["nodes"]:
            avg = node.get("avg_effectiveness", 0)
            color = "green" if avg >= 0.3 else ("orange" if avg >= 0 else "red")
            label = (
                f"{node['module']}\\n{node['action']}\\nn={node['count']} avg={avg:.2f}"
            )
            lines.append(f'  "{node["id"]}" [label="{label}", color={color}];')

        for edge in graph["edges"]:
            eff = edge.get("effectiveness", 0)
            style = "solid" if eff >= 0 else "dashed"
            lines.append(
                f'  "{edge["from"]}" -> "{edge["to"]}" '
                f'[style={style}, label="{eff:.2f}"];'
            )

        lines.append("}")

        dot_content = "\n".join(lines)
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(dot_content, encoding="utf-8")

        return dot_content

    def get_stats(self) -> Dict[str, Any]:
        return {
            "pairs_file": str(self._pairs_file),
            "pairs_file_size": self._pairs_file.stat().st_size
            if self._pairs_file.exists()
            else 0,
            "graph_file": str(self._graph_file),
            "summary_file": str(self._summary_file),
        }

    def clear(self):
        with self._lock:
            for f in [self._pairs_file, self._graph_file, self._summary_file]:
                if f.exists():
                    f.unlink()


__all__ = ["EvolutionBus", "CausalGraphStore"]
