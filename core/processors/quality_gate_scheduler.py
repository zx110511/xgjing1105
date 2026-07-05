# -*- coding: utf-8-sig -*-
"""质量门禁 — 自动调优调度器

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
from .quality_gate_adaptive import ConsumerAwareAdaptiveGate
class AutoTuningScheduler:
    """门禁自适应阈值自动调优调度器  [v10-ready]"""

    CONSUMERS = [
        "dictionary_builder",
        "knowledge_extractor",
        "semantic_indexer",
        "learning_loop",
        "evolution_loop",
        "audit_logger",
        "skill_extractor",
        "insight_engine",
        "reflection_engine",
    ]

    def __init__(
        self, adaptive_gate: ConsumerAwareAdaptiveGate, interval_seconds: float = 300.0
    ):
        """初始化调度器  [v10-ready]"""
        self._gate = adaptive_gate
        self._interval = interval_seconds
        self._running = False
        self._thread: Optional[Any] = None
        self._scheduler_lock = threading.Lock() if hasattr(threading, "Lock") else None
        self._cycle_count: int = 0
        self._total_tunings: int = 0
        self._last_tuning: float = 0.0

    def start(self):
        """启动后台调优线程  [v10-ready]"""
        if self._running:
            return
        self._running = True
        if hasattr(threading, "Thread"):
            self._thread = threading.Thread(
                target=self._scheduler_loop, daemon=True, name="tianji-auto-tuning"
            )
            self._thread.start()

    def stop(self):
        """停止调优线程  [v10-ready]"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _scheduler_loop(self):
        """调度主循环  [v10-ready]"""
        while self._running:
            try:
                time.sleep(self._interval)
                if not self._running:
                    break
                self._run_single_cycle()
            except Exception:
                pass

    def _run_single_cycle(self):
        """执行单次调优周期  [v10-ready]"""
        self._scan_all_consumers()
        self._detect_consumer_pressure()
        self._gate.run_tuning_cycle()
        self._cycle_count += 1
        self._total_tunings += 1
        self._last_tuning = time.time()

    def _scan_all_consumers(self):
        """扫描所有消费者并模拟压力  [v10-ready]"""
        for consumer_name in self.CONSUMERS:
            current_pressure = self._gate._consumer_pressure.get(consumer_name, 0.0)
            if current_pressure == 0.0:
                simulated = (
                    0.3 + (hash(consumer_name + str(self._cycle_count)) % 100) / 200.0
                )
                self._gate.update_consumer_pressure(consumer_name, min(1.0, simulated))

    def _detect_consumer_pressure(self):
        """根据压力推断负载与反馈质量  [v10-ready]"""
        pressures = list(self._gate._consumer_pressure.values())
        if pressures:
            avg = sum(pressures) / len(pressures)
            load = 0.3 + avg * 0.5
            self._gate.update_system_load(min(0.95, load))
            quality = max(0.3, 1.0 - avg * 0.6)
            self._gate.update_feedback_quality(min(1.0, quality))

    def run_now(self) -> Dict:
        """立即执行一次调优  [v10-ready]"""
        result = {}
        try:
            old_thresholds = self._gate.get_adaptive_thresholds()
            self._run_single_cycle()
            new_thresholds = self._gate.get_adaptive_thresholds()
            result = {
                "status": "completed",
                "cycle": self._cycle_count,
                "total_tunings": self._total_tunings,
                "old_thresholds": old_thresholds,
                "new_thresholds": new_thresholds,
                "consumer_pressures": dict(self._gate._consumer_pressure),
                "system_load": self._gate._system_load,
                "feedback_quality": self._gate._feedback_quality,
            }
        except Exception as e:
            result = {"status": "error", "error": str(e)[:200]}
        return result

    def get_scheduler_stats(self) -> Dict:
        """调度器统计  [v10-ready]"""
        return {
            "running": self._running,
            "interval_seconds": self._interval,
            "cycles_completed": self._cycle_count,
            "total_tunings": self._total_tunings,
            "last_tuning": self._last_tuning,
            "last_tuning_age": time.time() - self._last_tuning
            if self._last_tuning
            else -1,
            "gate_stats": self._gate.get_stats(),
        }

    @property
    def is_running(self) -> bool:
        """调度器运行状态  [v10-ready]"""
        return self._running


__all__ = [
    # v9.1 兼容载体
    "GateVerdict",
    "GateResult",
    "QualityGate",
    "ConsumerAwareAdaptiveGate",
    "AutoTuningScheduler",
    # 门禁插件 (core.gate 重新导出)
    "NoiseFilter",
    "PolicyEngine",
    "LocalGateStrategy",
    "RemoteGateStrategy",
    "PLUGIN_INFO",
    # v10 协议契约 (重新导出)
    "ProtocolGateVerdict",
    "ProtocolGateResult",
    "IGateStrategy",
    "IGatePolicy",
]


__all__ = ["AutoTuningScheduler"]
