# -*- coding: utf-8-sig -*-
"""engine_forget.py — ICMEEngineForgetMixin (SSS-PhaseB)

从 engine.py 拆分的方法组: forget
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

class ICMEEngineForgetMixin:
    """forget方法组Mixin"""


    def forget(self, entry_id: str) -> bool:
        return self._archiver.forget(entry_id)

    def force_evict_overcapacity(
        self, layer: str, target_ratio: float = 0.8, max_evict: int = 200
    ) -> dict:
        return self._archiver.force_evict_overcapacity(layer, target_ratio, max_evict)

    def purge_layer(self, layer_name: str) -> int:
        return self._archiver.purge_layer(layer_name)
