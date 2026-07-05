# -*- coding: utf-8-sig -*-
"""engine_recall.py — ICMEEngineRecallMixin (SSS-PhaseB)

从 engine.py 拆分的方法组: recall
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

class ICMEEngineRecallMixin:
    """recall方法组Mixin"""

    def _recall_via_core(
        self,
        query: str | None,
        layers: list[str] | None,
        limit: int,
    ) -> list[MemoryEntry]:
        """[v10-ready] Protocol 模式下委派检索到对应层 MemoryCore。

        Raises:
            任何异常由调用方捕获以触发降级。
        """
        cores = self._memory_cores or {}
        target_names = layers if layers else list(cores.keys())
        results: list[MemoryEntry] = []
        for name in target_names:
            core = cores.get(name)
            if core is None:
                continue
            for data in core.search(query or "", limit=limit):
                results.append(self._core_dict_to_entry(data))
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        self._publish_to_event_bus(
            "memory.retrieved",
            {"query": query, "layers": target_names, "hits": len(results)},
        )
        return results[:limit]


    def recall(
        self,
        query: str | None = None,
        layers: list[str] | None = None,
        tags: list[str] | None = None,
        priority: list[str] | None = None,
        limit: int = 20,
        min_score: float = 0.1,
        include_related: bool = True,
        include_archived: bool = False,
        use_llm: bool = False,
    ) -> list[MemoryEntry]:
        # [v9.1] Protocol 模式: 优先委派到 MemoryCore，失败静默降级。
        if self._protocol_mode and self._memory_cores:
            try:
                results = self._recall_via_core(query, layers, limit)
                self._apply_reconsolidation(results)
                return results
            except Exception as exc:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "[v9.1-Protocol] recall 委派 MemoryCore 失败，降级旧路径: %s",
                    exc,
                )
        results = self._indexer.recall(
            query,
            layers,
            tags,
            priority,
            limit,
            min_score,
            include_related,
            include_archived,
            use_llm,
        )
        self._apply_reconsolidation(results)
        return results

    def _apply_reconsolidation(self, entries: list[MemoryEntry]) -> None:
        """容量驱动的访问密度更新 — 检索时更新访问计数

        核心逻辑: 检索时不刷新时间相关的stability，只更新访问计数。
        访问计数用于访问密度计算，是纯容量驱动的，不含时间因子。
        不经常使用AI时，访问计数不变，记忆权重不变。
        """
        import time as _time

        now = _time.time()
        for entry in entries:
            if not hasattr(entry, 'metadata') or not isinstance(entry.metadata, dict):
                continue
            # 更新访问计数(用于访问密度计算)
            entry.metadata["access_count"] = entry.metadata.get("access_count", 0) + 1
            entry.metadata["last_access_time"] = now

    def search(self, query: str | None = None, limit: int = 20, **kwargs):
        return self._indexer.search(query, limit, **kwargs)

    def get_all_entries(
        self, layer: str | None = None, limit: int = 100
    ) -> list[MemoryEntry]:
        return self._indexer.get_all_entries(layer, limit)

    def _index_tags(self, *args, **kwargs):
        return self._indexer._index_tags(*args, **kwargs)

    def _unindex_tags(self, *args, **kwargs):
        return self._indexer._unindex_tags(*args, **kwargs)

    def _filter_and_score_entries(self, *args, **kwargs):
        return self._indexer._filter_and_score_entries(*args, **kwargs)

    def _apply_llm_enrichment(self, *args, **kwargs):
        return self._indexer._apply_llm_enrichment(*args, **kwargs)

    def _update_access_statistics(self, *args, **kwargs):
        return self._indexer._update_access_statistics(*args, **kwargs)

    def _score_entry(self, *args, **kwargs):
        return self._indexer._score_entry(*args, **kwargs)

    # ====================================================================
    # 晋升委派 → PromotionEngine
    # ====================================================================
