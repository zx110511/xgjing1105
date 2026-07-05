# -*- coding: utf-8-sig -*-
"""hybrid_engine_recall.py — ICMEStorageEngineRecallMixin (SSS-PhaseB)

从 hybrid_engine.py 拆分的方法组: recall
源文件: hybrid_engine.py
"""

import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any
from ..shared.config import ICMEConfig


# [FIX-MCP-Bug2/3-recall] 补充 logger 实例 (修复 recall 路径下 logger 未定义错误)
logger = logging.getLogger(__name__)
from .engine import ICMEEngine, MemoryEntry
from .storage.migration import MigrationManager
from .storage.tiered import (  # noqa: F401
    TieredStorageEngine,
)


from typing import Dict

class ICMEStorageEngineRecallMixin:
    """recall方法组Mixin"""

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
    ) -> list:
        # TCL增强检索: 将归一化后的规范术语追加到查询中，提升召回率
        tcl_enhanced_query = query
        if query:
            try:
                if self._init_tcl():
                    result = self._tcl_normalizer.normalize(query)
                    if result.canonical_id and result.canonical_term != query:
                        # 将规范术语追加到查询，FTS5会匹配更广
                        tcl_enhanced_query = f"{query} {result.canonical_term}"
            except Exception as e:
                logger.debug(
                    f"[HybridEngine] TCL增强检索跳过: {e}"
                )  # TCL增强检索失败不影响主流程

        if self._use_sqlite:
            with self._lock:
                self._stats["total_recall_calls"] += 1

            # v9.1 P1-2: SQLite检索 + 失败回退到JSON
            try:
                results = self._store.search(
                    query=tcl_enhanced_query,
                    layers=layers,
                    tags=tags,
                    priority=priority,
                    limit=limit,
                    min_score=min_score,
                    use_fts=True,
                    include_archived=include_archived,
                )
            except Exception as e:
                logger.error(f"[HybridEngine] SQLite search失败, 回退到JSON检索: {e}")
                return super().recall(
                    query=query,
                    layers=layers,
                    tags=tags,
                    priority=priority,
                    limit=limit,
                    min_score=min_score,
                    include_related=include_related,
                    include_archived=include_archived,
                )

            try:
                conn = self._store._get_conn()
                now = time.time()
                ids = [r["id"] for r in results]
                for mid in ids:
                    conn.execute(
                        "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                        (now, mid),
                    )
                conn.commit()
            except Exception as e:
                logger.warning(f"[HybridEngine] 访问计数更新失败: {e}")

            with self._lock:
                self._stats["total_accesses"] += len(results)
                if results:
                    self._stats["total_recall_hits"] += 1
                    # 高质量recall: 至少1条结果fts_rank<0或score>0
                    has_quality = any(
                        r.get("fts_rank", 0) < 0 or r.get("score", 0) > 0
                        for r in results
                    )
                    if has_quality:
                        self._stats["total_recall_quality_hits"] = (
                            self._stats.get("total_recall_quality_hits", 0) + 1
                        )

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="recall",
                        state_before={"query": query},
                        state_after={
                            "hits": len(results),
                            "total_accesses": self._stats["total_accesses"],
                        },
                    )
                except Exception as e:
                    logger.debug(
                        f"[HybridEngine] evo_loop.record_action(recall) 忽略: {e}"
                    )

            return results

        return super().recall(
            query=query,
            layers=layers,
            tags=tags,
            priority=priority,
            limit=limit,
            min_score=min_score,
            include_related=include_related,
            include_archived=include_archived,
        )

    def forget(self, entry_id: str) -> bool:
        if self._use_sqlite:
            try:
                from ..shared.kg_sync_hook import KGSyncHook

                if not hasattr(self, "_kg_sync"):
                    self._kg_sync = KGSyncHook(
                        str(self._store._db_path)
                        if hasattr(self._store, "_db_path")
                        else "data/.memory/icme.db"
                    )
                self._kg_sync.on_forget(entry_id)
            except Exception as e:
                logger.debug(f"[HybridEngine] KG同步(on_forget)跳过: {e}")
            return self._store.delete(entry_id)
        return super().forget(entry_id)
