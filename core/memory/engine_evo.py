# -*- coding: utf-8-sig -*-
"""engine_evo.py — ICMEEngineEvoMixin (SSS-PhaseB)

从 engine.py 拆分的方法组: evo
"""

import json
import threading
import time
from collections import OrderedDict, defaultdict
from typing import Any
from ..shared.config import DEFAULT_CONFIG, ICMEConfig, TIANJI_V91_PROTOCOL_MODE
from ..shared.learning_bridge import ClosedLoopLearningBridge
from . import (
    ArchiveManager,
    MemoryEntry,
    MemoryIndex,
    MemoryWriter,
    PromotionEngine,
)
try:
    from ..processors.conflict_resolver import (
        ConflictResolver,
        ConflictType,
        ResolutionStrategy,
        ResolutionVerdict,
    )
    from ..processors.consolidation_processor import (
        ConsolidationProcessor,
        OrchestrationStrategy,
    )
    from ..processors.preference_drift_detector import (
        DriftType,
        PreferenceDriftDetector,
    )
    _PROCESSORS_AVAILABLE = True
except ImportError:
    _PROCESSORS_AVAILABLE = False
__all__ = ["ICMEEngine", "MemoryEntry"]



from typing import Optional

class ICMEEngineEvoMixin:
    """evo方法组Mixin"""

    def _calc_engine_effectiveness(
        self, action: str, state_before: dict, state_after: dict
    ) -> float:
        if action == "memory_write":
            if state_after.get("result") == "rejected":
                return -0.3
            if state_after.get("result") == "downgraded":
                return -0.1
            if state_after.get("result") == "stored":
                return 0.3
        if action == "consolidation":
            if state_after.get("entries_consolidated", 0) > 0:
                return 0.4
            return -0.1
        if action == "capacity_enforcement":
            return -0.5
        return 0.0

    def _learn_from_engine_ops(self, causal_pairs, effectiveness_summary) -> dict:
        cap_enforcements = sum(
            1 for p in causal_pairs if p.action == "capacity_enforcement"
        )
        rejections = sum(
            1
            for p in causal_pairs
            if p.action == "memory_write" and p.effectiveness < 0
        )
        hot_layers = []
        for layer_name, size in self._layer_sizes.items():
            cap = next(
                (l.max_size_bytes for l in self.config.layers if l.name == layer_name),
                1,
            )
            if cap > 0 and size / cap > 0.7:
                hot_layers.append(layer_name)
        return {
            "capacity_enforcements": cap_enforcements,
            "write_rejections": rejections,
            "hot_layers": hot_layers,
            "avg_effectiveness": effectiveness_summary.get("avg", 0.0),
        }

    def _evolve_engine_config(self, learn_result, mutable_config) -> dict:
        changes = []
        hot_layers = learn_result.get("hot_layers", [])
        if len(hot_layers) >= 2:
            old_threshold = mutable_config.get("consolidation_threshold", 0.8)
            new_threshold = max(old_threshold - 0.05, 0.5)
            changes.append(
                {
                    "rule": "consolidation_threshold",
                    "old_value": old_threshold,
                    "new_value": new_threshold,
                }
            )
        if learn_result.get("write_rejections", 0) > 10:
            old_promo = mutable_config.get("promotion_min_score", 0.6)
            new_promo = max(old_promo - 0.05, 0.3)
            changes.append(
                {
                    "rule": "promotion_min_score",
                    "old_value": old_promo,
                    "new_value": new_promo,
                }
            )
        return {"changes": changes}

    def _get_engine_health(self) -> dict[str, float]:
        total_cap = sum(l.max_size_bytes for l in self.config.layers) or 1
        total_used = sum(self._layer_sizes.values())
        return {
            "capacity_usage": total_used / total_cap,
            "error_rate": self._stats.get("total_rejected", 0)
            / max(self._stats.get("total_entries", 1), 1),
        }

    @property
    def evolution_loop(self):
        return self._evo_loop

    def _sync_evo_config(self):
        if not self._evo_loop:
            return
        mc = self._evo_loop.mutable_config
        if "consolidation_threshold" in mc:
            pass

    def _trigger_evolution_cycle(self, layer_name: str = ""):
        """在固结完成后触发一轮进化循环"""

        if not self._evo_loop:
            return
        try:
            health = self._get_engine_health()
            urgency = self._evo_loop.urgency_accumulator.current_urgency()
            if urgency >= 5.0 or health.get("capacity_usage", 0) > 0.7:
                self._evo_loop.trigger(reason=f"post_consolidation({layer_name})")
        except Exception:
            pass

    # ====================================================================
    # 持久化 / 目录管理 (engine 共享基础设施)
    # ====================================================================
