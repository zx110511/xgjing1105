# -*- coding: utf-8-sig -*-
"""engine_capacity.py — ICMEEngineCapacityMixin (SSS-PhaseB)

从 engine.py 拆分的方法组: capacity
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

class ICMEEngineCapacityMixin:
    """capacity方法组Mixin"""


    def get_layer_capacity_info(self) -> dict[str, dict]:
        return self._archiver.get_layer_capacity_info()

    def get_accumulation_stats(self) -> dict[str, dict]:
        return self._archiver.get_accumulation_stats()

    def _get_layer_size(self, *args, **kwargs):
        return self._archiver._get_layer_size(*args, **kwargs)

    def _update_layer_size(self, *args, **kwargs):
        return self._archiver._update_layer_size(*args, **kwargs)

    def _get_layer_usage(self, *args, **kwargs):
        return self._archiver._get_layer_usage(*args, **kwargs)

    def _get_margin_ratio(self, *args, **kwargs):
        return self._archiver._get_margin_ratio(*args, **kwargs)

    def _get_margin_level(self, *args, **kwargs):
        return self._archiver._get_margin_level(*args, **kwargs)

    def _calc_current_rate(self, *args, **kwargs):
        return self._archiver._calc_current_rate(*args, **kwargs)

    def _get_accumulation_ratio(self, *args, **kwargs):
        return self._archiver._get_accumulation_ratio(*args, **kwargs)

    def _get_accumulation_entry_ratio(self, *args, **kwargs):
        return self._archiver._get_accumulation_entry_ratio(*args, **kwargs)

    # ====================================================================
    # 统计 / 一致性 / 导出 (engine 编排层职责)
    # ====================================================================
