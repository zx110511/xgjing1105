# -*- coding: utf-8-sig -*-
"""tianji_daemon_tianjiautopilot_core.py — TianjiAutopilotCoreMixin (SSS-PhaseB)

从 tianji_daemon_tianjiautopilot.py 拆分的方法组: core
源文件: tianji_daemon_tianjiautopilot.py
"""

import os
import sys



from typing import Optional

class TianjiAutopilotCoreMixin:
    """core方法组Mixin"""

    def __init__(self):
        self._build_task_configs()
        self._last_run = {k: 0.0 for k in self.TASK_CONFIGS}
        self._adaptive_intervals = {
            k: v["base_interval"] for k, v in self.TASK_CONFIGS.items()
        }
        self._consecutive_errors = {k: 0 for k in self.TASK_CONFIGS}
        self._last_capacity_state = "OK"
        self._system_load = 0.0
        self._cycle_count = 0
        self._event_queue = []
        self._anomaly_buffer = []
        self._rca_results = []
        self._correlation_graph = {}
        self._module_health_cache = {}
        self._stats = self._build_stats()
        self._scheduler_ref = None
        self._baseline_engine = None
        self._auto_healer = None
        self._skill_learner = None
        self._preference_learner = None
        self._learning_engine = None
        self._circuit_breaker = None
        self._quality_gate = None
        self._dynamic_mgr = None
        self._causal_recorder = None
        self._modules_initialized = False

    def _build_task_configs(self):
        configs = dict(self.TASK_CONFIGS_BASE)
        for mod in self._UNCOVERED_MODULES:
            configs[f"mod_{mod}"] = {
                "base_interval": 1800,
                "min_interval": 600,
                "max_interval": 7200,
                "priority": 4,
            }
        for daemon_task in self._DAEMON_TASKS:
            configs[f"daemon_{daemon_task}"] = {
                "base_interval": 600,
                "min_interval": 120,
                "max_interval": 3600,
                "priority": 3,
            }
        self.__class__.TASK_CONFIGS = configs

    def _build_stats(self):
        stats = {
            "capacity_checks": 0,
            "capacity_alerts": 0,
            "consolidations": 0,
            "consolidation_entries": 0,
            "evictions": 0,
            "eviction_entries": 0,
            "evolution_ticks": 0,
            "causal_pairs_recorded": 0,
            "deep_learning_reflections": 0,
            "knowledge_extracted": 0,
            "kg_builds": 0,
            "kg_triples_added": 0,
            "agent_dispatches": 0,
            "security_scans": 0,
            "security_violations": 0,
            "compliance_checks": 0,
            "compliance_violations": 0,
            "extract_tasks": 0,
            "extract_success": 0,
            "extract_fallback": 0,
            "anomaly_checks": 0,
            "anomalies_detected": 0,
            "anomaly_zscore": 0,
            "autoheal_attempts": 0,
            "autoheal_successes": 0,
            "autoheal_rejections": 0,
            "skill_learn_cycles": 0,
            "skills_created": 0,
            "skills_verified": 0,
            "preference_analyses": 0,
            "patterns_identified": 0,
            "mem_health_checks": 0,
            "mem_quality_scores": [],
            "prediction_cycles": 0,
            "predictions_made": 0,
            "prediction_accuracy": 0,
            "rca_analyses": 0,
            "rca_root_causes_found": 0,
            "resilience_checks": 0,
            "circuit_trips": 0,
            "scheduler_ticks": 0,
            "scheduler_tasks_dispatched": 0,
            "threshold_adjustments": 0,
            "correlation_analyses": 0,
            "correlation_clusters": 0,
            "adaptive_adjustments": 0,
            "total_cycles": 0,
            "module_patrols": 0,
            "modules_healthy": 0,
            "modules_degraded": 0,
            "modules_error": 0,
            "daemon_checks": 0,
            "daemon_healthy": 0,
            "daemon_degraded": 0,
        }
        return stats

    def push_event(self, event_type: str, payload: dict = None):
        self._event_queue.append((event_type, payload or {}, time.time()))
        if len(self._event_queue) > 1000:
            self._event_queue = self._event_queue[-500:]

    def _init_modules(self):
        if self._modules_initialized:
            return
        try:
            sys.path.insert(0, str(TIANJI_ROOT))
            from core.processors.auto_ops import AutoHealer, BaselineEngine

            self._auto_healer = AutoHealer()
            self._baseline_engine = BaselineEngine()
            log.info("[AUTOPILOT] AutoHealer + BaselineEngine initialized")
        except Exception as e:
            log.debug(f"[AUTOPILOT] AutoOps init skipped: {e}")

        try:
            from core.processors.learning_loop import ClosedLoopLearningEngine

            self._learning_engine = ClosedLoopLearningEngine()
            log.info("[AUTOPILOT] ClosedLoopLearningEngine initialized")
        except Exception as e:
            log.debug(f"[AUTOPILOT] Learning engine init skipped: {e}")

        try:
            from core.orchestration.intelligent_scheduler import TianjiIntelligentScheduler

            self._scheduler_ref = TianjiIntelligentScheduler()
            log.info("[AUTOPILOT] IntelligentScheduler initialized")
        except Exception as e:
            log.debug(f"[AUTOPILOT] Scheduler init skipped: {e}")

        try:
            from core.shared.skill_learner import SkillLearner

            self._skill_learner = SkillLearner()
            log.info("[AUTOPILOT] SkillLearner initialized")
        except Exception as e:
            log.debug(f"[AUTOPILOT] SkillLearner init skipped: {e}")

        try:
            from core.shared.preference_learner import PreferenceLearner

            self._preference_learner = PreferenceLearner()
            self._preference_learner.connect()
            log.info("[AUTOPILOT] PreferenceLearner initialized")
        except Exception as e:
            log.debug(f"[AUTOPILOT] PreferenceLearner init skipped: {e}")

        try:
            from core.enforcement.resilience import CircuitBreaker

            self._circuit_breaker = CircuitBreaker(
                "autopilot_memory", failure_threshold=5
            )
            log.info("[AUTOPILOT] CircuitBreaker initialized")
        except Exception as e:
            log.debug(f"[AUTOPILOT] CircuitBreaker init skipped: {e}")

        try:
            from core.processors.quality_gate import QualityGate

            self._quality_gate = QualityGate()
            log.info("[AUTOPILOT] QualityGate initialized")
        except Exception as e:
            log.debug(f"[AUTOPILOT] QualityGate init skipped: {e}")

        try:
            from core.processors.evolution_loop import CausalPairRecorder

            self._causal_recorder = CausalPairRecorder()
            log.info("[AUTOPILOT] CausalPairRecorder initialized")
        except Exception as e:
            log.debug(f"[AUTOPILOT] CausalRecorder init skipped: {e}")

        try:
            from core.memory.memory_dynamic_manager import AccumulationTracker

            self._dynamic_mgr = AccumulationTracker()
            log.info("[AUTOPILOT] AccumulationTracker initialized")
        except Exception as e:
            log.debug(f"[AUTOPILOT] DynamicMgr init skipped: {e}")

        self._modules_initialized = True
        log.info("[AUTOPILOT] v2.0 所有智能模块初始化完成")

    def run_cycle(self):
        self._cycle_count += 1
        self._stats["total_cycles"] += 1
        now = time.time()
        results = {}

        if not self._modules_initialized and self._cycle_count <= 1:
            self._init_modules()

        self._process_events(now)

        self._update_system_load()

        for task_name, config in sorted(
            self.TASK_CONFIGS.items(), key=lambda x: x[1]["priority"]
        ):
            if config["base_interval"] == 0:
                continue
            interval = self._adaptive_intervals[task_name]
            if now - self._last_run[task_name] >= interval:
                handler = self._get_handler(task_name)
                if handler:
                    try:
                        result = handler()
                        results[task_name] = result
                        self._last_run[task_name] = now
                        self._adaptive_feedback(task_name, result)
                    except Exception as e:
                        log.debug(f"[AUTOPILOT] {task_name} error: {e}")
                        results[task_name] = {"error": str(e)}

        return results

    def _get_handler(self, task_name):
        handler = getattr(self, f"_task_{task_name}", None)
        if handler:
            return handler
        if task_name.startswith("mod_"):
            return lambda: self._task_module_health(task_name)
        if task_name.startswith("daemon_"):
            return lambda: self._task_daemon_health(task_name)
        return None

    def _process_events(self, now):
        pending = list(self._event_queue)
        self._event_queue.clear()

        for event_type, payload, ts in pending:
            if event_type == "conversation_complete":
                self._task_extract(payload)
            elif event_type == "capacity_critical":
                self._task_capacity()
                self._task_consolidate()
            elif event_type == "agent_task":
                self._task_agent_dispatch(payload)

    def _update_system_load(self):
        try:
            import json
            import urllib.request

            url = "http://127.0.0.1:8771/api/memory/stats"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            total = data.get("total", 0)
            self._system_load = min(total / 10000.0, 1.0)
        except Exception:
            self._system_load = 0.5

    def _adaptive_feedback(self, task_name: str, result: dict):
        if not result:
            return
        config = self.TASK_CONFIGS.get(task_name, {})
        base = config.get("base_interval", 600)
        min_i = config.get("min_interval", 60)
        max_i = config.get("max_interval", 3600)

        if "error" in result:
            self._consecutive_errors[task_name] += 1
            new_interval = min(
                base * (1.5 ** self._consecutive_errors[task_name]), max_i
            )
        else:
            self._consecutive_errors[task_name] = 0
            if task_name == "capacity":
                critical = result.get("critical", 0)
                if critical > 0:
                    new_interval = max(min_i, base * 0.3)
                elif result.get("alerts", 0) > 0:
                    new_interval = max(min_i, base * 0.6)
                else:
                    new_interval = min(base * 1.2, max_i)
            elif task_name == "consolidate":
                consolidated = result.get("consolidated", 0)
                if consolidated > 50:
                    new_interval = max(min_i, base * 0.5)
                elif consolidated > 0:
                    new_interval = base
                else:
                    new_interval = min(base * 1.5, max_i)
            else:
                load_factor = 1.0 - self._system_load * 0.5
                new_interval = base * load_factor

        new_interval = max(min_i, min(new_interval, max_i))
        if abs(new_interval - self._adaptive_intervals[task_name]) > 1.0:
            self._adaptive_intervals[task_name] = new_interval
            self._stats["adaptive_adjustments"] += 1

    def _api_get(self, path: str, timeout: int = 10) -> dict:
        import json
        import urllib.request

        url = f"http://127.0.0.1:8771{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _api_post(self, path: str, payload: dict = None, timeout: int = 30) -> dict:
        import json
        import urllib.request

        url = f"http://127.0.0.1:8771{path}"
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _task_capacity(self):
        self._stats["capacity_checks"] += 1
        try:
            data = self._api_get("/api/memory/storage/management")
            alerts = data.get("alerts", [])
            critical = [a for a in alerts if a.get("level") == "error"]
            warning = [a for a in alerts if a.get("level") == "warn"]

            if critical:
                self._stats["capacity_alerts"] += 1
                self._last_capacity_state = "CRITICAL"
                for alert in critical:
                    layer = alert.get("layer", "")
                    log.warning(f"[AUTOPILOT] CAPACITY CRITICAL: {layer}")
                    self._auto_manage_layer(layer)
            elif warning:
                self._last_capacity_state = "WARNING"
            else:
                self._last_capacity_state = "OK"

            return {
                "alerts": len(alerts),
                "critical": len(critical),
                "warning": len(warning),
            }
        except Exception as e:
            log.debug(f"[AUTOPILOT] Capacity check failed: {e}")
            return {"error": str(e)}

    def _auto_manage_layer(self, layer: str):
        try:
            result = self._api_post(
                "/api/memory/storage/manage",
                {
                    "actions": ["emergency_consolidate", "preventive_consolidate"],
                    "target_layers": [layer],
                },
                timeout=30,
            )
            actions = result.get("management_actions", [])
            if actions:
                self._stats["consolidations"] += 1
                for a in actions:
                    if a.get("action") == "force_evict":
                        self._stats["evictions"] += 1
                        self._stats["eviction_entries"] += a.get("evicted", 0)
                log.info(f"[AUTOPILOT] Managed {layer}: {len(actions)} actions")
        except Exception as e:
            log.debug(f"[AUTOPILOT] Manage {layer} failed: {e}")

    def get_stats(self):
        stats = dict(self._stats)
        if self._stats["mem_quality_scores"]:
            stats["mem_avg_quality"] = round(
                sum(self._stats["mem_quality_scores"])
                / len(self._stats["mem_quality_scores"]),
                1,
            )
        stats["rca_history"] = len(self._rca_results)
        stats["correlation_graph_size"] = len(self._correlation_graph)
        stats["modules_initialized"] = self._modules_initialized
        return stats

    def get_adaptive_intervals(self):
        return dict(self._adaptive_intervals)

    def get_status(self):
        return {
            "cycle_count": self._cycle_count,
            "system_load": round(self._system_load, 3),
            "capacity_state": self._last_capacity_state,
            "adaptive_intervals": {
                k: round(v, 1) for k, v in self._adaptive_intervals.items()
            },
            "event_queue_size": len(self._event_queue),
            "modules_initialized": self._modules_initialized,
            "total_tasks": len(self.TASK_CONFIGS),
            "intelligent_tasks": len(self.TASK_CONFIGS_BASE),
            "module_patrol_tasks": len(self._UNCOVERED_MODULES),
            "daemon_tasks": len(self._DAEMON_TASKS),
            "module_health_cache": dict(self._module_health_cache),
            "stats": self.get_stats(),
        }


__all__ = ["TianjiAutopilot"]
