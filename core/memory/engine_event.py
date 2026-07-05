# -*- coding: utf-8-sig -*-
"""engine_event.py — ICMEEngineEventMixin (SSS-PhaseB)

从 engine.py 拆分的方法组: event
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

class ICMEEngineEventMixin:
    """event方法组Mixin"""

    def _emit_event(self, event_type: str, memory_id: str, layer: str, payload: dict):
        if self._sqlite_store:
            try:
                self._sqlite_store.append_event(event_type, memory_id, layer, payload)
            except Exception:
                pass
        # [v10-ready] v9.1: 额外发布到进程内事件总线 (可用时)。
        # 发布失败静默降级，绝不影响主流程。
        self._publish_to_event_bus(
            event_type, {"memory_id": memory_id, "layer": layer, **(payload or {})}
        )

    # ====================================================================
    # [v10-ready] v9.1 Protocol 集成: MemoryCore 委派 + 事件总线
    # ====================================================================
    def _publish_to_event_bus(self, event_type: str, payload: dict) -> None:
        """[v10-ready] 发布事件到总线，失败静默降级。"""
        try:
            bus = self._get_event_bus()
            if bus is not None:
                bus.publish(event_type, payload)
        except Exception:
            pass

    def _core_dict_to_entry(self, data: dict) -> MemoryEntry:
        """[v10-ready] 将 MemoryCore 返回的 dict 转为 MemoryEntry。"""


        now = time.time()
        return MemoryEntry(
            id=str(data.get("id", "")),
            content=str(data.get("content", "")),
            layer=str(data.get("layer", "working")),
            tags=list(data.get("tags", []) or []),
            priority=str(data.get("priority", "medium")),
            created_at=float(data.get("created_at", data.get("timestamp", now))),
            last_accessed=float(data.get("last_accessed", now)),
            access_count=int(data.get("access_count", 0)),
            effectiveness_score=float(data.get("effectiveness_score", 0.5)),
            related_ids=list(data.get("related_ids", []) or []),
            metadata=dict(data.get("metadata", {}) or {}),
            changelog=list(data.get("changelog", []) or []),
        )
