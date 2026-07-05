# -*- coding: utf-8-sig -*-
"""进化闭环 — 模块挑战者 (ModuleChallenger)

从 evolution_loop.py 拆分，负责主动扫描模块健康指标，发现问题。
"""


import threading  # SSS-PhaseE: 补充缺失导入
from typing import Any, Dict, List, Optional
from .evolution_loop_models import EvolutionSignal, EvolutionSignalType

class ModuleChallenger:
    """
    模块级挑战者 — 主动寻找问题而非被动等待异常

    每个模块的EvolutionLoop内置一个Challenger，
    定期扫描模块健康指标，主动生成挑战信号。

    扫描维度:
      1. 容量健康: 层/存储是否接近上限?
      2. 效率健康: 操作耗时是否异常?
      3. 质量健康: 拒绝率/降级率是否上升?
      4. 利用健康: 资源利用率是否过低?
      5. 趋势健康: 指标是否持续恶化?
    """

    DEFAULT_HEALTH_METRICS = {
        "capacity_usage": {"warn": 0.7, "critical": 0.9},
        "rejection_rate": {"warn": 0.15, "critical": 0.3},
        "downgrade_rate": {"warn": 0.1, "critical": 0.2},
        "avg_latency_ms": {"warn": 500, "critical": 2000},
        "error_rate": {"warn": 0.05, "critical": 0.1},
        "utilization": {"warn": 0.1, "critical": 0.05},
    }

    def __init__(
        self,
        module_name: str,
        health_metrics: Optional[Dict] = None,
        scan_interval: float = 300.0,
    ):
        self._module_name = module_name
        self._health_metrics = health_metrics or self.DEFAULT_HEALTH_METRICS
        self._scan_interval = scan_interval
        self._last_scan = 0.0
        self._metric_history: Dict[str, List[Tuple[float, float]]] = {}
        self._lock = threading.Lock()
        self._stats = {
            "scans_performed": 0,
            "challenges_generated": 0,
            "trends_detected": 0,
        }

    def scan(self, current_metrics: Dict[str, float]) -> List[EvolutionSignal]:
        signals = []
        now = time.time()

        if now - self._last_scan < self._scan_interval:
            return signals

        self._last_scan = now
        self._stats["scans_performed"] += 1

        for metric_name, value in current_metrics.items():
            thresholds = self._health_metrics.get(metric_name)
            if not thresholds:
                continue

            warn = thresholds.get("warn", 0.7)
            critical = thresholds.get("critical", 0.9)

            is_inverse = metric_name == "utilization"

            if is_inverse:
                if value < critical:
                    severity = 1.0 - (value / critical) if critical > 0 else 1.0
                    signals.append(
                        EvolutionSignal(
                            source_module=self._module_name,
                            signal_type=EvolutionSignalType.CAPACITY_PRESSURE,
                            severity=min(severity, 1.0),
                            description=f"{metric_name}={value:.2f} 低于临界值{critical}",
                            data={
                                "metric": metric_name,
                                "value": value,
                                "threshold": critical,
                            },
                        )
                    )
                elif value < warn:
                    severity = (warn - value) / warn if warn > 0 else 0.5
                    signals.append(
                        EvolutionSignal(
                            source_module=self._module_name,
                            signal_type=EvolutionSignalType.SKILL_UNDERUSE,
                            severity=min(severity, 1.0),
                            description=f"{metric_name}={value:.2f} 低于警告值{warn}",
                            data={
                                "metric": metric_name,
                                "value": value,
                                "threshold": warn,
                            },
                        )
                    )
            else:
                if value > critical:
                    severity = (
                        (value - critical) / (1.0 - critical) if critical < 1.0 else 1.0
                    )
                    signal_type = self._map_metric_to_signal(metric_name)
                    signals.append(
                        EvolutionSignal(
                            source_module=self._module_name,
                            signal_type=signal_type,
                            severity=min(severity, 1.0),
                            description=f"{metric_name}={value:.2f} 超过临界值{critical}",
                            data={
                                "metric": metric_name,
                                "value": value,
                                "threshold": critical,
                            },
                        )
                    )
                elif value > warn:
                    severity = (
                        (value - warn) / (critical - warn) if critical > warn else 0.5
                    )
                    signal_type = self._map_metric_to_signal(metric_name)
                    signals.append(
                        EvolutionSignal(
                            source_module=self._module_name,
                            signal_type=signal_type,
                            severity=min(severity, 0.7),
                            description=f"{metric_name}={value:.2f} 超过警告值{warn}",
                            data={
                                "metric": metric_name,
                                "value": value,
                                "threshold": warn,
                            },
                        )
                    )

            self._record_metric(metric_name, value)

        trend_signals = self._detect_trends()
        signals.extend(trend_signals)

        self._stats["challenges_generated"] += len(signals)
        return signals

    def _map_metric_to_signal(self, metric_name: str) -> EvolutionSignalType:
        mapping = {
            "capacity_usage": EvolutionSignalType.CAPACITY_PRESSURE,
            "rejection_rate": EvolutionSignalType.GATE_MISJUDGMENT,
            "downgrade_rate": EvolutionSignalType.QUALITY_DEGRADATION,
            "avg_latency_ms": EvolutionSignalType.ROUTE_INEFFICIENCY,
            "error_rate": EvolutionSignalType.WORKFLOW_BOTTLENECK,
        }
        return mapping.get(metric_name, EvolutionSignalType.CUSTOM)

    def _record_metric(self, metric_name: str, value: float):
        with self._lock:
            if metric_name not in self._metric_history:
                self._metric_history[metric_name] = []
            self._metric_history[metric_name].append((time.time(), value))
            if len(self._metric_history[metric_name]) > 100:
                self._metric_history[metric_name] = self._metric_history[metric_name][
                    -50:
                ]

    def _detect_trends(self) -> List[EvolutionSignal]:
        signals = []
        with self._lock:
            for metric_name, history in self._metric_history.items():
                if len(history) < 5:
                    continue

                recent = [v for _, v in history[-5:]]
                older = (
                    [v for _, v in history[-10:-5]]
                    if len(history) >= 10
                    else recent[:2]
                )

                avg_recent = sum(recent) / len(recent)
                avg_older = sum(older) / len(older)

                is_inverse = metric_name == "utilization"

                if is_inverse:
                    if avg_recent < avg_older * 0.7:
                        signals.append(
                            EvolutionSignal(
                                source_module=self._module_name,
                                signal_type=EvolutionSignalType.SKILL_UNDERUSE,
                                severity=0.6,
                                description=f"{metric_name}趋势下降: {avg_older:.2f}→{avg_recent:.2f}",
                                data={"metric": metric_name, "trend": "declining"},
                            )
                        )
                else:
                    if avg_recent > avg_older * 1.3:
                        signals.append(
                            EvolutionSignal(
                                source_module=self._module_name,
                                signal_type=EvolutionSignalType.QUALITY_DEGRADATION,
                                severity=0.6,
                                description=f"{metric_name}趋势上升: {avg_older:.2f}→{avg_recent:.2f}",
                                data={"metric": metric_name, "trend": "worsening"},
                            )
                        )

        if signals:
            self._stats["trends_detected"] += len(signals)
        return signals

    def get_stats(self) -> Dict:
        with self._lock:
            return {**self._stats, "last_scan": self._last_scan}




__all__ = ["ModuleChallenger"]
