# -*- coding: utf-8-sig -*-
"""质量门禁 — 自适应门禁

从 quality_gate.py 拆分 (SSS-PhaseB)
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from ..shared.config import DEFAULT_CONFIG, QualityGateConfig
from .gate import (
    PLUGIN_INFO,
    LocalGateStrategy,
    NoiseFilter,
    PolicyEngine,
    RemoteGateStrategy,
)
from .gate.noise_filter import (
    char_ngrams,
    has_semantic_overlap,
    longest_common_substring,
)
from ..shared.protocols import (
    GateResult as ProtocolGateResult,
)
from ..shared.protocols import (
    GateVerdict as ProtocolGateVerdict,
)
from ..shared.protocols import (
    IGatePolicy,
    IGateStrategy,
)
try:
    from .processors.conflict_resolver import (
        ConflictResolver,
        ResolutionVerdict,
    )
    from .processors.preference_drift_detector import PreferenceDriftDetector
except ImportError:
    ConflictResolver = None
    ResolutionVerdict = None
    PreferenceDriftDetector = None
try:
    from .evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None
from .quality_gate_core import QualityGate
class ConsumerAwareAdaptiveGate:
    """Consumer-Aware 自适应门禁 — 按下游消费压力动态调阈值  [v10-ready]

    核心逻辑:
      - 活跃 Consumer 需求压力高 → 降低 min_value_score，收录更多内容
      - 系统负载高 → 提高 max_similarity，减少重复写入
      - Feedback 反馈质量差 → 提高噪音阈值，收紧门禁
    """

    def __init__(self, gate: QualityGate):
        """初始化自适应门禁包装  [v10-ready]"""
        self._gate = gate
        self._consumer_pressure: Dict[str, float] = {}
        self._system_load: float = 0.5
        self._feedback_quality: float = 0.8
        self._adjustment_history: List[Dict] = []
        self._lock = threading.Lock() if hasattr(threading, "Lock") else None

    def update_consumer_pressure(self, consumer_name: str, pressure: float):
        """更新指定消费者压力  [v10-ready]"""
        self._consumer_pressure[consumer_name] = max(0.0, min(1.0, pressure))

    def update_system_load(self, load: float):
        """更新系统负载  [v10-ready]"""
        self._system_load = max(0.1, min(1.0, load))

    def update_feedback_quality(self, quality: float):
        """更新反馈质量  [v10-ready]"""
        self._feedback_quality = max(0.1, min(1.0, quality))

    def get_adaptive_thresholds(self) -> Dict[str, float]:
        """计算自适应阈值  [v10-ready]"""
        avg_pressure = sum(self._consumer_pressure.values()) / max(
            len(self._consumer_pressure), 1
        )
        base_noise = getattr(self._gate.config, "noise_threshold", 0.3)
        base_dup = getattr(self._gate.config, "duplicate_threshold", 0.85)
        base_min_len = getattr(self._gate.config, "min_content_length", 30)
        adjusted_noise = base_noise * (1.0 + (1.0 - self._feedback_quality) * 0.5)
        adjusted_noise = min(0.6, max(0.1, adjusted_noise))
        adjusted_dup = base_dup * (1.0 - avg_pressure * 0.15)
        adjusted_dup = min(0.95, max(0.6, adjusted_dup))
        adjusted_min_len = base_min_len * (1.0 - avg_pressure * 0.3)
        adjusted_min_len = max(15, int(adjusted_min_len))
        return {
            "noise_threshold": round(adjusted_noise, 3),
            "duplicate_threshold": round(adjusted_dup, 3),
            "min_content_length": adjusted_min_len,
            "effective_value_score": round(0.3 * (1.0 - avg_pressure * 0.4), 3),
            "consumer_pressure": round(avg_pressure, 3),
            "system_load": self._system_load,
            "feedback_quality": round(self._feedback_quality, 3),
        }

    def apply(self) -> Dict:
        """应用自适应阈值至门禁配置  [v10-ready]"""
        thresholds = self.get_adaptive_thresholds()
        old_thresholds = {
            "noise_threshold": getattr(self._gate.config, "noise_threshold", 0.3),
            "duplicate_threshold": getattr(
                self._gate.config, "duplicate_threshold", 0.85
            ),
            "min_content_length": getattr(self._gate.config, "min_content_length", 30),
        }
        self._gate.config.noise_threshold = thresholds["noise_threshold"]
        self._gate.config.duplicate_threshold = thresholds["duplicate_threshold"]
        self._gate.config.min_content_length = thresholds["min_content_length"]
        change = {
            "timestamp": time.time(),
            "old": old_thresholds,
            "new": {
                "noise_threshold": thresholds["noise_threshold"],
                "duplicate_threshold": thresholds["duplicate_threshold"],
                "min_content_length": thresholds["min_content_length"],
            },
            "consumer_pressure": thresholds["consumer_pressure"],
        }
        self._adjustment_history.append(change)
        if len(self._adjustment_history) > 100:
            self._adjustment_history = self._adjustment_history[-100:]
        return change

    def get_stats(self) -> Dict:
        """自适应门禁统计  [v10-ready]"""
        return {
            "adaptive_enabled": True,
            "current_thresholds": self.get_adaptive_thresholds(),
            "adjustment_count": len(self._adjustment_history),
            "last_adjustment": self._adjustment_history[-1]
            if self._adjustment_history
            else None,
            "consumer_pressure": dict(self._consumer_pressure),
        }

    def run_tuning_cycle(self) -> Dict:
        """执行一次调优周期  [v10-ready]"""
        result = {"timestamp": time.time(), "action": "tuning_cycle", "adjustments": {}}
        old_thresholds = {
            "noise_threshold": getattr(self._gate.config, "noise_threshold", 0.3),
            "duplicate_threshold": getattr(
                self._gate.config, "duplicate_threshold", 0.85
            ),
            "min_content_length": getattr(self._gate.config, "min_content_length", 30),
        }
        change = self.apply()
        result["adjustments"] = {
            "old": old_thresholds,
            "new": {
                "noise_threshold": change["new"]["noise_threshold"],
                "duplicate_threshold": change["new"]["duplicate_threshold"],
                "min_content_length": change["new"]["min_content_length"],
            },
            "consumer_pressure": change["consumer_pressure"],
            "delta_noise": round(
                change["new"]["noise_threshold"] - old_thresholds["noise_threshold"], 4
            ),
            "delta_dup": round(
                change["new"]["duplicate_threshold"]
                - old_thresholds["duplicate_threshold"],
                4,
            ),
            "delta_min_len": change["new"]["min_content_length"]
            - old_thresholds["min_content_length"],
        }
        return result

    def get_tuning_history(self, limit: int = 20) -> List[Dict]:
        """获取调优历史  [v10-ready]"""
        return self._adjustment_history[-limit:]

    def get_tuning_summary(self) -> Dict:
        """获取调优摘要  [v10-ready]"""
        history = self._adjustment_history[-50:]
        if not history:
            return {"total_adjustments": 0}
        noise_changes = [
            h["new"]["noise_threshold"] - h["old"]["noise_threshold"] for h in history
        ]
        dup_changes = [
            h["new"]["duplicate_threshold"] - h["old"]["duplicate_threshold"]
            for h in history
        ]
        return {
            "total_adjustments": len(self._adjustment_history),
            "recent_adjustments": len(history),
            "avg_noise_delta": round(sum(noise_changes) / len(noise_changes), 4),
            "avg_dup_delta": round(sum(dup_changes) / len(dup_changes), 4),
            "trend": "tightening" if sum(noise_changes) > 0 else "loosening",
            "last_adjustment_age_seconds": time.time()
            - (history[-1]["timestamp"] if history else time.time()),
        }




__all__ = ["ConsumerAwareAdaptiveGate"]
