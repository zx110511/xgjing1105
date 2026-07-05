# -*- coding: utf-8-sig -*-
"""自动运维 — 运维协调器

从 auto_ops.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-autoops-coord-002] 延迟类型注解求值,避免HealingRecord等NameError

import time
import json
import uuid
import math
import threading
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List, Tuple, Callable
from enum import Enum
from collections import defaultdict, deque
from enum import Enum

# [FIX-autoops-coord-001] 修复unexpected indent: 添加缺失的导入(原代码缩进错误导致未生效)
from .auto_ops_models import HealingAction, HealingSeverity, AnomalyType, HealingRecord, MetricSnapshot, AnomalyReport, ScaleRecommendation
from .evolution_loop import EvolutionLoop, EvolutionSignal, EvolutionSignalType  # [FIX-autoops-coord-004] 补充EvolutionLoop导入(误删恢复)
from .auto_ops_healer import AutoHealer  # [FIX-autoops-coord-005] 补充AutoHealer导入
from .auto_ops_baseline import BaselineEngine  # [FIX-autoops-coord-006] 补充BaselineEngine导入
from typing import Optional


class AutoOpsCoordinator:
    r"""
    自动化运维协调器 — Phase 3 核心入口

    职责:
      1. 连接 EvolutionBus → 接收进化信号，触发自愈决策
      2. 定期采集 Metric 快照 → 注入 BaselineEngine
      3. 基线异常 → 生成自愈信号 → AutoHealer
      4. 生成扩缩容建议
      5. 输出运维报告

    使用方式:
      coordinator = AutoOpsCoordinator(registry, evolution_bus, governance_pipeline)
      coordinator.start()  # 启动后台采集和监控
      report = coordinator.generate_ops_report()
    """

    def __init__(self, registry=None, evolution_bus=None,
                 governance_pipeline=None,
                 recorder: Optional[Any] = None,
                 learning_engine: Optional[Any] = None):
        self._registry = registry
        self._evolution_bus = evolution_bus
        self._governance_pipeline = governance_pipeline
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._errors = 0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="auto_ops",
                    effectiveness_fn=self._calc_ops_effectiveness,
                    learn_fn=self._learn_from_ops,
                    evolve_fn=self._evolve_ops_config,
                    mutable_config={
                        "collect_interval": self._collect_interval,
                        "monitor_interval": self._monitor_interval,
                        "heal_rate_limit_per_hour": 3,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception:
                pass

        self._healer = AutoHealer(
            registry=registry,
            evolution_bus=evolution_bus,
            governance_pipeline=governance_pipeline,
        )
        self._baseline = BaselineEngine(registry=registry)

        self._running = False
        self._collect_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._collect_interval: float = 300.0
        self._monitor_interval: float = 600.0

        self._scale_recommendations: List[ScaleRecommendation] = []
        self._ops_events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        if self._evolution_bus:
            self._evolution_bus.register_loop(self)
            self._register_signal_handler()

    def _register_signal_handler(self):
        if hasattr(self._evolution_bus, '_route_signal'):
            original_route = self._evolution_bus._route_signal

            def enhanced_route(signal):
                original_route(signal)
                self._handle_evolution_signal(signal)

            self._evolution_bus._route_signal = enhanced_route

    def _handle_evolution_signal(self, signal):
        source = getattr(signal, 'source_module', '')
        severity = getattr(signal, 'severity', 0.0)
        signal_type = getattr(signal, 'signal_type', None)

        if severity >= 0.7:
            logger.info(
                f"[AutoOpsCoordinator] 收到高严重度信号: {source} "
                f"type={signal_type} severity={severity:.2f}"
            )
            record = self._healer.heal(source, signal)
            self._ops_events.append({
                "type": "healing_triggered",
                "module_id": source,
                "signal_severity": severity,
                "healing_success": record.success,
                "healing_action": record.action.value,
                "timestamp": time.time(),
            })

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="handle_evolution_signal",
                        state_before={"module_id": source, "severity": severity},
                        state_after={"module_id": source,
                                     "healing_success": record.success,
                                     "healing_action": record.action.value,
                                     "severity": severity},
                    )
                except Exception:
                    pass

    def start(self):
        if self._running:
            return
        self._running = True
        self._collect_thread = threading.Thread(
            target=self._collect_loop, daemon=True, name="AutoOpsCollector"
        )
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="AutoOpsMonitor"
        )
        self._collect_thread.start()
        self._monitor_thread.start()
        logger.info("[AutoOpsCoordinator] 自动化运维监控已启动")

    def stop(self):
        self._running = False
        logger.info("[AutoOpsCoordinator] 自动化运维监控已停止")

    def _collect_loop(self):
        while self._running:
            try:
                self._collect_metrics()
            except Exception as e:
                logger.debug(f"[AutoOpsCoordinator] 指标采集异常: {e}")
            time.sleep(self._collect_interval)

    def _monitor_loop(self):
        while self._running:
            try:
                self._run_monitoring_cycle()
            except Exception as e:
                logger.debug(f"[AutoOpsCoordinator] 监控周期异常: {e}")
            time.sleep(self._monitor_interval)

    def _collect_metrics(self):
        if not self._registry:
            return
        for m in self._registry.list_all():
            module_id = m.module_id
            raw_stats = {}
            if m.stats_fn:
                try:
                    raw_stats = m.stats_fn()
                except Exception:
                    continue
            elif m.instance_ref and hasattr(m.instance_ref, 'get_stats'):
                try:
                    raw_stats = m.instance_ref.get_stats()
                except Exception:
                    continue
            else:
                continue

            numeric_metrics = {
                k: v for k, v in raw_stats.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
            if numeric_metrics:
                self._baseline.record_batch(module_id, numeric_metrics)

    def _run_monitoring_cycle(self):
        self._baseline.calculate_all_baselines()
        if not self._registry:
            return
        for m in self._registry.list_all():
            module_id = m.module_id
            metrics_to_check = ["capacity_usage", "error_rate",
                               "rejection_rate", "avg_latency_ms"]
            raw_stats = {}
            if m.stats_fn:
                try:
                    raw_stats = m.stats_fn()
                except Exception:
                    continue
            for metric_name in metrics_to_check:
                if metric_name in raw_stats:
                    current = raw_stats[metric_name]
                    if isinstance(current, (int, float)):
                        report = self._baseline.detect_anomalies(
                            module_id, metric_name, float(current)
                        )
                        if report and report.severity >= 0.5:
                            try:
                                from .evolution_loop import EvolutionSignal, EvolutionSignalType
                                signal = EvolutionSignal(
                                    source_module="auto_ops",
                                    signal_type=EvolutionSignalType.URGENCY_SIGNAL,
                                    severity=report.severity,
                                    description=f"异常: {module_id}.{metric_name}",
                                    data=report.to_dict(),
                                )
                                self._handle_evolution_signal(signal)
                            except ImportError:
                                self._healer.heal(module_id)

            scale_rec = self._baseline.generate_scale_recommendation(module_id)
            if scale_rec:
                with self._lock:
                    self._scale_recommendations.append(scale_rec)
                    if len(self._scale_recommendations) > 100:
                        self._scale_recommendations = (
                            self._scale_recommendations[-50:]
                        )

        if self._evo_loop is not None:
            try:
                healer_stats = self._healer.get_stats()
                baseline_stats = self._baseline.get_stats()
                self._evo_loop.record_action(
                    action="monitoring_cycle",
                    state_before={"anomalies_detected": baseline_stats.get("anomalies_detected", 0)},
                    state_after={"heal_attempts": healer_stats.get("total_heal_attempts", 0),
                                 "heal_successes": healer_stats.get("total_heal_successes", 0),
                                 "scale_recs": len(self._scale_recommendations)},
                )
            except Exception:
                pass

    def generate_ops_report(self) -> Dict[str, Any]:
        report = {
            "timestamp": time.time(),
            "phase": "Phase 3 - 自动化运维",
            "healer": self._healer.get_stats(),
            "baseline": self._baseline.get_stats(),
            "scale_recommendations": [
                r.to_dict() for r in self._scale_recommendations[-10:]
            ],
            "recent_ops_events": self._ops_events[-20:],
            "registry_summary": (
                self._registry.get_stats() if self._registry else {}
            ),
        }

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="generate_ops_report",
                    state_before={},
                    state_after={"heal_attempts": report["healer"].get("total_heal_attempts", 0),
                                 "anomalies_detected": report["baseline"].get("anomalies_detected", 0),
                                 "scale_recs": len(self._scale_recommendations)},
                )
            except Exception:
                pass

        return report

    def get_scale_recommendations(self, limit: int = 20) -> List[Dict]:
        with self._lock:
            return [r.to_dict() for r in self._scale_recommendations[-limit:]]

    def trigger_manual_heal(self, module_id: str,
                            action: HealingAction) -> HealingRecord:
        return self._healer.heal(module_id, custom_action=action)

    def force_baseline_recalc(self):
        self._baseline.calculate_all_baselines(force=True)

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ready",
            "version": "1.1",
            "running": self._running,
            "heal_attempts": self._healer.get_stats().get("total_heal_attempts", 0),
            "heal_successes": self._healer.get_stats().get("total_heal_successes", 0),
            "escalations": self._healer.get_stats().get("total_escalations", 0),
            "anomalies_detected": self._baseline.get_stats().get("anomalies_detected", 0),
            "scale_recs": len(self._scale_recommendations),
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
        }

    def get_stats(self) -> Dict:
        report = self.generate_ops_report()
        report["health"] = self.health()
        report["version"] = "1.1"
        report["evo_loop"] = self._evo_loop.get_stats() if self._evo_loop else {}
        return report

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_ops_effectiveness(self, action: str,
                                 state_before: Dict[str, Any],
                                 state_after: Dict[str, Any]) -> float:
        if action == "handle_evolution_signal":
            return 0.7 if state_after.get("healing_success", False) else 0.2
        elif action == "monitoring_cycle":
            successes = state_after.get("heal_successes", 0)
            attempts = state_after.get("heal_attempts", 1) or 1
            return 0.3 + min(0.5, successes / max(attempts, 1))
        elif action == "generate_ops_report":
            anomalies = state_after.get("anomalies_detected", 0)
            return 0.4 if anomalies < 10 else (0.2 if anomalies < 50 else 0.0)
        return 0.0

    def _learn_from_ops(self, causal_pairs: List[Any],
                         effectiveness_summary: Dict[str, Any]) -> Dict[str, Any]:
        healer_stats = self._healer.get_stats()
        baseline_stats = self._baseline.get_stats()
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "heal_attempts": healer_stats.get("total_heal_attempts", 0),
            "heal_successes": healer_stats.get("total_heal_successes", 0),
            "escalations": healer_stats.get("total_escalations", 0),
            "anomalies_detected": baseline_stats.get("anomalies_detected", 0),
            "rate_limited": healer_stats.get("rate_limited_rejections", 0),
        }

    def _evolve_ops_config(self, learn_result: Dict[str, Any],
                            mutable_config: Dict[str, Any]) -> Dict[str, Any]:
        changes = {}
        anomalies = learn_result.get("anomalies_detected", 0)
        if anomalies > 50:
            changes["collect_interval"] = max(60,
                mutable_config.get("collect_interval", 300) / 2)
            changes["monitor_interval"] = max(120,
                mutable_config.get("monitor_interval", 600) / 2)
        elif anomalies < 5:
            changes["collect_interval"] = 300
            changes["monitor_interval"] = 600
        escalations = learn_result.get("escalations", 0)
        if escalations > 20:
            changes["heal_rate_limit_per_hour"] = min(6,
                mutable_config.get("heal_rate_limit_per_hour", 3) + 1)
        return {"rules_modified": changes, "skills_created": []}


DEFAULT_OPS_COORDINATOR: Optional[AutoOpsCoordinator] = None


def get_ops_coordinator() -> Optional[AutoOpsCoordinator]:
    return DEFAULT_OPS_COORDINATOR


def init_ops_coordinator(registry=None, evolution_bus=None,
                         governance_pipeline=None) -> AutoOpsCoordinator:
    global DEFAULT_OPS_COORDINATOR
    DEFAULT_OPS_COORDINATOR = AutoOpsCoordinator(
        registry=registry,
        evolution_bus=evolution_bus,
        governance_pipeline=governance_pipeline,
    )
    return DEFAULT_OPS_COORDINATOR


__all__ = ["AutoOpsCoordinator", "init_ops_coordinator"]  # [FIX-autoops-coord-003] 补充init_ops_coordinator导出
