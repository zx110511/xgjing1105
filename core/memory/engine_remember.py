# -*- coding: utf-8-sig -*-
"""engine_remember.py — ICMEEngineRememberMixin (SSS-PhaseB)

从 engine.py 拆分的方法组: remember
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

class ICMEEngineRememberMixin:
    """remember方法组Mixin"""

    def _remember_via_core(
        self,
        content: str,
        layer: str,
        tags: list[str] | None,
        priority: str,
        metadata: dict | None,
    ) -> dict:
        """[v10-ready] Protocol 模式下委派写入到对应层 MemoryCore。

        Raises:
            任何异常由调用方捕获以触发降级。
        """
        cores = self._memory_cores or {}
        core = cores.get(layer)
        if core is None:
            raise KeyError(f"未找到层级 {layer!r} 对应的 MemoryCore")
        entry: dict[str, Any] = {
            "content": content,
            "layer": layer,
            "tags": list(tags or []),
            "priority": priority,
            "metadata": dict(metadata or {}),
        }
        entry_id = core.write(entry)
        self._emit_event(
            "memory.stored",
            str(entry_id),
            layer,
            {"via": "memory_core", "priority": priority},
        )
        return {
            "id": entry_id,
            "status": "stored",
            "actual_layer": layer,
            "requested_layer": layer,
            "size_bytes": len(content.encode("utf-8")),
            "llm_enriched": False,
            "via": "memory_core",
        }

    def _save_entry(self, entry: MemoryEntry):
        """[STO-PHASE-2] 原子写入JSON文件 — 先写临时文件，确认成功后rename

        防止进程中断导致文件不完整(半写状态)。
        配合SQLite事务实现双写一致性。
        """
        layer_dir = self._data_path / entry.layer
        layer_dir.mkdir(parents=True, exist_ok=True)
        entry_data = {
            "id": entry.id,
            "content": entry.content,
            "layer": entry.layer,
            "tags": entry.tags,
            "priority": entry.priority,
            "created_at": entry.created_at,
            "last_accessed": entry.last_accessed,
            "access_count": entry.access_count,
            "effectiveness_score": entry.effectiveness_score,
            "related_ids": entry.related_ids,
            "metadata": entry.metadata,
            "changelog": entry.changelog,
        }
        target_file = layer_dir / f"{entry.id}.json"
        temp_file = layer_dir / f"{entry.id}.json.tmp"

        try:
            # Step 1: 写入临时文件
            temp_file.write_text(
                json.dumps(entry_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            # Step 2: 原子替换(同文件系统rename是原子操作)
            temp_file.replace(target_file)
        except Exception:
            # 清理临时文件
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise

    def _delete_entry_file(self, entry_id: str, layer_name: str):
        entry_file = self._data_path / layer_name / f"{entry_id}.json"
        if entry_file.exists():
            entry_file.unlink()

    # ====================================================================
    # 写入委派 → MemoryWriter
    # ====================================================================
    def remember(
        self,
        content: str,
        layer: str = "working",
        tags: list[str] | None = None,
        priority: str = "medium",
        metadata: dict | None = None,
        use_llm: bool = True,
    ) -> dict:
        # [v10-ready] v9.1 Protocol 模式: 优先委派到 MemoryCore，失败静默降级。
        if self._protocol_mode and self._memory_cores:
            try:
                return self._remember_via_core(
                    content, layer, tags, priority, metadata
                )
            except Exception as exc:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "[v9.1-Protocol] remember 委派 MemoryCore 失败，降级旧路径: %s",
                    exc,
                )
        return self._writer.remember(
            content, layer, tags, priority, metadata, use_llm
        )

    def remember_batch(self, entries: list[dict], use_llm: bool = False) -> list[dict]:
        return self._writer.remember_batch(entries, use_llm)

    def fast_inject(self, entries: list[dict]) -> list[dict]:
        return self._writer.fast_inject(entries)

    def remember_async(
        self,
        content: str,
        layer: str = "working",
        tags: list[str] | None = None,
        priority: str = "medium",
        metadata: dict | None = None,
    ) -> Any:
        return self._writer.remember_async(content, layer, tags, priority, metadata)

    def ensure_async_executor(self):
        return self._writer.ensure_async_executor()

    def remember_guarded(
        self,
        content: str,
        layer: str = "working",
        tags: list[str] | None = None,
        priority: str = "medium",
        metadata: dict | None = None,
    ) -> dict:
        return self._writer.remember_guarded(
            content, layer, tags, priority, metadata
        )

    def _enrich_with_llm(self, *args, **kwargs):
        return self._writer._enrich_with_llm(*args, **kwargs)

    def _register_asset_atom(self, *args, **kwargs):
        return self._writer._register_asset_atom(*args, **kwargs)

    def _apply_quality_gate(self, *args, **kwargs):
        return self._writer._apply_quality_gate(*args, **kwargs)

    def _create_memory_entry(self, *args, **kwargs):
        return self._writer._create_memory_entry(*args, **kwargs)

    def _store_memory_entry(self, *args, **kwargs):
        return self._writer._store_memory_entry(*args, **kwargs)

    def _build_remember_result(self, *args, **kwargs):
        return self._writer._build_remember_result(*args, **kwargs)

    # ====================================================================
    # 检索委派 → MemoryIndex
    # ====================================================================
