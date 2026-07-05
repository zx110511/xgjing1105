# -*- coding: utf-8-sig -*-
"""engine_consolidate.py — ICMEEngineConsolidateMixin (SSS-PhaseB)

从 engine.py 拆分的方法组: consolidate
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

class ICMEEngineConsolidateMixin:
    """consolidate方法组Mixin"""


    def consolidate(self, from_layer: str, to_layer: str, entry_id: str) -> str | None:
        return self._promoter.consolidate(from_layer, to_layer, entry_id)

    def consolidate_batch(
        self,
        from_layer: str,
        to_layer: str | None = None,
        threshold: float = 0.6,
        max_entries: int = 50,
        use_quality_promotion: bool = True,
    ) -> dict:
        return self._promoter.consolidate_batch(
            from_layer, to_layer, threshold, max_entries, use_quality_promotion
        )

    def smart_promote(
        self, layer: str, threshold: float = 0.6, limit: int = 10
    ) -> list[dict]:
        return self._promoter.smart_promote(layer, threshold, limit)

    def consolidate_all_layers(
        self, threshold: float = 0.6, max_per_layer: int = 30
    ) -> dict:
        return self._promoter.consolidate_all_layers(threshold, max_per_layer)

    def check_l0_ttl(
        self, ttl_days: int = 7, archive_days: int = 30, max_l0_size_mb: float = 10.0
    ) -> dict:
        return self._promoter.check_l0_ttl(ttl_days, archive_days, max_l0_size_mb)

    def get_consolidation_candidates(
        self, layer: str = "", threshold: float = 0.5
    ) -> list[dict]:
        return self._promoter.get_consolidation_candidates(layer, threshold)

    def promotion_score(self, entry: MemoryEntry, engine=None) -> float:
        return self._promoter.promotion_score(entry, engine)

    def force_consolidate_layer(self, layer_name: str) -> int:
        return self._promoter.force_consolidate_layer(layer_name)

    def _check_orchestration_trigger(self, *args, **kwargs):
        return self._promoter._check_orchestration_trigger(*args, **kwargs)

    def _should_consolidate(self, *args, **kwargs):
        return self._promoter._should_consolidate(*args, **kwargs)

    def _can_consolidate_now(self, *args, **kwargs):
        return self._promoter._can_consolidate_now(*args, **kwargs)

    def _reset_accumulation(self, *args, **kwargs):
        return self._promoter._reset_accumulation(*args, **kwargs)

    def _log_consolidation_event(self, *args, **kwargs):
        return self._promoter._log_consolidation_event(*args, **kwargs)

    def _validate_consolidation_params(self, *args, **kwargs):
        return self._promoter._validate_consolidation_params(*args, **kwargs)

    def _create_consolidated_entry(self, *args, **kwargs):
        return self._promoter._create_consolidated_entry(*args, **kwargs)

    def _calculate_recency_factor(self, *args, **kwargs):
        return self._promoter._calculate_recency_factor(*args, **kwargs)

    def _calculate_weighted_promotion_sum(self, *args, **kwargs):
        return self._promoter._calculate_weighted_promotion_sum(*args, **kwargs)

    def _calc_upstream_depth(self, *args, **kwargs):
        return self._promoter._calc_upstream_depth(*args, **kwargs)

    def _calc_connectedness(self, *args, **kwargs):
        return self._promoter._calc_connectedness(*args, **kwargs)

    def _calc_quality_score(self, *args, **kwargs):
        return self._promoter._calc_quality_score(*args, **kwargs)

    def _calc_delta_frequency(self, *args, **kwargs):
        return self._promoter._calc_delta_frequency(*args, **kwargs)

    def _calc_consolidation_benefit(self, *args, **kwargs):
        return self._promoter._calc_consolidation_benefit(*args, **kwargs)

    def _calc_margin_pressure(self, *args, **kwargs):
        return self._promoter._calc_margin_pressure(*args, **kwargs)

    def _auto_consolidate(self, *args, **kwargs):
        return self._promoter._auto_consolidate(*args, **kwargs)

    def _check_hard_cap(self, *args, **kwargs):
        return self._promoter._check_hard_cap(*args, **kwargs)

    def _progressive_orchestration(self, *args, **kwargs):
        return self._promoter._progressive_orchestration(*args, **kwargs)

    # ====================================================================
    # 归档/容量委派 → ArchiveManager
    # ====================================================================
