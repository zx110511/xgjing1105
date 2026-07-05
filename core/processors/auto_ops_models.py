# -*- coding: utf-8-sig -*-
"""自动运维 — 数据模型

从 auto_ops.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-autoops-models-001] 延迟类型注解求值,避免前向引用NameError

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

# [FIX-autoops-001] 修复unexpected indent: 移除错误缩进的导入(这些类已在其他位置定义)
from typing import Optional

class HealingAction(str, Enum):
    NONE = "none"
    RESTART = "restart"
    ROLLBACK_CONFIG = "rollback_config"
    REINITIALIZE = "reinitialize"
    CLEAR_CACHE = "clear_cache"
    REDUCE_LOAD = "reduce_load"
    MARK_DEGRADED = "mark_degraded"
    MARK_ERROR = "mark_error"
    ESCALATE = "escalate"


class HealingSeverity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    SPIKE = "spike"
    DIP = "dip"
    DRIFT = "drift"
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    OSCILLATION = "oscillation"


class ScaleDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    NONE = "none"


@dataclass
class HealingRecord:
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    module_id: str = ""
    action: HealingAction = HealingAction.NONE
    severity: HealingSeverity = HealingSeverity.MILD
    trigger_signal: Optional[Dict[str, Any]] = None
    state_before: Optional[Dict[str, Any]] = None
    state_after: Optional[Dict[str, Any]] = None
    success: bool = False
    error_message: str = ""
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "module_id": self.module_id,
            "action": self.action.value,
            "severity": self.severity.value,
            "trigger_signal": self.trigger_signal,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "success": self.success,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class MetricSnapshot:
    module_id: str
    metric_name: str
    value: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class AnomalyReport:
    module_id: str
    metric_name: str
    anomaly_type: AnomalyType
    current_value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    severity: float
    recommendation: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "module_id": self.module_id,
            "metric_name": self.metric_name,
            "anomaly_type": self.anomaly_type.value,
            "current_value": self.current_value,
            "baseline_mean": self.baseline_mean,
            "baseline_std": self.baseline_std,
            "z_score": self.z_score,
            "severity": self.severity,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp,
        }


@dataclass
class ScaleRecommendation:
    module_id: str
    direction: ScaleDirection
    urgency: float
    reason: str
    current_load: float
    recommended_target: float
    supporting_metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "module_id": self.module_id,
            "direction": self.direction.value,
            "urgency": self.urgency,
            "reason": self.reason,
            "current_load": self.current_load,
            "recommended_target": self.recommended_target,
            "supporting_metrics": self.supporting_metrics,
            "timestamp": self.timestamp,
        }




__all__ = ["HealingAction", "HealingSeverity", "AnomalyType", "ScaleDirection", "HealingRecord", "MetricSnapshot", "AnomalyReport", "ScaleRecommendation"]
