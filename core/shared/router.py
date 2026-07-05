"""
智能层级路由 v1.1 - 集成自unified-memory-bridge
根据记忆类型自动选择最优系统处理

M22升级: EvolutionLoop闭环 + record_action喂入 + health() + 双注入
灵境道谱溯源: D5-3【意图路由煞】· 道五·编排体道 · 四地煞之枢之术
  - 意图分类路由+MemoryLayer×6层+ICME/BOTH/EXTERNAL三级路由分流
  - 源文件: core/router.py → LayerRouter

路由规则:
  BOTH处理 (双写保障):
    - L3 Episodic (情景记忆) - 高价值决策记录，双写防丢失
    - L4 Semantic (语义记忆) - 知识图谱，双写确保可恢复
    - L5 Meta (元认知) - 策略自优化，双写确保可恢复

  ICME处理:
    - L0 Sensory (感知记忆) - 实时捕获，轻量快速
    - L1 Working (工作记忆) - 当前会话上下文
    - L2 Short-Term (短期记忆) - 跨会话保持

动态降级:
    - 外部系统不可用时，BOTH路由自动降级为ICME
    - 健康检查周期可配置(默认30s)
"""

import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

try:
    from ..processors.evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


class MemoryLayer(Enum):
    SENSORY = "sensory"
    WORKING = "working"
    SHORT_TERM = "short_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    META = "meta"


class TargetSystem(Enum):
    ICME = "icme"
    EXTERNAL = "external"
    BOTH = "both"


@dataclass
class RoutingRule:
    layer: MemoryLayer
    target: TargetSystem
    reason: str


LAYER_ROUTING = {
    MemoryLayer.SENSORY: RoutingRule(MemoryLayer.SENSORY, TargetSystem.ICME, "实时捕获，轻量快速"),
    MemoryLayer.WORKING: RoutingRule(MemoryLayer.WORKING, TargetSystem.ICME, "会话上下文，即时响应"),
    MemoryLayer.SHORT_TERM: RoutingRule(
        MemoryLayer.SHORT_TERM, TargetSystem.ICME, "跨会话保持，自动晋升"
    ),
    MemoryLayer.EPISODIC: RoutingRule(
        MemoryLayer.EPISODIC, TargetSystem.BOTH, "高价值情景记忆，双写防丢失"
    ),
    MemoryLayer.SEMANTIC: RoutingRule(
        MemoryLayer.SEMANTIC, TargetSystem.BOTH, "知识图谱，双写确保可恢复"
    ),
    MemoryLayer.META: RoutingRule(MemoryLayer.META, TargetSystem.BOTH, "元认知策略，双写确保可恢复"),
}


class LayerRouter:
    def __init__(self, health_check_fn: Optional[Callable] = None, health_check_interval: float = 30.0,
                 recorder: Optional[Any] = None,
                 learning_engine: Optional[Any] = None):
        self.rules = LAYER_ROUTING
        self._health_check_fn = health_check_fn
        self._health_check_interval = health_check_interval
        self._external_healthy: Optional[bool] = None
        self._last_health_check: float = 0
        self._lock = threading.Lock()
        self._degradation_log: List[Dict[str, Any]] = []
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._stats: Dict[str, Any] = {
            "route_ops": 0,
            "split_ops": 0,
            "degradation_events": 0,
            "health_checks": 0,
            "start_time": time.time(),
        }
        self._errors = 0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="layer_router",
                    effectiveness_fn=self._calc_router_effectiveness,
                    learn_fn=self._learn_from_router,
                    evolve_fn=self._evolve_router_config,
                    mutable_config={
                        "health_check_interval": health_check_interval,
                        "degradation_log_max": 100,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception:
                pass

    def update_external_health(self, healthy: bool):
        with self._lock:
            if self._external_healthy is not None and self._external_healthy != healthy:
                self._degradation_log.append(
                    {
                        "event": "external_up" if healthy else "external_down",
                        "timestamp": time.time(),
                        "previous_state": self._external_healthy,
                    }
                )
                if len(self._degradation_log) > 100:
                    self._degradation_log = self._degradation_log[-100:]
            self._external_healthy = healthy
            self._last_health_check = time.time()

        self._stats["degradation_events"] += 1
        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="update_external_health",
                    state_before={"external_healthy": not healthy},
                    state_after={"external_healthy": healthy},
                )
            except Exception:
                pass

    def _check_external_health(self) -> bool:
        self._stats["health_checks"] += 1
        with self._lock:
            if self._external_healthy is not None:
                if time.time() - self._last_health_check < self._health_check_interval:
                    return self._external_healthy

        if self._health_check_fn:
            try:
                healthy = bool(self._health_check_fn())
                self.update_external_health(healthy)
                return healthy
            except Exception:
                self.update_external_health(False)
                return False

        with self._lock:
            if self._external_healthy is not None:
                return self._external_healthy
        return True

    def get_target(self, layer: str) -> TargetSystem:
        try:
            memory_layer = MemoryLayer(layer.lower())
            target = self.rules[memory_layer].target
            if target in (TargetSystem.BOTH, TargetSystem.EXTERNAL):
                if not self._check_external_health():
                    return TargetSystem.ICME
            return target
        except (ValueError, KeyError):
            return TargetSystem.ICME

    def route(
        self, content: str, layer: Optional[str] = None, tags: Optional[List[str]] = None
    ) -> TargetSystem:
        self._stats["route_ops"] += 1

        if layer:
            result = self.get_target(layer)
        else:
            tags = tags or []
            tag_lower = [t.lower() for t in tags]

            if any(t in tag_lower for t in ["semantic", "knowledge", "concept"]):
                if self._check_external_health():
                    result = TargetSystem.BOTH
                else:
                    result = TargetSystem.ICME
            elif any(t in tag_lower for t in ["meta", "strategy", "pattern"]):
                if self._check_external_health():
                    result = TargetSystem.BOTH
                else:
                    result = TargetSystem.ICME
            else:
                result = TargetSystem.ICME

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="route",
                    state_before={"route_ops": self._stats["route_ops"] - 1},
                    state_after={"route_ops": self._stats["route_ops"],
                                 "target": result.value, "layer": layer},
                )
            except Exception:
                pass
        return result

    def split_query(self, query: str, layers: Optional[List[str]] = None) -> dict:
        result = {"external_layers": [], "icme_layers": [], "both_layers": []}

        if not layers:
            layers = [l.value for l in MemoryLayer]

        for layer in layers:
            target = self.get_target(layer)
            if target == TargetSystem.EXTERNAL:
                result["external_layers"].append(layer)
            elif target == TargetSystem.BOTH:
                result["both_layers"].append(layer)
                result["external_layers"].append(layer)
                result["icme_layers"].append(layer)
            else:
                result["icme_layers"].append(layer)

        self._stats["split_ops"] += 1
        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="split_query",
                    state_before={"split_ops": self._stats["split_ops"] - 1},
                    state_after={"split_ops": self._stats["split_ops"],
                                 "layers": list(layers), "query_len": len(query)},
                )
            except Exception:
                pass
        return result

    def get_degradation_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._degradation_log)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "version": "1.1",
            "external_healthy": self._check_external_health(),
            "last_health_check": self._last_health_check,
            "degradation_events": len(self._degradation_log),
            "route_ops": self._stats["route_ops"],
            "split_ops": self._stats["split_ops"],
            "health_checks": self._stats["health_checks"],
            "errors": self._errors,
            "routing_rules": {layer.value: rule.target.value for layer, rule in self.rules.items()},
            "health": self.health(),
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ready",
            "version": "1.1",
            "external_healthy": self._check_external_health(),
            "degradation_events": len(self._degradation_log),
            "route_ops": self._stats["route_ops"],
            "split_ops": self._stats["split_ops"],
            "health_checks": self._stats["health_checks"],
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_router_effectiveness(self, action: str,
                                    state_before: Dict[str, Any],
                                    state_after: Dict[str, Any]) -> float:
        if action in ("route", "split_query"):
            return 0.3
        elif action == "update_external_health":
            prev = state_before.get("external_healthy", True)
            curr = state_after.get("external_healthy", True)
            return 0.2 if curr == prev else -0.1
        return 0.0

    def _learn_from_router(self, causal_pairs: List[Any],
                            effectiveness_summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "total_routes": self._stats["route_ops"],
            "degradation_count": len(self._degradation_log),
            "external_healthy": self._check_external_health(),
        }

    def _evolve_router_config(self, learn_result: Dict[str, Any],
                               mutable_config: Dict[str, Any]) -> Dict[str, Any]:
        changes = {}
        degradation_count = learn_result.get("degradation_count", 0)
        if degradation_count > 10:
            changes["health_check_interval"] = max(5.0,
                mutable_config.get("health_check_interval", 30.0) * 0.5)
        if degradation_count < 2:
            changes["health_check_interval"] = min(60.0,
                mutable_config.get("health_check_interval", 30.0) * 1.5)
        return {"rules_modified": changes, "skills_created": []}
