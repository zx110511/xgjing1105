r"""
天机记忆系统 (TIANJI) - 检索与索引组件 MemoryIndex  [v10-ready]
==============================================================
负责检索与标签索引：tag 索引维护 → 评分过滤 → LLM 重排 → recall 主入口，
以及 get_all_entries / _score_entry 等检索辅助。

[v10-ready] 组件通过构造函数接收 engine 宿主，所有共享状态（_layers/
_tag_index/_archive/_stats 等）均经由宿主访问，组件之间不互相 import。
"""

import time

from . import MemoryEntry


class MemoryIndex:
    """检索与索引引擎 — recall / 评分 / tag 索引维护。"""

    def __init__(self, engine):
        self._engine = engine

    # --------------------------------------------------------------- tag 索引
    def _index_tags(self, entry_id: str, tags: list[str]):
        for tag in tags:
            self._engine._tag_index[tag].add(entry_id)

    def _unindex_tags(self, entry_id: str, tags: list[str]):
        for tag in tags:
            if tag in self._engine._tag_index:
                self._engine._tag_index[tag].discard(entry_id)

    # ----------------------------------------------------------- 评分与过滤
    def _filter_and_score_entries(
        self,
        query: str | None,
        tags: list[str] | None,
        priority: list[str] | None,
        layers: list[str],
        min_score: float,
        include_archived: bool,
    ) -> list[tuple[float, MemoryEntry]]:
        """评分并过滤条目"""
        results: list[tuple[float, MemoryEntry]] = []

        for layer_name in layers:
            if layer_name not in self._engine._layers:
                continue
            for entry in self._engine._layers[layer_name].values():
                score = self._engine._score_entry(entry, query, tags, priority)
                if score >= min_score:
                    results.append((score, entry))

        if include_archived:
            for entry in self._engine._archive.values():
                score = self._engine._score_entry(entry, query, tags, priority)
                if score >= min_score:
                    results.append((score * 0.5, entry))

        return results

    def _apply_llm_enrichment(
        self, query: str, entries: list[MemoryEntry], limit: int, use_llm: bool
    ) -> list[MemoryEntry]:
        """应用LLM增强"""
        if (
            use_llm
            and query
            and self._engine._llm_bridge
            and self._engine._llm_bridge.is_ready
        ):
            return self._engine._llm_bridge.enrich_recall(query, entries, limit)
        return entries[:limit]

    def _update_access_statistics(self, entries: list[MemoryEntry]) -> None:
        """更新访问统计"""
        current_time = time.time()
        for entry in entries:
            entry.last_accessed = current_time
            entry.access_count += 1
        self._engine._stats["total_accesses"] += len(entries)

    def _score_entry(
        self,
        entry: MemoryEntry,
        query: str | None,
        tags: list[str] | None,
        priority: list[str] | None,
    ) -> float:
        score = entry.value_score()
        if tags:
            matched = sum(1 for t in tags if t in entry.tags)
            if matched == 0:
                return 0.0
            score *= 1.0 + 0.3 * matched / len(tags)
        if priority:
            if entry.priority not in priority:
                return 0.0
            score *= 1.5
        if query:
            query_lower = query.lower()
            content_lower = entry.content.lower()
            if query_lower in content_lower:
                score *= 3.0
            else:
                query_words = set(query_lower.split())
                content_words = set(content_lower.split())
                overlap = query_words & content_words
                if overlap:
                    score *= 1.0 + 0.5 * len(overlap) / len(query_words)
                else:
                    score *= 0.3
        return score

    # ------------------------------------------------------------------ recall
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
        """检索记忆条目"""
        with self._engine._lock:
            self._engine._stats["total_recall_calls"] += 1
            layers = layers or [l.name for l in self._engine.config.layers]

            # TCL增强检索: 通过canonical_ids扩展查询
            tcl_expanded_tags = list(tags or [])
            if query:
                try:
                    from ..tcl_normalizer import (
                        TCLNormalizer,
                        TerminologyStore,
                        seed_terminology,
                    )

                    if not hasattr(self._engine, "_tcl_store"):
                        tcl_db = (
                            str(self._engine._data_path / "tcl_terminology.db")
                            if hasattr(self._engine, "_data_path")
                            else "data/tcl_terminology.db"
                        )
                        self._engine._tcl_store = TerminologyStore(tcl_db)
                        if self._engine._tcl_store.get_stats()["total_terms"] == 0:
                            seed_terminology(self._engine._tcl_store)
                        self._engine._tcl_normalizer = TCLNormalizer(
                            self._engine._tcl_store,
                            llm_bridge=getattr(self._engine, "_llm_bridge", None),
                        )
                    result = self._engine._tcl_normalizer.normalize(query)
                    if result.canonical_id:
                        tcl_expanded_tags.append(result.canonical_id)
                except Exception:
                    pass  # TCL增强检索失败不影响主流程

            scored_entries = self._engine._filter_and_score_entries(
                query, tcl_expanded_tags, priority, layers, min_score, include_archived
            )

            scored_entries.sort(key=lambda x: x[0], reverse=True)
            entries = [e for _, e in scored_entries[: limit * 2]]

            if entries:
                self._engine._stats["total_recall_hits"] += 1

            entries = self._engine._apply_llm_enrichment(query, entries, limit, use_llm)

            self._engine._update_access_statistics(entries)

            return entries

    def search(self, query: str | None = None, limit: int = 20, **kwargs):
        """[v10-ready] recall 的语义别名，便于与通用检索接口对齐。"""
        return self._engine.recall(query=query, limit=limit, **kwargs)

    def get_all_entries(
        self, layer: str | None = None, limit: int = 100
    ) -> list[MemoryEntry]:
        with self._engine._lock:
            entries = []
            if layer:
                if layer in self._engine._layers:
                    entries = list(self._engine._layers[layer].values())
            else:
                for layer_data in self._engine._layers.values():
                    entries.extend(layer_data.values())
            entries.sort(key=lambda e: e.value_score(), reverse=True)
            return entries[:limit]
