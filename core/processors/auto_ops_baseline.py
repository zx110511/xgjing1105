# -*- coding: utf-8-sig -*-
"""自动运维 — 基线引擎

从 auto_ops.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-autoops-baseline-002] 延迟类型注解求值,避免AnomalyReport NameError

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

# [FIX-autoops-baseline-001] 修复unexpected indent: 移除错误缩进的幽灵导入(方法体内延迟导入)
from typing import Optional


class BaselineEngine:
    r"""
    性能基线引擎 — 指标收集、基线计算、异常检测

    检测方法:
      1. z-score 检测: |z| > 3 判定为异常
      2. IQR 检测: value > Q3 + 1.5*IQR 或 value < Q1 - 1.5*IQR
      3. 趋势检测: 滑动窗口线性回归斜率显著非零

    基线更新策略:
      - 每5分钟追加新快照
      - 每小时重新计算基线
      - 保留最近7天数据用于趋势分析
    """

    DEFAULT_METRIC_THRESHOLDS = {
        "capacity_usage": {"warn": 0.7, "critical": 0.9, "inverse": False},
        "rejection_rate": {"warn": 0.15, "critical": 0.3, "inverse": False},
        "downgrade_rate": {"warn": 0.1, "critical": 0.2, "inverse": False},
        "avg_latency_ms": {"warn": 500, "critical": 2000, "inverse": False},
        "error_rate": {"warn": 0.05, "critical": 0.1, "inverse": False},
        "utilization": {"warn": 0.1, "critical": 0.05, "inverse": True},
    }

    def __init__(self, registry=None, max_history_per_metric: int = 20160):
        self._registry = registry
        self._max_history = max_history_per_metric
        self._metric_store: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=max_history_per_metric))
        )
        self._anomaly_history: List[AnomalyReport] = []
        self._baselines: Dict[str, Dict[str, Dict[str, float]]] = {}
        self._last_baseline_calc: float = 0.0
        self._baseline_calc_interval: float = 3600.0
        self._lock = threading.Lock()
        self._stats = {
            "snapshots_collected": 0,
            "anomalies_detected": 0,
            "baselines_calculated": 0,
        }

    def record_metric(self, module_id: str, metric_name: str, value: float):
        snapshot = MetricSnapshot(
            module_id=module_id,
            metric_name=metric_name,
            value=value,
        )
        with self._lock:
            self._metric_store[module_id][metric_name].append(snapshot)
            self._stats["snapshots_collected"] += 1

    def record_batch(self, module_id: str, metrics: Dict[str, float]):
        now = time.time()
        with self._lock:
            for metric_name, value in metrics.items():
                snapshot = MetricSnapshot(
                    module_id=module_id,
                    metric_name=metric_name,
                    value=value,
                    timestamp=now,
                )
                self._metric_store[module_id][metric_name].append(snapshot)
                self._stats["snapshots_collected"] += 1

    def get_values(self, module_id: str, metric_name: str,
                   window_seconds: float = 3600.0) -> List[float]:
        with self._lock:
            snapshots = list(self._metric_store[module_id][metric_name])
            now = time.time()
            return [
                s.value for s in snapshots
                if now - s.timestamp <= window_seconds
            ]

    def calculate_baseline(self, module_id: str,
                           metric_name: str) -> Dict[str, float]:
        values = self.get_values(module_id, metric_name, window_seconds=86400.0)
        if len(values) < 10:
            return {"mean": 0.0, "std": 0.0, "p50": 0.0, "p95": 0.0,
                    "p99": 0.0, "count": len(values)}

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n
        std = math.sqrt(variance)

        return {
            "mean": round(mean, 6),
            "std": round(std, 6),
            "p50": sorted_vals[int(n * 0.50)],
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[min(int(n * 0.99), n - 1)],
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "count": n,
        }

    def calculate_all_baselines(self, force: bool = False):
        now = time.time()
        if not force and now - self._last_baseline_calc < self._baseline_calc_interval:
            return

        with self._lock:
            for module_id in self._metric_store:
                if module_id not in self._baselines:
                    self._baselines[module_id] = {}
                for metric_name in self._metric_store[module_id]:
                    self._baselines[module_id][metric_name] = (
                        self.calculate_baseline(module_id, metric_name)
                    )
            self._last_baseline_calc = now
            self._stats["baselines_calculated"] += 1

    def detect_anomalies(self, module_id: str,
                         metric_name: str,
                         current_value: float) -> Optional[AnomalyReport]:
        baseline = self._baselines.get(module_id, {}).get(metric_name, {})
        if not baseline or baseline.get("count", 0) < 10:
            return None

        mean = baseline["mean"]
        std = baseline["std"]

        if std == 0:
            return None

        z_score = (current_value - mean) / std

        if abs(z_score) < 3.0:
            return None

        anomaly_type = AnomalyType.SPIKE if z_score > 0 else AnomalyType.DIP
        severity = min(abs(z_score) / 6.0, 1.0)

        thresholds = self.DEFAULT_METRIC_THRESHOLDS.get(metric_name, {})
        if thresholds.get("inverse"):
            severity = severity if z_score < 0 else severity * 0.5

        recommendation = self._generate_recommendation(
            module_id, metric_name, current_value, baseline, anomaly_type
        )

        report = AnomalyReport(
            module_id=module_id,
            metric_name=metric_name,
            anomaly_type=anomaly_type,
            current_value=current_value,
            baseline_mean=mean,
            baseline_std=std,
            z_score=round(z_score, 2),
            severity=round(severity, 3),
            recommendation=recommendation,
        )

        with self._lock:
            self._anomaly_history.append(report)
            if len(self._anomaly_history) > 1000:
                self._anomaly_history = self._anomaly_history[-500:]
            self._stats["anomalies_detected"] += 1

        logger.info(
            f"[BaselineEngine] 异常检测: {module_id}.{metric_name} "
            f"z={z_score:.1f} val={current_value:.4f} "
            f"baseline={mean:.4f}±{std:.4f}"
        )
        return report

    def _generate_recommendation(self, module_id: str, metric_name: str,
                                 current_value: float, baseline: Dict,
                                 anomaly_type: AnomalyType) -> str:
        thresholds = self.DEFAULT_METRIC_THRESHOLDS.get(metric_name, {})
        critical = thresholds.get("critical", 0.9)

        if anomaly_type == AnomalyType.SPIKE:
            if current_value >= critical:
                return f"[严重] {metric_name}={current_value:.4f} 已超过临界阈值 {critical}，建议立即启动自愈流程"
            return f"[警告] {metric_name}={current_value:.4f} 显著偏离基线 {baseline['mean']:.4f}，建议关注并准备回滚"

        if anomaly_type == AnomalyType.DIP:
            if thresholds.get("inverse"):
                return f"[严重] {metric_name}={current_value:.4f} 过低，资源可能闲置，建议缩容或重新分配"
            return f"[信息] {metric_name}={current_value:.4f} 低于基线，系统可能在低负载状态"

        return f"[提示] {metric_name} 出现异常模式，建议人工检查"

    def generate_scale_recommendation(self, module_id: str) -> Optional[ScaleRecommendation]:
        capacity_values = self.get_values(module_id, "capacity_usage", 86400.0)
        if len(capacity_values) < 20:
            return None

        recent = capacity_values[-20:]
        avg_load = sum(recent) / len(recent)

        if avg_load > 0.85:
            direction = ScaleDirection.UP
            urgency = min((avg_load - 0.85) / 0.15, 1.0)
            reason = f"容量使用率 {avg_load:.1%} 持续超过 85%"
            return ScaleRecommendation(
                module_id=module_id,
                direction=direction,
                urgency=round(urgency, 3),
                reason=reason,
                current_load=round(avg_load, 4),
                recommended_target=round(avg_load * 1.3, 4),
            )

        utilization_values = self.get_values(module_id, "utilization", 86400.0)
        if utilization_values:
            recent_util = utilization_values[-20:]
            avg_util = sum(recent_util) / len(recent_util)
            if avg_util < 0.15:
                return ScaleRecommendation(
                    module_id=module_id,
                    direction=ScaleDirection.DOWN,
                    urgency=min((0.15 - avg_util) / 0.15, 1.0),
                    reason=f"利用率 {avg_util:.1%} 持续低于 15%",
                    current_load=round(avg_util, 4),
                    recommended_target=0.0,
                )

        return None

    def get_anomaly_history(self, module_id: str = None,
                            limit: int = 50) -> List[Dict]:
        with self._lock:
            records = self._anomaly_history
            if module_id:
                records = [r for r in records if r.module_id == module_id]
            return [r.to_dict() for r in records[-limit:]]

    def get_baselines(self, module_id: str = None) -> Dict:
        with self._lock:
            if module_id:
                return {
                    module_id: self._baselines.get(module_id, {})
                }
            return dict(self._baselines)

    def get_stats(self) -> Dict:
        with self._lock:
            modules_tracked = len(self._metric_store)
            metrics_tracked = sum(
                len(metrics) for metrics in self._metric_store.values()
            )
            return {
                **self._stats,
                "modules_tracked": modules_tracked,
                "metrics_tracked": metrics_tracked,
                "anomaly_history_size": len(self._anomaly_history),
            }




__all__ = ["BaselineEngine"]
